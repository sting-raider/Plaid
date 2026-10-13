"""Independent complete writer/transform/BREAK/root/handler consumption graph."""
from pathlib import Path
import copy
import importlib.util
ROOT=Path(__file__).resolve().parents[2]
FORMAT='plaid-rsp-cpu-imem-history-v14'
PROFILE='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-writer-break-handler-consumption-v14'
INITIAL=dict(bank=0,descriptor=dict(pbus=0,dram=0,length=0,count=0,skip=0))
RAM_START=0
LW=0x8e080000
SW_HANDLER=0xae880000
XORI=0x3908000d
SW=0xae680000
CACHE=0xbe500000
ROOT_PC=0xffffffff80000180


def build():
    spec=importlib.util.spec_from_file_location('transform_model',ROOT/'spikes/070-cpu-xori-ram-cached/verify.py')
    prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
    events,definitions,expected=prior.build()
    for event in events:
        if event['gpr']:event['gpr'][20]=0xffffffffa0000180
    extension=list(LW.to_bytes(4,'big')+SW_HANDLER.to_bytes(4,'big')+XORI.to_bytes(4,'big')+SW.to_bytes(4,'big')+bytes(16))
    for key in ('initial_ram','final_ram'):expected[key]=[0]*0x6000+expected[key]+extension
    def append(template,**changes):
        event=copy.deepcopy(template);event.update(changes,ordinal=len(events)+1);events.append(event);return event
    cpu=copy.deepcopy(events[-1]);cpu['word']=0
    append(cpu,kind='cpu_reentry',phase=43,context=296,pc=0xffffffffa0006060)
    read=copy.deepcopy(next(e for e in events if e['kind']=='ram_read'))
    fetch=copy.deepcopy(next(e for e in events if e['kind']=='ram_fetch_begin'))
    for phase,context,decoder,address,word in [(43,297,300,0x6060,LW),(44,303,306,0x6064,SW_HANDLER),
            (45,309,312,0x6068,XORI),(46,314,317,0x606c,SW)]:
        pc=0xffffffffa0000000+address
        fetch.update(phase=phase,context=context,pc=pc,address=address,fetch=dict(physical=address,cached=False))
        append(fetch);append(read,phase=phase,context=context,pc=pc,address=address,value=word)
        append(fetch,kind='ram_fetch_end',value=word)
        append(cpu,kind='cpu_begin',phase=phase,context=decoder,pc=pc,word=word)
        if word==LW:
            sp=copy.deepcopy(next(e for e in events if e['kind']=='sp_read'))
            append(sp,phase=phase,context=decoder,pc=pc,word=word,value=0);cpu['gpr'][8]=0
        elif word in (SW,SW_HANDLER):
            append(read,kind='cpu_ram_write',phase=phase,context=decoder,pc=pc,word=word,
                address=0x180 if word==SW_HANDLER else 0x6028,value=0 if word==SW_HANDLER else 13)
        else:cpu['gpr'][8]=13
        append(cpu,phase=phase,context=decoder,pc=pc,word=word)
        expected['fetches'].append(dict(fetch_context=context,read_ordinal=context+1,decoder_context=decoder,
            pc=pc,physical=address,word=word,origins=[dict(kind='unknown',cut_ordinal=None) for _ in range(4)]))
    parent=copy.deepcopy(expected['cpu_writes'][0]['copy_parent']);parent.update(load_context=300,read_ordinal=301)
    expected['cpu_writes'].append(dict(decoder_context=306,write_ordinal=307,destination=0x180,
        source_register=8,register_value=0,word=0,copy_parent=copy.deepcopy(parent)))
    parent['transform']=dict(decoder_context=312,pc=0xffffffffa0006068,word=XORI,source_value=0,result_value=13)
    expected['cpu_writes'].append(dict(decoder_context=317,write_ordinal=318,destination=0x6028,
        source_register=8,register_value=13,word=13,copy_parent=parent))
    expected['final_ram'][0x6028:0x602c]=[0,0,0,13]
    old=expected['cache_fills'][-1]
    fresh=copy.deepcopy(old);fresh['cache_line']['words'][2]=13
    fresh.update(fetch_context=327,burst_ordinal=328,fill_ordinal=329)
    fresh['source_bytes'][8:12]=[dict(kind='cpu_copy',write_ordinal=318,source_offset=n) for n in range(4)]
    for phase,context,decoder,address,word in [(47,321,323,0x6034,CACHE),(48,327,331,0x6028,13)]:
        pc=0xffffffff80000000+address
        append(cpu,kind='cpu_reentry',phase=phase,context=context-1,pc=pc,word=0)
        fetch.update(phase=phase,context=context,pc=pc,address=address,fetch=dict(physical=address,cached=True))
        append(fetch)
        selected=fresh if word==13 else old
        frame=selected['cache_line']
        if word==13:
            burst=copy.deepcopy(next(e for e in events if e['kind']=='cache_burst_read'))
            append(burst,phase=phase,context=context,pc=pc,cache_line=frame);append(events[-1],kind='cache_fill')
        append(fetch,kind='ram_fetch_end',value=word,cache_line=frame)
        begin=append(cpu,kind='cpu_begin',phase=phase,context=decoder,pc=pc,word=word)
        if word==CACHE:
            operation=copy.deepcopy(expected['cache_invalidations'][0]['operation'])
            operation['before']=copy.deepcopy(frame);operation['after']=copy.deepcopy(frame);operation['after']['tag_key'] &= ~1
            append(next(e for e in events if e['kind']=='cache_operation'),phase=phase,context=decoder,pc=pc,cache_operation=operation)
            expected['cache_invalidations'].append(dict(decoder_context=323,ordinal=324,physical=0x6028,
                operation=operation,hit=True,ended_fill=292))
        else:
            before=dict(pc=pc,bev=False,exl=False,erl=False,kernel_mode='bits32',kernel=True,cause=0,
                branch_delay=False,epc=0,delay_slot=False)
            after=dict(before,pc=ROOT_PC,exl=True,cause=9,epc=pc)
            begin['exception_state']=before
            append(read,kind='exception_transfer',phase=phase,context=decoder,pc=pc,word=word,address=0,bytes=0,value=0,exception_state=after)
            expected['exception_roots']=[dict(trigger_context=331,transfer_ordinal=332,before=before,after=after,
                root=dict(input=dict(class_='general'),vector_class='general',root=ROOT_PC),fetch_context=334,decoder_context=338)]
            expected['exception_roots'][0]['root']['input']=dict(class_='general',bev=False,exl=False,kernel_mode='bits32')
            expected['exception_roots'][0]['root']['input']['class']=expected['exception_roots'][0]['root']['input'].pop('class_')
        append(cpu,phase=phase,context=decoder,pc=pc,word=word)
        lane=address&31
        expected['cached_fetches'].append(dict(fetch_context=context,end_ordinal=context+(3 if word==13 else 1),
            decoder_context=decoder,pc=pc,physical=address,word=word,burst_ordinal=selected['burst_ordinal'],
            fill_ordinal=selected['fill_ordinal'],origins=copy.deepcopy(selected['source_bytes'][lane:lane+4])))
    expected['cache_fills'].append(fresh)
    fetch.update(phase=49,context=334,pc=ROOT_PC,address=0x180,fetch=dict(physical=0x180,cached=True))
    append(fetch)
    frame=dict(slot=12,tag_key=1,index=0x180,words=[0]*8)
    burst=copy.deepcopy(next(e for e in events if e['kind']=='cache_burst_read'))
    append(burst,phase=49,context=334,pc=ROOT_PC,address=0x180,cache_line=frame);append(events[-1],kind='cache_fill')
    append(fetch,kind='ram_fetch_end',value=0,cache_line=frame)
    append(cpu,kind='cpu_begin',phase=49,context=338,pc=ROOT_PC,word=0);append(events[-1],kind='cpu_end')
    parents=[dict(kind='unknown',cut_ordinal=None) for _ in range(32)]
    parents[:4]=[dict(kind='cpu_copy',write_ordinal=307,source_offset=n) for n in range(4)]
    expected['cache_fills'].append(dict(fetch_context=334,burst_ordinal=335,fill_ordinal=336,
        physical_line=0x180,cache_line=frame,source_bytes=parents))
    expected['cached_fetches'].append(dict(fetch_context=334,end_ordinal=337,decoder_context=338,pc=ROOT_PC,
        physical=0x180,word=0,burst_ordinal=335,fill_ordinal=336,origins=parents[:4]))
    return events,definitions,expected


