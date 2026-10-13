"""Independent transformed EPC target/ERET and executable ancestry graph."""
from pathlib import Path
import copy
import importlib.util
ROOT=Path(__file__).resolve().parents[2]
FORMAT='plaid-rsp-cpu-imem-history-v17'
PROFILE='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-epc-transform-target-consumption-v17'
INITIAL=dict(bank=0,descriptor=dict(pbus=0,dram=0,length=0,count=0,skip=0))
RAM_START=0
ROOT_PC=0xffffffff80000180
LW=0x8e080000
SW=0xae680000
CACHE=0xbe500000
ERET=0x42000018


def build():
    spec=importlib.util.spec_from_file_location('epc_model',ROOT/'spikes/073-guest-epc-return/verify.py')
    prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
    events,definitions,expected=prior.build()
    events=events[:349] # existing handler LW/SW through original writer348
    words=[0,LW,SW,SW|4,CACHE,0x40087000,0x39080004,0x40887000]
    code=list(b''.join(w.to_bytes(4,'big') for w in words[1:])+ERET.to_bytes(4,'big'))
    for field in ('initial_ram','final_ram'):expected[field][0x184:0x1a4]=code
    for event in events:
        if event.get('cache_line',{}).get('slot')==12:event['cache_line']['words']=words[:]
    expected['cache_fills']=expected['cache_fills'][:-1]
    expected['cache_fills'][-1]['cache_line']['words']=words[:]
    expected['cached_fetches']=[r for r in expected['cached_fetches'] if r['decoder_context']<=347]
    expected['cache_invalidations']=expected['cache_invalidations'][:-1]
    expected['epc_reads']=[];expected['epc_writes']=[]
    def append(template,**changes):
        event=copy.deepcopy(template);event.update(changes,ordinal=len(events)+1);events.append(event);return event
    cpu=copy.deepcopy(events[-1]);cpu['gpr'][8]=0
    fetch=copy.deepcopy(events[344]);fetch.pop('cache_line',None)
    frame=copy.deepcopy(expected['cache_fills'][-1]['cache_line'])
    for phase,context,decoder,address,word in [(52,350,352,0x18c,SW|4),(53,355,357,0x190,CACHE),
            (54,360,362,0x194,0x40087000),(55,365,367,0x198,0x39080004),
            (56,369,371,0x19c,0x40887000),(57,374,378,0x1a0,ERET)]:
        pc=0xffffffff80000000+address
        fetch.update(phase=phase,context=context,pc=pc,address=address,fetch=dict(physical=address,cached=True))
        append(fetch)
        if word==ERET:
            frame=dict(slot=13,tag_key=1,index=0x1a0,words=[ERET]+[0]*7)
            burst=copy.deepcopy(next(e for e in events if e['kind']=='cache_burst_read'))
            append(burst,phase=phase,context=context,pc=pc,address=0x1a0,cache_line=frame)
            append(events[-1],kind='cache_fill')
            expected['cache_fills'].append(dict(fetch_context=context,burst_ordinal=375,fill_ordinal=376,
                physical_line=0x1a0,cache_line=frame,source_bytes=[dict(kind='unknown',cut_ordinal=None)]*32))
        append(fetch,kind='ram_fetch_end',value=word,cache_line=frame)
        begin=append(cpu,kind='cpu_begin',phase=phase,context=decoder,pc=pc,word=word)
        if word==SW|4:
            write=copy.deepcopy(next(e for e in events if e['kind']=='cpu_ram_write'))
            append(write,phase=phase,context=decoder,pc=pc,word=word,address=0x602c,value=0)
            receipt=copy.deepcopy(expected['cpu_writes'][-1]);receipt.update(decoder_context=352,write_ordinal=353,destination=0x602c)
            expected['cpu_writes'].append(receipt)
        elif word==CACHE:
            template=copy.deepcopy(next(e for e in reversed(events) if e['kind']=='cache_operation'))
            before=copy.deepcopy(expected['cache_fills'][-2]['cache_line'])
            operation=copy.deepcopy(template['cache_operation']);operation['before']=before
            operation['after']=copy.deepcopy(before);operation['after']['tag_key'] &= ~1
            append(template,phase=phase,context=decoder,pc=pc,word=word,cache_operation=operation)
            expected['cache_invalidations'].append(dict(decoder_context=357,ordinal=358,physical=0x6028,
                operation=operation,hit=True,ended_fill=329))
        elif word==0x39080004:
            transform=dict(decoder_context=367,pc=pc,word=word,source_value=cpu['gpr'][8],result_value=cpu['gpr'][8]^4)
            cpu['gpr'][8] ^= 4
        else:
            state=copy.deepcopy(expected['exception_roots'][0]['after']);state['pc']=pc
            if word==ERET:state['epc']=0xffffffff8000602c
            before=dict(state=state,interrupt_enable=False,llbit=False)
            transfer=copy.deepcopy(next(e for e in events if e['kind']=='exception_transfer'));transfer.pop('exception_state')
            if word==ERET:
                after=copy.deepcopy(before);after['state'].update(pc=state['epc'],exl=False)
                begin['return_state']=before
                append(transfer,kind='return_transfer',phase=phase,context=decoder,pc=pc,word=word,return_state=after)
                expected['eret_returns']=[dict(epc_transfer_ordinal=332,epc_write_ordinal=372,decoder_context=378,
                    transfer_ordinal=379,before=before,after=after,fetch_context=381,target_decoder_context=385)]
            else:
                begin['epc_state']=before;after=copy.deepcopy(before)
                if word==0x40887000:after['state']['epc']=cpu['gpr'][8]
                append(transfer,kind='epc_read' if word==0x40087000 else 'epc_write',phase=phase,context=decoder,
                    pc=pc,word=word,epc_state=after)
                if word==0x40087000:
                    cpu['gpr'][8]=0xffffffff80006028
                    expected['epc_reads'].append(dict(decoder_context=362,read_ordinal=363,register=8,
                        value=cpu['gpr'][8],epc_transfer_ordinal=332,epc_write_ordinal=None,before=before,after=after))
                else:
                    expected['epc_writes'].append(dict(decoder_context=371,write_ordinal=372,register=8,
                        value=cpu['gpr'][8],read_parent=copy.deepcopy(expected['epc_reads'][0]),transform=transform,before=before,after=after))
        append(cpu,phase=phase,context=decoder,pc=pc,word=word)
        fill=expected['cache_fills'][-1];lane=address&31
        expected['cached_fetches'].append(dict(fetch_context=context,end_ordinal=decoder-1,decoder_context=decoder,
            pc=pc,physical=address,word=word,burst_ordinal=fill['burst_ordinal'],fill_ordinal=fill['fill_ordinal'],
            origins=copy.deepcopy(fill['source_bytes'][lane:lane+4])))
    expected['final_ram'][0x602c:0x6030]=[0]*4
    fresh=copy.deepcopy(expected['cache_fills'][-3]);fresh.update(fetch_context=381,burst_ordinal=382,fill_ordinal=383)
    fresh['cache_line']['words'][2:4]=[0,0]
    fresh['source_bytes'][8:16]=[dict(kind='cpu_copy',write_ordinal=348 if n<4 else 353,source_offset=n%4) for n in range(8)]
    fetch.update(phase=58,context=381,pc=0xffffffff8000602c,address=0x602c,fetch=dict(physical=0x602c,cached=True))
    append(fetch);burst=copy.deepcopy(next(e for e in events if e['kind']=='cache_burst_read'))
    append(burst,phase=58,context=381,pc=fetch['pc'],cache_line=fresh['cache_line']);append(events[-1],kind='cache_fill')
    append(fetch,kind='ram_fetch_end',value=0,cache_line=fresh['cache_line'])
    append(cpu,kind='cpu_begin',phase=58,context=385,pc=fetch['pc'],word=0);append(events[-1],kind='cpu_end')
    expected['cache_fills'].append(fresh)
    expected['cached_fetches'].append(dict(fetch_context=381,end_ordinal=384,decoder_context=385,pc=fetch['pc'],
        physical=0x602c,word=0,burst_ordinal=382,fill_ordinal=383,origins=fresh['source_bytes'][12:16]))
    return events,definitions,expected


