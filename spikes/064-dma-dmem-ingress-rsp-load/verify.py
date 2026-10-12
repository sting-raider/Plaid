"""Independent two-read/two-write DMEM ingress and actual RSP load census."""
from pathlib import Path
import copy
import importlib.util
ROOT=Path(__file__).resolve().parents[2]
FORMAT='plaid-rsp-cpu-imem-history-v7'
PROFILE='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-rsp-dmem-ram-dmem-imem-consumption-v7'

def prior():
    spec=importlib.util.spec_from_file_location('roundtrip_model',ROOT/'spikes/063-dma-ram-imem-roundtrip/verify.py')
    model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)
    return model

def dmem_origins():
    return [dict(kind='dmem_dma',promote_context=143,read_ordinal=144,write_ordinal=146,
        source=0x6028+n,parent=dict(kind='sp_dma',write_ordinal=55,source_offset=n)) for n in range(4)]

def expected_events():
    events,definitions=prior().expected_events()
    for event in events:
        if event['kind'] in ('dma_promote','dma_complete'):event['dma_direction']='imem_ingress' if event['bank'] else 'dmem_egress'
    promote=copy.deepcopy(events[136]);promote.update(ordinal=143,context=143,phase=20,bank=0,offset=0,
        dma=dict(pbus=0,dram=0x6028,length=0,count=0,skip=0),dma_direction='dmem_ingress')
    data=[]
    for kind,first in (('dmem_dma_read',144),('dmem_dma_write',146)):
        for lane,value in ((0,0),(4,0xaaee7722)):
            event=copy.deepcopy(promote);event.pop('dma_direction')
            event.update(kind=kind,ordinal=first+lane//4,address=0x6028+lane,offset=lane,bytes=4,value=value)
            data.append(event)
    complete=copy.deepcopy(promote);complete.pop('dma')
    complete.update(kind='dma_complete',ordinal=148,address=0x6030,offset=8)
    seed=copy.deepcopy(events[0]);seed.update(ordinal=149,phase=21,pc=0xffffffffa000602c,address=0x320,offset=0x320,value=0x8c040000)
    begin=copy.deepcopy(events[-2]);begin.update(ordinal=150,context=150,phase=21,pc=0x320,next=0x320,word=0x8c040000)
    read=copy.deepcopy(data[0]);read.pop('dma');read.update(kind='rsp_read',ordinal=151,context=150,phase=21,pc=0x320,word=0x8c040000,address=0,offset=0)
    end=copy.deepcopy(begin);end.update(kind='rsp_end',ordinal=152,next=0x324)
    definitions.append(dict(context=150,phase=21,pc=0x320,word=0x8c040000,register=4,value=0,
        expression=dict(kind='dmem_word_load',read_ordinal=151,address=0,offset=0,payload=[0]*4,origins=dmem_origins())))
    return events+[promote]+data+[complete,seed,begin,read,end],definitions

def replay(events,definitions):
    base=prior();expected=base.replay(events[:142],definitions[:6])
    expected['final_dmem'][:4]=[0]*4
    expected['final_imem'][0x320:0x324]=list((0x8c040000).to_bytes(4,'big'))
    expected['imem_fetches'].append(dict(context=150,pc=0x320,word=0x8c040000,
        origins=[dict(kind='unknown',cut_ordinal=149) for _ in range(4)]))
    expected['requests'].append(dict(promote_context=143,complete_ordinal=148,descriptor=events[142]['dma'],write_ordinals=[146,147],direction='dmem_ingress'))
    expected['dmem_installs']=[]
    for lane in (0,4):
        expected['dmem_installs'].append(dict(promote_context=143,read_ordinal=144+lane//4,write_ordinal=146+lane//4,
            descriptor=events[142]['dma'],source=0x6028+lane,offset=lane,value=0 if not lane else 0xaaee7722,
            source_bytes=[dict(kind='sp_dma',write_ordinal=55+lane//4,source_offset=lane+n) for n in range(4)]))
    return expected

def inspect(run):
    events,definitions=expected_events();expected=replay(events,definitions)
    assert run['events']==events,'complete independent read-low/read-high/write-low/write-high and RSP load census'
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
    assert graph['promoted_requests']==expected['requests'] and graph['imem_installs']==expected['installs']
    assert graph['dmem_installs']==expected['dmem_installs']
    assert len(report['imem_fetches'])==19 and len(graph['promoted_requests'])==3
    assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
