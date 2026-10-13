"""Independent pending-register mutations on the complete producer/fetch clock."""
from pathlib import Path
import copy
import importlib.util
ROOT=Path(__file__).resolve().parents[2]
FORMAT='plaid-rsp-cpu-imem-history-v8'
PROFILE='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-mutable-pending-dma-consumption-v8'
INITIAL=dict(bank=0,descriptor=dict(pbus=0,dram=0,length=0,count=0,skip=0))


def prior():
    spec=importlib.util.spec_from_file_location('dmem_model',ROOT/'spikes/064-dma-dmem-ingress-rsp-load/verify.py')
    model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)
    return model


def remap(data,mapping,key=None):
    identities={'context','read_ordinal','write_ordinal','cut_ordinal','promote_context',
        'decoder_context','fetch_context','begin_ordinal','end_ordinal','complete_ordinal'}
    if isinstance(data,dict):return {k:remap(v,mapping,k) for k,v in data.items()}
    if isinstance(data,list):return [mapping[v] if key=='write_ordinals' else remap(v,mapping) for v in data]
    return mapping[data] if key in identities and data is not None and data else data


def build():
    base=prior();old,definitions=base.expected_events();expected=base.replay(old,definitions)
    events=[];mapping={};snapshot=copy.deepcopy(INITIAL);direction=None;commit=None
    pbus_writer=dram_writer=None;commits=[];parents={}
    def append(event):
        event=copy.deepcopy(event);event['ordinal']=len(events)+1;events.append(event);return event
    def pending(reg,value,template):
        nonlocal direction,commit,pbus_writer,dram_writer
        descriptor=snapshot['descriptor'];ordinal=len(events)+1
        if reg==0:
            descriptor['pbus']=value&0xff8;snapshot['bank']=(value>>12)&1;pbus_writer=ordinal
            if direction and direction!='dmem_egress':direction='imem_ingress' if snapshot['bank'] else 'dmem_ingress'
        elif reg==1:descriptor['dram']=value&0xfffff8;dram_writer=ordinal
        else:
            descriptor.update(length=value&0xff8,count=(value>>12)&255,skip=(value>>20)&0xff8)
            direction='dmem_egress' if reg==3 else 'imem_ingress' if snapshot['bank'] else 'dmem_ingress'
            commits.append(dict(commit_ordinal=ordinal,superseded_commit=commit));commit=ordinal
        e=copy.deepcopy(template)
        e.update(kind='dma_pending_write',context=ordinal,address=reg,bank=snapshot['bank'],offset=descriptor['pbus'],
            bytes=4,value=value,cpu=True,dma=copy.deepcopy(descriptor),pending_full=commit is not None)
        e.pop('dma_direction',None)
        if direction:e['dma_direction']=direction
        return append(e)
    def promote(event):
        nonlocal direction,commit
        assert commit and event['dma']==snapshot['descriptor'] and event['bank']==snapshot['bank'] and event['dma_direction']==direction
        parents[event['ordinal']]=dict(commit_ordinal=commit,pbus_write_ordinal=pbus_writer,dram_write_ordinal=dram_writer)
        commit=direction=None
    for original in old:
        if original['kind']=='dma_promote':
            pending(0,original['dma']['pbus']|(original['bank']<<12),original)
            pending(1,original['dma']['dram'],original)
            pending(3 if original['dma_direction']=='dmem_egress' else 2,0,original)
        event=append(original);mapping[original['ordinal']]=event['ordinal']
        if event['kind']=='dma_promote':promote(event)
    for event in events:
        if event['kind']!='dma_pending_write':event['context']=mapping.get(event['context'],event['context'])
    expected=remap(expected,mapping);definitions=remap(definitions,mapping)
    for request in expected['requests']:request['pending_provenance']=parents[request['promote_context']]
    # A running request, B pending, equal length recommit C, then address mutation.
    template=copy.deepcopy(events[mapping[143]-1]);template.update(phase=22)
    pending(0,0x1340,template);pending(1,0x6028,template);pending(2,0,template)
    a=copy.deepcopy(template);a.update(context=len(events)+1,address=0x6028,bank=1,offset=0x340,
        dma=dict(pbus=0x340,dram=0x6028,length=0,count=0,skip=0),dma_direction='imem_ingress')
    a=append(a);promote(a)
    pending(0,0x1380,template);pending(1,0x6028,template);pending(2,0,template)
    pending(2,0,template);pending(0,0x13c0,template);pending(1,0x6028,template)
    def drain(start):
        read=copy.deepcopy(start);read.pop('dma_direction');read.update(kind='imem_dma_read',bytes=8,value=0xaaee7722)
        read=append(read)
        write=append(dict(read,kind='imem_dma_write'))
        complete=copy.deepcopy(start);complete.pop('dma');complete.update(kind='dma_complete',address=0x6030,offset=start['offset']+8)
        complete=append(complete)
        expected['installs'].append(dict(promote_context=start['context'],read_ordinal=read['ordinal'],write_ordinal=write['ordinal'],
            descriptor=start['dma'],value=0xaaee7722,
            source_bytes=[dict(kind='sp_dma',write_ordinal=mapping[55+n//4],source_offset=n) for n in range(8)]))
        expected['requests'].append(dict(promote_context=start['context'],complete_ordinal=complete['ordinal'],
            descriptor=start['dma'],write_ordinals=[write['ordinal']],direction='imem_ingress',pending_provenance=parents[start['ordinal']]))
        offset=start['offset'];expected['final_imem'][offset:offset+8]=list((0xaaee7722).to_bytes(8,'big'))
        return read,write
    drain(a)
    b=copy.deepcopy(a);b.update(context=len(events)+1,offset=0x3c0,dma=dict(pbus=0x3c0,dram=0x6028,length=0,count=0,skip=0))
    b=append(b);promote(b);read,write=drain(b)
    begin=copy.deepcopy(events[mapping[150]-1]);begin.update(context=len(events)+1,phase=23,pc=0x3c0,next=0x3c0,word=0)
    # The prior LW only rewrites r4 with zero, so the GPR snapshot is unchanged.
    begin=append(begin);append(dict(begin,kind='rsp_end',next=0x3c4))
    expected['imem_fetches'].append(dict(context=begin['context'],pc=0x3c0,word=0,
        origins=[dict(kind='imem_dma',promote_context=b['context'],read_ordinal=read['ordinal'],write_ordinal=write['ordinal'],
            source=0x6028+n,parent=dict(kind='sp_dma',write_ordinal=mapping[55],source_offset=n)) for n in range(4)]))
    expected['pending_commits']=commits
    return events,definitions,expected


def expected_events():
    events,definitions,_=build();return events,definitions


def replay(events,definitions):
    expected_events,expected_definitions,expected=build()
    assert events==expected_events and definitions==expected_definitions
    return expected


def inspect(run):
    events,definitions,expected=build()
    assert run['events']==events,'complete pending/producer/read/install/fetch census'
    assert run['initial_pending']==INITIAL
    for field in ('initial_ram','final_ram','final_dmem','initial_imem','final_imem'):assert run[field]==expected[field],field
    assert run['initial_dmem']==list(bytes.fromhex('340800aaaaee7722')+bytes(4088))
    starts=[e for e in events if e['kind']=='cpu_begin'];ends=[e for e in events if e['kind']=='cpu_end']
    assert run['steps']==[dict(phase=a['phase'],index=i,word=a['word'],pc=a['pc'],before=a['gpr'],after=b['gpr']) for i,(a,b) in enumerate(zip(starts,ends))]
    source={key:run[key] for key in ('initial_dmem','initial_imem','final_dmem','final_imem','steps','events','initial_pending')}
    source.update(format=FORMAT,profile=PROFILE,ram=dict(start=0x6000,initial=run['initial_ram'],final_bytes=run['final_ram']))
    return source,definitions


def compare_report(report,definitions):
    _,expected_definitions,expected=build();assert definitions==expected_definitions
    assert report['rsp_definitions']==definitions and report['imem_fetches']==expected['imem_fetches']
    graph=report['dma_consumption']
    for field,key in (('writes','writers'),('fetches','fetches'),('promoted_requests','requests'),
        ('imem_installs','installs'),('dmem_installs','dmem_installs'),('pending_commits','pending_commits')):
        assert graph[field]==expected[key],field
    assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
