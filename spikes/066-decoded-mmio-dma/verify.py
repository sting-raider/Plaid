"""Independent decoded SW length-write through DMA to actual RSP consumption."""
from pathlib import Path
import copy
import importlib.util
ROOT=Path(__file__).resolve().parents[2]
FORMAT='plaid-rsp-cpu-imem-history-v9'
PROFILE='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-decoded-mmio-dma-consumption-v9'
INITIAL=dict(bank=0,descriptor=dict(pbus=0,dram=0,length=0,count=0,skip=0))
SW=(0x2b<<26)|(17<<21)|8


def prior():
    spec=importlib.util.spec_from_file_location('pending_model',ROOT/'spikes/065-mutable-pending-dma/verify.py')
    model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)
    return model


def build():
    events,definitions,expected=prior().build()
    for event in events:
        if event['gpr']:event['gpr'][17]=0xffffffffa4040000
    def append(template,**changes):
        event=copy.deepcopy(template);event.update(changes,ordinal=len(events)+1);events.append(event);return event
    pending=copy.deepcopy(next(e for e in events if e['kind']=='dma_pending_write'))
    pending.update(phase=24,pc=0xffffffffa000602c,bank=1,offset=0x3e0,
        dma=dict(pbus=0x3e0,dram=0x6028,length=0,count=0,skip=0),pending_full=False)
    pending.pop('dma_direction',None)
    append(pending,context=181,address=0,value=0x13e0)
    append(pending,context=182,address=1,value=0x6028)
    seed=copy.deepcopy(next(e for e in events if e['kind']=='ram_write'));seed.pop('dma')
    append(seed,context=0,phase=24,pc=0xffffffffa000602c,address=0x602c,offset=0,value=SW)
    fetch=copy.deepcopy(next(e for e in events if e['kind']=='ram_fetch_begin'))
    fetch.update(phase=24,context=184,pc=0xffffffffa000602c,address=0x602c,fetch=dict(physical=0x602c,cached=False))
    append(fetch)
    read=copy.deepcopy(next(e for e in events if e['kind']=='ram_read'))
    append(read,phase=24,context=184,pc=0xffffffffa000602c,address=0x602c,value=SW)
    append(fetch,kind='ram_fetch_end',value=SW)
    cpu=copy.deepcopy(next(e for e in reversed(events) if e['kind']=='cpu_end'))
    append(cpu,kind='cpu_begin',phase=24,context=187,pc=0xffffffffa000602c,word=SW)
    append(pending,context=187,address=2,value=0,word=SW,pending_full=True,dma_direction='imem_ingress')
    promote=copy.deepcopy(next(e for e in reversed(events) if e['kind']=='dma_promote'))
    append(promote,phase=24,context=189,offset=0x3e0,dma=pending['dma'])
    append(cpu,phase=24,context=187,pc=0xffffffffa000602c,word=SW)
    ingress=copy.deepcopy(next(e for e in reversed(events) if e['kind']=='imem_dma_read'))
    append(ingress,phase=25,context=189,pc=0xffffffffa0006030,offset=0x3e0,value=SW,dma=pending['dma'])
    append(events[-1],kind='imem_dma_write')
    complete=copy.deepcopy(next(e for e in reversed(events) if e['kind']=='dma_complete'))
    append(complete,phase=25,context=189,pc=0xffffffffa0006030,offset=0x3e8)
    rsp=copy.deepcopy(next(e for e in reversed(events) if e['kind']=='rsp_begin'))
    append(rsp,phase=26,context=194,pc=0x3e0,next=0x3e0)
    append(events[-1],kind='rsp_end',next=0x3e4)
    expected['final_ram'][-4:]=list(SW.to_bytes(4,'big'))
    expected['final_imem'][0x3e0:0x3e8]=list(SW.to_bytes(8,'big'))
    parents=[dict(kind='sp_dma',write_ordinal=58,source_offset=n) for n in range(4)]+[dict(kind='unknown',cut_ordinal=183) for _ in range(4)]
    expected['fetches'].append(dict(fetch_context=184,read_ordinal=185,decoder_context=187,
        pc=0xffffffffa000602c,physical=0x602c,word=SW,origins=parents[4:]))
    expected['installs'].append(dict(promote_context=189,read_ordinal=191,write_ordinal=192,
        descriptor=pending['dma'],value=SW,source_bytes=parents))
    expected['requests'].append(dict(promote_context=189,complete_ordinal=193,descriptor=pending['dma'],
        write_ordinals=[192],direction='imem_ingress',pending_provenance=dict(commit_ordinal=188,
            pbus_write_ordinal=181,dram_write_ordinal=182,commit_decoder_context=187)))
    expected['pending_commits'].append(dict(commit_ordinal=188,superseded_commit=None,decoder_context=187))
    expected['imem_fetches'].append(dict(context=194,pc=0x3e0,word=0,origins=[dict(kind='imem_dma',
        promote_context=189,read_ordinal=191,write_ordinal=192,source=0x6028+n,parent=parents[n]) for n in range(4)]))
    return events,definitions,expected


def expected_events():
    events,definitions,_=build();return events,definitions


def replay(events,definitions):
    source,defs,expected=build();assert events==source and definitions==defs;return expected


def inspect(run):
    events,definitions,expected=build()
    assert run['events']==events,'complete decoded SW/pending/promotion/install/fetch census'
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
        ('imem_installs','installs'),('dmem_installs','dmem_installs'),('pending_commits','pending_commits')):
        assert graph[field]==expected[key],field
    assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
