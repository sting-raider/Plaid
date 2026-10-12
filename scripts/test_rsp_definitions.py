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
    args = parser.parse_args()
    reads = args.word_reads or args.execution
    recipe = ('060-rsp-installed-imem-fetch' if args.execution else
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
    if args.execution:
        expected['initial_imem'],expected['final_imem'],_ = model.replay_image(events)
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
        if args.execution:
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
        if args.execution:
            for mode in range(4):
                forged = json.loads(original)
                fetch = next(f for f in forged['imem_fetches'] if f['pc']==0)
                if mode==0: del forged['imem_fetches']
                elif mode==1: fetch['origins'][0]['write_ordinal'] += 1
                elif mode==2: fetch['word']=13
                else: forged['imem_execution_certified']=True
                output.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-rsp-cpu-imem',digest,False)
    print('RSP definitions: original-clock ORI/ADDU parents, phase cuts, full register snapshots, source/report/input gates and unchanged proof flags passed')


if __name__=='__main__': main()
