"""Complete promoted descriptor progression on the original consumption clock."""
from pathlib import Path
import copy
import importlib.util
ROOT=Path(__file__).resolve().parents[2]
FORMAT='plaid-rsp-cpu-imem-history-v5'
PROFILE='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-promoted-dmem-dma-cpu-consumption-v5'

def prior():
    spec=importlib.util.spec_from_file_location('dma_model',ROOT/'spikes/061-rsp-dmem-dma-cpu-fetch/verify.py')
    model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)
    return model

def expected_events():
    original,definitions=prior().expected_events()
    result=[];mapping={}
    for event in original:
        if event['kind']=='ram_write' and event['offset']==0:
            promote=copy.deepcopy(event)
            promote.update(kind='dma_promote',ordinal=0,context=0,bytes=0,value=0)
            result.append(promote)
        copied=copy.deepcopy(event);copied['_old']=event['ordinal'];result.append(copied)
        if event['kind']=='ram_write' and event['offset']==4:
            complete=copy.deepcopy(event);complete.pop('dma')
            complete.update(kind='dma_complete',ordinal=0,context=0,address=0x6030,offset=8,bytes=0,value=0)
            result.append(complete)
    active=request=0
    for ordinal,event in enumerate(result,1):
        if '_old' in event:mapping[event.pop('_old')]=ordinal
        event['ordinal']=ordinal
        if event['kind']=='dma_promote':request=ordinal
        if event['kind'] in ('cpu_begin','rsp_begin','ram_fetch_begin'):active=ordinal
        event['context']=request if event['kind'] in ('dma_promote','ram_write','dma_complete') else active
        if event['kind'] in ('cpu_end','rsp_end','ram_fetch_end'):active=0
        if event['kind']=='dma_complete':request=0
    def remap(value):
        if isinstance(value,dict):return {k:(mapping[v] if k in ('context','read_ordinal','write_ordinal','source_definition') else remap(v)) for k,v in value.items()}
        if isinstance(value,list):return [remap(v) for v in value]
        return value
    return result,remap(definitions)

def replay(events,definitions):
    expected=prior().replay(events,definitions)
    promote=next(e for e in events if e['kind']=='dma_promote')
    complete=next(e for e in events if e['kind']=='dma_complete')
    for writer in expected['writers']:writer['promote_context']=promote['ordinal']
    expected['requests']=[dict(promote_context=promote['ordinal'],complete_ordinal=complete['ordinal'],
        descriptor=promote['dma'],write_ordinals=[w['write_ordinal'] for w in expected['writers']])]
    assert len(expected['writers'])==((promote['dma']['length']+8)//8)*(promote['dma']['count']+1)*2
    return expected

def inspect(run):
    events,definitions=expected_events();expected=replay(events,definitions)
    assert run['events']==events,'complete independent promotion/effect/completion census'
    for field in ('initial_ram','final_ram','final_dmem','initial_imem','final_imem'):assert run[field]==expected[field],field
    assert run['initial_dmem']==list(bytes.fromhex('340800aaaaee7722')+bytes(4088))
    starts=[e for e in events if e['kind']=='cpu_begin'];ends=[e for e in events if e['kind']=='cpu_end']
    assert run['steps']==[dict(phase=a['phase'],index=i,word=a['word'],pc=a['pc'],before=a['gpr'],after=b['gpr']) for i,(a,b) in enumerate(zip(starts,ends))]
    source={key:run[key] for key in ('initial_dmem','initial_imem','final_dmem','final_imem','steps','events')}
    source.update(format=FORMAT,profile=PROFILE,ram=dict(start=0x6000,initial=run['initial_ram'],final_bytes=run['final_ram']))
    return source,definitions

def compare_report(report,definitions):
    events,_=expected_events();expected=replay(events,definitions)
    assert report['rsp_definitions']==definitions and report['imem_fetches']==expected['imem_fetches']
    graph=report['dma_consumption']
    assert graph['writes']==expected['writers'] and graph['fetches']==expected['fetches']
    assert graph['promoted_requests']==expected['requests']
    assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
