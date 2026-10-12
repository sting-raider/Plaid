"""Independent exact census: actual LW read identity, not equal-value inference."""
from pathlib import Path
import copy
import importlib.util

ROOT = Path(__file__).resolve().parents[2]
FORMAT = 'plaid-rsp-cpu-imem-history-v2'
PROFILE = 'ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-rsp-cpu-imem-word-read-definitions-sbv2e0-v2'


def expected_events():
    spec = importlib.util.spec_from_file_location('arithmetic_census',ROOT/'spikes/058-rsp-defined-imem/verify.py')
    prior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior)
    events,definitions = prior.expected_events()
    before = events[15]['rgpr'][:]
    after = before[:]
    after[4] = 0x3344
    begin = copy.deepcopy(events[10])
    begin.update(kind='rsp_begin',ordinal=17,context=17,pc=0x118,next=0x118,word=0x8c240000,rgpr=before)
    read = copy.deepcopy(begin)
    read.update(kind='rsp_read',ordinal=18,address=0,offset=0,bytes=4,value=0x3344,next=0,rgpr=[])
    end = copy.deepcopy(begin)
    end.update(kind='rsp_end',ordinal=19,next=0x11c,rgpr=after)
    added = [begin,read,end]
    begin = copy.deepcopy(begin)
    begin.update(ordinal=20,context=20,pc=0x11c,next=0x11c,word=0x00801021,rgpr=after)
    end = copy.deepcopy(begin)
    end.update(kind='rsp_end',ordinal=21,next=0x120)
    added.extend((begin,end))
    for event in copy.deepcopy(events[10:16]):
        event['ordinal'] += 11
        event['context'] += 11
        event['pc'] += 12
        if event['rgpr']: event['rgpr'][4] = 0x3344
        if event['kind'] in ('rsp_begin','rsp_end'): event['next'] += 12
        added.append(event)
    for event in events[16:]:
        event['ordinal'] += 11
        if event['context']: event['context'] += 11
        if event['rgpr']: event['rgpr'][4] = 0x3344
        if event['phase']==1:
            event['pc'] += 12
            event['next'] += 12
    events[16:16] = added
    definitions.append(dict(context=17,phase=1,pc=0x118,word=0x8c240000,register=4,value=0x3344,
        expression=dict(kind='dmem_word_load',read_ordinal=18,address=0,offset=0,payload=[0,0,0x33,0x44],
            origins=[dict(kind='rsp',context=11,pc=0x114,word=0xac220000,write_ordinal=12+n,source_definition=9) for n in range(4)])))
    definitions.append(dict(context=20,phase=1,pc=0x11c,word=0x00801021,register=2,value=0x3344,
        expression=dict(kind='addu',left=dict(kind='definition',context=17),right=dict(kind='architectural_zero'))))
    return events,definitions


def inspect(run):
    events,definitions = expected_events()
    assert run['events']==events, 'complete independent read/definition/effect census'
    starts = [e for e in events if e['kind']=='cpu_begin']
    ends = [e for e in events if e['kind']=='cpu_end']
    steps = [dict(phase=a['phase'],index=i,word=a['word'],pc=a['pc'],before=a['gpr'],after=b['gpr']) for i,(a,b) in enumerate(zip(starts,ends))]
    assert run['steps']==steps
    assert run['initial_dmem']==list(bytes.fromhex('340800aaaaee7722'))
    assert run['initial_imem']==list(bytes.fromhex('deadbeef')*5)
    assert run['final_dmem']==list(bytes.fromhex('aaee7722aaee7722'))
    assert run['final_imem']==list(bytes.fromhex('0000334400003344aaee7722aaee7722aaee7722'))
    source = {key:run[key] for key in ('initial_dmem','initial_imem','final_dmem','final_imem','steps','events')}
    source.update(format=FORMAT,profile=PROFILE)
    return source,definitions


def compare_report(report, definitions):
    assert report['rsp_definitions']==definitions
    assert len(report['copies'])==3
    assert all(b['source_definition']==20 for b in report['copies'][0]['source_bytes'])
    assert all('source_definition' not in b for b in report['copies'][1]['source_bytes'])
    assert not any(report[key] for key in ('source_ancestry_certified','mutation_coverage_certified',
        'imem_execution_certified','executable_lifetime_certified','native_complete'))
