"""Independent transformed EPC target/ERET and executable ancestry graph."""
from pathlib import Path
import copy
import importlib.util
ROOT=Path(__file__).resolve().parents[2]
FORMAT='plaid-rsp-cpu-imem-history-v18'
PROFILE='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-tlbwi-mapped-cache-root-return-v18'
INITIAL=dict(bank=0,descriptor=dict(pbus=0,dram=0,length=0,count=0,skip=0))
RAM_START=0
ROOT_PC=0xffffffff80000180
LW=0x8e080000
SW=0xae680000
CACHE=0xbe500000
ERET=0x42000018


FIELDS=('global','valid','dirty','cca','physical','page_mask','virtual_address','asid','region','globals','mask_hi','mask_lo','select')
BLANK={'global':[False,False],'valid':[False,False],'dirty':[False,False],'cca':[0,0],'physical':[0,0],
    'page_mask':0,'virtual_address':0,'asid':0,'region':0,'globals':False,'mask_hi':((1<<40)-1)&~0x1fff,'mask_lo':0xfff,'select':0x1000}
STAGED=copy.deepcopy(BLANK);STAGED.update(valid=[True,False],dirty=[True,False],cca=[3,3],physical=[0x6000,0x7000],virtual_address=0x6000,asid=7)
TLB_INITIAL=dict(index=0,staged=STAGED,entries=[copy.deepcopy(BLANK) for _ in range(32)])
ROOT_CONTEXT=352
TRANSFORM_CONTEXT=381

