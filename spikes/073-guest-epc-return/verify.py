"""Independent guest EPC read/write/ERET and executable ancestry graph."""
from pathlib import Path
import copy
import importlib.util
ROOT=Path(__file__).resolve().parents[2]
FORMAT='plaid-rsp-cpu-imem-history-v16'
PROFILE='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-guest-epc-return-consumption-v16'
INITIAL=dict(bank=0,descriptor=dict(pbus=0,dram=0,length=0,count=0,skip=0))
RAM_START=0
ROOT_PC=0xffffffff80000180
LW=0x8e080000
SW=0xae680000
CACHE=0xbe500000
ERET=0x42000018


def build():
    spec=importlib.util.spec_from_file_location('root_model',ROOT/'spikes/072-live-epc-handler-return/verify.py')
    prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
    events,definitions,expected=prior.build()
    v15=copy.deepcopy(expected)
    # Retain the original prefix through handler invalidation and its CpuEnd.
    events=events[:354]
    words=[0,LW,SW,CACHE,0x40087000,0x40887000,ERET,0]
    code=list(b''.join(word.to_bytes(4,'big') for word in words[1:7]))
    for field in ('initial_ram','final_ram'):expected[field][0x184:0x19c]=code
    for event in events:
        if event.get('cache_line',{}).get('slot')==12:event['cache_line']['words']=words[:]
    expected['cache_fills']=expected['cache_fills'][:-1]
    expected['cache_fills'][-1]['cache_line']['words']=words[:]
    def append(template,**changes):
        event=copy.deepcopy(template);event.update(changes,ordinal=len(events)+1);events.append(event);return event
    cpu=copy.deepcopy(events[-1]);cpu['gpr'][8]=0
    fetch=copy.deepcopy(events[349]);fetch.pop('cache_line',None)
    frame=copy.deepcopy(expected['cache_fills'][-1]['cache_line'])
    for key in ('cpu_writes','cache_invalidations','cached_fetches'):
        expected[key]=copy.deepcopy(v15[key])
    expected['cached_fetches']=expected['cached_fetches'][:-2] # replace ERET/returned fetch
    expected['final_ram'][0x6028:0x602c]=[0]*4
    expected['epc_reads']=[];expected['epc_writes']=[]
    for phase,context,decoder,address,word in [(53,355,357,0x190,0x40087000),
            (54,360,362,0x194,0x40887000),(55,365,367,0x198,ERET)]:
        pc=0xffffffff80000000+address
        fetch.update(phase=phase,context=context,pc=pc,address=address,fetch=dict(physical=address,cached=True))
        append(fetch);append(fetch,kind='ram_fetch_end',value=word,cache_line=frame)
        begin=append(cpu,kind='cpu_begin',phase=phase,context=decoder,pc=pc,word=word)
        state=copy.deepcopy(expected['exception_roots'][0]['after']);state['pc']=pc
        before=dict(state=state,interrupt_enable=False,llbit=False)
        transfer=copy.deepcopy(next(e for e in events if e['kind']=='exception_transfer'));transfer.pop('exception_state')
        if word==ERET:
            after=copy.deepcopy(before);after['state'].update(pc=0xffffffff80006028,exl=False)
            begin['return_state']=before
            append(transfer,kind='return_transfer',phase=phase,context=decoder,pc=pc,word=word,return_state=after)
            expected['eret_returns']=[dict(epc_transfer_ordinal=332,epc_write_ordinal=363,decoder_context=367,
                transfer_ordinal=368,before=before,after=after,fetch_context=370,target_decoder_context=374)]
        else:
            begin['epc_state']=before
            append(transfer,kind='epc_read' if word==0x40087000 else 'epc_write',phase=phase,context=decoder,
                pc=pc,word=word,epc_state=before)
            if word==0x40087000:
                cpu['gpr'][8]=0xffffffff80006028
                expected['epc_reads'].append(dict(decoder_context=357,read_ordinal=358,register=8,
                    value=cpu['gpr'][8],epc_transfer_ordinal=332,epc_write_ordinal=None,before=before,after=before))
            else:
                expected['epc_writes'].append(dict(decoder_context=362,write_ordinal=363,register=8,
                    value=cpu['gpr'][8],read_parent=copy.deepcopy(expected['epc_reads'][0]),before=before,after=before))
        append(cpu,phase=phase,context=decoder,pc=pc,word=word)
        lane=address&31
        expected['cached_fetches'].append(dict(fetch_context=context,end_ordinal=context+1,decoder_context=decoder,
            pc=pc,physical=address,word=word,burst_ordinal=335,fill_ordinal=336,
            origins=copy.deepcopy(expected['cache_fills'][-1]['source_bytes'][lane:lane+4])))
    fresh=copy.deepcopy(v15['cache_fills'][-1]);fresh.update(fetch_context=370,burst_ordinal=371,fill_ordinal=372)
    fetch.update(phase=56,context=370,pc=0xffffffff80006028,address=0x6028,fetch=dict(physical=0x6028,cached=True))
    append(fetch)
    burst=copy.deepcopy(next(e for e in events if e['kind']=='cache_burst_read'))
    append(burst,phase=56,context=370,pc=fetch['pc'],cache_line=fresh['cache_line']);append(events[-1],kind='cache_fill')
    append(fetch,kind='ram_fetch_end',value=0,cache_line=fresh['cache_line'])
    append(cpu,kind='cpu_begin',phase=56,context=374,pc=fetch['pc'],word=0);append(events[-1],kind='cpu_end')
    expected['cache_fills'].append(fresh)
    expected['cached_fetches'].append(dict(fetch_context=370,end_ordinal=373,decoder_context=374,pc=fetch['pc'],
        physical=0x6028,word=0,burst_ordinal=371,fill_ordinal=372,origins=fresh['source_bytes'][8:12]))
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
    source.update(format=FORMAT,profile=PROFILE,ram=dict(start=RAM_START,initial=run['initial_ram'],final_bytes=run['final_ram']))
    return source,definitions


def compare_report(report,definitions):
    _,defs,expected=build();assert definitions==defs
    assert report['rsp_definitions']==defs and report['imem_fetches']==expected['imem_fetches']
    assert report['exception_roots']==expected['exception_roots'] and report['eret_returns']==expected['eret_returns']
    assert report['epc_reads']==expected['epc_reads'] and report['epc_writes']==expected['epc_writes']
    graph=report['dma_consumption']
    for field,key in (('writes','writers'),('fetches','fetches'),('promoted_requests','requests'),
        ('imem_installs','installs'),('dmem_installs','dmem_installs'),('pending_commits','pending_commits'),
        ('cache_fills','cache_fills'),('cached_fetches','cached_fetches'),('cache_invalidations','cache_invalidations'),('cpu_writes','cpu_writes')):
        assert graph[field]==expected[key],field
    assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
