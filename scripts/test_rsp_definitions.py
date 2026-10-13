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
    parser.add_argument('--cache-invalidation',action='store_true')
    parser.add_argument('--cpu-ram-copy',action='store_true')
    parser.add_argument('--cpu-xori',action='store_true')
    parser.add_argument('--break-root',action='store_true')
    parser.add_argument('--eret-return',action='store_true')
    parser.add_argument('--guest-epc',action='store_true')
    parser.add_argument('--epc-target',action='store_true')
    parser.add_argument('--mapped-root',action='store_true')
    parser.add_argument('--entryhi-context',action='store_true')
    parser.add_argument('--mapped-reactivation',action='store_true')
    parser.add_argument('--entrylo-remap',action='store_true')
    parser.add_argument('--tlbr-context',action='store_true')
    parser.add_argument('--conditional-imem',action='store_true')
    parser.add_argument('--subword-imem',action='store_true')
    parser.add_argument('--ram-load-imem',action='store_true')
    parser.add_argument('--cached-ram-imem',action='store_true')
    args = parser.parse_args()
    args.ram_load_imem = args.ram_load_imem or args.cached_ram_imem
    args.subword_imem = args.subword_imem or args.ram_load_imem
    args.conditional_imem = args.conditional_imem or args.subword_imem
    args.tlbr_context = args.tlbr_context or args.conditional_imem
    args.entrylo_remap = args.entrylo_remap or args.tlbr_context
    args.mapped_reactivation = args.mapped_reactivation or args.entrylo_remap
    args.entryhi_context = args.entryhi_context or args.mapped_reactivation
    args.mapped_root = args.mapped_root or args.entryhi_context
    args.epc_target = args.epc_target or args.mapped_root
    args.guest_epc = args.guest_epc or args.epc_target
    args.eret_return = args.eret_return or args.guest_epc
    args.break_root = args.break_root or args.eret_return
    args.cpu_xori = args.cpu_xori or args.break_root
    args.cpu_ram_copy = args.cpu_ram_copy or args.cpu_xori
    args.cache_invalidation = args.cache_invalidation or args.cpu_ram_copy
    args.cached_cpu = args.cached_cpu or args.cache_invalidation
    args.decoded_mmio = args.decoded_mmio or args.cached_cpu
    args.pending = args.pending or args.decoded_mmio
    roundtrip = args.roundtrip or args.dmem_ingress or args.pending
    promoted = args.promoted or roundtrip
    dma = args.dma or promoted
    execution = args.execution or dma
    reads = args.word_reads or execution
    recipe = ('083-cached-ram-load-imem-consumption' if args.cached_ram_imem else
        '082-ram-load-imem-consumption' if args.ram_load_imem else
        '081-subword-transform-imem-consumption' if args.subword_imem else
        '080-conditional-sp-imem-consumption' if args.conditional_imem else
        '079-tlbr-context-root-return' if args.tlbr_context else
        '078-entrylo-remap-root-return' if args.entrylo_remap else
        '077-mapped-cache-reactivation' if args.mapped_reactivation else
        '076-entryhi-context-mapped-root-return' if args.entryhi_context else
        '075-tlb-mapped-cache-root-return' if args.mapped_root else
        '074-epc-transform-target' if args.epc_target else
        '073-guest-epc-return' if args.guest_epc else
        '072-live-epc-handler-return' if args.eret_return else
        '071-writer-break-handler' if args.break_root else
        '070-cpu-xori-ram-cached' if args.cpu_xori else
        '069-cpu-copy-ram-cached' if args.cpu_ram_copy else
        '068-dma-cache-invalidation' if args.cache_invalidation else
        '067-dma-cached-cpu' if args.cached_cpu else
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
            ram=dict(start=getattr(model,'RAM_START',0x6000),initial=replayed['initial_ram'],final_bytes=replayed['final_ram']))
    elif execution:
        expected['initial_imem'],expected['final_imem'],_ = model.replay_image(events)
    if args.pending:
        expected['initial_pending']=model.INITIAL
    if args.mapped_root:expected['initial_tlb']=model.TLB_INITIAL
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
                    if 'dcache_event' in event:event['dcache_event']['ordinal']=ordinal
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
                elif mode==5: next(e for e in writes if e.get('dma_direction')=='imem_ingress')['dma_direction']='dmem_egress'
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
                end=[e for e in rows if e['kind']=='ram_fetch_end' and e['fetch']['cached']][-1]
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
        if args.cache_invalidation:
            for mode in range(13):
                forged=copy.deepcopy(expected);rows=forged['events']
                operation=next(e for e in rows if e['kind']=='cache_operation')
                begin=next(e for e in rows if e['kind']=='cpu_begin' and e['context']==operation['context'])
                end=next(e for e in rows if e['kind']=='cpu_end' and e['context']==operation['context'])
                snapshot=operation['cache_operation']
                if mode==0: rows.remove(operation);reclock(rows)
                elif mode==1: rows.insert(rows.index(operation),copy.deepcopy(operation));reclock(rows)
                elif mode==2: snapshot['operation']=0
                elif mode==3: snapshot['virtual_address'] += 4
                elif mode==4: operation['address'] += 0x4000
                elif mode==5: snapshot['before']['words'][7]=1
                elif mode==6: snapshot['after']['words'][7]=1
                elif mode==7: snapshot['after']['tag_key'] |= 1
                elif mode==8: operation['context']=operation['ordinal']
                elif mode==9: end['gpr'][5]=1
                elif mode==10: begin['gpr'][18] += 4
                elif mode==11:
                    rows.remove(next(e for e in reversed(rows) if e['kind']=='cache_burst_read'));reclock(rows)
                else: forged['format']='plaid-rsp-cpu-imem-history-v10';forged['profile']='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-dma-cached-cpu-consumption-v10'
                run('inspect-rsp-cpu-imem',save(forged),False)
        if args.cpu_ram_copy:
            for mode in range(10):
                forged=copy.deepcopy(expected);rows=forged['events']
                write=next(e for e in rows if e['kind']=='cpu_ram_write')
                begin=next(e for e in rows if e['kind']=='cpu_begin' and e['context']==write['context'])
                end=next(e for e in rows if e['kind']=='cpu_end' and e['context']==write['context'])
                if mode==0: rows.remove(write);reclock(rows)
                elif mode==1: rows.insert(rows.index(write),copy.deepcopy(write));reclock(rows)
                elif mode==2: write['value']=1
                elif mode==3: write['address'] += 4
                elif mode==4: write['context']=write['ordinal']
                elif mode==5: write['bytes']=8
                elif mode==6: write['cpu']=False
                elif mode==7: begin['gpr'][19]=0xffffffff80006028
                elif mode==8: end['gpr'][8]=1
                else: forged['format']='plaid-rsp-cpu-imem-history-v11';forged['profile']='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-dma-cached-cpu-invalidation-v11'
                run('inspect-rsp-cpu-imem',save(forged),False)
        if args.cpu_xori:
            for mode in range(7):
                forged=copy.deepcopy(expected);rows=forged['events']
                begin=next(e for e in rows if e['kind']=='cpu_begin' and e['word']>>26==14)
                end=next(e for e in rows if e['kind']=='cpu_end' and e['context']==begin['context'])
                if mode==0: end['gpr'][8]=0
                elif mode==1: end['gpr'][9]=1
                elif mode==2: begin['gpr'][8]=1
                elif mode==3: begin['word'] ^= 1
                elif mode==4: rows.remove(begin);reclock(rows)
                elif mode==5: forged['steps'][22]['after'][8]=0
                else: forged['format']='plaid-rsp-cpu-imem-history-v12';forged['profile']='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-cpu-copy-ram-cached-consumption-v12'
                run('inspect-rsp-cpu-imem',save(forged),False)
        if args.break_root:
            for mode in range(14):
                forged=copy.deepcopy(expected);rows=forged['events']
                begin=next(e for e in rows if e['kind']=='cpu_begin' and e.get('exception_state'))
                transfer=next(e for e in rows if e['kind']=='exception_transfer')
                before=begin['exception_state'];after=transfer['exception_state']
                if mode==0: rows.remove(transfer);reclock(rows)
                elif mode==1: rows.insert(rows.index(transfer),copy.deepcopy(transfer));reclock(rows)
                elif mode==2: before['exl']=True
                elif mode==3: before['bev']=True
                elif mode==4: before['delay_slot']=True
                elif mode==5: before['kernel_mode']='bits64'
                elif mode==6: after['epc']-=4
                elif mode==7: after['pc']+=4
                elif mode==8: after['cause']=8
                elif mode==9: after['exl']=False
                elif mode==10: after['branch_delay']=True
                elif mode==11: transfer['context']=transfer['ordinal']
                elif mode==12:
                    forged['events']=rows[:rows.index(transfer)+2];forged['steps']=forged['steps'][:-1]
                else:
                    seed=copy.deepcopy(next(e for e in reversed(rows) if e['kind']=='cpu_reentry'))
                    seed.update(phase=49,pc=model.ROOT_PC)
                    rows.insert(next(i for i,e in enumerate(rows) if e['kind']=='ram_fetch_begin' and e['pc']==model.ROOT_PC),seed);reclock(rows)
                run('inspect-rsp-cpu-imem',save(forged),False)
        if args.eret_return:
            for mode in range(11):
                forged=copy.deepcopy(expected);rows=forged['events']
                begin=next(e for e in rows if e['kind']=='cpu_begin' and e['word']==0x42000018)
                transfer=next(e for e in rows if e['kind']=='return_transfer')
                if mode==0: rows.remove(transfer);reclock(rows)
                elif mode==1: rows.insert(rows.index(transfer),copy.deepcopy(transfer));reclock(rows)
                elif mode==2: begin['return_state']['state']['epc'] += 4
                elif mode==3: begin['return_state']['state']['erl']=True
                elif mode==4: begin['return_state']['interrupt_enable']=True
                elif mode==5: transfer['return_state']['state']['pc']+=4
                elif mode==6: transfer['return_state']['state']['exl']=True
                elif mode==7: transfer['return_state']['llbit']=True
                elif mode==8: transfer['context']=transfer['ordinal']
                elif mode==9:
                    seed=copy.deepcopy(next(e for e in rows if e['kind']=='cpu_reentry'))
                    end=next(e for e in rows if e['kind']=='cpu_end' and e['context']==getattr(model,'ROOT_CONTEXT',338))
                    seed.update(phase=end['phase']+1,pc=model.ROOT_PC+4,gpr=end['gpr'],word=0)
                    rows.insert(next(i for i,e in enumerate(rows) if e['kind']=='ram_fetch_begin' and e['context']==getattr(model,'ROOT_CONTEXT',338)+2),seed);reclock(rows)
                else:
                    forged['events']=rows[:rows.index(transfer)+2];forged['steps']=forged['steps'][:-1]
                run('inspect-rsp-cpu-imem',save(forged),False)
        if args.guest_epc:
            for mode in range(15):
                forged=copy.deepcopy(expected);rows=forged['events']
                read=next(e for e in rows if e['kind']=='epc_read')
                write=next(e for e in rows if e['kind']=='epc_write')
                begin=next(e for e in rows if e['kind']=='cpu_begin' and e['context']==write['context'])
                if mode==0: rows.remove(read);reclock(rows)
                elif mode==1: rows.remove(write);reclock(rows)
                elif mode==2: rows.insert(rows.index(read),copy.deepcopy(read));reclock(rows)
                elif mode==3: rows.insert(rows.index(write),copy.deepcopy(write));reclock(rows)
                elif mode==4: begin['word'] ^= 0x800 # wrong CP0 register
                elif mode==5: begin['word'] ^= 0x10000 # wrong source GPR
                elif mode==6: begin['gpr'][8] ^= 1<<32 # equal low bits, wrong full register
                elif mode==7: begin['epc_state']['state']['epc'] += 4
                elif mode==8: write['epc_state']['state']['epc'] += 4
                elif mode==9: read['epc_state']['state']['pc'] += 4
                elif mode==10: write['context']=write['ordinal']
                elif mode==11: begin['epc_state']['interrupt_enable']=True
                elif mode==12: begin['epc_state']['state']['erl']=True
                elif mode==13:
                    read['epc_state']=copy.deepcopy(read['epc_state']);read['epc_state']['llbit']=True
                else: write['value']=write['epc_state']['state']['epc']
                run('inspect-rsp-cpu-imem',save(forged),False)
            # Insert a real modeled no-op register rewrite or equal second MTC0
            # on the continuous cached handler path. Require the precise stale
            # ancestry error, so malformed fixture bookkeeping cannot pass it.
            for word in (() if args.epc_target else (0x39080000,0x01004021,0x40887000)):
                forged=json.loads(json.dumps(expected));rows=forged['events']
                extra_write=word==0x40887000
                insertion=next(i for i,e in enumerate(rows) if e['kind']=='ram_fetch_begin'
                    and e['context']==(365 if extra_write else 360))
                block=copy.deepcopy(rows[359:364]) # original MTC0 fetch/decoder/effect/end
                if not extra_write: block.pop(3)
                address=0x198 if extra_write else 0x194
                phase=55 if extra_write else 54
                for e in block:
                    e.update(pc=0xffffffff80000000+address,phase=phase)
                    if e['kind'].startswith('ram_fetch'):
                        e['address']=address;e['fetch']['physical']=address
                        if e['kind']=='ram_fetch_end':e['value']=word
                    else:e['word']=word
                    if 'epc_state' in e:
                        e['epc_state']['state']['pc']=e['pc']
                        if not extra_write:e.pop('epc_state')
                for e in rows[insertion:]:
                    e['phase']+=1
                    if 0xffffffff80000190<=e['pc']<0xffffffff80000200:
                        e['pc']+=4
                        if e['kind'].startswith('ram_fetch'):
                            e['address']+=4;e['fetch']['physical']+=4
                        for key in ('epc_state','return_state'):
                            if key in e and e[key]['state']['pc']!=0xffffffff80006028:e[key]['state']['pc']+=4
                rows[insertion:insertion]=block
                words=[0,model.LW,model.SW,model.CACHE,0x40087000,
                    0x40887000 if extra_write else word,0x40887000,0x42000018]
                code=list(b''.join(w.to_bytes(4,'big') for w in words))
                for key in ('initial','final_bytes'):forged['ram'][key][0x180:0x1a0]=code
                for e in rows:
                    if e.get('cache_line',{}).get('slot')==12:e['cache_line']['words']=words[:]
                reclock(rows)
                starts=[e for e in rows if e['kind']=='cpu_begin'];ends=[e for e in rows if e['kind']=='cpu_end']
                forged['steps']=[dict(phase=a['phase'],index=i,word=a['word'],pc=a['pc'],before=a['gpr'],after=b['gpr'])
                    for i,(a,b) in enumerate(zip(starts,ends))]
                rejection=subprocess.run([str(exe),'inspect-rsp-cpu-imem',str(source),save(forged),str(output)],capture_output=True,text=True)
                assert rejection.returncode!=0 and ('past EPC read generation' if extra_write else 'lacks held current EPC read') in rejection.stderr,rejection.stderr
        if args.epc_target:
            for mode in range(8):
                forged=copy.deepcopy(expected);rows=forged['events']
                transform=next(e for e in rows if e['kind']=='cpu_begin' and e['context']==getattr(model,'TRANSFORM_CONTEXT',367))
                write=next(e for e in rows if e['kind']=='epc_write')
                ret=next(e for e in rows if e['kind']=='cpu_begin' and e['word']==0x42000018)
                if mode==0: transform['word'] ^= 0x10000 # renamed destination loses held ancestry
                elif mode==1: transform['word'] ^= 0x20 # different result
                elif mode==2: transform['gpr'][8] ^= 1<<32
                elif mode==3: write['epc_state']['state']['epc']=0xffffffff80006028
                elif mode==4: ret['return_state']['state']['epc']=0xffffffff80006028
                elif mode==5:
                    seed=copy.deepcopy(next(e for e in rows if e['kind']=='cpu_reentry'))
                    end=next(e for e in rows if e['kind']=='cpu_end' and e['context']==getattr(model,'TRANSFORM_CONTEXT',367))
                    seed.update(phase=end['phase']+1,pc=0xffffffff8000019c,gpr=end['gpr'],word=0)
                    rows.insert(next(i for i,e in enumerate(rows) if e['kind']=='ram_fetch_begin' and e['context']==getattr(model,'TRANSFORM_CONTEXT',367)+2),seed);reclock(rows)
                elif mode==6:
                    forged['format']='plaid-rsp-cpu-imem-history-v16';forged['profile']='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-guest-epc-return-consumption-v16'
                else: write['epc_state']['state']['exl']=False
                run('inspect-rsp-cpu-imem',save(forged),False)
        if args.mapped_root:
            for mode in range(18):
                forged=json.loads(json.dumps(expected));rows=forged['events']
                writes=[e for e in rows if e['kind']=='tlb_write']
                begin=next(e for e in rows if e['kind']=='cpu_begin' and e['context']==writes[-1]['context'])
                fetch=next(e for e in rows if e['kind']=='ram_fetch_begin' and 'mapping' in e)
                if mode==0: rows.remove(writes[-1]);reclock(rows)
                elif mode==1: rows.insert(rows.index(writes[-1]),copy.deepcopy(writes[-1]));reclock(rows)
                elif mode==2: writes[-1]['tlb_state']['entries'][0]['physical'][0]=0x8000
                elif mode==3: writes[-1]['tlb_state']['entries'][1]=copy.deepcopy(model.STAGED)
                elif mode==4: begin['tlb_state']['index']=32
                elif mode==5: begin['tlb_state']['control']['state']['kernel']=False
                elif mode==6: begin['tlb_state']['control']['state']['exl']=True
                elif mode==7: fetch['mapping']['asid']=8
                elif mode==8: fetch['mapping']['entries'][0]['valid'][0]=False
                elif mode==9: fetch['mapping']['entries'][0]['cca'][0]=2
                elif mode==10: fetch['fetch']['physical']+=4
                elif mode==11: forged['initial_tlb']['entries'][0]=copy.deepcopy(model.STAGED)
                elif mode==12: fetch['mapping']['bits']=64
                elif mode==13: writes[-1]['context']=writes[-1]['ordinal']
                elif mode==14: begin['tlb_state']['staged']['page_mask']=0x6000
                elif mode==15: next(e for e in rows if e['kind']=='ram_fetch_end' and 'mapping' in e).pop('mapping')
                elif mode==16: begin['word'] ^= 4 # cannot borrow a TLBWR occurrence
                else: next(e for e in rows if e['kind']=='ram_fetch_end' and not e['fetch']['cached'])['mapping']=copy.deepcopy(fetch['mapping'])
                run('inspect-rsp-cpu-imem',save(forged),False)
        if args.entryhi_context:
            for mode in range(12):
                forged=json.loads(json.dumps(expected));rows=forged['events']
                writes=[e for e in rows if e['kind']=='entry_hi_write'];write=writes[-1]
                begin=next(e for e in rows if e['kind']=='cpu_begin' and e['context']==write['context'])
                if mode==0: rows.remove(write);reclock(rows)
                elif mode==1: rows.insert(rows.index(write),copy.deepcopy(write));reclock(rows)
                elif mode==2: write['value'] ^= 1<<32
                elif mode==3: write['tlb_state']['staged']['asid'] ^= 1
                elif mode==4: write['tlb_state']['entries'][0]['asid']=8
                elif mode==5: begin['word'] ^= 0x800
                elif mode==6: begin['gpr'][26] ^= 1<<32
                elif mode==7: write['tlb_state']['staged']['virtual_address']=0x8000
                elif mode==8: write['tlb_state']['staged']['region']=1
                elif mode==9: write['context']=write['ordinal']
                elif mode==10: begin['tlb_state']['control']['state']['kernel']=False
                else: next(e for e in rows if e['kind']=='ram_fetch_begin' and 'mapping' in e)['mapping']['asid']=8
                run('inspect-rsp-cpu-imem',save(forged),False)
        if args.mapped_reactivation:
            for mode in range(9):
                forged=json.loads(json.dumps(expected));rows=forged['events']
                hit=next(e for e in rows if e['kind']=='ram_fetch_begin' and 'mapping' in e)
                end=next(e for e in rows if e['kind']=='ram_fetch_end' and e['context']==hit['context'])
                restored=next(e for e in rows if e['kind']=='ram_fetch_begin' and 'mapping' in e and e['ordinal']>hit['ordinal'])
                if mode==0: hit['fetch']['physical']=hit['address']=hit['pc']
                elif mode==1: hit['mapping']['asid']=8
                elif mode==2: hit.pop('mapping')
                elif mode==3: end['cache_line']['tag_key'] ^= 0x8000
                elif mode==4: end['value']=13 # current backing cannot replace stale resident
                elif mode==5: end['cache_line']['words'][2]=13
                elif mode==6: restored['mapping']['asid']=8
                elif mode==7: restored['mapping']['entries'][0]['physical'][0]=0xe000
                else: hit['pc']=0x6028 # physical identity is not the mapped virtual PC
                run('inspect-rsp-cpu-imem',save(forged),False)
        if args.entrylo_remap:
            for mode in range(14):
                forged=json.loads(json.dumps(expected));rows=forged['events']
                writes=[e for e in rows if e['kind']=='entry_lo_write'];write=writes[-1]
                begin=next(e for e in rows if e['kind']=='cpu_begin' and e['context']==write['context'])
                mapped=next(e for e in rows if e['kind']=='ram_fetch_begin' and e.get('mapping') and e['fetch']['physical']==0xe028)
                if mode==0: rows.remove(write);reclock(rows)
                elif mode==1: rows.insert(rows.index(write),copy.deepcopy(write));reclock(rows)
                elif mode==2: write['value'] ^= 1<<32
                elif mode==3: write['tlb_state']['entries'][0]['physical'][0]=0xe000
                elif mode==4: write['tlb_state']['staged']['physical'][0]=0x6000
                elif mode==5: write['tlb_state']['staged']['physical'][1]=0xe000
                elif mode==6: write['tlb_state']['staged']['asid']=8
                elif mode==7: begin['word'] ^= 0x800 # EntryLo1 is not this captured setter
                elif mode==8: begin['gpr'][27] ^= 1<<32
                elif mode==9: write['tlb_state']['staged']['dirty'][0]=False
                elif mode==10: mapped['mapping']['entries'][0]['physical'][0]=0x6000
                elif mode==11: mapped['fetch']['physical']=0x6028
                elif mode==12: begin['tlb_state']['control']['state']['exl']=True
                else: forged['format']=model.prior.FORMAT;forged['profile']=model.prior.PROFILE
                run('inspect-rsp-cpu-imem',save(forged),False)
        if args.tlbr_context:
            for mode in range(12):
                forged=json.loads(json.dumps(expected));rows=forged['events']
                load=next(e for e in reversed(rows) if e['kind']=='tlb_read')
                begin=next(e for e in rows if e['kind']=='cpu_begin' and e['context']==load['context'])
                if mode==0: rows.remove(load);reclock(rows)
                elif mode==1: rows.insert(rows.index(load),copy.deepcopy(load));reclock(rows)
                elif mode==2: load['address']=1
                elif mode==3: load['tlb_state']['entries'][0]['asid']=8
                elif mode==4: load['tlb_state']['staged']['physical'][0]=0x6000
                elif mode==5: load['tlb_state']['staged']['asid']=8
                elif mode==6: begin['word'] ^= 6 # TLBP does not load EntryHi
                elif mode==7: load['tlb_state']['control']['interrupt_enable']=True
                elif mode==8: begin['tlb_state']['control']['state']['exl']=True
                elif mode==9: load['context']=load['ordinal']
                elif mode==10: load['value']=1
                else: forged['format']=model.prior.FORMAT;forged['profile']=model.prior.PROFILE
                run('inspect-rsp-cpu-imem',save(forged),False)
        if args.conditional_imem:
            for mode in range(14):
                forged=json.loads(json.dumps(expected));rows=forged['events']
                begin=next(e for e in rows if e['kind']=='cpu_begin' and e['word']==0xe2081000 and e['ordinal']>514)
                write=next(e for e in rows if e['kind']=='sp_write' and e['context']==begin['context'])
                end=next(e for e in rows if e['kind']=='cpu_end' and e['context']==begin['context'])
                if mode==0: rows.remove(write);reclock(rows)
                elif mode==1: rows.insert(rows.index(write),copy.deepcopy(write));reclock(rows)
                elif mode==2: write['value']=1 # post-SC success flag is not source payload
                elif mode==3: write['context']=511
                elif mode==4: write['bank']=0
                elif mode==5: write['address']+=4
                elif mode==6: end['gpr'][8]=0
                elif mode==7: begin['linked_state']['control']['llbit']=False
                elif mode==8: end['linked_state']['control']['llbit']=False
                elif mode==9: next(e for e in rows if e['kind']=='cpu_end' and e['word']==0xc2080000)['linked_state']['linked_address']+=1
                elif mode==10: begin.pop('linked_state')
                elif mode==11: begin['linked_state']['control']['state']['kernel']=False
                elif mode==12: next(e for e in rows if e['kind']=='cpu_end' and e['ordinal']==512)['gpr'][8]=1
                else: forged['format']=model.prior.FORMAT;forged['profile']=model.prior.PROFILE
                run('inspect-rsp-cpu-imem',save(forged),False)
        if args.subword_imem:
            for mode in range(14):
                forged=json.loads(json.dumps(expected));rows=forged['events']
                write=next(e for e in rows if e['kind']=='sp_write' and e['word']==0xa2081003)
                begin=next(e for e in rows if e['kind']=='cpu_begin' and e['context']==write['context'])
                end=next(e for e in rows if e['kind']=='cpu_end' and e['context']==write['context'])
                if mode==0: rows.remove(write);reclock(rows)
                elif mode==1: rows.insert(rows.index(write),copy.deepcopy(write));reclock(rows)
                elif mode==2: write['bytes']=1
                elif mode==3: write['sp_device_address']-=1
                elif mode==4: write['address']+=4
                elif mode==5: write['value']=0x21000000
                elif mode==6: write['bank']=0
                elif mode==7: begin['store_state']['reverse_endian']=True
                elif mode==8: end['store_state']['linked']['control']['llbit']=False
                elif mode==9: begin['store_state']['linked']['control']['state']['kernel']=False
                elif mode==10: write.pop('sp_device_address')
                elif mode==11: begin.pop('store_state')
                elif mode==12: begin['gpr'][8] ^= 1<<32
                else: forged['format']=model.prior.FORMAT;forged['profile']=model.prior.PROFILE
                run('inspect-rsp-cpu-imem',save(forged),False)
            # A valid shifted Word sink retains its witness, but has no identity
            # copy receipt. Skip executing that unsupported RSP word in this
            # synthetic chronology; all completeness flags remain false.
            shifted=json.loads(json.dumps(expected));rows=shifted['events']
            for field in ('initial','final_bytes'):
                shifted['ram'][field][0x60f8:0x60fc]=list((0xa2081000).to_bytes(4,'big'))
            for event in rows:
                if event['pc']==0xffffffffa00060f8:
                    if event['word']==0xa2081003:event['word']=0xa2081000
                    if event['kind'] in ('ram_read','ram_fetch_end'):event['value']=0xa2081000
                    if event['kind']=='sp_write':event.update(value=0x21000000,sp_device_address=0x04001000)
            next(s for s in shifted['steps'] if s['pc']==0xffffffffa00060f8)['word']=0xa2081000
            rows[:]=[e for e in rows if e['ordinal'] not in (561,562)]
            reclock(rows)
            run('inspect-rsp-cpu-imem',save(shifted));partial=json.loads(output.read_bytes())
            assert len(partial['copies'])==len(report['copies'])-1
            assert partial['subword_sp_writes'][0]['value']==0x21000000
            assert not any(partial[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
        if args.ram_load_imem:
            for mode in range(15):
                forged=json.loads(json.dumps(expected));rows=forged['events']
                read=next(e for e in rows if e['kind']=='cpu_ram_read')
                begin=next(e for e in rows if e['kind']=='cpu_begin' and e['context']==read['context'])
                end=next(e for e in rows if e['kind']=='cpu_end' and e['context']==read['context'])
                if mode==0: rows.remove(read);reclock(rows)
                elif mode==1: rows.insert(rows.index(read),copy.deepcopy(read));reclock(rows)
                elif mode==2: read['context']=548
                elif mode==3: read['address']-=4
                elif mode==4: read['value']=0x21
                elif mode==5: read['bytes']=8
                elif mode==6: read['kind']='ram_read' # fetch-stage observation cannot supply an operand
                elif mode==7: read['cpu']=False
                elif mode==8: begin.pop('ram_load_state')
                elif mode==9: end.pop('ram_load_state')
                elif mode==10: begin['ram_load_state']['reverse_endian']=True
                elif mode==11: end['ram_load_state']['linked']['control']['llbit']=False
                elif mode==12: begin['ram_load_state']['linked']['control']['state']['kernel']=False
                elif mode==13: end['gpr'][8]=0x21
                else: forged['format']=model.prior.FORMAT;forged['profile']=model.prior.PROFILE
                run('inspect-rsp-cpu-imem',save(forged),False)
        if args.cached_ram_imem:
            for mode in range(17):
                forged=json.loads(json.dumps(expected));rows=forged['events']
                read=next(e for e in rows if e['ordinal']==643)
                fill=next(e for e in rows if e['ordinal']==617)
                burst=next(e for e in rows if e['ordinal']==616)
                invalidate=next(e for e in rows if e['ordinal']==657)
                if mode==0: rows.remove(read);reclock(rows)
                elif mode==1: rows.insert(rows.index(read),copy.deepcopy(read));reclock(rows)
                elif mode==2: read['dcache_event']['payload']=[0,0,0,0x21] # current backing is not resident data
                elif mode==3: fill['dcache_event']['payload'][-1]=0x21
                elif mode==4: burst['dcache_event']['payload'][-1]=0x21
                elif mode==5: read['dcache_line']['tag']^=4096
                elif mode==6: read['dcache_line']['dirty']=1
                elif mode==7: read['dcache_event']['physical']-=4
                elif mode==8: read['dcache_event']['effective_virtual']=0xffffffffa000e02c
                elif mode==9: read['dcache_event']['ordinal']=618
                elif mode==10: read.pop('dcache_line')
                elif mode==11: invalidate['dcache_line']['tag']|=1
                elif mode==12: invalidate['dcache_event']['slot']=3
                elif mode==13: next(e for e in rows if e['kind']=='cpu_begin' and e['context']==656).pop('dcache_cpu_state')
                elif mode==14: next(e for e in rows if e['kind']=='cpu_end' and e['context']==642)['gpr'][8]=0x21
                elif mode==15: rows.remove(invalidate);reclock(rows)
                else: forged['format']=model.prior.FORMAT;forged['profile']=model.prior.PROFILE
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
                else: next(r for r in graph['promoted_requests'] if r['direction']=='imem_ingress')['direction']='dmem_egress'
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
                if mode==0: next(c for c in graph['pending_commits'] if 'decoder_context' in c).pop('decoder_context')
                else: next(r for r in graph['promoted_requests'] if 'commit_decoder_context' in r['pending_provenance'])['pending_provenance']['commit_decoder_context']=1
                output.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-rsp-cpu-imem',digest,False)
        if args.cache_invalidation:
            for mode in range(5):
                forged=json.loads(original);graph=forged['dma_consumption']
                if mode==0: graph.pop('cache_invalidations')
                elif mode==1: graph['cache_invalidations'][0]['hit']=False
                elif mode==2: graph['cache_invalidations'][0]['ended_fill']=None
                elif mode==3: graph['cached_fetches'][-1]['fill_ordinal']=199
                else: graph['cached_fetches'][-1]['origins'][0]['write_ordinal']=58
                output.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-rsp-cpu-imem',digest,False)
        if args.cpu_ram_copy:
            for mode in range(7):
                forged=json.loads(original);graph=forged['dma_consumption'];writer=graph['cpu_writes'][0]
                if mode==0: graph.pop('cpu_writes')
                elif mode==1: writer['copy_parent']=None
                elif mode==2: writer['copy_parent']['read_ordinal']=231
                elif mode==3: writer['copy_parent']['source_bytes'][0]['parent']['write_ordinal']=219
                elif mode==4: writer['source_register']=9
                elif mode==5: graph['cached_fetches'][-1]['origins'][0]=dict(kind='sp_dma',write_ordinal=219,source_offset=0)
                else: next(f for f in graph['cached_fetches'] if f['fetch_context']==243)['origins'][0]=dict(kind='cpu_copy',write_ordinal=240,source_offset=0)
                output.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-rsp-cpu-imem',digest,False)
        if args.cpu_xori:
            for mode in range(6):
                forged=json.loads(original);graph=forged['dma_consumption']
                parent=next(w['copy_parent'] for w in graph['cpu_writes'] if w['write_ordinal']==276);transform=parent['transform']
                if mode==0: parent.pop('transform')
                elif mode==1: transform['decoder_context']=264
                elif mode==2: transform['source_value']=0x21
                elif mode==3: transform['result_value']=0
                elif mode==4: transform['word'] ^= 1
                else: graph['cached_fetches'][-1]['origins'][0]['write_ordinal']=240
                output.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-rsp-cpu-imem',digest,False)
        if args.break_root:
            for mode in range(6):
                forged=json.loads(original);root=forged['exception_roots'][0]
                if mode==0: forged.pop('exception_roots')
                elif mode==1: root['trigger_context']=317
                elif mode==2: root['root']['input']['class']='tlb_miss'
                elif mode==3: root['fetch_context']=327
                elif mode==4: root['decoder_context']=331
                else: forged['dma_consumption']['cached_fetches'][-1]['origins'][0]['write_ordinal']=318
                output.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-rsp-cpu-imem',digest,False)
        if args.eret_return:
            for mode in range(5):
                forged=json.loads(original);receipt=forged['eret_returns'][0]
                if mode==0: forged.pop('eret_returns')
                elif mode==1: receipt['epc_transfer_ordinal']=307
                elif mode==2: receipt['fetch_context']=327
                elif mode==3: receipt['target_decoder_context']=331
                else: forged['dma_consumption']['cached_fetches'][-1]['origins'][0]['write_ordinal']=318
                output.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-rsp-cpu-imem',digest,False)
        if args.guest_epc:
            for mode in range(8):
                forged=json.loads(original)
                if mode==0: forged.pop('epc_reads')
                elif mode==1: forged.pop('epc_writes')
                elif mode==2: forged['eret_returns'][0].pop('epc_write_ordinal')
                elif mode==3: forged['eret_returns'][0]['epc_write_ordinal']=332
                elif mode==4: forged['epc_writes'][0]['read_parent']['read_ordinal']=343
                elif mode==5: forged['epc_reads'][0]['epc_write_ordinal']=363
                elif mode==6: forged['epc_writes'][0]['value'] ^= 1<<32
                else: forged['epc_writes'][0]['write_ordinal']=332
                output.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-rsp-cpu-imem',digest,False)
        if args.epc_target:
            for mode in range(8):
                forged=json.loads(original);write=forged['epc_writes'][0]
                if mode==0: write.pop('transform')
                elif mode==1: write['transform']['decoder_context']=362
                elif mode==2: write['transform']['source_value']=write['value']
                elif mode==3: write['transform']['result_value']=write['read_parent']['value']
                elif mode==4: write['transform']['word'] ^= 4
                elif mode==5: forged['eret_returns'][0]['before']['state']['epc']=0xffffffff80006028
                elif mode==6: forged['dma_consumption']['cached_fetches'][-1]['origins'][0]['write_ordinal']=348
                else: write['read_parent']['epc_transfer_ordinal']=363
                output.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-rsp-cpu-imem',digest,False)
        if args.mapped_root:
            for mode in range(9):
                forged=json.loads(original);graph=forged['dma_consumption']
                mapped=next(f for f in graph['cached_fetches'] if 'mapping' in f)
                if mode==0: graph.pop('tlb_generations')
                elif mode==1: graph['tlb_generations'].pop()
                elif mode==2: mapped['mapping']['write_ordinal']=325 # equal first write cannot replace second
                elif mode==3: mapped['mapping']['selected_slot']=1
                elif mode==4: graph['tlb_generations'][-1]['same_entry_content']=not graph['tlb_generations'][-1]['same_entry_content']
                elif mode==5: graph['tlb_generations'][-1]['write_ordinal']=325
                elif mode==6: mapped.pop('mapping')
                elif mode==7: mapped['mapping']['entry']['physical'][0]=0x8000
                else: graph['tlb_generations'][-1]['staged_entry']['sha256']='0'*64
                output.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-rsp-cpu-imem',digest,False)
        if args.entryhi_context:
            for mode in range(8):
                forged=json.loads(original);graph=forged['dma_consumption'];write=graph['context_writes'][-1]
                mapped=next(f for f in graph['cached_fetches'] if 'context_write_ordinal' in f.get('mapping',{}))
                if mode==0: graph.pop('context_writes')
                elif mode==1: graph['context_writes'].pop()
                elif mode==2: mapped['mapping']['context_write_ordinal']=346
                elif mode==3: mapped['mapping'].pop('context_write_ordinal')
                elif mode==4: write['same_staged_content']=not write['same_staged_content']
                elif mode==5: write['register_value'] ^= 1<<32
                elif mode==6: write['after']['entries'][0]['asid']=8
                else: write['write_ordinal']=332
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
        if args.mapped_reactivation:
            for mode in range(8):
                forged=json.loads(original);graph=forged['dma_consumption']
                mapped=[f for f in graph['cached_fetches'] if 'mapping' in f]
                replaced=next(f for f in mapped if f['word']==13)
                if mode==0: mapped[0]['fill_ordinal']=replaced['fill_ordinal']
                elif mode==1: mapped[1]['origins'][0]['write_ordinal']=318
                elif mode==2: mapped[0]['physical']=mapped[0]['pc']
                elif mode==3: mapped[0]['mapping']['context_write_ordinal']=358
                elif mode==4: mapped[1]['mapping']['context_write_ordinal']=351
                elif mode==5: mapped[1]['fill_ordinal']=replaced['fill_ordinal']
                elif mode==6: replaced['origins'][0]['write_ordinal']=276
                else: forged['eret_returns'][0]['after']['state']['pc']=0x602c
                output.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-rsp-cpu-imem',digest,False)
        if args.entrylo_remap:
            for mode in range(10):
                forged=json.loads(original);graph=forged['dma_consumption']
                mapped=[f for f in graph['cached_fetches'] if 'mapping' in f]
                installed=next(f for f in mapped if f['word']==13)
                if mode==0: graph.pop('entry_lo_writes')
                elif mode==1: graph['entry_lo_writes'].pop()
                elif mode==2: installed['mapping']['entry_lo_write_ordinal']=398
                elif mode==3: installed['mapping'].pop('entry_lo_write_ordinal')
                elif mode==4: mapped[2]['mapping']['entry_lo_write_ordinal']=405 # staged writer not installed yet
                elif mode==5: installed['mapping']['write_ordinal']=332
                elif mode==6: installed['origins'][0]['write_ordinal']=318 # equal BREAK, different physical writer
                elif mode==7: graph['entry_lo_writes'][-1]['same_staged_content']=False
                elif mode==8: graph['entry_lo_writes'][-1]['register_value'] ^= 1<<32
                else: installed['mapping']['entry']['physical'][0]=0x6000
                output.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-rsp-cpu-imem',digest,False)
        if args.tlbr_context:
            for mode in range(10):
                forged=json.loads(original);graph=forged['dma_consumption']
                load=graph['context_loads'][-1]
                mapped=next(f for f in graph['cached_fetches'] if 'tlbr_load_ordinal' in f.get('mapping',{}))
                if mode==0: graph.pop('context_loads')
                elif mode==1: graph['context_loads'].pop()
                elif mode==2: mapped['mapping']['tlbr_load_ordinal']=431
                elif mode==3: mapped['mapping']['context_write_ordinal']=424
                elif mode==4: mapped['mapping'].pop('tlbr_load_ordinal')
                elif mode==5: load['installed_write_ordinal']=332
                elif mode==6: load['entry_lo_write_ordinal']=398
                elif mode==7: load['generation']['same_context_content']=False
                elif mode==8: load['generation']['selected_entry']['sha256']='0'*64
                else: load['generation']['load_ordinal']=431
                output.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-rsp-cpu-imem',digest,False)
        if args.conditional_imem:
            for mode in range(10):
                forged=json.loads(original);attempts=forged['conditional_sp_attempts'];fetches=forged['imem_fetches']
                if mode==0: forged.pop('conditional_sp_attempts')
                elif mode==1: attempts[0]['completed_effect']=copy.deepcopy(attempts[1]['completed_effect'])
                elif mode==2: attempts[-1]['completed_effect']['effect_ordinal']=525
                elif mode==3: attempts[-1]['completed_effect']['source_value_before']=1
                elif mode==4: attempts[-1]['completed_effect']['context_id']=524
                elif mode==5: fetches[-1]['origins'][0]['write_ordinal']=525
                elif mode==6: next(f for f in fetches if f['context']==513)['origins'][0]['write_ordinal']=525 # failed attempt leaves old parent
                elif mode==7: forged['copies'][-1]['read_ordinal']=519
                elif mode==8: forged['final_imem_writers'][0]['write_ordinal']=525
                else: attempts[-1]['completed_effect']=None
                output.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-rsp-cpu-imem',digest,False)
        if args.subword_imem:
            for mode in range(10):
                forged=json.loads(original);writes=forged['subword_sp_writes']
                copy_parent=next(c for c in forged['copies'] if c['store_context']==566)
                if mode==0: forged.pop('subword_sp_writes')
                elif mode==1: writes[-1]['effect_ordinal']=559
                elif mode==2: writes[-1]['translated_physical']=0x04001003
                elif mode==3: writes[-1]['value']=0x21000000
                elif mode==4: copy_parent.pop('transform')
                elif mode==5: copy_parent['transform']['decoder_context']=532
                elif mode==6: copy_parent['source_bytes'][0]['parent']['write_ordinal']=220
                elif mode==7: forged['imem_fetches'][-1]['origins'][0]['write_ordinal']=559
                elif mode==8: forged['final_imem_writers'][0]['write_ordinal']=559
                else: copy_parent['read_ordinal']=519
                output.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-rsp-cpu-imem',digest,False)
        if args.ram_load_imem:
            for mode in range(11):
                forged=json.loads(original)
                first=next(c for c in forged['copies'] if c['store_context']==586)
                last=next(c for c in forged['copies'] if c['store_context']==606);origins=last['source_bytes']
                if mode==0: forged['copies'].remove(last)
                elif mode==1: origins[0]['parent']['write_ordinal']=473 # equal older RAM writer
                elif mode==2: origins[0]['read_ordinal']=576
                elif mode==3: origins[0]['physical']-=4
                elif mode==4: origins[0]['parent']['source_offset']=1
                elif mode==5: first['source_bytes'][0]['parent']['write_ordinal']=595 # future write cannot change prior load
                elif mode==6: first['transform']['decoder_context']=553
                elif mode==7: last['load_context']=575
                elif mode==8: next(w for w in forged['dma_consumption']['cpu_writes'] if w['write_ordinal']==595)['copy_parent']['source_bytes'][0]['parent']['write_ordinal']=595
                elif mode==9: forged['imem_fetches'][-1]['origins'][0]['write_ordinal']=587
                else: forged['final_imem_writers'][0]['write_ordinal']=587
                output.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-rsp-cpu-imem',digest,False)
        if args.cached_ram_imem:
            for mode in range(13):
                forged=json.loads(original);graph=forged['dma_consumption']['dcache_consumption'];reads=graph['cache']['reads'];copies=forged['copies'][-3:]
                if mode==0: forged['dma_consumption'].pop('dcache_consumption')
                elif mode==1: copies[1]['source_bytes'][0]['parent']['write_ordinal']=637
                elif mode==2: copies[1]['source_bytes'][0]['resident_generation']=664
                elif mode==3: copies[-1]['source_bytes'][0]['parent']['write_ordinal']=595
                elif mode==4: reads[1]['origins'][0]['backing_read_ordinal']=663
                elif mode==5: graph['backing_fills'][0]['source_bytes'][12]['write_ordinal']=637
                elif mode==6: graph['backing_fills'][-1]['source_bytes'][12]['write_ordinal']=595
                elif mode==7: reads[1]['current_captured_backing']['write_ordinal']=595
                elif mode==8: reads[1]['payload']=[0,0,0,0x21]
                elif mode==9: graph['cache']['writeback']['invalidations']=0
                elif mode==10: copies[-1]['source_bytes'][0]['physical']-=4
                elif mode==11: forged['imem_fetches'][-1]['origins'][0]['write_ordinal']=649
                else: forged['final_imem_writers'][0]['write_ordinal']=649
                output.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-rsp-cpu-imem',digest,False)
    print('RSP definitions: original-clock ORI/ADDU parents, phase cuts, full register snapshots, source/report/input gates and unchanged proof flags passed')


if __name__=='__main__': main()
