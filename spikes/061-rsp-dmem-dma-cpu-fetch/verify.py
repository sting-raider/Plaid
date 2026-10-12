"""Independent complete RSP definition -> DMA -> CPU consumption census."""
from pathlib import Path
import copy
import hashlib
import importlib.util

ROOT=Path(__file__).resolve().parents[2]
FORMAT='plaid-rsp-cpu-imem-history-v4'
PROFILE='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-rsp-dmem-dma-cpu-consumption-v4'

def prior():
    spec=importlib.util.spec_from_file_location('imem_model',ROOT/'spikes/060-rsp-installed-imem-fetch/verify.py')
    model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)
    return model

def expected_events():
    original,definitions=prior().expected_events()
    result=[];mapping={}
    def fetch(begin):
        start=copy.deepcopy(begin)
        start.update(kind='ram_fetch_begin',word=0,context=0,ordinal=0,address=begin['pc']&0x1fffffff,
            gpr=[],value=0,fetch=dict(physical=begin['pc']&0x1fffffff,cached=False))
        read=copy.deepcopy(start);read.pop('fetch');read.update(kind='ram_read',bytes=4,value=begin['word'])
        end=copy.deepcopy(start);end.update(kind='ram_fetch_end',value=begin['word'])
        return [start,read,end]
    for event in original:
        if event['kind']=='cpu_begin':result.extend(fetch(event))
        copied=copy.deepcopy(event);copied['_old']=event['ordinal'];result.append(copied)
        if event['kind']=='rsp_end' and event['phase']==3:
            for lane,value in ((0,0),(4,0xaaee7722)):
                write=copy.deepcopy(event)
                write.update(kind='ram_write',ordinal=0,context=0,pc=0xffffffffa0006008,word=0,
                    address=0x6028+lane,offset=lane,bytes=4,value=value,next=0,rgpr=[],
                    dma=dict(pbus=0,dram=0x6028,length=0,count=0,skip=0))
                result.append(write)
    begin=copy.deepcopy(next(e for e in reversed(original) if e['kind']=='cpu_end'))
    begin.update(kind='cpu_begin',phase=17,pc=0xffffffffa0006028,word=0,ordinal=0,context=0)
    result.extend(fetch(begin));result.append(begin)
    end=copy.deepcopy(begin);end['kind']='cpu_end';result.append(end)
    active=0
    for ordinal,event in enumerate(result,1):
        if '_old' in event:mapping[event.pop('_old')]=ordinal
        event['ordinal']=ordinal
        if event['kind'] in ('cpu_begin','rsp_begin','ram_fetch_begin'):active=ordinal
        event['context']=active
        if event['kind'] in ('cpu_end','rsp_end','ram_fetch_end'):active=0
    def remap(value):
        if isinstance(value,dict):
            return {k:(mapping[v] if k in ('context','read_ordinal','write_ordinal','source_definition') else remap(v)) for k,v in value.items()}
        if isinstance(value,list):return [remap(v) for v in value]
        return value
    return result,remap(definitions)

