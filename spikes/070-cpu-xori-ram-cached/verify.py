"""Independent complete source/transform/writer/resident/refill executable graph."""
from pathlib import Path
import copy
import importlib.util
ROOT=Path(__file__).resolve().parents[2]
FORMAT='plaid-rsp-cpu-imem-history-v13'
PROFILE='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-cpu-xori-ram-cached-consumption-v13'
INITIAL=dict(bank=0,descriptor=dict(pbus=0,dram=0,length=0,count=0,skip=0))
LW=0x8e080000
XORI=0x39080021
SW=0xae680000
CACHE=0xbe500000


def build():
    spec=importlib.util.spec_from_file_location('copy_model',ROOT/'spikes/069-cpu-copy-ram-cached/verify.py')
    prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
    events,definitions,expected=prior.build()
    extension=list(LW.to_bytes(4,'big')+XORI.to_bytes(4,'big')+SW.to_bytes(4,'big')+bytes(20))
    expected['initial_ram'].extend(extension);expected['final_ram'].extend(extension)
    def append(template,**changes):
        event=copy.deepcopy(template);event.update(changes,ordinal=len(events)+1);events.append(event);return event
    cpu=copy.deepcopy(events[-1])
    append(cpu,kind='cpu_reentry',phase=37,context=260,pc=0xffffffffa0006040)
    read=copy.deepcopy(next(e for e in events if e['kind']=='ram_read'))
    fetch=copy.deepcopy(next(e for e in events if e['kind']=='ram_fetch_begin'))
    for phase,context,decoder,address,word in [(37,261,264,0x6040,LW),(38,267,270,0x6044,XORI),(39,272,275,0x6048,SW)]:
        pc=0xffffffffa0000000+address
        fetch.update(phase=phase,context=context,pc=pc,address=address,fetch=dict(physical=address,cached=False))
        append(fetch);append(read,phase=phase,context=context,pc=pc,address=address,value=word)
        append(fetch,kind='ram_fetch_end',value=word)
        append(cpu,kind='cpu_begin',phase=phase,context=decoder,pc=pc,word=word)
        if word==LW:
            sp=copy.deepcopy(next(e for e in events if e['kind']=='sp_read'))
            append(sp,phase=phase,context=decoder,pc=pc,word=word,value=0)
        elif word==SW:
            append(read,kind='cpu_ram_write',phase=phase,context=decoder,pc=pc,word=word,address=0x6028,value=0x21)
        else:cpu['gpr'][8]=0x21
        append(cpu,phase=phase,context=decoder,pc=pc,word=word)
        expected['fetches'].append(dict(fetch_context=context,read_ordinal=context+1,decoder_context=decoder,
            pc=pc,physical=address,word=word,origins=[dict(kind='unknown',cut_ordinal=None) for _ in range(4)]))
    parent=copy.deepcopy(expected['cpu_writes'][0]['copy_parent'])
    parent.update(load_context=264,read_ordinal=265,transform=dict(decoder_context=270,
        pc=0xffffffffa0006044,word=XORI,source_value=0,result_value=0x21))
    expected['cpu_writes'].append(dict(decoder_context=275,write_ordinal=276,destination=0x6028,
        source_register=8,register_value=0x21,word=0x21,copy_parent=parent))
    expected['final_ram'][0x28:0x2c]=[0,0,0,0x21]
    old=expected['cache_fills'][-1]
    fresh=copy.deepcopy(old);fresh['cache_line']['words'][2]=0x21
    fresh.update(fetch_context=290,burst_ordinal=291,fill_ordinal=292)
    fresh['source_bytes'][8:12]=[dict(kind='cpu_copy',write_ordinal=276,source_offset=n) for n in range(4)]
    for phase,context,decoder,address,word in [(40,279,281,0x6028,0),(41,284,286,0x6034,CACHE),(42,290,294,0x6028,0x21)]:
        pc=0xffffffff80000000+address
        append(cpu,kind='cpu_reentry',phase=phase,context=context-1,pc=pc,word=0)
        fetch.update(phase=phase,context=context,pc=pc,address=address,fetch=dict(physical=address,cached=True))
        append(fetch)
        frame=fresh['cache_line'] if phase==42 else old['cache_line']
        if phase==42:
            burst=copy.deepcopy(next(e for e in events if e['kind']=='cache_burst_read'))
            append(burst,phase=phase,context=context,pc=pc,cache_line=frame)
            append(events[-1],kind='cache_fill')
        append(fetch,kind='ram_fetch_end',value=word,cache_line=frame)
        append(cpu,kind='cpu_begin',phase=phase,context=decoder,pc=pc,word=word)
        if word==CACHE:
            operation=copy.deepcopy(expected['cache_invalidations'][0]['operation'])
            operation['before']=copy.deepcopy(frame);operation['after']=copy.deepcopy(frame);operation['after']['tag_key'] &= ~1
            template=next(e for e in events if e['kind']=='cache_operation')
            append(template,phase=phase,context=decoder,pc=pc,cache_operation=operation)
            expected['cache_invalidations'].append(dict(decoder_context=286,ordinal=287,physical=0x6028,
                operation=operation,hit=True,ended_fill=256))
        append(cpu,phase=phase,context=decoder,pc=pc,word=word)
        selected=fresh if phase==42 else old
        lane=address&31
        expected['cached_fetches'].append(dict(fetch_context=context,end_ordinal=context+(3 if phase==42 else 1),
            decoder_context=decoder,pc=pc,physical=address,word=word,burst_ordinal=selected['burst_ordinal'],
            fill_ordinal=selected['fill_ordinal'],origins=copy.deepcopy(selected['source_bytes'][lane:lane+4])))
    expected['cache_fills'].append(fresh)
    return events,definitions,expected


def expected_events():
    events,definitions,_=build();return events,definitions


def replay(events,definitions):
    source,defs,expected=build();assert events==source and definitions==defs;return expected


def inspect(run):
    events,definitions,expected=build()
    assert run['events']==events,'complete XORI/CPU writer/resident/invalidation/refill census'
    assert run['initial_pending']==INITIAL
    for field in ('initial_ram','final_ram','final_dmem','initial_imem','final_imem'):assert run[field]==expected[field],field
    assert run['initial_dmem']==list(bytes.fromhex('340800aaaaee7722')+bytes(4088))
    starts=[e for e in events if e['kind']=='cpu_begin'];ends=[e for e in events if e['kind']=='cpu_end']
    assert run['steps']==[dict(phase=a['phase'],index=i,word=a['word'],pc=a['pc'],before=a['gpr'],after=b['gpr']) for i,(a,b) in enumerate(zip(starts,ends))]
    source={key:run[key] for key in ('initial_dmem','initial_imem','final_dmem','final_imem','steps','events','initial_pending')}
    source.update(format=FORMAT,profile=PROFILE,ram=dict(start=0x6000,initial=run['initial_ram'],final_bytes=run['final_ram']))
    return source,definitions


def compare_report(report,definitions):
    _,defs,expected=build();assert definitions==defs
    assert report['rsp_definitions']==defs and report['imem_fetches']==expected['imem_fetches']
    graph=report['dma_consumption']
    for field,key in (('writes','writers'),('fetches','fetches'),('promoted_requests','requests'),
        ('imem_installs','installs'),('dmem_installs','dmem_installs'),('pending_commits','pending_commits'),
        ('cache_fills','cache_fills'),('cached_fetches','cached_fetches'),('cache_invalidations','cache_invalidations'),('cpu_writes','cpu_writes')):
        assert graph[field]==expected[key],field
    assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