def build():
    spec=importlib.util.spec_from_file_location('target_model',ROOT/'spikes/074-epc-transform-target/verify.py')
    prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
    events,definitions,expected=prior.build()
    import json
    expected=json.loads(json.dumps(expected)) # detach shared value aliases before rebasing identities
    keys={'ordinal','context','decoder_context','trigger_context','transfer_ordinal','fetch_context','end_ordinal',
        'load_context','read_ordinal','write_ordinal','store_context','burst_ordinal','fill_ordinal','ended_fill',
        'epc_transfer_ordinal','epc_write_ordinal','cut_ordinal','begin_ordinal','target_decoder_context'}
    def shift(value):
        if isinstance(value,dict):
            for key,v in value.items():
                if key in keys and isinstance(v,int) and v>=320:value[key]=v+14
                else:shift(v)
        elif isinstance(value,list):
            for v in value:shift(v)
    shift(events);shift(expected)
    for e in events:
        if e['ordinal']>=334:e['phase']+=2
        if 340<=e['ordinal']<=347:e['pc']=0x6028
        if e['ordinal']>=395:e['pc']=0x602c
        if e['ordinal']>=378 and e['gpr']:
            if e['gpr'][8] in (0xffffffff80006028,0xffffffff8000602c):e['gpr'][8] &= 0x1fffffff
        for key in ('exception_state','epc_state','return_state'):
            if key in e:
                state=e[key]['state'] if key!='exception_state' else e[key]
                if state['epc'] in (0xffffffff80006028,0xffffffff8000602c):state['epc'] &= 0x1fffffff
                if key=='exception_state' and e['kind']=='cpu_begin':state['pc']=0x6028
                if key=='return_state' and e['kind']=='return_transfer':state['pc']=0x602c
    for field in ('initial_ram','final_ram'):
        expected[field]+=list((0x42000002).to_bytes(4,'big'))+[0]*28
    root=expected['exception_roots'][0];root['before']['pc']=0x6028;root['after']['epc']=0x6028
    read=expected['epc_reads'][0];read['value']=0x6028
    write=expected['epc_writes'][0];write['value']=0x602c;write['read_parent']['value']=0x6028
    write['transform'].update(source_value=0x6028,result_value=0x602c)
    ret=expected['eret_returns'][0];ret['after']['state']['pc']=0x602c
    for receipt in (read,write,write['read_parent'],ret):
        for field in ('before','after'):receipt[field]['state']['epc'] &= 0x1fffffff
    current=copy.deepcopy(TLB_INITIAL['entries']);gens=[];extra=[]
    template=copy.deepcopy(events[318]);fetch=copy.deepcopy(events[313]);fetch.pop('cache_line',None)
    def append(e,**updates):
        e=copy.deepcopy(e);e.update(updates,ordinal=320+len(extra));extra.append(e);return e
    import hashlib,json
    def fingerprint(entry):
        raw=(json.dumps({k:entry[k] for k in FIELDS},separators=(',',':'))).encode()
        return dict(sha256=hashlib.sha256(raw).hexdigest())
    for phase,seed,context,decoder in [(47,320,321,324),(48,327,328,331)]:
        pc=0xffffffffa0006080
        append(template,kind='cpu_reentry',context=seed,pc=pc,phase=phase,word=0)
        fetch.update(context=context,pc=pc,phase=phase,address=0x6080,fetch=dict(physical=0x6080,cached=False))
        append(fetch)
        scalar=copy.deepcopy(next(e for e in events if e['kind']=='ram_read'))
        append(scalar,context=context,pc=pc,phase=phase,address=0x6080,value=0x42000002)
        append(fetch,kind='ram_fetch_end',value=0x42000002)
        begin=append(template,kind='cpu_begin',context=decoder,pc=pc,phase=phase,word=0x42000002)
        state=dict(pc=pc,bev=False,exl=False,erl=False,kernel_mode='bits32',kernel=True,cause=0,branch_delay=False,epc=0,delay_slot=False)
        control=dict(state=state,interrupt_enable=False,llbit=False)
        before=dict(control=control,index=0,staged=copy.deepcopy(STAGED),entries=copy.deepcopy(current));begin['tlb_state']=before
        old=copy.deepcopy(current[0]);current[0]=copy.deepcopy(STAGED)
        after=dict(control=copy.deepcopy(control),index=0,staged=copy.deepcopy(STAGED),entries=copy.deepcopy(current))
        effect=copy.deepcopy(next(e for e in events if e['kind']=='exception_transfer'));effect.pop('exception_state')
        append(effect,kind='tlb_write',context=decoder,pc=pc,phase=phase,word=0x42000002,tlb_state=after)
        append(template,kind='cpu_end',context=decoder,pc=pc,phase=phase,word=0x42000002)
        gens.append(dict(operation_generation=len(gens)+1,epoch=1,context=decoder,pc=pc,begin_ordinal=decoder,
            write_ordinal=decoder+1,end_ordinal=decoder+2,selected_slot=0,staged_entry=fingerprint(STAGED),
            before_entry=fingerprint(old),after_entry=fingerprint(STAGED),same_entry_content=old==STAGED))
        expected['fetches'].append(dict(fetch_context=context,read_ordinal=context+1,decoder_context=decoder,
            pc=pc,physical=0x6080,word=0x42000002,origins=[dict(kind='unknown',cut_ordinal=None)]*4))
    events[319:319]=extra
    observation=dict(asid=7,kernel=True,bits=32,entries=current)
    witness=dict(write_ordinal=332,selected_slot=0,current_asid=7,entry=STAGED)
    for e in events:
        if e['kind'] in ('ram_fetch_begin','ram_fetch_end') and e['pc'] in (0x6028,0x602c):e['mapping']=copy.deepcopy(observation)
    for f in expected['cached_fetches']:
        if f['decoder_context'] in (345,399):f['pc'] &= 0x1fffffff;f['mapping']=copy.deepcopy(witness)
    expected['tlb_generations']=gens
    return events,definitions,expected


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
    for field,key in (('writes','writers'),('fetches','fetches'),('promoted_requests','requests'),
        ('imem_installs','installs'),('dmem_installs','dmem_installs'),('pending_commits','pending_commits'),
        ('cache_fills','cache_fills'),('cached_fetches','cached_fetches'),('cache_invalidations','cache_invalidations'),('cpu_writes','cpu_writes')):
        assert graph[field]==expected[key],field
    assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
