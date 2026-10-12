"""Independent complete RAM-to-IMEM installation and decoded consumption graph."""
from pathlib import Path
import copy
import importlib.util
ROOT=Path(__file__).resolve().parents[2]
FORMAT='plaid-rsp-cpu-imem-history-v6'
PROFILE='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-rsp-dmem-ram-imem-dma-consumption-v6'

def prior():
    spec=importlib.util.spec_from_file_location('promoted_model',ROOT/'spikes/062-promoted-dma-cpu-consumption/verify.py')
    model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)
    return model

def expected_events():
    events,definitions=prior().expected_events()
    promote=copy.deepcopy(next(e for e in events if e['kind']=='dma_promote'))
    promote.update(ordinal=137,context=137,phase=18,pc=0xffffffffa000602c,bank=1,offset=0x300,
        dma=dict(pbus=0x300,dram=0x6028,length=0,count=0,skip=0))
    read=copy.deepcopy(promote);read.update(kind='imem_dma_read',ordinal=138,bytes=8,value=0xaaee7722)
    write=copy.deepcopy(read);write.update(kind='imem_dma_write',ordinal=139)
    complete=copy.deepcopy(promote);complete.pop('dma')
    complete.update(kind='dma_complete',ordinal=140,address=0x6030,offset=0x308)
    begin=copy.deepcopy(next(e for e in reversed(events) if e['kind']=='rsp_end'))
    begin.update(kind='rsp_begin',ordinal=141,context=141,phase=19,pc=0x300,word=0,next=0x300,halted=False)
    end=copy.deepcopy(begin);end.update(kind='rsp_end',ordinal=142,next=0x304)
    return events+[promote,read,write,complete,begin,end],definitions

def replay(events,definitions):
    base=prior();expected=base.replay(events[:136],definitions)
    parents=[dict(kind='sp_dma',write_ordinal=55+n//4,source_offset=n) for n in range(8)]
    promote,read,write,complete,begin,end=events[136:]
    assert expected['final_ram'][40:48]==list(write['value'].to_bytes(8,'big'))
    expected['final_imem'][0x300:0x308]=list(write['value'].to_bytes(8,'big'))
    origins=[dict(kind='imem_dma',promote_context=137,read_ordinal=138,write_ordinal=139,
        source=0x6028+n,parent=parents[n]) for n in range(8)]
    assert int.from_bytes(bytes(expected['final_imem'][begin['pc']:begin['pc']+4]),'big')==begin['word']
    expected['imem_fetches'].append(dict(context=141,pc=0x300,word=0,origins=origins[:4]))
    for request in expected['requests']:request['direction']='dmem_egress'
    expected['requests'].append(dict(promote_context=137,complete_ordinal=140,descriptor=promote['dma'],write_ordinals=[139],direction='imem_ingress'))
    expected['installs']=[dict(promote_context=137,read_ordinal=138,write_ordinal=139,
        descriptor=promote['dma'],value=write['value'],source_bytes=parents)]
    return expected

def inspect(run):
    events,definitions=expected_events();expected=replay(events,definitions)
    assert run['events']==events,'complete independent ingress/read/sink/fetch census'
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
    assert len(report['imem_fetches'])==18 and len(graph['promoted_requests'])==2
    assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
