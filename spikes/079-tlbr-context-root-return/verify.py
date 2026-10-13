"""Independent installed-slot TLBR/context and executable ancestry composition."""
from pathlib import Path
import copy
import importlib.util
import json
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('page_model',ROOT/'spikes/078-entrylo-remap-root-return/verify.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
FORMAT='plaid-rsp-cpu-imem-history-v21'
PROFILE='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-tlbr-context-remap-root-return-v21'
INITIAL,TLB_INITIAL,STAGED,RAM_START=prior.INITIAL,prior.TLB_INITIAL,prior.STAGED,prior.RAM_START
ROOT_PC,LW,SW,CACHE,ERET=prior.ROOT_PC,prior.LW,prior.SW,prior.CACHE,prior.ERET
ROOT_CONTEXT,TRANSFORM_CONTEXT=prior.ROOT_CONTEXT+21,prior.TRANSFORM_CONTEXT+21


def build():
    events,definitions,expected=prior.build()
    events,expected=json.loads(json.dumps(events)),json.loads(json.dumps(expected))
    keys={'ordinal','context','decoder_context','trigger_context','transfer_ordinal','fetch_context','end_ordinal',
        'load_context','read_ordinal','write_ordinal','store_context','burst_ordinal','fill_ordinal','ended_fill',
        'epc_transfer_ordinal','epc_write_ordinal','cut_ordinal','begin_ordinal','target_decoder_context','context_write_ordinal'}
    def shift(value):
        if isinstance(value,dict):
            for k,v in value.items():
                if k in keys and isinstance(v,int) and v>=419:value[k]=v+21
                else:shift(v)
        elif isinstance(value,list):
            for v in value:shift(v)
    shift(events);shift(expected)
    for field in ('initial_ram','final_ram'):expected[field][0x60ac:0x60b0]=(0x42000001).to_bytes(4,'big')
    current=copy.deepcopy(TLB_INITIAL['entries']);staged=copy.deepcopy(STAGED);staged['physical'][0]=0xe000
    current[0]=copy.deepcopy(staged);extra=[];template=copy.deepcopy(events[417]);gpr=template['gpr'].copy()
    def append(kind,**fields):
        e=copy.deepcopy(template);e.update(kind=kind,ordinal=419+len(extra),context=0,phase=51,word=0,value=0,gpr=[]);e.update(fields)
        extra.append(e);return e
    def state(pc):
        return dict(control=dict(state=dict(pc=pc,bev=False,exl=False,erl=False,kernel_mode='bits32',kernel=True,cause=0,
            branch_delay=False,epc=0,delay_slot=False),interrupt_enable=False,llbit=False),index=0,
            staged=copy.deepcopy(staged),entries=copy.deepcopy(current))
    loads=[]
    for word,pc in ((0x40995000,0xffffffffa00060a0),(0x42000001,0xffffffffa00060ac),(0x42000001,0xffffffffa00060ac)):
        seed=419+len(extra);append('cpu_reentry',context=seed,pc=pc,gpr=gpr.copy())
        fetch=419+len(extra);access=dict(physical=pc&0x1fffffff,cached=False)
        append('ram_fetch_begin',context=fetch,pc=pc,address=access['physical'],cpu=True,fetch=access)
        append('ram_read',context=fetch,pc=pc,address=access['physical'],cpu=True,bytes=4,value=word)
        append('ram_fetch_end',context=fetch,pc=pc,address=access['physical'],cpu=True,fetch=access,value=word)
        decoder=419+len(extra);before=state(pc)
        append('cpu_begin',context=decoder,pc=pc,cpu=True,word=word,gpr=gpr.copy(),tlb_state=before)
        if word==0x40995000:
            staged['asid']=8;after=state(pc)
            occurrence=append('entry_hi_write',context=decoder,pc=pc,cpu=True,word=word,value=0xe008,tlb_state=after)
            expected['context_writes'].append(dict(decoder_context=decoder,write_ordinal=occurrence['ordinal'],end_ordinal=occurrence['ordinal']+1,
                source_register=25,register_value=0xe008,before=before,after=after,same_staged_content=False))
        else:
            staged=copy.deepcopy(current[0]);after=state(pc)
            occurrence=append('tlb_read',context=decoder,pc=pc,cpu=True,word=word,tlb_state=after)
            def fingerprint(entry):return dict(sha256=prior.prior.fingerprint(entry)['sha256'],asid=entry['asid'])
            loads.append(dict(generation=dict(operation_generation=len(loads)+1,epoch=1,context=decoder,pc=pc,begin_ordinal=decoder,
                load_ordinal=occurrence['ordinal'],end_ordinal=occurrence['ordinal']+1,selected_slot=0,
                before_context=fingerprint(before['staged']),selected_entry=fingerprint(current[0]),after_context=fingerprint(after['staged']),
                same_context_content=before['staged']==after['staged']),installed_write_ordinal=417,entry_lo_write_ordinal=405))
        append('cpu_end',context=decoder,pc=pc,cpu=True,word=word,gpr=gpr.copy())
        expected['fetches'].append(dict(fetch_context=fetch,read_ordinal=fetch+1,decoder_context=decoder,pc=pc,physical=access['physical'],word=word,
            origins=[dict(kind='unknown',cut_ordinal=None) for _ in range(4)]))
    events[418:418]=extra
    expected['context_loads']=loads;expected['fetches'].sort(key=lambda f:f['decoder_context'])
    for f in expected['cached_fetches']:
        if 'mapping' in f and f['fetch_context']>=440:
            f['mapping'].pop('context_write_ordinal');f['mapping']['tlbr_load_ordinal']=438
    assert [e['ordinal'] for e in events]==list(range(1,507))
    return events,definitions,expected


def expected_events():
    events,definitions,_=build();return events,definitions


def replay(events,definitions):
    source,defs,expected=build();assert events==source and definitions==defs;return expected


def inspect(run):
    events,definitions,expected=build()
    assert run['events']==events,'complete TLBR/context census'
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
    for field in ('rsp_definitions','imem_fetches','exception_roots','eret_returns','epc_reads','epc_writes'):
        assert report[field]==(defs if field=='rsp_definitions' else expected[field]),field
    graph=report['dma_consumption']
    for field,key in (('writes','writers'),('fetches','fetches'),('promoted_requests','requests'),
        ('imem_installs','installs'),('dmem_installs','dmem_installs'),('pending_commits','pending_commits'),
        ('cache_fills','cache_fills'),('cached_fetches','cached_fetches'),('cache_invalidations','cache_invalidations'),
        ('cpu_writes','cpu_writes'),('tlb_generations','tlb_generations'),('context_writes','context_writes'),
        ('entry_lo_writes','entry_lo_writes'),('context_loads','context_loads')):
        assert graph[field]==expected[key],field
    assert len(graph['tlb_generations'])==3 and graph['context_loads'][1]['generation']['same_context_content']
    mapped=[f for f in graph['cached_fetches'] if 'mapping'in f]
    for f in mapped[-2:]:
        assert 'context_write_ordinal' not in f['mapping'] and f['mapping']['tlbr_load_ordinal']==438
        assert f['mapping']['write_ordinal']==417 and f['mapping']['entry_lo_write_ordinal']==405
    assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
