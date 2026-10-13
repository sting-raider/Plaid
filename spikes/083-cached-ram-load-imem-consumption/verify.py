"""Independent cached operand/RAM writer/IMEM consumption graph."""
from pathlib import Path
import copy
import importlib.util
import json
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('ram_model',ROOT/'spikes/082-ram-load-imem-consumption/verify.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
FORMAT='plaid-rsp-cpu-imem-history-v25'
PROFILE='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-cached-ram-load-imem-consumption-v25'
INITIAL,TLB_INITIAL,STAGED,RAM_START=prior.INITIAL,prior.TLB_INITIAL,prior.STAGED,prior.RAM_START
ROOT_PC,LW,SW,CACHE,ERET=prior.ROOT_PC,prior.LW,prior.SW,prior.CACHE,prior.ERET
ROOT_CONTEXT,TRANSFORM_CONTEXT=prior.ROOT_CONTEXT,prior.TRANSFORM_CONTEXT


def build():
    events,definitions,expected=prior.build()
    events,expected=json.loads(json.dumps(events)),json.loads(json.dumps(expected))
    code=(0x8e480004,0xae081000,0x39080021,0xae680004,0x8e480004,0xae081000,0xbe510004,0x8e480004,0xae081000)
    for field in ('initial_ram','final_ram'):
        for i,word in enumerate(code):expected[field][0x6130+4*i:0x6134+4*i]=word.to_bytes(4,'big')
    expected['final_ram'][0xe02c:0xe030]=[0,0,0,0x21];expected['final_imem'][:4]=[0,0,0,0x21]
    template=copy.deepcopy(next(e for e in reversed(events) if e['kind']=='cpu_end'));gpr=template['gpr'].copy()
    template.pop('ram_load_state',None)
    state_template=copy.deepcopy(next(e['ram_load_state'] for e in events if 'ram_load_state' in e))
    def append(kind,**fields):
        e=copy.deepcopy(template);e.update(kind=kind,ordinal=len(events)+1,context=0,word=0,value=0,gpr=[]);e.update(fields)
        events.append(e);return e
    def state(pc):
        s=copy.deepcopy(state_template);s['linked']['control']['state']['pc']=pc;return s
    append('cpu_reentry',context=611,phase=86,pc=0xffffffffa0006130,gpr=gpr.copy())
    copies=[];held=None;reads=[];fills=[];generation=617;backing_read=616;ram_writer=595
    def consume(phase,origin,word):
        context=len(events)+1;rsp=copy.deepcopy(next(e for e in reversed(events) if e['kind']=='rsp_end'))
        rsp.update(kind='rsp_begin',ordinal=context,context=context,pc=0,phase=phase,word=word,next=0,halted=False)
        events.append(rsp);end=copy.deepcopy(rsp);end.update(kind='rsp_end',ordinal=context+1,next=4);events.append(end)
        expected['imem_fetches'].append(dict(context=context,pc=0,word=word,origins=[copy.deepcopy(origin) for _ in range(4)]))
    for index,phase in enumerate((86,87,89,90,91,92,94,95,96)):
        word=code[index];pc=0xffffffffa0006130+4*index;fetch=len(events)+1;access=dict(physical=pc&0x1fffffff,cached=False)
        append('ram_fetch_begin',context=fetch,phase=phase,pc=pc,cpu=True,address=access['physical'],fetch=access)
        append('ram_read',context=fetch,phase=phase,pc=pc,cpu=True,address=access['physical'],bytes=4,value=word)
        append('ram_fetch_end',context=fetch,phase=phase,pc=pc,cpu=True,address=access['physical'],fetch=access,value=word)
        decoder=len(events)+1;begin=append('cpu_begin',context=decoder,phase=phase,pc=pc,cpu=True,word=word,gpr=gpr.copy())
        def primitive(record,fields,snapshot=None):
            meta=dict(record=record,ordinal=len(events)+1,**fields)
            e=append('dcache_primitive',context=decoder,phase=phase,pc=pc,cpu=True,word=word,dcache_event=meta)
            if snapshot is not None:e['dcache_line']=snapshot
            return e
        if index in (0,4,7):
            begin['ram_load_state']=state(pc)
            value=0x21 if index==7 else 0;resident=[0,0,0,0x21] if index==7 else [0,0,0,0]
            snapshot=dict(slot=2,tag=0xe001,index=0x20,dirty=0,words=resident)
            if index in (0,7):
                burst=primitive('backing_read',dict(physical_line=0xe020,payload=[0]*12+[0,0,0,value]))
                backing_read=burst['ordinal'];fill=primitive('fill',dict(physical_line=0xe020,slot=2,payload=[0]*12+[0,0,0,value]),snapshot)
                generation=fill['ordinal']
                parents=[dict(kind='unknown',cut_ordinal=None) for _ in range(8)]
                parents += [dict(kind='cpu_copy',write_ordinal=468,source_offset=n) for n in range(4)]
                parents += [dict(kind='cpu_copy',write_ordinal=ram_writer,source_offset=n) for n in range(4)]
                fills.append(dict(read_ordinal=backing_read,physical_line=0xe020,source_bytes=parents))
            read=primitive('cached_word_read',dict(pc=pc,effective_virtual=0xffffffff8000e02c,physical=0xe02c,slot=2,payload=[0,0,0,value]),snapshot)
            gpr[8]=value
            origins=[dict(kind='backing_fill',backing_read_ordinal=backing_read,fill_ordinal=generation,physical=0xe02c+n) for n in range(4)]
            reads.append(dict(read_ordinal=read['ordinal'],pc=pc,effective_virtual=0xffffffff8000e02c,physical=0xe02c,slot=2,payload=[0,0,0,value],
                resident_generation=generation,resident_revision=generation,origins=origins,current_captured_backing=dict(write_ordinal=ram_writer,from_writeback=False,payload=[0,0,0,0x21 if ram_writer==637 else 0])))
            parent_writer=637 if index==7 else 595
            held=dict(load_context=decoder,read_ordinal=read['ordinal'],source=0xe02c,
                source_bytes=[dict(kind='cpu_cached_ram_load',decoder_context=decoder,read_ordinal=read['ordinal'],physical=0xe02c+n,
                    resident_generation=generation,resident_revision=generation,origin=origins[n],
                    parent=dict(kind='cpu_copy',write_ordinal=parent_writer,source_offset=n)) for n in range(4)])
        elif index==2:
            held['transform']=dict(decoder_context=decoder,pc=pc,word=word,source_value=0,result_value=0x21);gpr[8]=0x21
        elif index==6:
            begin['dcache_cpu_state']=state(pc)
            primitive('invalidate',dict(slot=2),dict(slot=2,tag=0xe000,index=0x20,dirty=0,words=[0,0,0,0]))
        else:
            imem=index in (1,5,8)
            write=append('sp_write' if imem else 'cpu_ram_write',context=decoder,phase=phase,pc=pc,cpu=True,word=word,
                address=0x04001000 if imem else 0xe02c,bank=1 if imem else 0,bytes=4,value=gpr[8])
            if imem:
                origin=dict(kind='cpu',context=decoder,pc=pc,word=word,write_ordinal=write['ordinal'])
                copies.append(dict(phase=phase,store_context=decoder,write_ordinal=write['ordinal'],source_register=8,destination=0x04001000,word=gpr[8],**copy.deepcopy(held)))
            else:
                ram_writer=write['ordinal']
                expected['cpu_writes'].append(dict(decoder_context=decoder,write_ordinal=ram_writer,destination=0xe02c,source_register=8,
                    register_value=gpr[8],word=gpr[8],copy_parent=copy.deepcopy(held)))
        end=append('cpu_end',context=decoder,phase=phase,pc=pc,cpu=True,word=word,gpr=gpr.copy())
        if index in (0,4,7):end['ram_load_state']=state(pc)
        if index==6:end['dcache_cpu_state']=state(pc)
        expected['fetches'].append(dict(fetch_context=fetch,read_ordinal=fetch+1,decoder_context=decoder,pc=pc,
            physical=access['physical'],word=word,origins=[dict(kind='unknown',cut_ordinal=None) for _ in range(4)]))
        if index in (1,5,8):consume({1:88,5:93,8:97}[index],origin,gpr[8])
    expected.update(cached_ram_copies=copies,cached_ram_final_writer=origin,dcache_reads=reads,dcache_fills=fills)
    assert [e['ordinal'] for e in events]==list(range(1,675))
    return events,definitions,expected


def expected_events():
    events,definitions,_=build();return events,definitions


def replay(events,definitions):
    source,defs,expected=build();assert events==source and definitions==defs;return expected


def inspect(run):
    events,definitions,expected=build()
    assert run['events']==events,'complete cached operand/IMEM source census'
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
    projected['copies']=projected['copies'][:9];projected['imem_fetches']=projected['imem_fetches'][:-3]
    projected['final_imem_writers'][:4]=[old['ram_load_final_writer']]*4
    projected['dma_consumption']['fetches']=projected['dma_consumption']['fetches'][:-9]
    projected['dma_consumption']['cpu_writes']=projected['dma_consumption']['cpu_writes'][:-1]
    prior.compare_report(projected,definitions)
    for field in ('imem_fetches','cpu_writes','fetches'):
        actual=report[field] if field=='imem_fetches' else report['dma_consumption'][field]
        assert actual==expected[field],field
    assert len(report['copies'])==12 and report['copies'][-3:]==expected['cached_ram_copies']
    assert report['final_imem_writers'][:4]==[expected['cached_ram_final_writer']]*4
    graph=report['dma_consumption']['dcache_consumption'];cache=graph['cache']
    assert graph['backing_fills']==expected['dcache_fills'] and cache['reads']==expected['dcache_reads']
    backing=sum(e['kind'] in ('ram_write','cpu_ram_write') for e in events)
    assert cache==dict(format='plaid-dcache-resident-read-report-v1',observed_backing_word_mutations=backing,
        reads=expected['dcache_reads'],cpu_operand_dataflow_certified=False,pointer_table_immutability_certified=False,executable_target_identity_certified=False,
        writeback=dict(format='plaid-dcache-writeback-report-v0',scope='finite_direct_kseg0_identity_rdram_aligned_word_writeback',
            source_sha256=report['source_sha256'],events=backing+8,backing_reads=2,fills=2,resident_word_mutations=0,invalidations=1,
            retired_unexported_mutations=0,successful_backing_writebacks=0,receipts=[],sensor_coverage_certified=False,cache_semantics_complete=False,
            tlb_cacheability_certified=False,executable_lifetime_certified=False,native_complete=False))
    assert [c['source_bytes'][0]['parent']['write_ordinal'] for c in report['copies'][-3:]]==[595,595,637]
    assert [c['source_bytes'][0]['resident_generation'] for c in report['copies'][-3:]]==[617,617,664]
    assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
