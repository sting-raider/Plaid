"""Independent transformed EPC target/ERET and executable ancestry graph."""
from pathlib import Path
import copy
import importlib.util
ROOT=Path(__file__).resolve().parents[2]
FORMAT='plaid-rsp-cpu-imem-history-v19'
PROFILE='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-entryhi-context-mapped-root-return-v19'
INITIAL=dict(bank=0,descriptor=dict(pbus=0,dram=0,length=0,count=0,skip=0))
RAM_START=0
ROOT_PC=0xffffffff80000180
LW=0x8e080000
SW=0xae680000
CACHE=0xbe500000
ERET=0x42000018


ROOT_CONTEXT=373
TRANSFORM_CONTEXT=402

def build():
    import json
    spec=importlib.util.spec_from_file_location('mapped_model',ROOT/'spikes/075-tlb-mapped-cache-root-return/verify.py')
    prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
    events,definitions,expected=prior.build();events=json.loads(json.dumps(events));expected=json.loads(json.dumps(expected))
    keys={'ordinal','context','decoder_context','trigger_context','transfer_ordinal','fetch_context','end_ordinal',
        'load_context','read_ordinal','write_ordinal','store_context','burst_ordinal','fill_ordinal','ended_fill',
        'epc_transfer_ordinal','epc_write_ordinal','cut_ordinal','begin_ordinal','target_decoder_context'}
    def shift(value):
        if isinstance(value,dict):
            for k,v in value.items():
                if k in keys and isinstance(v,int) and v>=334:value[k]=v+21
                else:shift(v)
        elif isinstance(value,list):
            for v in value:shift(v)
    shift(events);shift(expected)
    for e in events:
        if e['ordinal']>=355:e['phase']+=3
        if e['gpr']:e['gpr'][25:27]=[0x6008,0x6007]
    for field in ('initial_ram','final_ram'):
        expected[field]+=list((0x40995000).to_bytes(4,'big')+(0x409a5000).to_bytes(4,'big'))+[0]*24
    current=copy.deepcopy(prior.TLB_INITIAL['entries']);current[0]=copy.deepcopy(prior.STAGED)
    staged=copy.deepcopy(prior.STAGED);extra=[];writes=[]
    template=copy.deepcopy(events[332]);fetch=copy.deepcopy(events[327])
    def append(e,**updates):
        e=copy.deepcopy(e);e.update(updates,ordinal=334+len(extra));extra.append(e);return e
    for phase,seed,context,decoder,address,register,value in [(49,334,335,338,0x60a0,25,0x6008),
            (50,341,342,345,0x60a4,26,0x6007),(51,348,349,352,0x60a4,26,0x6007)]:
        word=0x40805000|(register<<16);pc=0xffffffffa0000000+address
        append(template,kind='cpu_reentry',context=seed,pc=pc,phase=phase,word=0)
        fetch.update(context=context,pc=pc,phase=phase,address=address,fetch=dict(physical=address,cached=False))
        append(fetch);scalar=copy.deepcopy(next(e for e in events if e['kind']=='ram_read'))
        append(scalar,context=context,pc=pc,phase=phase,address=address,value=word)
        append(fetch,kind='ram_fetch_end',value=word)
        begin=append(template,kind='cpu_begin',context=decoder,pc=pc,phase=phase,word=word)
        state=dict(pc=pc,bev=False,exl=False,erl=False,kernel_mode='bits32',kernel=True,cause=0,branch_delay=False,epc=0,delay_slot=False)
        control=dict(state=state,interrupt_enable=False,llbit=False)
        before=dict(control=control,index=0,staged=copy.deepcopy(staged),entries=copy.deepcopy(current));begin['tlb_state']=before
        staged['asid']=value&255
        after=dict(control=copy.deepcopy(control),index=0,staged=copy.deepcopy(staged),entries=copy.deepcopy(current))
        effect=copy.deepcopy(next(e for e in events if e['kind']=='tlb_write'));effect.pop('tlb_state')
        append(effect,kind='entry_hi_write',context=decoder,pc=pc,phase=phase,word=word,value=value,tlb_state=after)
        append(template,kind='cpu_end',context=decoder,pc=pc,phase=phase,word=word)
        writes.append(dict(decoder_context=decoder,write_ordinal=decoder+1,end_ordinal=decoder+2,
            source_register=register,register_value=value,before=before,after=after,same_staged_content=before['staged']==after['staged']))
        expected['fetches'].append(dict(fetch_context=context,read_ordinal=context+1,decoder_context=decoder,
            pc=pc,physical=address,word=word,origins=[dict(kind='unknown',cut_ordinal=None)]*4))
    events[333:333]=extra
    for f in expected['cached_fetches']:
        if 'mapping' in f:f['mapping']['context_write_ordinal']=353
    expected['context_writes']=writes
    return events,definitions,expected

spec=importlib.util.spec_from_file_location('initial_mapping',ROOT/'spikes/075-tlb-mapped-cache-root-return/verify.py')
initial=importlib.util.module_from_spec(spec);spec.loader.exec_module(initial)
TLB_INITIAL=initial.TLB_INITIAL
STAGED=initial.STAGED


def expected_events():
    events,definitions,_=build();return events,definitions


def replay(events,definitions):
    source,defs,expected=build();assert events==source and definitions==defs;return expected


def inspect(run):
    events,definitions,expected=build()
    assert run['events']==events,'complete live-EPC/handler/return census'
    assert run['initial_pending']==INITIAL
    for field in ('initial_ram','final_ram','final_dmem','initial_imem','final_imem'):assert run[field]==expected[field],field
    assert run['initial_dmem']==list(bytes.fromhex('340800aaaaee7722')+bytes(4088))
    starts=[e for e in events if e['kind']=='cpu_begin'];ends=[e for e in events if e['kind']=='cpu_end']
    assert run['steps']==[dict(phase=a['phase'],index=i,word=a['word'],pc=a['pc'],before=a['gpr'],after=b['gpr']) for i,(a,b) in enumerate(zip(starts,ends))]
    source={key:run[key] for key in ('initial_dmem','initial_imem','final_dmem','final_imem','steps','events','initial_pending')}
    assert run['initial_tlb']==TLB_INITIAL
    source['initial_tlb']=TLB_INITIAL
    source.update(format=FORMAT,profile=PROFILE,ram=dict(start=RAM_START,initial=run['initial_ram'],final_bytes=run['final_ram']))
    return source,definitions


def compare_report(report,definitions):
    _,defs,expected=build();assert definitions==defs
    assert report['rsp_definitions']==defs and report['imem_fetches']==expected['imem_fetches']
    assert report['exception_roots']==expected['exception_roots'] and report['eret_returns']==expected['eret_returns']
    assert report['epc_reads']==expected['epc_reads'] and report['epc_writes']==expected['epc_writes']
    graph=report['dma_consumption']
    assert graph['tlb_generations']==expected['tlb_generations']
    assert graph['context_writes']==expected['context_writes']
    for field,key in (('writes','writers'),('fetches','fetches'),('promoted_requests','requests'),
        ('imem_installs','installs'),('dmem_installs','dmem_installs'),('pending_commits','pending_commits'),
        ('cache_fills','cache_fills'),('cached_fetches','cached_fetches'),('cache_invalidations','cache_invalidations'),('cpu_writes','cpu_writes')):
        assert graph[field]==expected[key],field
    assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
