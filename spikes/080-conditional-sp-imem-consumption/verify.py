"""Independent completed conditional SP writer and actual IMEM consumption graph."""
from pathlib import Path
import copy
import importlib.util
import json
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('context_model',ROOT/'spikes/079-tlbr-context-root-return/verify.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
FORMAT='plaid-rsp-cpu-imem-history-v22'
PROFILE='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-conditional-sp-imem-consumption-v22'
INITIAL,TLB_INITIAL,STAGED,RAM_START=prior.INITIAL,prior.TLB_INITIAL,prior.STAGED,prior.RAM_START
ROOT_PC,LW,SW,CACHE,ERET=prior.ROOT_PC,prior.LW,prior.SW,prior.CACHE,prior.ERET
ROOT_CONTEXT,TRANSFORM_CONTEXT=prior.ROOT_CONTEXT,prior.TRANSFORM_CONTEXT


def build():
    events,definitions,expected=prior.build()
    events,expected=json.loads(json.dumps(events)),json.loads(json.dumps(expected))
    for field in ('initial_ram','final_ram'):
        for i,word in enumerate((0xe2081000,0xc2080000,0xe2081000,0xc2080000,0xe2081000)):
            expected[field][0x60d0+4*i:0x60d4+4*i]=word.to_bytes(4,'big')
    template=copy.deepcopy(events[-1]);gpr=template['gpr'].copy();llbit=False;linked_address=0
    def append(kind,**fields):
        e=copy.deepcopy(template);e.update(kind=kind,ordinal=len(events)+1,context=0,word=0,value=0,gpr=[]);e.update(fields)
        events.append(e);return e
    def state(pc):
        return dict(control=dict(state=dict(pc=pc,bev=False,exl=False,erl=False,kernel_mode='bits32',kernel=True,cause=9,
            branch_delay=False,epc=0xe02c,delay_slot=False),interrupt_enable=False,llbit=llbit),linked_address=linked_address)
    append('cpu_reentry',context=507,phase=64,pc=0xffffffffa00060d0,gpr=gpr.copy())
    attempts=[];copies=[]
    # These are explicit known writer identities in the independent prefix.
    old_origin=dict(kind='cpu',context=49,pc=0xffffffffa0006004,word=0xae081000,write_ordinal=50)
    source_bytes=copy.deepcopy(next(w['copy_parent']['source_bytes'] for w in expected['cpu_writes'] if w['write_ordinal']==391))
    current_origin=old_origin;load_context=read_ordinal=None
    def consume(phase):
        context=len(events)+1
        rsp=copy.deepcopy(next(e for e in reversed(events) if e['kind']=='rsp_end'))
        rsp.update(kind='rsp_begin',ordinal=context,context=context,pc=0,phase=phase,word=0,next=0,halted=False)
        events.append(rsp);end=copy.deepcopy(rsp);end.update(kind='rsp_end',ordinal=context+1,next=4);events.append(end)
        expected['imem_fetches'].append(dict(context=context,pc=0,word=0,origins=[copy.deepcopy(current_origin) for _ in range(4)]))
    for index,phase in enumerate((64,66,67,69,70)):
        pc=0xffffffffa00060d0+4*index;word=0xc2080000 if index in (1,3) else 0xe2081000
        fetch=len(events)+1;access=dict(physical=pc&0x1fffffff,cached=False)
        append('ram_fetch_begin',context=fetch,phase=phase,pc=pc,cpu=True,address=access['physical'],fetch=access)
        append('ram_read',context=fetch,phase=phase,pc=pc,cpu=True,address=access['physical'],bytes=4,value=word)
        append('ram_fetch_end',context=fetch,phase=phase,pc=pc,cpu=True,address=access['physical'],fetch=access,value=word)
        decoder=len(events)+1
        append('cpu_begin',context=decoder,phase=phase,pc=pc,cpu=True,word=word,gpr=gpr.copy(),linked_state=state(pc))
        if index in (1,3):
            read=append('sp_read',context=decoder,phase=phase,pc=pc,cpu=True,word=word,address=0x04000000,bytes=4)
            load_context,read_ordinal=decoder,read['ordinal'];gpr[8]=0;llbit=True;linked_address=0x400000
        else:
            effect=None
            if llbit:
                write=append('sp_write',context=decoder,phase=phase,pc=pc,cpu=True,word=word,address=0x04001000,bank=1,bytes=4)
                effect=dict(effect_ordinal=write['ordinal'],context_id=decoder,pc=pc,source_register=8,source_value_before=0,
                    virtual_destination=0xffffffffa4001000,physical_destination=0x04001000,bank=1,offset=0,value=0)
                current_origin=dict(kind='cpu',context=decoder,pc=pc,word=word,write_ordinal=write['ordinal'])
                copies.append(dict(phase=phase,load_context=load_context,read_ordinal=read_ordinal,store_context=decoder,
                    write_ordinal=write['ordinal'],source_register=8,source=0x04000000,destination=0x04001000,word=0,source_bytes=copy.deepcopy(source_bytes)))
            attempts.append(dict(decoder_context=decoder,completed_effect=effect));gpr[8]=int(llbit)
        append('cpu_end',context=decoder,phase=phase,pc=pc,cpu=True,word=word,gpr=gpr.copy(),linked_state=state(pc))
        expected['fetches'].append(dict(fetch_context=fetch,read_ordinal=fetch+1,decoder_context=decoder,pc=pc,
            physical=access['physical'],word=word,origins=[dict(kind='unknown',cut_ordinal=None) for _ in range(4)]))
        if index in (0,2,4):consume(65 if index==0 else 68 if index==2 else 71)
    expected['conditional_sp_attempts']=attempts;expected['conditional_copies']=copies
    expected['conditional_final_writer']=current_origin
    assert [e['ordinal'] for e in events]==list(range(1,543))
    return events,definitions,expected


def expected_events():
    events,definitions,_=build();return events,definitions


def replay(events,definitions):
    source,defs,expected=build();assert events==source and definitions==defs;return expected


def inspect(run):
    events,definitions,expected=build()
    assert run['events']==events,'complete linked/conditional IMEM census'
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
    for field in ('rsp_definitions','imem_fetches','exception_roots','eret_returns','epc_reads','epc_writes','conditional_sp_attempts'):
        assert report[field]==(defs if field=='rsp_definitions' else expected[field]),field
    assert len(report['copies'])==5 and report['copies'][-2:]==expected['conditional_copies']
    assert report['final_imem_writers'][:4]==[expected['conditional_final_writer']]*4
    graph=report['dma_consumption']
    for field,key in (('writes','writers'),('fetches','fetches'),('promoted_requests','requests'),
        ('imem_installs','installs'),('dmem_installs','dmem_installs'),('pending_commits','pending_commits'),
        ('cache_fills','cache_fills'),('cached_fetches','cached_fetches'),('cache_invalidations','cache_invalidations'),
        ('cpu_writes','cpu_writes'),('tlb_generations','tlb_generations'),('context_writes','context_writes'),
        ('entry_lo_writes','entry_lo_writes'),('context_loads','context_loads')):
        assert graph[field]==expected[key],field
    assert [f['origins'][0]['write_ordinal'] for f in report['imem_fetches'][-3:]]==[50,525,539]
    assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
