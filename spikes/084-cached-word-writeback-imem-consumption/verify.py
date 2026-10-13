"""Independent equal cached-store/revision/complete-line export graph."""
from pathlib import Path
import copy
import importlib.util
import json
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('cached_model',ROOT/'spikes/083-cached-ram-load-imem-consumption/verify.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
FORMAT='plaid-rsp-cpu-imem-history-v26'
PROFILE='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-cached-word-writeback-imem-consumption-v26'
INITIAL,TLB_INITIAL,STAGED,RAM_START=prior.INITIAL,prior.TLB_INITIAL,prior.STAGED,prior.RAM_START
ROOT_PC,LW,SW,CACHE,ERET=prior.ROOT_PC,prior.LW,prior.SW,prior.CACHE,prior.ERET
ROOT_CONTEXT,TRANSFORM_CONTEXT=prior.ROOT_CONTEXT,prior.TRANSFORM_CONTEXT


def build():
    events,definitions,expected=prior.build();events,expected=json.loads(json.dumps(events)),json.loads(json.dumps(expected))
    code=(0x8e080000,0xae480004,0xae480004,0xbe590004,0x8e680004,0xae081000,0x8e480004,0xae081000)
    for field in ('initial_ram','final_ram'):
        for i,word in enumerate(code):expected[field][0x6170+4*i:0x6174+4*i]=word.to_bytes(4,'big')
    expected['final_ram'][0xe020:0xe030]=[0]*16;expected['final_imem'][:4]=[0]*4
    template=copy.deepcopy(next(e for e in reversed(events) if e['kind']=='cpu_end'));gpr=template['gpr'].copy()
    state_template=copy.deepcopy(next(e['ram_load_state'] for e in events if 'ram_load_state' in e))
    def state(pc):
        s=copy.deepcopy(state_template);s['linked']['control']['state']['pc']=pc;return s
    def append(kind,**fields):
        e=copy.deepcopy(template);e.update(kind=kind,ordinal=len(events)+1,context=0,word=0,value=0,gpr=[]);e.update(fields)
        events.append(e);return e
    append('cpu_reentry',context=675,phase=98,pc=0xffffffffa0006170,gpr=gpr.copy())
    held=None;mutations=[];copies=[];cache_snapshot=dict(slot=2,tag=0xe001,index=0x20,dirty=0xf000,words=[0]*4)
    sp_parents=copy.deepcopy(expected['subword_copies'][0]['source_bytes'])
    def consume(phase,origin):
        context=len(events)+1;rsp=copy.deepcopy(next(e for e in reversed(events) if e['kind']=='rsp_end'))
        rsp.update(kind='rsp_begin',ordinal=context,context=context,pc=0,phase=phase,word=0,next=0,halted=False)
        events.append(rsp);end=copy.deepcopy(rsp);end.update(kind='rsp_end',ordinal=context+1,next=4);events.append(end)
        expected['imem_fetches'].append(dict(context=context,pc=0,word=0,origins=[copy.deepcopy(origin) for _ in range(4)]))
    for index,phase in enumerate((98,99,100,101,102,103,105,106)):
        word=code[index];pc=0xffffffffa0006170+4*index;fetch=len(events)+1;access=dict(physical=pc&0x1fffffff,cached=False)
        append('ram_fetch_begin',context=fetch,phase=phase,pc=pc,cpu=True,address=access['physical'],fetch=access)
        append('ram_read',context=fetch,phase=phase,pc=pc,cpu=True,address=access['physical'],bytes=4,value=word)
        append('ram_fetch_end',context=fetch,phase=phase,pc=pc,cpu=True,address=access['physical'],fetch=access,value=word)
        decoder=len(events)+1;begin=append('cpu_begin',context=decoder,phase=phase,pc=pc,cpu=True,word=word,gpr=gpr.copy())
        def primitive(record,fields,snapshot=None):
            e=append('dcache_primitive',context=decoder,phase=phase,pc=pc,cpu=True,word=word,dcache_event=dict(record=record,ordinal=len(events)+1,**fields))
            if snapshot is not None:e['dcache_line']=copy.deepcopy(snapshot)
            return e
        if index==0:
            read=append('sp_read',context=decoder,phase=phase,pc=pc,cpu=True,word=word,address=0x04000000,bytes=4);gpr[8]=0
            held=dict(load_context=decoder,read_ordinal=read['ordinal'],source=0x04000000,source_bytes=sp_parents)
        elif index in (1,2):
            begin['dcache_cpu_state']=state(pc)
            mutation=primitive('resident_word_mutation',dict(physical=0xe02c,slot=2,payload=[0]*4),cache_snapshot)
            mutations.append(dict(decoder_context=decoder,mutation_ordinal=mutation['ordinal'],destination=0xe02c,source_register=8,
                register_value=0,word=0,copy_parent=copy.deepcopy(held)))
        elif index==3:
            begin['dcache_cpu_state']=state(pc);begin['dcache_cpu_line']=copy.deepcopy(cache_snapshot)
            primitive('writeback_begin',dict(physical_line=0xe020,slot=2),cache_snapshot)
            primitive('backing_write',dict(physical_line=0xe020,payload=[0]*16))
            primitive('writeback_end',dict(slot=2),cache_snapshot)
        elif index==4:
            begin['ram_load_state']=state(pc)
            read=append('cpu_ram_read',context=decoder,phase=phase,pc=pc,cpu=True,word=word,address=0xe02c,bytes=4)
            held=dict(load_context=decoder,read_ordinal=read['ordinal'],source=0xe02c,
                source_bytes=[dict(kind='cpu_ram_load',decoder_context=decoder,read_ordinal=read['ordinal'],physical=0xe02c+n,
                    parent=dict(kind='dcache_writeback',write_ordinal=699,source_offset=12+n)) for n in range(4)])
        elif index==6:
            begin['ram_load_state']=state(pc);clean=copy.deepcopy(cache_snapshot);clean['dirty']=0
            read=primitive('cached_word_read',dict(pc=pc,effective_virtual=0xffffffff8000e02c,physical=0xe02c,slot=2,payload=[0]*4),clean)
            held=dict(load_context=decoder,read_ordinal=read['ordinal'],source=0xe02c,
                source_bytes=[dict(kind='cpu_cached_mutation_load',decoder_context=decoder,read_ordinal=read['ordinal'],physical=0xe02c+n,
                    resident_generation=664,resident_revision=692,mutation_ordinal=692,source_offset=n) for n in range(4)])
            expected['dcache_reads'].append(dict(read_ordinal=read['ordinal'],pc=pc,effective_virtual=0xffffffff8000e02c,physical=0xe02c,slot=2,payload=[0]*4,
                resident_generation=664,resident_revision=692,origins=[dict(kind='resident_word_mutation',mutation_ordinal=692,byte_index=n) for n in range(4)],
                current_captured_backing=dict(write_ordinal=699,from_writeback=True,payload=[0]*4)))
        else:
            write=append('sp_write',context=decoder,phase=phase,pc=pc,cpu=True,word=word,address=0x04001000,bank=1,bytes=4)
            origin=dict(kind='cpu',context=decoder,pc=pc,word=word,write_ordinal=write['ordinal'])
            copies.append(dict(phase=phase,store_context=decoder,write_ordinal=write['ordinal'],source_register=8,destination=0x04001000,word=0,**copy.deepcopy(held)))
        end=append('cpu_end',context=decoder,phase=phase,pc=pc,cpu=True,word=word,gpr=gpr.copy())
        if index in (1,2,3):end['dcache_cpu_state']=state(pc)
        if index==3:clean=copy.deepcopy(cache_snapshot);clean['dirty']=0;end['dcache_cpu_line']=clean
        if index in (4,6):end['ram_load_state']=state(pc)
        expected['fetches'].append(dict(fetch_context=fetch,read_ordinal=fetch+1,decoder_context=decoder,pc=pc,
            physical=access['physical'],word=word,origins=[dict(kind='unknown',cut_ordinal=None) for _ in range(4)]))
        if index in (5,7):consume(104 if index==5 else 107,origin)
    expected.update(writeback_mutations=mutations,writeback_copies=copies,writeback_final_writer=origin)
    assert [e['ordinal'] for e in events]==list(range(1,730))
    return events,definitions,expected


def expected_events():
    events,definitions,_=build();return events,definitions


def replay(events,definitions):
    source,defs,expected=build();assert events==source and definitions==defs;return expected


def inspect(run):
    events,definitions,expected=build()
    assert run['events']==events,'complete cached-store/writeback census'
    assert run['initial_pending']==INITIAL and run['initial_tlb']==TLB_INITIAL
    for field in ('initial_ram','final_ram','final_dmem','initial_imem','final_imem'):assert run[field]==expected[field],field
    assert run['initial_dmem']==list(bytes.fromhex('340800aaaaee7722')+bytes(4088))
    starts=[e for e in events if e['kind']=='cpu_begin'];ends=[e for e in events if e['kind']=='cpu_end']
    assert run['steps']==[dict(phase=a['phase'],index=i,word=a['word'],pc=a['pc'],before=a['gpr'],after=b['gpr']) for i,(a,b) in enumerate(zip(starts,ends))]
    source={key:run[key] for key in ('initial_dmem','initial_imem','final_dmem','final_imem','steps','events','initial_pending','initial_tlb')}
    source.update(format=FORMAT,profile=PROFILE,ram=dict(start=RAM_START,initial=run['initial_ram'],final_bytes=run['final_ram']))
    return source,definitions


def compare_report(report,definitions):
    events,defs,expected=build();assert definitions==defs
    projected=copy.deepcopy(report);_,_,old=prior.build()
    projected['copies']=projected['copies'][:12];projected['imem_fetches']=projected['imem_fetches'][:-2]
    projected['final_imem_writers'][:4]=[old['cached_ram_final_writer']]*4
    projected['dma_consumption']['fetches']=projected['dma_consumption']['fetches'][:-8]
    graph=projected['dma_consumption']['dcache_consumption'];graph.pop('cpu_word_mutations')
    graph['cache']['reads']=graph['cache']['reads'][:-1]
    graph['cache']['writeback'].update(events=23,resident_word_mutations=0,successful_backing_writebacks=0,receipts=[])
    prior.compare_report(projected,definitions)
    for field in ('imem_fetches','fetches'):
        actual=report[field] if field=='imem_fetches' else report['dma_consumption'][field]
        assert actual==expected[field],field
    assert len(report['copies'])==14 and report['copies'][-2:]==expected['writeback_copies']
    assert report['final_imem_writers'][:4]==[expected['writeback_final_writer']]*4
    graph=report['dma_consumption']['dcache_consumption'];cache=graph['cache'];wb=cache['writeback']
    assert graph['cpu_word_mutations']==expected['writeback_mutations'] and cache['reads']==expected['dcache_reads']
    origins=[dict(kind='backing_fill',backing_read_ordinal=663,fill_ordinal=664,physical=0xe020+n) for n in range(12)]
    origins += [dict(kind='resident_word_mutation',mutation_ordinal=692,byte_index=n) for n in range(4)]
    assert wb['receipts']==[dict(begin_ordinal=698,backing_write_ordinal=699,slot=2,resident_generation=664,resident_revision=692,physical_line=0xe020,origins=origins)]
    assert (wb['events'],wb['resident_word_mutations'],wb['successful_backing_writebacks'])==(29,2,1)
    assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
