"""Independent continuous handler/live-EPC/returned-instruction graph."""
from pathlib import Path
import copy
import importlib.util
ROOT=Path(__file__).resolve().parents[2]
FORMAT='plaid-rsp-cpu-imem-history-v15'
PROFILE='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-live-epc-handler-return-consumption-v15'
INITIAL=dict(bank=0,descriptor=dict(pbus=0,dram=0,length=0,count=0,skip=0))
RAM_START=0
ROOT_PC=0xffffffff80000180
LW=0x8e080000
SW=0xae680000
CACHE=0xbe500000
ERET=0x42000018


def build():
    spec=importlib.util.spec_from_file_location('root_model',ROOT/'spikes/071-writer-break-handler/verify.py')
    prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
    events,definitions,expected=prior.build()
    words=[0,LW,SW,CACHE,ERET,0,0,0]
    code=list(LW.to_bytes(4,'big')+SW.to_bytes(4,'big')+CACHE.to_bytes(4,'big')+ERET.to_bytes(4,'big'))
    for field in ('initial_ram','final_ram'):expected[field][0x184:0x194]=code
    for event in events:
        if event.get('cache_line',{}).get('slot')==12:event['cache_line']['words']=words[:]
    expected['cache_fills'][-1]['cache_line']['words']=words[:]
    def append(template,**changes):
        event=copy.deepcopy(template);event.update(changes,ordinal=len(events)+1);events.append(event);return event
    cpu=copy.deepcopy(events[-1])
    fetch=copy.deepcopy(events[-6]);fetch.pop('cache_line',None)
    frame=copy.deepcopy(expected['cache_fills'][-1]['cache_line'])
    for phase,context,decoder,address,word in [(50,340,342,0x184,LW),(51,345,347,0x188,SW),
            (52,350,352,0x18c,CACHE),(53,355,357,0x190,ERET)]:
        pc=0xffffffff80000000+address
        fetch.update(phase=phase,context=context,pc=pc,address=address,fetch=dict(physical=address,cached=True))
        append(fetch);append(fetch,kind='ram_fetch_end',value=word,cache_line=frame)
        begin=append(cpu,kind='cpu_begin',phase=phase,context=decoder,pc=pc,word=word)
        if word==LW:
            sp=copy.deepcopy(next(e for e in events if e['kind']=='sp_read'))
            append(sp,phase=phase,context=decoder,pc=pc,word=word,value=0);cpu['gpr'][8]=0
        elif word==SW:
            write=copy.deepcopy(next(e for e in events if e['kind']=='cpu_ram_write'))
            append(write,phase=phase,context=decoder,pc=pc,address=0x6028,value=0)
        elif word==CACHE:
            template=copy.deepcopy(next(e for e in reversed(events) if e['kind']=='cache_operation'))
            before=copy.deepcopy(expected['cache_fills'][-2]['cache_line'])
            operation=copy.deepcopy(template['cache_operation']);operation['before']=before
            operation['after']=copy.deepcopy(before);operation['after']['tag_key'] &= ~1
            append(template,phase=phase,context=decoder,pc=pc,cache_operation=operation)
            expected['cache_invalidations'].append(dict(decoder_context=352,ordinal=353,physical=0x6028,
                operation=operation,hit=True,ended_fill=329))
        else:
            before=copy.deepcopy(expected['exception_roots'][0]['after']);before['pc']=pc
            after=copy.deepcopy(before);after.update(pc=0xffffffff80006028,exl=False)
            before=dict(state=before,interrupt_enable=False,llbit=False)
            after=dict(state=after,interrupt_enable=False,llbit=False)
            begin['return_state']=before
            transfer=copy.deepcopy(next(e for e in events if e['kind']=='exception_transfer'))
            transfer.pop('exception_state')
            append(transfer,kind='return_transfer',phase=phase,context=decoder,pc=pc,word=word,return_state=after)
            expected['eret_returns']=[dict(epc_transfer_ordinal=332,decoder_context=357,transfer_ordinal=358,
                before=before,after=after,fetch_context=360,target_decoder_context=364)]
        append(cpu,phase=phase,context=decoder,pc=pc,word=word)
        lane=address&31
        expected['cached_fetches'].append(dict(fetch_context=context,end_ordinal=context+1,decoder_context=decoder,
            pc=pc,physical=address,word=word,burst_ordinal=335,fill_ordinal=336,
            origins=copy.deepcopy(expected['cache_fills'][-1]['source_bytes'][lane:lane+4])))
    parent=copy.deepcopy(expected['cpu_writes'][0]['copy_parent']);parent.update(load_context=342,read_ordinal=343)
    expected['cpu_writes'].append(dict(decoder_context=347,write_ordinal=348,destination=0x6028,
        source_register=8,register_value=0,word=0,copy_parent=parent))
    expected['final_ram'][0x6028:0x602c]=[0]*4
    fresh=copy.deepcopy(expected['cache_fills'][-2]);fresh.update(fetch_context=360,burst_ordinal=361,fill_ordinal=362)
    fresh['cache_line']['words'][2]=0
    fresh['source_bytes'][8:12]=[dict(kind='cpu_copy',write_ordinal=348,source_offset=n) for n in range(4)]
    fetch.update(phase=54,context=360,pc=0xffffffff80006028,address=0x6028,fetch=dict(physical=0x6028,cached=True))
    append(fetch)
    burst=copy.deepcopy(next(e for e in events if e['kind']=='cache_burst_read'))
    append(burst,phase=54,context=360,pc=fetch['pc'],cache_line=fresh['cache_line']);append(events[-1],kind='cache_fill')
    append(fetch,kind='ram_fetch_end',value=0,cache_line=fresh['cache_line'])
    append(cpu,kind='cpu_begin',phase=54,context=364,pc=fetch['pc'],word=0);append(events[-1],kind='cpu_end')
    expected['cache_fills'].append(fresh)
    expected['cached_fetches'].append(dict(fetch_context=360,end_ordinal=363,decoder_context=364,pc=fetch['pc'],
        physical=0x6028,word=0,burst_ordinal=361,fill_ordinal=362,origins=fresh['source_bytes'][8:12]))
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
    graph=report['dma_consumption']
    for field,key in (('writes','writers'),('fetches','fetches'),('promoted_requests','requests'),
        ('imem_installs','installs'),('dmem_installs','dmem_installs'),('pending_commits','pending_commits'),
        ('cache_fills','cache_fills'),('cached_fetches','cached_fetches'),('cache_invalidations','cache_invalidations'),('cpu_writes','cpu_writes')):
        assert graph[field]==expected[key],field
    assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
