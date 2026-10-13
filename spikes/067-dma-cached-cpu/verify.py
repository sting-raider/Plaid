"""Independent RAM burst/fill parents and stale-resident CPU consumption."""
from pathlib import Path
import copy
import importlib.util
ROOT=Path(__file__).resolve().parents[2]
FORMAT='plaid-rsp-cpu-imem-history-v10'
PROFILE='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-dma-cached-cpu-consumption-v10'
INITIAL=dict(bank=0,descriptor=dict(pbus=0,dram=0,length=0,count=0,skip=0))


def prior():
    spec=importlib.util.spec_from_file_location('decoded_model',ROOT/'spikes/066-decoded-mmio-dma/verify.py')
    model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)
    return model


def build():
    events,definitions,expected=prior().build()
    expected['initial_ram'].extend([0]*16);expected['final_ram'].extend([0]*16)
    frame=dict(slot=257,tag_key=0x6001,index=0x20,words=[0x01404021,0xae08100c,0,0xae200008,0,0,0,0])
    def append(template,**changes):
        event=copy.deepcopy(template);event.update(changes,ordinal=len(events)+1);events.append(event);return event
    fetch=copy.deepcopy(next(e for e in events if e['kind']=='ram_fetch_begin'))
    fetch.update(phase=27,context=197,pc=0xffffffff80006030,address=0x6030,fetch=dict(physical=0x6030,cached=True))
    seed=copy.deepcopy(next(e for e in reversed(events) if e['kind']=='cpu_end'))
    append(seed,kind='cpu_reentry',phase=27,context=196,pc=0xffffffff80006030,word=0)
    append(fetch)
    burst=copy.deepcopy(fetch);burst.pop('fetch')
    burst.update(kind='cache_burst_read',address=0x6020,bytes=32,cache_line=frame)
    append(burst);append(burst,kind='cache_fill')
    append(fetch,kind='ram_fetch_end',cache_line=frame)
    cpu=copy.deepcopy(next(e for e in reversed(events) if e['kind']=='cpu_end'))
    cpu.update(phase=27,context=201,pc=0xffffffff80006030,word=0)
    append(cpu,kind='cpu_begin');append(cpu)
    write=copy.deepcopy(next(e for e in events if e['kind']=='ram_write'));write.pop('dma')
    append(write,context=0,phase=28,pc=0xffffffff80006034,address=0x6028,offset=0,value=13)
    seed=copy.deepcopy(cpu);seed.update(kind='cpu_reentry',context=204,phase=28,pc=0xffffffff80006028)
    append(seed)
    append(fetch,phase=28,context=205,pc=0xffffffff80006028,address=0x6028,fetch=dict(physical=0x6028,cached=True))
    append(events[-1],kind='ram_fetch_end',cache_line=frame)
    append(cpu,kind='cpu_begin',phase=28,context=207,pc=0xffffffff80006028)
    append(events[-1],kind='cpu_end')
    expected['final_ram'][0x28:0x2c]=[0,0,0,13]
    parents=[dict(kind='unknown',cut_ordinal=None) for _ in range(32)]
    parents[8:12]=[dict(kind='sp_dma',write_ordinal=58,source_offset=n) for n in range(4)]
    parents[12:16]=[dict(kind='unknown',cut_ordinal=183) for _ in range(4)]
    expected['cache_fills']=[dict(fetch_context=197,burst_ordinal=198,fill_ordinal=199,
        physical_line=0x6020,cache_line=frame,source_bytes=parents)]
    expected['cached_fetches']=[dict(fetch_context=context,end_ordinal=end,decoder_context=decoder,
        pc=pc,physical=address,word=0,burst_ordinal=198,fill_ordinal=199,origins=parents[address&31:(address&31)+4])
        for context,end,decoder,pc,address in [(197,200,201,0xffffffff80006030,0x6030),(205,206,207,0xffffffff80006028,0x6028)]]
    return events,definitions,expected


def expected_events():
    events,definitions,_=build();return events,definitions


def replay(events,definitions):
    source,defs,expected=build();assert events==source and definitions==defs;return expected


def inspect(run):
    events,definitions,expected=build()
    assert run['events']==events,'complete burst/fill/opaque reentry/cached decoder census'
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
        ('cache_fills','cache_fills'),('cached_fetches','cached_fetches')):
        assert graph[field]==expected[key],field
    assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
