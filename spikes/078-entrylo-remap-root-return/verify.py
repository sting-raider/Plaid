"""Independent staged-page/remap and executable writer/cache/root composition."""
from pathlib import Path
import copy
import importlib.util
import json

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('reactivation_model',ROOT/'spikes/077-mapped-cache-reactivation/verify.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
FORMAT='plaid-rsp-cpu-imem-history-v20'
PROFILE='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-entrylo-remap-root-return-v20'
INITIAL,TLB_INITIAL,STAGED,RAM_START=prior.INITIAL,prior.TLB_INITIAL,prior.STAGED,prior.RAM_START
ROOT_PC,LW,SW,CACHE,ERET=prior.ROOT_PC,prior.LW,prior.SW,prior.CACHE,prior.ERET
ROOT_CONTEXT,TRANSFORM_CONTEXT=prior.ROOT_CONTEXT+54,prior.TRANSFORM_CONTEXT+54
WORDS=[0x8e080000,0x3908000d,0x3a738000,0x3a528000,0xae680000]


def build():
    events,definitions,expected=prior.build()
    events,expected=json.loads(json.dumps(events)),json.loads(json.dumps(expected))
    keys={'ordinal','context','decoder_context','trigger_context','transfer_ordinal','fetch_context','end_ordinal',
        'load_context','read_ordinal','write_ordinal','store_context','burst_ordinal','fill_ordinal','ended_fill',
        'epc_transfer_ordinal','epc_write_ordinal','cut_ordinal','begin_ordinal','target_decoder_context','context_write_ordinal'}
    def shift(value):
        if isinstance(value,dict):
            for k,v in value.items():
                if k in keys and isinstance(v,int) and v>=365:value[k]=v+54
                else:shift(v)
        elif isinstance(value,list):
            for v in value:shift(v)
    shift(events);shift(expected)
    for e in events:
        if e['gpr']:
            e['gpr'][27]=0x39e
            if e['ordinal']>=419:
                e['gpr'][18]^=0x8000;e['gpr'][19]^=0x8000
    for field in ('initial_ram','final_ram'):
        expected[field]+= [0]*(0xe0c0-len(expected[field]))
        for address,word in [(0x60a8,0x409b1000)]+[(0x60b0+4*i,w) for i,w in enumerate(WORDS)]:
            expected[field][address:address+4]=word.to_bytes(4,'big')
    expected['final_ram'][0x6028:0x602c]=(13).to_bytes(4,'big')
    expected['final_ram'][0x602c:0x6030]=(0xaaee7722).to_bytes(4,'big')
    current=copy.deepcopy(TLB_INITIAL['entries']);current[0]=copy.deepcopy(STAGED)
    staged=copy.deepcopy(STAGED)
    new_stage=copy.deepcopy(staged);new_stage['physical'][0]=0xe000
    new_table=copy.deepcopy(current);new_table[0]=copy.deepcopy(new_stage)
    extra=[];template=copy.deepcopy(events[363]);gpr=template['gpr'].copy()
    def append(kind,**fields):
        e=copy.deepcopy(template);e.update(kind=kind,ordinal=365+len(extra),context=0,phase=51,word=0,value=0,gpr=[]);e.update(fields)
        extra.append(e);return e
    def seed(pc):append('cpu_reentry',context=365+len(extra),pc=pc,gpr=gpr.copy())
    def state(pc,stage,table):
        control=dict(state=dict(pc=pc,bev=False,exl=False,erl=False,kernel_mode='bits32',kernel=True,cause=0,
            branch_delay=False,epc=0,delay_slot=False),interrupt_enable=False,llbit=False)
        return dict(control=control,index=0,staged=copy.deepcopy(stage),entries=copy.deepcopy(table))
    unknown=[dict(kind='unknown',cut_ordinal=None) for _ in range(4)]
    def instruction(pc,word,effect=None):
        fetch=365+len(extra)
        append('ram_fetch_begin',context=fetch,pc=pc,address=pc&0x1fffffff,cpu=True,fetch=dict(physical=pc&0x1fffffff,cached=False))
        append('ram_read',context=fetch,pc=pc,address=pc&0x1fffffff,bytes=4,value=word,cpu=True)
        append('ram_fetch_end',context=fetch,pc=pc,address=pc&0x1fffffff,value=word,cpu=True,fetch=dict(physical=pc&0x1fffffff,cached=False))
        decoder=365+len(extra)
        begin=append('cpu_begin',context=decoder,pc=pc,word=word,gpr=gpr.copy(),cpu=True)
        if effect:effect(begin)
        append('cpu_end',context=decoder,pc=pc,word=word,gpr=gpr.copy(),cpu=True)
        expected['fetches'].append(dict(fetch_context=fetch,read_ordinal=fetch+1,decoder_context=decoder,
            pc=pc,physical=pc&0x1fffffff,word=word,origins=copy.deepcopy(unknown)))
        return begin
    seed(0xffffffffa00060b0)
    def load(begin):
        append('sp_read',context=begin['context'],pc=begin['pc'],word=begin['word'],cpu=True,address=0x04000000,bytes=4,value=0)
        gpr[8]=0
    instruction(0xffffffffa00060b0,WORDS[0],load)
    for i,register,immediate in ((1,8,13),(2,19,0x8000),(3,18,0x8000)):
        def transform(begin,r=register,imm=immediate):gpr[r]^=imm
        instruction(0xffffffffa00060b0+4*i,WORDS[i],transform)
    def store(begin):append('cpu_ram_write',context=begin['context'],pc=begin['pc'],word=begin['word'],cpu=True,address=0xe028,bytes=4,value=13)
    instruction(0xffffffffa00060c0,WORDS[4],store)
    page_writes=[]
    for _ in range(2):
        pc=0xffffffffa00060a8;seed(pc)
        def page(begin):
            nonlocal staged
            before=state(pc,staged,current);begin['tlb_state']=before
            staged=copy.deepcopy(new_stage);after=state(pc,staged,current)
            occurrence=append('entry_lo_write',context=begin['context'],pc=pc,word=begin['word'],cpu=True,value=0x39e,tlb_state=after)
            page_writes.append(dict(decoder_context=begin['context'],write_ordinal=occurrence['ordinal'],end_ordinal=occurrence['ordinal']+1,
                source_register=27,register_value=0x39e,before=before,after=after,same_staged_content=before['staged']==after['staged']))
        instruction(pc,0x409b1000,page)
    seed(0xe028)
    hit=365+len(extra);observation=dict(asid=7,kernel=True,bits=32,entries=copy.deepcopy(current))
    frame=copy.deepcopy(next(e['cache_line'] for e in events if e['ordinal']==292))
    append('ram_fetch_begin',context=hit,pc=0xe028,cpu=True,address=0x6028,fetch=dict(physical=0x6028,cached=True),mapping=observation)
    append('ram_fetch_end',context=hit,pc=0xe028,cpu=True,address=0x6028,value=0x21,fetch=dict(physical=0x6028,cached=True),mapping=copy.deepcopy(observation),cache_line=frame)
    decoder=365+len(extra)
    append('cpu_begin',context=decoder,pc=0xe028,cpu=True,word=0x21,gpr=gpr.copy())
    append('cpu_end',context=decoder,pc=0xe028,cpu=True,word=0x21,gpr=gpr.copy())
    expected['cached_fetches'].append(dict(fetch_context=hit,end_ordinal=hit+1,decoder_context=decoder,pc=0xe028,physical=0x6028,
        word=0x21,burst_ordinal=291,fill_ordinal=292,origins=[dict(kind='cpu_copy',write_ordinal=276,source_offset=n) for n in range(4)],
        mapping=dict(write_ordinal=332,selected_slot=0,current_asid=7,entry=copy.deepcopy(STAGED),context_write_ordinal=358)))
    pc=0xffffffffa0006080;seed(pc)
    def install(begin):
        begin['tlb_state']=state(pc,staged,current)
        append('tlb_write',context=begin['context'],pc=pc,word=begin['word'],cpu=True,tlb_state=state(pc,staged,new_table))
    instruction(pc,0x42000002,install)
    assert len(extra)==54
    events[364:364]=extra
    for e in events:
        if e['ordinal']<419:continue
        if e['kind']=='cpu_ram_write':e['address']^=0x8000
        if 'mapping' in e:
            e['mapping']['entries']=copy.deepcopy(new_table)
            e['address']^=0x8000;e['fetch']['physical']^=0x8000
        if e['kind'] in ('cache_burst_read','cache_fill') and e['address']==0x6020:e['address']=0xe020
        if 'cache_line' in e and e['cache_line']['tag_key']==0x6001:
            # The pre-trap CACHE instruction hit uses old resident state; only
            # newly mapped fetches select the replacement physical tag.
            if e['pc']==0xe028 or e['pc']==0xe02c:
                e['cache_line']['tag_key']=0xe001
                e['cache_line']['words']=[0,0,13,0,0,0,0,0] if e['pc']==0xe028 else [0]*8
        if 'cache_operation' in e:
            op=e['cache_operation'];op['virtual_address']^=0x8000;e['address']^=0x8000
            if e['ordinal']==423:op['after']=copy.deepcopy(op['before'])
            elif e['ordinal']==457:
                for name in ('before','after'):
                    op[name]['tag_key']^=0x8000;op[name]['words']=[0,0,13,0,0,0,0,0]
    for writer in expected['cpu_writes']:
        if writer['write_ordinal']>=419:writer['destination']^=0x8000
    writer=copy.deepcopy(next(w for w in expected['cpu_writes'] if w['write_ordinal']==318))
    writer.update(decoder_context=390,write_ordinal=391,destination=0xe028)
    writer['copy_parent'].update(load_context=369,read_ordinal=370)
    writer['copy_parent']['transform'].update(decoder_context=375,pc=0xffffffffa00060b4)
    expected['cpu_writes'].append(writer);expected['cpu_writes'].sort(key=lambda w:w['write_ordinal'])
    expected['entry_lo_writes']=page_writes
    expected['tlb_generations'].append(dict(operation_generation=3,epoch=1,context=416,pc=pc,begin_ordinal=416,
        write_ordinal=417,end_ordinal=418,selected_slot=0,staged_entry=prior.fingerprint(new_stage),
        before_entry=prior.fingerprint(STAGED),after_entry=prior.fingerprint(new_stage),same_entry_content=False))
    for invalidation in expected['cache_invalidations']:
        if invalidation['ordinal']>=419:
            invalidation['physical']^=0x8000;invalidation['operation']['virtual_address']^=0x8000
            if invalidation['ordinal']==423:
                invalidation.update(hit=False,ended_fill=None);invalidation['operation']['after']=copy.deepcopy(invalidation['operation']['before'])
            elif invalidation['ordinal']==457:
                for name in ('before','after'):
                    invalidation['operation'][name]['tag_key']^=0x8000
                    invalidation['operation'][name]['words']=[0,0,13,0,0,0,0,0]
    for fill in expected['cache_fills']:
        if fill['physical_line']==0x6020 and fill['fill_ordinal']>=419:
            fill['physical_line']=0xe020;fill['cache_line']['tag_key']=0xe001
            fill['cache_line']['words']=[0,0,13,0,0,0,0,0] if fill['fill_ordinal']==428 else [0]*8
            fill['source_bytes']=[dict(kind='unknown',cut_ordinal=None) for _ in range(32)]
            for n in range(4):
                fill['source_bytes'][8+n]=dict(kind='cpu_copy',write_ordinal=391 if fill['fill_ordinal']==428 else 447,source_offset=n)
                if fill['fill_ordinal']!=428:fill['source_bytes'][12+n]=dict(kind='cpu_copy',write_ordinal=452,source_offset=n)
    for fetch in expected['cached_fetches']:
        if 'mapping' in fetch and fetch['fetch_context']>=419:
            fetch['physical']^=0x8000
            fetch['mapping'].update(write_ordinal=417,entry=copy.deepcopy(new_stage),entry_lo_write_ordinal=405)
            if fetch['word']==13:fetch['origins']=[dict(kind='cpu_copy',write_ordinal=391,source_offset=n) for n in range(4)]
    expected['cached_fetches'].sort(key=lambda f:f['decoder_context']);expected['fetches'].sort(key=lambda f:f['decoder_context'])
    assert [e['ordinal'] for e in events]==list(range(1,486))
    return events,definitions,expected


def expected_events():
    events,definitions,_=build();return events,definitions


def replay(events,definitions):
    source,defs,expected=build();assert events==source and definitions==defs;return expected


def inspect(run):
    events,definitions,expected=build()
    assert run['events']==events,'complete EntryLo0/remap census'
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
        ('cpu_writes','cpu_writes'),('tlb_generations','tlb_generations'),('context_writes','context_writes'),('entry_lo_writes','entry_lo_writes')):
        assert graph[field]==expected[key],field
    mapped=[f for f in graph['cached_fetches'] if 'mapping'in f]
    assert [f['word'] for f in mapped]==[0x21,0x21,0x21,13,0]
    assert all(f['physical']==0x6028 and f['fill_ordinal']==292 for f in mapped[:3])
    assert 'entry_lo_write_ordinal' not in mapped[2]['mapping']
    assert mapped[3]['physical']==0xe028 and mapped[3]['mapping']['entry_lo_write_ordinal']==405
    assert graph['entry_lo_writes'][1]['same_staged_content']
    assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