def expected_events():
    events,definitions,_=build();return events,definitions


def replay(events,definitions):
    source,defs,expected=build();assert events==source and definitions==defs;return expected


def inspect(run):
    events,definitions,expected=build()
    assert run['events']==events,'complete live-EPC/handler/return census'
    assert run['initial_pending']==INITIAL
    for field in ('initial_ram','final_ram','final_dmem','initial_imem','final_imem'):assert run[field]==expected[field],field
    assert run['initial_dmem']==list(bytes.fromhex('340800aaaaee7722')+bytes(4088))
    starts=[e for e in events if e['kind']=='cpu_begin'];ends=[e for e in events if e['kind']=='cpu_end']
    assert run['steps']==[dict(phase=a['phase'],index=i,word=a['word'],pc=a['pc'],before=a['gpr'],after=b['gpr']) for i,(a,b) in enumerate(zip(starts,ends))]
    source={key:run[key] for key in ('initial_dmem','initial_imem','final_dmem','final_imem','steps','events','initial_pending')}
    source.update(format=FORMAT,profile=PROFILE,ram=dict(start=RAM_START,initial=run['initial_ram'],final_bytes=run['final_ram']))
    return source,definitions


def compare_report(report,definitions):
    _,defs,expected=build();assert definitions==defs
    assert report['rsp_definitions']==defs and report['imem_fetches']==expected['imem_fetches']
    assert report['exception_roots']==expected['exception_roots'] and report['eret_returns']==expected['eret_returns']
    assert report['epc_reads']==expected['epc_reads'] and report['epc_writes']==expected['epc_writes']
    graph=report['dma_consumption']
    for field,key in (('writes','writers'),('fetches','fetches'),('promoted_requests','requests'),
        ('imem_installs','installs'),('dmem_installs','dmem_installs'),('pending_commits','pending_commits'),
        ('cache_fills','cache_fills'),('cached_fetches','cached_fetches'),('cache_invalidations','cache_invalidations'),('cpu_writes','cpu_writes')):
        assert graph[field]==expected[key],field
    assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
