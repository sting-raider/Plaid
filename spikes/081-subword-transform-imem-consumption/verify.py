"""Independent actual subword-to-Word sink and transformed IMEM consumption."""
from pathlib import Path
import copy
import importlib.util
import json
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('conditional_model',ROOT/'spikes/080-conditional-sp-imem-consumption/verify.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
FORMAT='plaid-rsp-cpu-imem-history-v23'
PROFILE='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-subword-transform-imem-consumption-v23'
INITIAL,TLB_INITIAL,STAGED,RAM_START=prior.INITIAL,prior.TLB_INITIAL,prior.STAGED,prior.RAM_START
ROOT_PC,LW,SW,CACHE,ERET=prior.ROOT_PC,prior.LW,prior.SW,prior.CACHE,prior.ERET
ROOT_CONTEXT,TRANSFORM_CONTEXT=prior.ROOT_CONTEXT,prior.TRANSFORM_CONTEXT


def build():
    events,definitions,expected=prior.build()
    events,expected=json.loads(json.dumps(events)),json.loads(json.dumps(expected))
    for field in ('initial_ram','final_ram'):
        for i,word in enumerate((0x8e080000,0x39080021,0xa2081003,0xa6081002)):
            expected[field][0x60f0+4*i:0x60f4+4*i]=word.to_bytes(4,'big')
    expected['final_imem'][:4]=[0,0,0,0x21]
    template=copy.deepcopy(next(e for e in reversed(events) if e['kind']=='cpu_end'));gpr=template['gpr'].copy()
    template.pop('linked_state')
    def append(kind,**fields):
        e=copy.deepcopy(template);e.update(kind=kind,ordinal=len(events)+1,context=0,word=0,value=0,gpr=[]);e.update(fields)
        events.append(e);return e
    def state(pc):
        return dict(linked=dict(control=dict(state=dict(pc=pc,bev=False,exl=False,erl=False,kernel_mode='bits32',kernel=True,cause=9,
            branch_delay=False,epc=0xe02c,delay_slot=False),interrupt_enable=False,llbit=True),linked_address=0x400000),reverse_endian=False)
    append('cpu_reentry',context=543,phase=72,pc=0xffffffffa00060f0,gpr=gpr.copy())
    witnesses=[];copies=[]
    source_bytes=copy.deepcopy(expected['conditional_copies'][0]['source_bytes'])
    def consume(phase,origin):
        context=len(events)+1;rsp=copy.deepcopy(next(e for e in reversed(events) if e['kind']=='rsp_end'))
        rsp.update(kind='rsp_begin',ordinal=context,context=context,pc=0,phase=phase,word=0x21,next=0,halted=False)
        events.append(rsp);end=copy.deepcopy(rsp);end.update(kind='rsp_end',ordinal=context+1,next=4);events.append(end)
        expected['imem_fetches'].append(dict(context=context,pc=0,word=0x21,origins=[copy.deepcopy(origin) for _ in range(4)]))
    for index,phase,word in ((0,72,0x8e080000),(1,73,0x39080021),(2,74,0xa2081003),(3,76,0xa6081002)):
        pc=0xffffffffa00060f0+4*index;fetch=len(events)+1;access=dict(physical=pc&0x1fffffff,cached=False)
        append('ram_fetch_begin',context=fetch,phase=phase,pc=pc,cpu=True,address=access['physical'],fetch=access)
        append('ram_read',context=fetch,phase=phase,pc=pc,cpu=True,address=access['physical'],bytes=4,value=word)
        append('ram_fetch_end',context=fetch,phase=phase,pc=pc,cpu=True,address=access['physical'],fetch=access,value=word)
        decoder=len(events)+1;begin=append('cpu_begin',context=decoder,phase=phase,pc=pc,cpu=True,word=word,gpr=gpr.copy())
        if index==0:
            append('sp_read',context=decoder,phase=phase,pc=pc,cpu=True,word=word,address=0x04000000,bytes=4);gpr[8]=0
        elif index==1:gpr[8]=0x21
        else:
            begin['store_state']=state(pc);device=0x04001003 if index==2 else 0x04001002
            write=append('sp_write',context=decoder,phase=phase,pc=pc,cpu=True,word=word,address=0x04001000,bank=1,bytes=4,value=0x21,sp_device_address=device)
            witness=dict(context_ordinal=decoder,effect_ordinal=write['ordinal'],pc=pc,kind='sb' if index==2 else 'sh',base_register=16,source_register=8,
                virtual_destination=0xffffffffa0000000+device,translated_physical=device,device_physical=device,
                sink_word_address=0x04001000,bank='imem',offset=0,source_u32=0x21,value=0x21)
            witnesses.append(witness)
            origin=dict(kind='cpu',context=decoder,pc=pc,word=word,write_ordinal=write['ordinal'])
            copies.append(dict(phase=phase,load_context=547,read_ordinal=548,store_context=decoder,write_ordinal=write['ordinal'],
                source_register=8,source=0x04000000,destination=0x04001000,word=0x21,source_bytes=copy.deepcopy(source_bytes),
                transform=dict(decoder_context=553,pc=0xffffffffa00060f4,word=0x39080021,source_value=0,result_value=0x21)))
        end=append('cpu_end',context=decoder,phase=phase,pc=pc,cpu=True,word=word,gpr=gpr.copy())
        if index>=2:end['store_state']=state(pc)
        expected['fetches'].append(dict(fetch_context=fetch,read_ordinal=fetch+1,decoder_context=decoder,pc=pc,
            physical=access['physical'],word=word,origins=[dict(kind='unknown',cut_ordinal=None) for _ in range(4)]))
        if index>=2:consume(75 if index==2 else 77,origin)
    expected['subword_sp_writes']=witnesses;expected['subword_copies']=copies;expected['subword_final_writer']=origin
    assert [e['ordinal'] for e in events]==list(range(1,571))
    return events,definitions,expected


def expected_events():
    events,definitions,_=build();return events,definitions


def replay(events,definitions):
    source,defs,expected=build();assert events==source and definitions==defs;return expected


def inspect(run):
    events,definitions,expected=build()
    assert run['events']==events,'complete subword/transform IMEM census'
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
    for field in ('rsp_definitions','imem_fetches','exception_roots','eret_returns','epc_reads','epc_writes','conditional_sp_attempts','subword_sp_writes'):
        assert report[field]==(defs if field=='rsp_definitions' else expected[field]),field
    assert len(report['copies'])==7 and report['copies'][3:5]==expected['conditional_copies'] and report['copies'][-2:]==expected['subword_copies']
    assert report['final_imem_writers'][:4]==[expected['subword_final_writer']]*4
    graph=report['dma_consumption']
    for field,key in (('writes','writers'),('fetches','fetches'),('promoted_requests','requests'),
        ('imem_installs','installs'),('dmem_installs','dmem_installs'),('pending_commits','pending_commits'),
        ('cache_fills','cache_fills'),('cached_fetches','cached_fetches'),('cache_invalidations','cache_invalidations'),
        ('cpu_writes','cpu_writes'),('tlb_generations','tlb_generations'),('context_writes','context_writes'),
        ('entry_lo_writes','entry_lo_writes'),('context_loads','context_loads')):
        assert graph[field]==expected[key],field
    assert [f['origins'][0]['write_ordinal'] for f in report['imem_fetches'][-2:]]==[559,567]
    assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
