"""Independent current RAM-writer -> CPU load -> IMEM executable graph."""
from pathlib import Path
import copy
import importlib.util
import json
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('subword_model',ROOT/'spikes/081-subword-transform-imem-consumption/verify.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
FORMAT='plaid-rsp-cpu-imem-history-v24'
PROFILE='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-ram-load-imem-consumption-v24'
INITIAL,TLB_INITIAL,STAGED,RAM_START=prior.INITIAL,prior.TLB_INITIAL,prior.STAGED,prior.RAM_START
ROOT_PC,LW,SW,CACHE,ERET=prior.ROOT_PC,prior.LW,prior.SW,prior.CACHE,prior.ERET
ROOT_CONTEXT,TRANSFORM_CONTEXT=prior.ROOT_CONTEXT,prior.TRANSFORM_CONTEXT


def build():
    events,definitions,expected=prior.build()
    events,expected=json.loads(json.dumps(events)),json.loads(json.dumps(expected))
    code=(0x8e680004,0x39080000,0xae081000,0xae680004,0x8e680004,0xae081000)
    for field in ('initial_ram','final_ram'):
        for i,word in enumerate(code):expected[field][0x6110+4*i:0x6114+4*i]=word.to_bytes(4,'big')
    expected['final_imem'][:4]=[0,0,0,0]
    template=copy.deepcopy(next(e for e in reversed(events) if e['kind']=='cpu_end'));gpr=template['gpr'].copy()
    state_template=template.pop('store_state')
    def append(kind,**fields):
        e=copy.deepcopy(template);e.update(kind=kind,ordinal=len(events)+1,context=0,word=0,value=0,gpr=[]);e.update(fields)
        events.append(e);return e
    def state(pc):
        s=copy.deepcopy(state_template);s['linked']['control']['state']['pc']=pc;return s
    append('cpu_reentry',context=571,phase=78,pc=0xffffffffa0006110,gpr=gpr.copy())
    copies=[];held=None;ram_writer=473
    def consume(phase,origin):
        context=len(events)+1;rsp=copy.deepcopy(next(e for e in reversed(events) if e['kind']=='rsp_end'))
        rsp.update(kind='rsp_begin',ordinal=context,context=context,pc=0,phase=phase,word=0,next=0,halted=False)
        events.append(rsp);end=copy.deepcopy(rsp);end.update(kind='rsp_end',ordinal=context+1,next=4);events.append(end)
        expected['imem_fetches'].append(dict(context=context,pc=0,word=0,origins=[copy.deepcopy(origin) for _ in range(4)]))
    for index,phase in enumerate((78,79,80,82,83,84)):
        word=code[index];pc=0xffffffffa0006110+4*index;fetch=len(events)+1;access=dict(physical=pc&0x1fffffff,cached=False)
        append('ram_fetch_begin',context=fetch,phase=phase,pc=pc,cpu=True,address=access['physical'],fetch=access)
        append('ram_read',context=fetch,phase=phase,pc=pc,cpu=True,address=access['physical'],bytes=4,value=word)
        append('ram_fetch_end',context=fetch,phase=phase,pc=pc,cpu=True,address=access['physical'],fetch=access,value=word)
        decoder=len(events)+1;begin=append('cpu_begin',context=decoder,phase=phase,pc=pc,cpu=True,word=word,gpr=gpr.copy())
        if index in (0,4):
            begin['ram_load_state']=state(pc)
            read=append('cpu_ram_read',context=decoder,phase=phase,pc=pc,cpu=True,word=word,address=0xe02c,bytes=4)
            gpr[8]=0
            held=dict(load_context=decoder,read_ordinal=read['ordinal'],source=0xe02c,
                source_bytes=[dict(kind='cpu_ram_load',decoder_context=decoder,read_ordinal=read['ordinal'],physical=0xe02c+n,
                    parent=dict(kind='cpu_copy',write_ordinal=ram_writer,source_offset=n)) for n in range(4)])
        elif index==1:
            held['transform']=dict(decoder_context=decoder,pc=pc,word=word,source_value=0,result_value=0)
        else:
            imem=index in (2,5)
            write=append('sp_write' if imem else 'cpu_ram_write',context=decoder,phase=phase,pc=pc,cpu=True,word=word,
                address=0x04001000 if imem else 0xe02c,bank=1 if imem else 0,bytes=4)
            if imem:
                origin=dict(kind='cpu',context=decoder,pc=pc,word=word,write_ordinal=write['ordinal'])
                copies.append(dict(phase=phase,store_context=decoder,write_ordinal=write['ordinal'],source_register=8,destination=0x04001000,word=0,**copy.deepcopy(held)))
            else:
                ram_writer=write['ordinal']
                expected['cpu_writes'].append(dict(decoder_context=decoder,write_ordinal=ram_writer,destination=0xe02c,source_register=8,
                    register_value=0,word=0,copy_parent=copy.deepcopy(held)))
        end=append('cpu_end',context=decoder,phase=phase,pc=pc,cpu=True,word=word,gpr=gpr.copy())
        if index in (0,4):end['ram_load_state']=state(pc)
        expected['fetches'].append(dict(fetch_context=fetch,read_ordinal=fetch+1,decoder_context=decoder,pc=pc,
            physical=access['physical'],word=word,origins=[dict(kind='unknown',cut_ordinal=None) for _ in range(4)]))
        if index in (2,5):consume(81 if index==2 else 85,origin)
    expected['ram_load_copies']=copies;expected['ram_load_final_writer']=origin
    assert [e['ordinal'] for e in events]==list(range(1,611))
    return events,definitions,expected


def expected_events():
    events,definitions,_=build();return events,definitions


def replay(events,definitions):
    source,defs,expected=build();assert events==source and definitions==defs;return expected


def inspect(run):
    events,definitions,expected=build()
    assert run['events']==events,'complete RAM-load/IMEM source census'
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
    projected=copy.deepcopy(report);_,_,old=prior.build()
    projected['copies']=projected['copies'][:7];projected['imem_fetches']=projected['imem_fetches'][:-2]
    projected['final_imem_writers'][:4]=[old['subword_final_writer']]*4
    projected['dma_consumption']['fetches']=projected['dma_consumption']['fetches'][:-6]
    projected['dma_consumption']['cpu_writes']=projected['dma_consumption']['cpu_writes'][:-1]
    prior.compare_report(projected,definitions)
    for field in ('imem_fetches','cpu_writes','fetches'):
        actual=report[field] if field=='imem_fetches' else report['dma_consumption'][field]
        assert actual==expected[field],field
    assert len(report['copies'])==9 and report['copies'][-2:]==expected['ram_load_copies']
    assert report['final_imem_writers'][:4]==[expected['ram_load_final_writer']]*4
    assert [c['source_bytes'][0]['parent']['write_ordinal'] for c in report['copies'][-2:]]==[473,595]
    assert [f['origins'][0]['write_ordinal'] for f in report['imem_fetches'][-2:]]==[587,607]
    assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
