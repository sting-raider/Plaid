"""Independent complete CPU copy to RAM/resident/invalidation/refill graph."""
from pathlib import Path
import copy
import importlib.util
ROOT=Path(__file__).resolve().parents[2]
FORMAT='plaid-rsp-cpu-imem-history-v12'
PROFILE='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-cpu-copy-ram-cached-consumption-v12'
INITIAL=dict(bank=0,descriptor=dict(pbus=0,dram=0,length=0,count=0,skip=0))
LW=0x8e080000
SW=0xae680000
CACHE=0xbe500000


def build():
    spec=importlib.util.spec_from_file_location('invalidation_model',ROOT/'spikes/068-dma-cache-invalidation/verify.py')
    prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
    events,definitions,expected=prior.build()
    def update(frame):frame['words'][6:8]=[LW,SW]
    for event in events:
        if event['gpr']:event['gpr'][19]=0xffffffffa0006028
        if 'cache_line' in event:update(event['cache_line'])
        if 'cache_operation' in event:
            for key in ('before','after'):update(event['cache_operation'][key])
    for fill in expected['cache_fills']:update(fill['cache_line'])
    for operation in expected['cache_invalidations']:
        for key in ('before','after'):update(operation['operation'][key])
    for key in ('initial_ram','final_ram'):expected[key][0x38:0x40]=list(LW.to_bytes(4,'big')+SW.to_bytes(4,'big'))
    def append(template,**changes):
        event=copy.deepcopy(template);event.update(changes,ordinal=len(events)+1);events.append(event);return event
    cpu=copy.deepcopy(events[-1])
    append(cpu,kind='cpu_reentry',phase=32,context=229,pc=0xffffffffa0006038)
    fetch=copy.deepcopy(next(e for e in events if e['kind']=='ram_fetch_begin'))
    fetch.update(phase=32,context=230,pc=0xffffffffa0006038,address=0x6038,fetch=dict(physical=0x6038,cached=False))
    append(fetch)
    read=copy.deepcopy(next(e for e in events if e['kind']=='ram_read'))
    append(read,phase=32,context=230,pc=fetch['pc'],address=0x6038,value=LW)
    append(fetch,kind='ram_fetch_end',value=LW)
    append(cpu,kind='cpu_begin',phase=32,context=233,pc=fetch['pc'],word=LW)
    sp=copy.deepcopy(next(e for e in events if e['kind']=='sp_read'))
    append(sp,phase=32,context=233,pc=fetch['pc'],word=LW,value=0)
    cpu['gpr'][8]=0
    append(cpu,phase=32,context=233,pc=fetch['pc'],word=LW)
    fetch.update(phase=33,context=236,pc=0xffffffffa000603c,address=0x603c,fetch=dict(physical=0x603c,cached=False))
    append(fetch)
    append(read,phase=33,context=236,pc=fetch['pc'],address=0x603c,value=SW)
    append(fetch,kind='ram_fetch_end',value=SW)
    append(cpu,kind='cpu_begin',phase=33,context=239,pc=fetch['pc'],word=SW)
    append(read,kind='cpu_ram_write',phase=33,context=239,pc=fetch['pc'],word=SW,address=0x6028,value=0)
    append(cpu,phase=33,context=239,pc=fetch['pc'],word=SW)
    ingress=expected['dmem_installs'][0]
    parents=[dict(kind='dmem_dma',promote_context=ingress['promote_context'],read_ordinal=ingress['read_ordinal'],
        write_ordinal=ingress['write_ordinal'],source=ingress['source']+n,parent=ingress['source_bytes'][n]) for n in range(4)]
    expected['cpu_writes']=[dict(decoder_context=239,write_ordinal=240,destination=0x6028,
        source_register=8,register_value=0,word=0,copy_parent=dict(load_context=233,read_ordinal=234,
            source=0x04000000,source_bytes=parents))]
    for context,address,word,phase,decoder in [(243,0x6028,0,34,245),(248,0x6034,CACHE,35,250),(254,0x6028,0,36,258)]:
        pc=0xffffffff80000000+address
        append(cpu,kind='cpu_reentry',phase=phase,context=context-1,pc=pc,word=0)
        fetch.update(phase=phase,context=context,pc=pc,address=address,fetch=dict(physical=address,cached=True))
        append(fetch)
        frame=expected['cache_fills'][1]['cache_line']
        if context==254:
            burst=copy.deepcopy(next(e for e in events if e['kind']=='cache_burst_read'))
            append(burst,phase=phase,context=context,pc=pc,cache_line=frame)
            append(events[-1],kind='cache_fill')
        append(fetch,kind='ram_fetch_end',value=word,cache_line=frame)
        append(cpu,kind='cpu_begin',phase=phase,context=decoder,pc=pc,word=word)
        if word==CACHE:
            operation=copy.deepcopy(expected['cache_invalidations'][0]['operation'])
            operation['before']=copy.deepcopy(frame);operation['after']=copy.deepcopy(frame);operation['after']['tag_key'] &= ~1
            template=next(e for e in events if e['kind']=='cache_operation')
            append(template,phase=phase,context=decoder,pc=pc,cache_operation=operation)
            expected['cache_invalidations'].append(dict(decoder_context=250,ordinal=251,physical=0x6028,
                operation=operation,hit=True,ended_fill=225))
        append(cpu,phase=phase,context=decoder,pc=pc,word=word)
        origins=expected['cache_fills'][1]['source_bytes'][address&31:(address&31)+4]
        if context==254:origins=[dict(kind='cpu_copy',write_ordinal=240,source_offset=n) for n in range(4)]
        expected['cached_fetches'].append(dict(fetch_context=context,end_ordinal=context+(3 if context==254 else 1),
            decoder_context=decoder,pc=pc,physical=address,word=word,burst_ordinal=255 if context==254 else 224,
            fill_ordinal=256 if context==254 else 225,origins=copy.deepcopy(origins)))
    fresh=copy.deepcopy(expected['cache_fills'][1]);fresh.update(fetch_context=254,burst_ordinal=255,fill_ordinal=256)
    fresh['source_bytes'][8:12]=[dict(kind='cpu_copy',write_ordinal=240,source_offset=n) for n in range(4)]
    expected['cache_fills'].append(fresh)
    expected['fetches'].extend([dict(fetch_context=context,read_ordinal=context+1,decoder_context=decoder,
        pc=pc,physical=address,word=word,origins=[dict(kind='unknown',cut_ordinal=None) for _ in range(4)])
        for context,decoder,pc,address,word in [(230,233,0xffffffffa0006038,0x6038,LW),(236,239,0xffffffffa000603c,0x603c,SW)]])
    return events,definitions,expected