def replay(events,definitions):
    initial_ram=b''.join(e['word'].to_bytes(4,'big') for e in events if e['kind']=='cpu_begin')+bytes(4)
    ram=bytearray(initial_ram);ram_origins=[dict(kind='unknown',cut_ordinal=None) for _ in ram]
    dmem=bytearray(bytes.fromhex('340800aaaaee7722')+bytes(4088))
    dorig=[dict(kind='unknown',cut_ordinal=None) for _ in dmem]
    writers=[];fetches=[];pending=None
    for event in events:
        kind=event['kind']
        if kind in ('rsp_sink','foreign_sink') or (kind=='sp_write' and event['bank']==0):
            data=event['value'].to_bytes(event['bytes'],'big')
            origin=dict(kind='unknown',cut_ordinal=event['ordinal'])
            if kind=='rsp_sink':
                origin=dict(kind='rsp',context=event['context'],pc=event['pc'],word=event['word'],write_ordinal=event['ordinal'])
                before=[d for d in definitions if d['phase']==event['phase'] and d['context']<event['context'] and d['register']==2]
                if before:origin['source_definition']=before[-1]['context']
            elif kind=='sp_write' and event['context']:
                origin=dict(kind='cpu',context=event['context'],pc=event['pc'],word=event['word'],write_ordinal=event['ordinal'])
            for n,value in enumerate(data):
                offset=(event['offset']+n)&4095;dmem[offset]=value;dorig[offset]=copy.deepcopy(origin)
        if kind=='ram_write':
            source=event['offset'];address=event['address']-0x6000
            assert dmem[source:source+4]==event['value'].to_bytes(4,'big')
            writers.append(dict(write_ordinal=event['ordinal'],destination=event['address'],descriptor=event['dma'],
                source_offset=source,word=event['value'],source_bytes=copy.deepcopy(dorig[source:source+4])))
            ram[address:address+4]=event['value'].to_bytes(4,'big')
            for n in range(4):ram_origins[address+n]=dict(kind='sp_dma',write_ordinal=event['ordinal'],source_offset=source+n)
        if kind=='ram_read':
            address=event['address']-0x6000
            assert ram[address:address+4]==event['value'].to_bytes(4,'big')
            pending=dict(fetch_context=event['context'],read_ordinal=event['ordinal'],decoder_context=0,
                pc=event['pc'],physical=event['address'],word=event['value'],origins=copy.deepcopy(ram_origins[address:address+4]))
        if kind=='cpu_begin':
            assert pending and pending['word']==event['word'] and pending['pc']==event['pc']
            pending['decoder_context']=event['context'];fetches.append(pending);pending=None
    initial_imem,final_imem,imem_fetches=prior().replay_image(events)
    return dict(initial_ram=list(initial_ram),final_ram=list(ram),final_dmem=list(dmem),
        initial_imem=initial_imem,final_imem=final_imem,imem_fetches=imem_fetches,writers=writers,fetches=fetches)

def inspect(run):
    events,definitions=expected_events();expected=replay(events,definitions)
    assert run['events']==events,'complete independent DMA/read/fetch/decoder census'
    for field in ('initial_ram','final_ram','final_dmem','initial_imem','final_imem'):assert run[field]==expected[field],field
    assert run['initial_dmem']==list(bytes.fromhex('340800aaaaee7722')+bytes(4088))
    starts=[e for e in events if e['kind']=='cpu_begin'];ends=[e for e in events if e['kind']=='cpu_end']
    steps=[dict(phase=a['phase'],index=i,word=a['word'],pc=a['pc'],before=a['gpr'],after=b['gpr']) for i,(a,b) in enumerate(zip(starts,ends))]
    assert run['steps']==steps
    source={key:run[key] for key in ('initial_dmem','initial_imem','final_dmem','final_imem','steps','events')}
    source.update(format=FORMAT,profile=PROFILE,ram=dict(start=0x6000,initial=run['initial_ram'],final_bytes=run['final_ram']))
    return source,definitions

def compare_report(report,definitions):
    events,_=expected_events();expected=replay(events,definitions)
    assert report['rsp_definitions']==definitions and report['imem_fetches']==expected['imem_fetches']
    composed=report['dma_consumption']
    assert composed['ram_start']==0x6000 and composed['ram_bytes']==48
    assert composed['writes']==expected['writers'] and composed['fetches']==expected['fetches']
    assert composed['initial_ram_sha256']==hashlib.sha256(bytes(expected['initial_ram'])).hexdigest()
    assert composed['final_ram_sha256']==hashlib.sha256(bytes(expected['final_ram'])).hexdigest()
    fetched=composed['fetches'][-1];writer=composed['writes'][0]
    assert fetched['word']==0 and all(o['write_ordinal']==writer['write_ordinal'] for o in fetched['origins'])
    assert all(o['source_definition']==definitions[-1]['context'] for o in writer['source_bytes'])
    assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
