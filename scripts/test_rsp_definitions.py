"""RSP definitions compose into existing CPU IMEM copies; no root promotion."""
from pathlib import Path
import argparse
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source',type=Path)
    parser.add_argument('--word-reads',action='store_true')
    parser.add_argument('--execution',action='store_true')
    parser.add_argument('--dma',action='store_true')
    parser.add_argument('--promoted',action='store_true')
    parser.add_argument('--roundtrip',action='store_true')
    parser.add_argument('--dmem-ingress',action='store_true')
    parser.add_argument('--pending',action='store_true')
    parser.add_argument('--decoded-mmio',action='store_true')
    parser.add_argument('--cached-cpu',action='store_true')
    args = parser.parse_args()
    args.decoded_mmio = args.decoded_mmio or args.cached_cpu
    args.pending = args.pending or args.decoded_mmio
    roundtrip = args.roundtrip or args.dmem_ingress or args.pending
    promoted = args.promoted or roundtrip
    dma = args.dma or promoted
    execution = args.execution or dma
    reads = args.word_reads or execution
    recipe = ('067-dma-cached-cpu' if args.cached_cpu else
        '066-decoded-mmio-dma' if args.decoded_mmio else
        '065-mutable-pending-dma' if args.pending else
        '064-dma-dmem-ingress-rsp-load' if args.dmem_ingress else
        '063-dma-ram-imem-roundtrip' if roundtrip else
        '062-promoted-dma-cpu-consumption' if promoted else
        '061-rsp-dmem-dma-cpu-fetch' if dma else
        '060-rsp-installed-imem-fetch' if execution else
        '059-rsp-word-read-imem' if reads else '058-rsp-defined-imem')
    spec = importlib.util.spec_from_file_location('census',ROOT/'spikes'/recipe/'verify.py')
    model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(model)
    events,definitions = model.expected_events()
    starts = [e for e in events if e['kind']=='cpu_begin']
    ends = [e for e in events if e['kind']=='cpu_end']
    expected = dict(format=model.FORMAT,profile=model.PROFILE,events=events,
        steps=[dict(phase=a['phase'],index=i,word=a['word'],pc=a['pc'],before=a['gpr'],after=b['gpr'])
            for i,(a,b) in enumerate(zip(starts,ends))],
        initial_dmem=list(bytes.fromhex('340800aaaaee7722')),initial_imem=list(bytes.fromhex('deadbeef')*5),
        final_dmem=list(bytes.fromhex('aaee7722aaee7722')),
        final_imem=list(bytes.fromhex('0000334400003344aaee7722aaee7722aaee7722')))
    if dma:
        replayed = model.replay(events,definitions)
        expected.update(initial_dmem=list(bytes.fromhex('340800aaaaee7722')+bytes(4088)),
            final_dmem=replayed['final_dmem'],initial_imem=replayed['initial_imem'],final_imem=replayed['final_imem'],
            ram=dict(start=0x6000,initial=replayed['initial_ram'],final_bytes=replayed['final_ram']))
    elif execution:
        expected['initial_imem'],expected['final_imem'],_ = model.replay_image(events)
    if args.pending:
        expected['initial_pending']=model.INITIAL
    if args.source:
        assert json.loads(args.source.read_bytes())==expected, 'actual source differs from independent census'
    cargo = shutil.which('cargo') or str(Path.home()/'.cargo/bin/cargo.exe')
    subprocess.run([cargo,'build','--locked','-p','plaid'],cwd=ROOT,check=True)
    exe = ROOT/('target/debug/plaid.exe' if os.name=='nt' else 'target/debug/plaid')
    with tempfile.TemporaryDirectory(prefix='rsp-defined-imem-',dir=ROOT/'target') as temporary:
        directory = Path(temporary)
        source,output = directory/'source.json',directory/'report.json'
        def save(data):
            source.write_text(json.dumps(data)+'\n',encoding='utf-8')
            return hashlib.sha256(source.read_bytes()).hexdigest()
        def run(command,digest,ok=True,destination=output):
            result = subprocess.run([str(exe),command,str(source),digest,str(destination)],capture_output=True,text=True)
            assert (result.returncode==0)==ok,(command,result.stdout,result.stderr)
        digest = save(expected)
        run('inspect-rsp-cpu-imem',digest)
        run('verify-rsp-cpu-imem',digest)
        report = json.loads(output.read_bytes())
        model.compare_report(report,definitions)
        original = output.read_bytes()
        before = source.read_bytes()
        run('inspect-rsp-cpu-imem',digest,False,source)
        assert source.read_bytes()==before
        run('inspect-rsp-cpu-imem','0'*64,False)
        for mode in range(5):
            forged = copy.deepcopy(expected)
            end = next(e for e in forged['events'] if e['kind']=='rsp_end')
            if mode==0: end['rgpr'][2] ^= 1
            elif mode==1: end['rgpr'][6] = 1
            elif mode==2:
                begin = next(e for e in forged['events'] if e['kind']=='rsp_begin' and e['word'] in (0x34023344,0x34020000))
                end = next(e for e in forged['events'] if e['kind']=='rsp_end' and e['context']==begin['context'])
                begin['word']=end['word']=0x34033344
            elif mode==3: forged['profile']= 'ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-rsp-cpu-imem-scalar-sbv2e0-v0'
            else: next(e for e in forged['events'] if e['kind']=='rsp_begin')['rgpr'][0]=1
            run('inspect-rsp-cpu-imem',save(forged),False)
        if reads:
            for mode in range(3):
                forged = copy.deepcopy(expected)
                read = next(e for e in forged['events'] if e['kind']=='rsp_read')
                if mode==0:
                    forged['events'].remove(read)
                    active=0
                    for ordinal,event in enumerate(forged['events'],1):
                        event['ordinal']=ordinal
                        if event['kind'] in ('rsp_begin','cpu_begin'): active=ordinal
                        event['context']=active
                        if event['kind'] in ('rsp_end','cpu_end'): active=0
                elif mode==1: read.update(address=4,offset=4)
                else: read['value'] ^= 1
                run('inspect-rsp-cpu-imem',save(forged),False)
        if execution:
            for mode in range(5):
                forged = copy.deepcopy(expected)
                fetch = next(e for e in forged['events'] if e['kind']=='rsp_begin' and e['pc']==0)
                if mode==0: fetch['word']=13
                elif mode==1: forged['initial_imem']=forged['initial_imem'][:20]
                elif mode==2: forged['final_imem'][0] ^= 1
                elif mode==3:
                    seed = next(e for e in forged['events'] if e['kind']=='opaque_imem_seed')
                    seed['offset'] += 1
                else:
                    seed = next(e for e in forged['events'] if e['kind']=='opaque_imem_seed')
                    seed['value'] ^= 1
                run('inspect-rsp-cpu-imem',save(forged),False)
        if dma:
            def reclock(rows):
                active=request=0
                for ordinal,event in enumerate(rows,1):
                    event['ordinal']=ordinal
                    if event['kind'] in ('cpu_begin','rsp_begin','ram_fetch_begin'): active=ordinal
                    if event['kind']=='dma_promote':request=ordinal
                    owned=event['kind'] in ('dma_promote','dma_complete','imem_dma_read','imem_dma_write','dmem_dma_read','dmem_dma_write') or (event['kind']=='ram_write' and event.get('dma') is not None and promoted)
                    event['context']=(active if event['word'] else ordinal) if event['kind']=='dma_pending_write' else ordinal if event['kind']=='cpu_reentry' else request if owned else active
                    if event['kind'] in ('cpu_end','rsp_end','ram_fetch_end'): active=0
                    if event['kind']=='dma_complete':request=0
            for mode in range(7):
                forged = copy.deepcopy(expected)
                write = next(e for e in forged['events'] if e['kind']=='ram_write')
                if mode==0: write['dma']['pbus']=0x1000
                elif mode==1: write['offset']=4
                elif mode==2: write['value']=1
                elif mode==3:
                    read = next(e for e in forged['events'] if e['kind']=='ram_read')
                    forged['events'].remove(read);reclock(forged['events'])
                elif mode==4:
                    read = next(e for e in forged['events'] if e['kind']=='ram_read')
                    forged['events'].insert(forged['events'].index(read),copy.deepcopy(read));reclock(forged['events'])
                elif mode==5: next(e for e in forged['events'] if e['kind']=='ram_fetch_begin')['fetch']['cached']=True
                else: forged['ram']['final_bytes'][0] ^= 1
                run('inspect-rsp-cpu-imem',save(forged),False)
        if promoted:
            for mode in range(6):
                forged = copy.deepcopy(expected)
                if mode in (0,1):
                    kind='dma_promote' if mode==0 else 'dma_complete'
                    forged['events']=[e for e in forged['events'] if e['kind']!=kind]
                    reclock(forged['events'])
                elif mode==2:
                    for event in forged['events']:
                        if event.get('dma') is not None:event['dma']['length']=16
                        if event['kind']=='dma_complete':event.update(address=0x6040,offset=24)
                elif mode==3: next(e for e in forged['events'] if e['kind']=='ram_write')['context']=1
                elif mode==4:
                    write = next(e for e in forged['events'] if e['kind']=='ram_write')
                    forged['events'].insert(forged['events'].index(write),copy.deepcopy(write));reclock(forged['events'])
                else: next(e for e in forged['events'] if e['kind']=='dma_complete')['offset']=16
                run('inspect-rsp-cpu-imem',save(forged),False)
        if roundtrip:
            for mode in range(6):
                forged = copy.deepcopy(expected)
                read = next(e for e in forged['events'] if e['kind']=='imem_dma_read')
                sink = next(e for e in forged['events'] if e['kind']=='imem_dma_write')
                if mode==0: forged['events'].remove(read);reclock(forged['events'])
                elif mode==1: forged['events'].insert(forged['events'].index(read),copy.deepcopy(read));reclock(forged['events'])
                elif mode==2: forged['events'].remove(sink);reclock(forged['events'])
                elif mode==3: read['bank']=0
                elif mode==4: sink['value'] ^= 1
                else: read['address']=0x6020
                run('inspect-rsp-cpu-imem',save(forged),False)
        if args.dmem_ingress or args.pending:
            for mode in range(6):
                forged = copy.deepcopy(expected)
                reads = [e for e in forged['events'] if e['kind']=='dmem_dma_read']
                writes = [e for e in forged['events'] if e['kind']=='dmem_dma_write']
                if mode==0: forged['events'].remove(reads[1]);reclock(forged['events'])
                elif mode==1:
                    a,b=forged['events'].index(reads[1]),forged['events'].index(writes[0])
                    forged['events'][a],forged['events'][b]=forged['events'][b],forged['events'][a];reclock(forged['events'])
                elif mode==2: reads[0]['address'] += 4
                elif mode==3: writes[0]['value'] ^= 1
                elif mode==4: next(e for e in forged['events'] if e.get('dma_direction')=='dmem_ingress')['dma_direction']='dmem_egress'
                else: forged['events'].insert(forged['events'].index(reads[0]),copy.deepcopy(reads[0]));reclock(forged['events'])
                run('inspect-rsp-cpu-imem',save(forged),False)
        if args.pending:
            for mode in range(7):
                forged=copy.deepcopy(expected)
                writes=[e for e in forged['events'] if e['kind']=='dma_pending_write']
                if mode==0: del forged['initial_pending']
                elif mode==1: next(e for e in reversed(writes) if e['address'] in (2,3))['pending_full']=False
                elif mode==2:
                    promote=[e for e in forged['events'] if e['kind']=='dma_promote'][-1]
                    promote['dma']['pbus']=promote['offset']=0x380
                elif mode==3: writes[-1]['value']=0x6020
                elif mode==4: writes[-1]['value']=1<<32
                elif mode==5: writes[-1]['dma_direction']='dmem_egress'
                else: writes[-1]['cpu']=False
                run('inspect-rsp-cpu-imem',save(forged),False)
        if args.decoded_mmio:
            for mode in range(7):
                forged=copy.deepcopy(expected)
                rows=forged['events'];write=next(e for e in rows if e['kind']=='dma_pending_write' and e['word'])
                promote=next(e for e in rows if e['kind']=='dma_promote' and e['ordinal']==189)
                end=next(e for e in rows if e['kind']=='cpu_end' and e['context']==187)
                if mode==0: write['value']=1
                elif mode==1: write['context']=write['ordinal']
                elif mode==2: write['word'] ^= 1
                elif mode==3: rows.remove(promote);reclock(rows)
                elif mode==4:
                    a,b=rows.index(promote),rows.index(end);rows[a],rows[b]=rows[b],rows[a];reclock(rows)
                elif mode==5: rows.insert(rows.index(write),copy.deepcopy(write));reclock(rows)
                else: end['gpr'][5]=1
                run('inspect-rsp-cpu-imem',save(forged),False)
        if args.cached_cpu:
            for mode in range(10):
                forged=copy.deepcopy(expected);rows=forged['events']
                burst=next(e for e in rows if e['kind']=='cache_burst_read')
                fill=next(e for e in rows if e['kind']=='cache_fill')
                seed=next(e for e in rows if e['kind']=='cpu_reentry')
                end=[e for e in rows if e['kind']=='ram_fetch_end'][-1]
                if mode==0: rows.remove(burst);reclock(rows)
                elif mode==1: rows.remove(fill);reclock(rows)
                elif mode==2: rows.insert(rows.index(burst),copy.deepcopy(burst));reclock(rows)
                elif mode==3: fill['cache_line']['words'][7]=1
                elif mode==4: end['cache_line']['tag_key'] ^= 0x1000
                elif mode==5: end['value']=13
                elif mode==6: rows.remove(seed);reclock(rows)
                elif mode==7: seed['gpr'][5]=1
                elif mode==8: burst['context']=1
                else: burst['address'] += 32
                run('inspect-rsp-cpu-imem',save(forged),False)
        digest = save(expected)
        for mode in range(4):
            forged = json.loads(original)
            if mode==0: forged['rsp_definitions'][3]['expression']['left']['context']=999999
            elif mode==1: forged['copies'][1]['source_bytes'][0]['source_definition']=9
            elif mode==2: del forged['rsp_definitions']
            else: forged['source_ancestry_certified']=True
            output.write_text(json.dumps(forged),encoding='utf-8')
            run('verify-rsp-cpu-imem',digest,False)
        if reads:
            forged = json.loads(original)
            forged['rsp_definitions'][4]['expression']['origins'][0]['source_definition']=3
            output.write_text(json.dumps(forged),encoding='utf-8')
            run('verify-rsp-cpu-imem',digest,False)
        if execution:
            for mode in range(4):
                forged = json.loads(original)
                fetch = next(f for f in forged['imem_fetches'] if f['pc']==0)
                if mode==0: del forged['imem_fetches']
                elif mode==1: fetch['origins'][0]['write_ordinal'] += 1
                elif mode==2: fetch['word']=13
                else: forged['imem_execution_certified']=True
                output.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-rsp-cpu-imem',digest,False)
        if dma:
            for mode in range(4):
                forged = json.loads(original)
                if mode==0: del forged['dma_consumption']
                elif mode==1: forged['dma_consumption']['fetches'][-1]['decoder_context']=1
                elif mode==2: next(e for e in forged['dma_consumption']['fetches'] if e['origins'][0]['kind']=='sp_dma')['origins'][0]['write_ordinal'] += 1
                else: forged['dma_consumption']['writes'][0]['source_bytes'][0]['source_definition']=1
                output.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-rsp-cpu-imem',digest,False)
        if promoted:
            for mode in range(3):
                forged = json.loads(original)
                if mode==0: del forged['dma_consumption']['promoted_requests']
                elif mode==1: forged['dma_consumption']['promoted_requests'][0]['write_ordinals'].pop()
                else: forged['dma_consumption']['writes'][0]['promote_context']=1
                output.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-rsp-cpu-imem',digest,False)
        if roundtrip:
            for mode in range(4):
                forged = json.loads(original)
                graph = forged['dma_consumption']
                if mode==0: del graph['imem_installs']
                elif mode==1: graph['imem_installs'][0]['source_bytes'][0]['write_ordinal'] += 1
                elif mode==2: next(f for f in forged['imem_fetches'] if f['pc']==0x300)['origins'][0]['parent']['write_ordinal'] += 1
                else: graph['promoted_requests'][-1]['direction']='dmem_egress'
                output.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-rsp-cpu-imem',digest,False)
        if args.dmem_ingress or args.pending:
            for mode in range(3):
                forged = json.loads(original)
                if mode==0: del forged['dma_consumption']['dmem_installs']
                elif mode==1: forged['dma_consumption']['dmem_installs'][0]['read_ordinal'] += 1
                else: forged['rsp_definitions'][-1]['expression']['origins'][0]['parent']['write_ordinal'] += 1
                output.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-rsp-cpu-imem',digest,False)
        if args.pending:
            for mode in range(4):
                forged=json.loads(original);graph=forged['dma_consumption']
                if mode==0: del graph['pending_commits']
                elif mode==1: next(e for e in graph['pending_commits'] if e['superseded_commit'] is not None)['superseded_commit']=None
                elif mode==2: graph['promoted_requests'][-1]['pending_provenance']['commit_ordinal']-=1
                else: graph['promoted_requests'][-1]['pending_provenance']['pbus_write_ordinal']-=1
                output.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-rsp-cpu-imem',digest,False)
        if args.decoded_mmio:
            for mode in range(2):
                forged=json.loads(original);graph=forged['dma_consumption']
                if mode==0: graph['pending_commits'][-1].pop('decoder_context')
                else: graph['promoted_requests'][-1]['pending_provenance']['commit_decoder_context']=1
                output.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-rsp-cpu-imem',digest,False)
        if args.cached_cpu:
            for mode in range(5):
                forged=json.loads(original);graph=forged['dma_consumption']
                if mode==0: graph.pop('cache_fills')
                elif mode==1: graph.pop('cached_fetches')
                elif mode==2: graph['cache_fills'][0]['source_bytes'][8]['write_ordinal'] += 1
                elif mode==3: graph['cached_fetches'][-1]['origins'][0]=dict(kind='unknown',cut_ordinal=202)
                else: graph['cached_fetches'][-1]['fill_ordinal']=197
                output.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-rsp-cpu-imem',digest,False)
    print('RSP definitions: original-clock ORI/ADDU parents, phase cuts, full register snapshots, source/report/input gates and unchanged proof flags passed')


if __name__=='__main__': main()
