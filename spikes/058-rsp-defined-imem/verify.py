"""Independent full census for the arithmetic prefix and retained copy fixture."""
from pathlib import Path
import copy
import importlib.util

ROOT = Path(__file__).resolve().parents[2]
FORMAT = 'plaid-rsp-cpu-imem-history-v1'
PROFILE = 'ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-rsp-cpu-imem-scalar-definitions-sbv2e0-v1'


def expected_events():
    spec = importlib.util.spec_from_file_location('legacy_census', ROOT/'spikes/047-ares-rsp-cpu-imem-compose/verify.py')
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)
    events = legacy.fixture_events()
    def replace(value):
        if isinstance(value, dict): return {k:replace(v) for k,v in value.items()}
        if isinstance(value, list): return [replace(v) for v in value]
        return 0x3344 if value == 0x11223344 else value
    events = replace(events)
    for event in events:
        if event['phase'] in (1,4) and event['kind']=='rsp_sink' and event['offset']<2:
            event['value'] = 0
        if event['rgpr']: event['rgpr'][3] = 0x3344
        if event['phase']==1:
            event['pc'] += 20
            if event['kind'] in ('rsp_begin','rsp_end'): event['next'] += 20
        event['ordinal'] += 10
        if event['context']: event['context'] += 10
    regs = [0]*32
    regs[2] = 0x13579bdf
    prefix = []
    definitions = []
    parents = {}
    for index,word in enumerate((0x3400ffff,0x34023344,0x34023344,0x00401821,0x00601021)):
        context = len(prefix)+1
        pc = 0x100+index*4
        before = regs[:]
        rs,rt,rd = word>>21 & 31,word>>16 & 31,word>>11 & 31
        def parent(register):
            if register==0: return dict(kind='architectural_zero')
            if register in parents: return dict(kind='definition',context=parents[register])
            return dict(kind='captured_input',register=register,value=before[register])
        if word>>26==13:
            target,value = rt,before[rs] | (word & 65535)
            expression = dict(kind='ori',source=parent(rs),immediate=word & 65535)
        else:
            target,value = rd,(before[rs]+before[rt]) & 0xffffffff
            expression = dict(kind='addu',left=parent(rs),right=parent(rt))
        if target:
            regs[target]=value
            definitions.append(dict(context=context,phase=1,pc=pc,word=word,register=target,
                value=value,expression=expression))
            parents[target]=context
        begin = copy.deepcopy(events[0])
        begin.update(kind='rsp_begin',ordinal=context,context=context,pc=pc,next=pc,
            word=word,rgpr=before)
        end = copy.deepcopy(begin)
        end.update(kind='rsp_end',ordinal=context+1,next=pc+4,rgpr=regs[:])
        prefix.extend((begin,end))
    return prefix+events,definitions


def inspect(run):
    events,definitions = expected_events()
    assert run['events']==events, 'complete independent instruction/effect census'
    starts = [e for e in events if e['kind']=='cpu_begin']
    ends = [e for e in events if e['kind']=='cpu_end']
    expected_steps = [dict(phase=a['phase'],index=i,word=a['word'],pc=a['pc'],before=a['gpr'],after=b['gpr'])
        for i,(a,b) in enumerate(zip(starts,ends))]
    assert run['steps']==expected_steps, 'independent CPU steps'
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
    first,second = report['copies'][:2]
    assert first['word']==second['word']==0x3344
    assert all(b['source_definition']==9 for b in first['source_bytes'])
    assert all('source_definition' not in b for b in second['source_bytes']), 'reentry must cut equal-value ancestry'
    assert not any(report[key] for key in ('source_ancestry_certified','mutation_coverage_certified',
        'imem_execution_certified','executable_lifetime_certified','native_complete'))
