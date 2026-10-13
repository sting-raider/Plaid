"""Independent D-cache export -> old-vs-refilled mapped CPU execution."""
from pathlib import Path
import copy
import importlib.util
import json
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('writeback_model',ROOT/'spikes/084-cached-word-writeback-imem-consumption/verify.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
FORMAT,PROFILE=prior.FORMAT,prior.PROFILE
INITIAL,TLB_INITIAL,STAGED,RAM_START=prior.INITIAL,prior.TLB_INITIAL,prior.STAGED,prior.RAM_START
ROOT_PC,LW,SW,CACHE,ERET=prior.ROOT_PC,prior.LW,prior.SW,prior.CACHE,prior.ERET
ROOT_CONTEXT,TRANSFORM_CONTEXT=prior.ROOT_CONTEXT,prior.TRANSFORM_CONTEXT


def build():
    events,definitions,expected=prior.build();events,expected=json.loads(json.dumps(events)),json.loads(json.dumps(expected))
    for field in ('initial_ram','final_ram'):expected[field][0x61b0:0x61b4]=(0xbe500004).to_bytes(4,'big')
    template=copy.deepcopy(next(e for e in reversed(events) if e['kind']=='cpu_end'));gpr=template['gpr'].copy()
    cache_line=copy.deepcopy(expected['cache_fills'][-1]['cache_line'])
    mapping=copy.deepcopy(next(e['mapping'] for e in reversed(events) if e['kind']=='ram_fetch_end' and 'mapping' in e))
    witness=copy.deepcopy(expected['cached_fetches'][-1]['mapping'])
    def append(kind,**fields):
        e=copy.deepcopy(template);e.update(kind=kind,ordinal=len(events)+1,context=0,word=0,value=0,gpr=[]);e.update(fields);events.append(e);return e
    for phase in (108,109,110):
        pc=0xffffffffa00061b0 if phase==109 else 0xe02c;word=0xbe500004 if phase==109 else 0
        root=len(events)+1;append('cpu_reentry',context=root,phase=phase,pc=pc,gpr=gpr.copy())
        fetch=len(events)+1;access=dict(physical=pc&0x1fffffff,cached=phase!=109)
        begin=append('ram_fetch_begin',context=fetch,phase=phase,pc=pc,cpu=True,address=access['physical'],fetch=access)
        if phase!=109:begin['mapping']=copy.deepcopy(mapping)
        if phase==109:
            append('ram_read',context=fetch,phase=phase,pc=pc,cpu=True,address=access['physical'],bytes=4,value=word)
        if phase==110:
            line=copy.deepcopy(cache_line);line['tag_key']|=1
            burst=append('cache_burst_read',context=fetch,phase=phase,pc=pc,cpu=True,address=0xe020,bytes=32,cache_line=line)
            fill=append('cache_fill',context=fetch,phase=phase,pc=pc,cpu=True,address=0xe020,bytes=32,cache_line=line)
            parents=[dict(kind='dcache_writeback',write_ordinal=699,source_offset=n) for n in range(16)]
            parents += [dict(kind='unknown',cut_ordinal=None) for _ in range(16)]
            expected['cache_fills'].append(dict(fetch_context=fetch,burst_ordinal=burst['ordinal'],fill_ordinal=fill['ordinal'],physical_line=0xe020,cache_line=line,source_bytes=parents))
        end=append('ram_fetch_end',context=fetch,phase=phase,pc=pc,cpu=True,address=access['physical'],fetch=access,value=word)
        if phase!=109:end.update(cache_line=copy.deepcopy(cache_line),mapping=copy.deepcopy(mapping))
        decoder=len(events)+1;append('cpu_begin',context=decoder,phase=phase,pc=pc,cpu=True,word=word,gpr=gpr.copy())
        if phase==109:
            before=copy.deepcopy(cache_line);after=copy.deepcopy(before);after['tag_key']&=~1
            operation=append('cache_operation',context=decoder,phase=phase,pc=pc,cpu=True,word=word,address=0xe02c,
                cache_operation=dict(virtual_address=0xffffffff8000e02c,operation=16,before=before,after=after))
            expected['cache_invalidations'].append(dict(decoder_context=decoder,ordinal=operation['ordinal'],physical=0xe02c,
                operation=operation['cache_operation'],hit=True,ended_fill=503))
            expected['fetches'].append(dict(fetch_context=fetch,read_ordinal=fetch+1,decoder_context=decoder,pc=pc,physical=access['physical'],word=word,
                origins=[dict(kind='unknown',cut_ordinal=None) for _ in range(4)]))
        else:
            parents=[dict(kind='cpu_copy',write_ordinal=473,source_offset=n) for n in range(4)] if phase==108 else [dict(kind='dcache_writeback',write_ordinal=699,source_offset=12+n) for n in range(4)]
            expected['cached_fetches'].append(dict(mapping=copy.deepcopy(witness),fetch_context=fetch,end_ordinal=end['ordinal'],decoder_context=decoder,
                pc=pc,physical=0xe02c,word=0,burst_ordinal=502 if phase==108 else 744,fill_ordinal=503 if phase==108 else 745,origins=parents))
        append('cpu_end',context=decoder,phase=phase,pc=pc,cpu=True,word=word,gpr=gpr.copy())
    assert [e['ordinal'] for e in events]==list(range(1,749))
    return events,definitions,expected


def expected_events():
    events,definitions,_=build();return events,definitions


def replay(events,definitions):
    source,defs,expected=build();assert events==source and definitions==defs;return expected


def inspect(run):
    events,definitions,expected=build();assert run['events']==events,'complete writeback/mapped CPU source census'
    assert run['initial_pending']==INITIAL and run['initial_tlb']==TLB_INITIAL
    for field in ('initial_ram','final_ram','final_dmem','initial_imem','final_imem'):assert run[field]==expected[field],field
    assert run['initial_dmem']==list(bytes.fromhex('340800aaaaee7722')+bytes(4088))
    starts=[e for e in events if e['kind']=='cpu_begin'];ends=[e for e in events if e['kind']=='cpu_end']
    assert run['steps']==[dict(phase=a['phase'],index=i,word=a['word'],pc=a['pc'],before=a['gpr'],after=b['gpr']) for i,(a,b) in enumerate(zip(starts,ends))]
    source={key:run[key] for key in ('initial_dmem','initial_imem','final_dmem','final_imem','steps','events','initial_pending','initial_tlb')}
    source.update(format=FORMAT,profile=PROFILE,ram=dict(start=RAM_START,initial=run['initial_ram'],final_bytes=run['final_ram']))
    return source,definitions


def compare_report(report,definitions):
    _,defs,expected=build();assert definitions==defs
    projected=copy.deepcopy(report);graph=projected['dma_consumption']
    graph['fetches']=graph['fetches'][:-1];graph['cached_fetches']=graph['cached_fetches'][:-2]
    graph['cache_fills']=graph['cache_fills'][:-1];graph['cache_invalidations']=graph['cache_invalidations'][:-1]
    prior.compare_report(projected,definitions)
    graph=report['dma_consumption']
    for field in ('fetches','cached_fetches','cache_fills','cache_invalidations'):assert graph[field]==expected[field],field
    assert [f['fill_ordinal'] for f in graph['cached_fetches'][-2:]]==[503,745]
    assert graph['cached_fetches'][-2]['origins'][0]['write_ordinal']==473 and graph['cached_fetches'][-1]['origins'][0]['write_ordinal']==699
    assert graph['cached_fetches'][-1]['mapping']==graph['cached_fetches'][-2]['mapping']
    assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