def expected_events():
    events,definitions,_=build();return events,definitions


def replay(events,definitions):
    source,defs,expected=build();assert events==source and definitions==defs;return expected


def inspect(run):
    events,definitions,expected=build()
    assert run['events']==events,'complete CPU copy/resident/invalidation/refill census'
    assert run['initial_pending']==INITIAL
    for field in ('initial_ram','final_ram','final_dmem','initial_imem','final_imem'):assert run[field]==expected[field],field
    assert run['initial_dmem']==list(bytes.fromhex('340800aaaaee7722')+bytes(4088))
    starts=[e for e in events if e['kind']=='cpu_begin'];ends=[e for e in events if e['kind']=='cpu_end']
    assert run['steps']==[dict(phase=a['phase'],index=i,word=a['word'],pc=a['pc'],before=a['gpr'],after=b['gpr']) for i,(a,b) in enumerate(zip(starts,ends))]
    source={key:run[key] for key in ('initial_dmem','initial_imem','final_dmem','final_imem','steps','events','initial_pending')}
    source.update(format=FORMAT,profile=PROFILE,ram=dict(start=0x6000,initial=run['initial_ram'],final_bytes=run['final_ram']))
    return source,definitions


def compare_report(report,definitions):
    _,defs,expected=build();assert definitions==defs
    assert report['rsp_definitions']==defs and report['imem_fetches']==expected['imem_fetches']
    graph=report['dma_consumption']
    for field,key in (('writes','writers'),('fetches','fetches'),('promoted_requests','requests'),
        ('imem_installs','installs'),('dmem_installs','dmem_installs'),('pending_commits','pending_commits'),
        ('cache_fills','cache_fills'),('cached_fetches','cached_fetches'),('cache_invalidations','cache_invalidations'),('cpu_writes','cpu_writes')):
        assert graph[field]==expected[key],field
    assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
