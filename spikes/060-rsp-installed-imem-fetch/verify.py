"""Independent controlled instruction-consumption and writer census."""
from pathlib import Path
import copy
import importlib.util

ROOT=Path(__file__).resolve().parents[2]
FORMAT='plaid-rsp-cpu-imem-history-v3'
PROFILE='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-rsp-cpu-imem-controlled-consumption-v3'


def expected_events():
    spec=importlib.util.spec_from_file_location('read_census',ROOT/'spikes/059-rsp-word-read-imem/verify.py')
    prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
    original,definitions=prior.expected_events()
    def zero(value):
        if isinstance(value,dict):return {k:zero(v) for k,v in value.items()}
        if isinstance(value,list):
            if value==[0,0,0x33,0x44]:return [0,0,0,0]
            return [zero(v) for v in value]
        if value==0x3344:return 0
        if value==0x34023344:return 0x34020000
        return value
    original=zero(original);definitions=zero(definitions)
    for e in original:
        if e['kind']=='rsp_sink' and e['phase'] in (1,4):e['value']=0
    seeds={1:[0x3400ffff,0x34020000,0x34020000,0x00401821,0x00601021,0xac220000,0x8c240000,0x00801021,0xac220000,13],
        4:[0xac220000,13],9:[(58<<26)|(1<<21)|(2<<16),13],10:[0xa0220000,13]}
    seed_pc={1:0xffffffffbfc00000,4:0xffffffffa0006008,9:0xffffffffa0006014,10:0xffffffffa0006014}
    result=[];seen=set();mapping={};last_rsp=None
    for event in original:
        if event['kind']=='rsp_begin' and event['phase'] not in seen:
            phase=event['phase'];seen.add(phase)
            for n,word in enumerate(seeds[phase]):
                seed=copy.deepcopy(event)
                seed.update(kind='opaque_imem_seed',ordinal=0,context=0,pc=seed_pc[phase],word=0,
                    address=0x100+n*4,bank=1,offset=0x100+n*4,bytes=4,value=word,
                    next=0,halted=False,vector_byte=0,gpr=[],rgpr=[])
                result.append(seed)
        if event['kind']=='rsp_end':last_rsp=copy.deepcopy(event)
        copied=copy.deepcopy(event)
        copied['_old_ordinal']=event['ordinal']
        result.append(copied)
        if event['kind']=='cpu_end' and event['phase']==3:
            begin=copy.deepcopy(last_rsp)
            begin.update(kind='rsp_begin',ordinal=0,context=0,pc=0,phase=3,word=0,next=0,halted=False)
            end=copy.deepcopy(begin);end.update(kind='rsp_end',next=4)
            result.extend((begin,end))
    active=0
    for ordinal,event in enumerate(result,1):
        if '_old_ordinal' in event:mapping[event.pop('_old_ordinal')]=ordinal
        event['ordinal']=ordinal
        if event['kind'] in ('rsp_begin','cpu_begin'):active=ordinal
        event['context']=active
        if event['kind'] in ('rsp_end','cpu_end'):active=0
    def remap(value):
        if isinstance(value,dict):
            return {k:(mapping[v] if k in ('context','read_ordinal','write_ordinal','source_definition') else remap(v)) for k,v in value.items()}
        if isinstance(value,list):return [remap(v) for v in value]
        return value
    return result,remap(definitions)


def replay_image(events):
    image=bytearray(bytes.fromhex('deadbeef')*5+bytes(4096-20))
    origins=[dict(kind='unknown',cut_ordinal=None) for _ in range(4096)]
    initial=list(image);fetched=[]
    for e in events:
        if e['kind']=='opaque_imem_seed' or (e['kind']=='sp_write' and e['bank']==1):
            address=e['offset'];data=e['value'].to_bytes(4,'big')
            origin=dict(kind='unknown',cut_ordinal=e['ordinal'])
            if e['kind']=='sp_write' and e['context']:
                origin=dict(kind='cpu',context=e['context'],pc=e['pc'],word=e['word'],write_ordinal=e['ordinal'])
            image[address:address+4]=data
            origins[address:address+4]=[copy.deepcopy(origin) for _ in range(4)]
        if e['kind']=='rsp_begin':
            pc=e['pc'];assert int.from_bytes(image[pc:pc+4],'big')==e['word']
            fetched.append(dict(context=e['context'],pc=pc,word=e['word'],origins=copy.deepcopy(origins[pc:pc+4])))
    return initial,list(image),fetched


def inspect(run):
    events,definitions=expected_events()
    assert run['events']==events,'complete independent seed/write/fetch census'
    starts=[e for e in events if e['kind']=='cpu_begin'];ends=[e for e in events if e['kind']=='cpu_end']
    steps=[dict(phase=a['phase'],index=i,word=a['word'],pc=a['pc'],before=a['gpr'],after=b['gpr']) for i,(a,b) in enumerate(zip(starts,ends))]
    assert run['steps']==steps
    initial,final,fetched=replay_image(events)
    assert run['initial_imem']==initial and run['final_imem']==final
    assert run['initial_dmem']==list(bytes.fromhex('340800aaaaee7722'))
    assert run['final_dmem']==list(bytes.fromhex('aaee7722aaee7722'))
    source={key:run[key] for key in ('initial_dmem','initial_imem','final_dmem','final_imem','steps','events')}
    source.update(format=FORMAT,profile=PROFILE)
    return source,definitions


def compare_report(report,definitions):
    events,_=expected_events();_,_,fetched=replay_image(events)
    assert report['rsp_definitions']==definitions and report['imem_fetches']==fetched
    assert len(report['copies'])==3
    installed=[f for f in fetched if all(o['kind']=='cpu' for o in f['origins'])]
    assert len(installed)==1 and installed[0]['pc']==0 and installed[0]['word']==0
    first,second=report['copies'][:2]
    assert first['word']==second['word']==0
    assert all(o['write_ordinal']==first['write_ordinal'] and o['context']==first['store_context']
        for o in installed[0]['origins'])
    assert all(o['source_definition']==definitions[-1]['context'] for o in first['source_bytes'])
    assert all('source_definition' not in o for o in second['source_bytes'])
    assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