def expected_events():
    events,definitions,_=build();return events,definitions


def replay(events,definitions):
    source,defs,expected=build();assert events==source and definitions==defs;return expected


def inspect(run):
    events,definitions,expected=build()
    assert run['events']==events,'complete writer/BREAK/root/handler census'
    assert run['initial_pending']==INITIAL
    for field in ('initial_ram','final_ram','final_dmem','initial_imem','final_imem'):assert run[field]==expected[field],field
    assert run['initial_dmem']==list(bytes.fromhex('340800aaaaee7722')+bytes(4088))
    starts=[e for e in events if e['kind']=='cpu_begin'];ends=[e for e in events if e['kind']=='cpu_end']
    assert run['steps']==[dict(phase=a['phase'],index=i,word=a['word'],pc=a['pc'],before=a['gpr'],after=b['gpr']) for i,(a,b) in enumerate(zip(starts,ends))]
    source={key:run[key] for key in ('initial_dmem','initial_imem','final_dmem','final_imem','steps','events','initial_pending')}
    source.update(format=FORMAT,profile=PROFILE,ram=dict(start=RAM_START,initial=run['initial_ram'],final_bytes=run['final_ram']))
    return source,definitions


def compare_report(report,definitions):
    _,defs,expected=build();assert definitions==defs
    assert report['rsp_definitions']==defs and report['imem_fetches']==expected['imem_fetches']
    assert report['exception_roots']==expected['exception_roots']
    graph=report['dma_consumption']
    for field,key in (('writes','writers'),('fetches','fetches'),('promoted_requests','requests'),
        ('imem_installs','installs'),('dmem_installs','dmem_installs'),('pending_commits','pending_commits'),
        ('cache_fills','cache_fills'),('cached_fetches','cached_fetches'),('cache_invalidations','cache_invalidations'),('cpu_writes','cpu_writes')):
        assert graph[field]==expected[key],field
    assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
