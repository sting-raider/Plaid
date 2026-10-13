"""Independent complete guest invalidation/DMA/refill consumption census."""
from pathlib import Path
import copy
import importlib.util
ROOT=Path(__file__).resolve().parents[2]
FORMAT='plaid-rsp-cpu-imem-history-v11'
PROFILE='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-dma-cached-cpu-invalidation-v11'
INITIAL=dict(bank=0,descriptor=dict(pbus=0,dram=0,length=0,count=0,skip=0))
CACHE=0xbe500000


def build():
    spec=importlib.util.spec_from_file_location('cached_model',ROOT/'spikes/067-dma-cached-cpu/verify.py')
    prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
    events,definitions,expected=prior.build()
    for event in events:
        if event['gpr']:event['gpr'][18]=0xffffffff80006028
        if 'cache_line' in event:event['cache_line']['words'][5]=CACHE
    expected['initial_ram'][0x34:0x38]=list(CACHE.to_bytes(4,'big'))
    expected['final_ram'][0x34:0x38]=list(CACHE.to_bytes(4,'big'))
    frame=expected['cache_fills'][0]['cache_line'];frame['words'][5]=CACHE
    def append(template,**changes):
        event=copy.deepcopy(template);event.update(changes,ordinal=len(events)+1);events.append(event);return event
    root=copy.deepcopy(events[203])
    append(root,phase=29,context=209,pc=0xffffffff80006034)
    fetch=copy.deepcopy(events[204])
    fetch.update(phase=29,context=210,pc=0xffffffff80006034,address=0x6034,fetch=dict(physical=0x6034,cached=True))
    append(fetch);append(fetch,kind='ram_fetch_end',value=CACHE,cache_line=frame)
    cpu=copy.deepcopy(events[206]);cpu.update(phase=29,context=212,pc=0xffffffff80006034,word=CACHE)
    append(cpu)
    after=copy.deepcopy(frame);after['tag_key'] &= ~1
    operation=dict(virtual_address=0xffffffff80006028,operation=16,before=frame,after=after)
    effect=copy.deepcopy(next(e for e in events if e['kind']=='ram_read'))
    append(effect,kind='cache_operation',phase=29,context=212,pc=cpu['pc'],word=CACHE,
        address=0x6028,bytes=0,value=0,cache_operation=operation)
    append(cpu,kind='cpu_end')
    descriptor=dict(pbus=0,dram=0x6028,length=0,count=0,skip=0)
    pending=copy.deepcopy(next(e for e in events if e['kind']=='dma_pending_write'))
    pending.update(phase=30,pc=0xffffffff80006038,bank=0,offset=0,dma=descriptor,pending_full=False)
    pending.pop('dma_direction',None)
    append(pending,context=215,address=0,value=0)
    append(pending,context=216,address=1,value=0x6028)
    append(pending,context=217,address=3,value=0,pending_full=True,dma_direction='dmem_egress')
    promote=copy.deepcopy(next(e for e in events if e['kind']=='dma_promote'))
    append(promote,context=218,phase=30,pc=0xffffffff80006038)
    for lane,old in enumerate(expected['writers'][:2]):
        template=next(e for e in events if e['ordinal']==old['write_ordinal'])
        append(template,context=218,phase=30,pc=0xffffffff80006038)
        ingress=expected['dmem_installs'][lane]
        parents=[dict(kind='dmem_dma',promote_context=ingress['promote_context'],read_ordinal=ingress['read_ordinal'],
            write_ordinal=ingress['write_ordinal'],source=ingress['source']+n,parent=ingress['source_bytes'][n]) for n in range(4)]
        expected['writers'].append(dict(write_ordinal=219+lane,destination=old['destination'],descriptor=descriptor,
            source_offset=lane*4,word=old['word'],source_bytes=parents,promote_context=218))
    complete=copy.deepcopy(next(e for e in events if e['kind']=='dma_complete'))
    append(complete,context=218,phase=30,pc=0xffffffff80006038)
    expected['requests'].append(dict(promote_context=218,complete_ordinal=221,descriptor=descriptor,
        write_ordinals=[219,220],direction='dmem_egress',pending_provenance=dict(commit_ordinal=217,
            pbus_write_ordinal=215,dram_write_ordinal=216)))
    expected['pending_commits'].append(dict(commit_ordinal=217,superseded_commit=None))
    append(root,phase=31,context=222)
    fetch=copy.deepcopy(events[204]);fetch.update(phase=31,context=223)
    append(fetch)
    fresh=copy.deepcopy(frame);fresh['words'][3]=0xaaee7722
    burst=copy.deepcopy(events[197]);burst.update(phase=31,context=223,pc=fetch['pc'],cache_line=fresh)
    append(burst);append(burst,kind='cache_fill')
    append(fetch,kind='ram_fetch_end',cache_line=fresh)
    append(events[206],phase=31,context=227);append(events[-1],kind='cpu_end')
    expected['final_ram'][0x28:0x30]=list(bytes.fromhex('00000000aaee7722'))
    parents=copy.deepcopy(expected['cache_fills'][0]['source_bytes'])
    parents[8:12]=[dict(kind='sp_dma',write_ordinal=219,source_offset=n) for n in range(4)]
    parents[12:16]=[dict(kind='sp_dma',write_ordinal=220,source_offset=n) for n in range(4,8)]
    expected['cache_fills'].append(dict(fetch_context=223,burst_ordinal=224,fill_ordinal=225,
        physical_line=0x6020,cache_line=fresh,source_bytes=parents))
    oldparents=expected['cache_fills'][0]['source_bytes']
    expected['cached_fetches'].append(dict(fetch_context=210,end_ordinal=211,decoder_context=212,
        pc=0xffffffff80006034,physical=0x6034,word=CACHE,burst_ordinal=198,fill_ordinal=199,origins=oldparents[20:24]))
    expected['cached_fetches'].append(dict(fetch_context=223,end_ordinal=226,decoder_context=227,
        pc=0xffffffff80006028,physical=0x6028,word=0,burst_ordinal=224,fill_ordinal=225,origins=parents[8:12]))
    expected['cache_invalidations']=[dict(decoder_context=212,ordinal=213,physical=0x6028,
        operation=operation,hit=True,ended_fill=199)]
    return events,definitions,expected


def expected_events():
    events,definitions,_=build();return events,definitions


def replay(events,definitions):
    source,defs,expected=build();assert events==source and definitions==defs;return expected


def inspect(run):
    events,definitions,expected=build()
    assert run['events']==events,'complete invalidation/DMA/refill/decoder census'
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
        ('cache_fills','cache_fills'),('cached_fetches','cached_fetches'),('cache_invalidations','cache_invalidations')):
        assert graph[field]==expected[key],field
    assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
