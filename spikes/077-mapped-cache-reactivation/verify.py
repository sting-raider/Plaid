"""Independent nonidentity mapping/context/cache/root/return composition.

Uses the existing v19 protocol; no new admission policy or completeness claim.
"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('context_model', ROOT/'spikes/076-entryhi-context-mapped-root-return/verify.py')
prior = importlib.util.module_from_spec(spec); spec.loader.exec_module(prior)
FORMAT, PROFILE, INITIAL, RAM_START = prior.FORMAT, prior.PROFILE, prior.INITIAL, prior.RAM_START
ROOT_PC, LW, SW, CACHE, ERET = prior.ROOT_PC, prior.LW, prior.SW, prior.CACHE, prior.ERET
ROOT_CONTEXT, TRANSFORM_CONTEXT = prior.ROOT_CONTEXT + 10, prior.TRANSFORM_CONTEXT + 10
TLB_INITIAL = copy.deepcopy(prior.TLB_INITIAL)
STAGED = TLB_INITIAL['staged']; STAGED['virtual_address'] = 0xe000
FIELDS = prior.initial.FIELDS


def fingerprint(entry):
    raw = json.dumps({k: entry[k] for k in FIELDS}, separators=(',', ':')).encode()
    return dict(sha256=hashlib.sha256(raw).hexdigest())


def build():
    events, definitions, expected = prior.build()
    events, expected = json.loads(json.dumps(events)), json.loads(json.dumps(expected))
    keys = {'ordinal','context','decoder_context','trigger_context','transfer_ordinal','fetch_context','end_ordinal',
        'load_context','read_ordinal','write_ordinal','store_context','burst_ordinal','fill_ordinal','ended_fill',
        'epc_transfer_ordinal','epc_write_ordinal','cut_ordinal','begin_ordinal','target_decoder_context', 'context_write_ordinal'}
    def rebase(value):
        if isinstance(value, dict):
            for key, v in value.items():
                if key in keys and isinstance(v, int):
                    value[key] = v + (10 if v >= 355 else 5 if v >= 334 else 0)
                elif key == 'virtual_address' and v == 0x6000: value[key] = 0xe000
                elif key in ('pc','epc','register_value','source_value','result_value') and v in (0x6028,0x602c,0x6008,0x6007): value[key] = v + 0x8000
                elif key == 'value' and v in (0x6028,0x602c,0x6008,0x6007) and value.get('kind') not in ('dma_pending_write',): value[key] = v + 0x8000
                elif key == 'gpr' and v:
                    v[25:27] = [0xe008,0xe007]
                    if v[8] in (0x6028,0x602c): v[8] += 0x8000
                else: rebase(v)
        elif isinstance(value, list):
            for v in value: rebase(v)
    rebase(events); rebase(expected)
    for generation in expected['tlb_generations']:
        generation['staged_entry'] = fingerprint(STAGED)
        generation['after_entry'] = fingerprint(STAGED)
        if generation['same_entry_content']: generation['before_entry'] = fingerprint(STAGED)
    current = copy.deepcopy(TLB_INITIAL['entries']); current[0] = copy.deepcopy(STAGED)
    observation = dict(asid=7,kernel=True,bits=32,entries=current)
    seed_template = copy.deepcopy(events[332])
    end_template = copy.deepcopy(events[292])
    for first, phase, context_writer in ((334,48,None),(360,51,358)):
        seed = copy.deepcopy(seed_template)
        seed.update(kind='cpu_reentry',ordinal=first,context=first,phase=phase,pc=0xe028,word=0)
        begin = copy.deepcopy(end_template); begin.pop('cache_line')
        begin.update(kind='ram_fetch_begin',ordinal=first+1,context=first+1,phase=phase,pc=0xe028,value=0,mapping=copy.deepcopy(observation))
        end = copy.deepcopy(end_template)
        end.update(ordinal=first+2,context=first+1,phase=phase,pc=0xe028,value=0x21,mapping=copy.deepcopy(observation))
        decoder = copy.deepcopy(seed)
        decoder.update(kind='cpu_begin',ordinal=first+3,context=first+3,word=0x21)
        completed = copy.deepcopy(decoder); completed.update(kind='cpu_end',ordinal=first+4)
        position = next(i for i,e in enumerate(events) if e['ordinal']>first)
        events[position:position] = [seed,begin,end,decoder,completed]
        witness = dict(write_ordinal=332,selected_slot=0,current_asid=7,entry=copy.deepcopy(STAGED))
        if context_writer is not None: witness['context_write_ordinal'] = context_writer
        parents = [dict(kind='cpu_copy',write_ordinal=276,source_offset=n) for n in range(4)]
        expected['cached_fetches'].append(dict(fetch_context=first+1,end_ordinal=first+2,decoder_context=first+3,
            pc=0xe028,physical=0x6028,word=0x21,burst_ordinal=291,fill_ordinal=292,origins=parents,mapping=witness))
    expected['cached_fetches'].sort(key=lambda f:f['decoder_context'])
    assert [e['ordinal'] for e in events] == list(range(1,432))
    return events, definitions, expected


def expected_events():
    events, definitions, _ = build(); return events, definitions


def replay(events, definitions):
    source, defs, expected = build(); assert events == source and definitions == defs; return expected


def inspect(run):
    events, definitions, expected = build()
    assert run['events'] == events, 'complete mapped reactivation census'
    assert run['initial_pending'] == INITIAL and run['initial_tlb'] == TLB_INITIAL
    for field in ('initial_ram','final_ram','final_dmem','initial_imem','final_imem'): assert run[field] == expected[field], field
    assert run['initial_dmem'] == list(bytes.fromhex('340800aaaaee7722')+bytes(4088))
    starts = [e for e in events if e['kind']=='cpu_begin']; ends = [e for e in events if e['kind']=='cpu_end']
    assert run['steps'] == [dict(phase=a['phase'],index=i,word=a['word'],pc=a['pc'],before=a['gpr'],after=b['gpr']) for i,(a,b) in enumerate(zip(starts,ends))]
    source = {key:run[key] for key in ('initial_dmem','initial_imem','final_dmem','final_imem','steps','events','initial_pending','initial_tlb')}
    source.update(format=FORMAT,profile=PROFILE,ram=dict(start=RAM_START,initial=run['initial_ram'],final_bytes=run['final_ram']))
    return source, definitions


def compare_report(report, definitions):
    _, defs, expected = build(); assert definitions == defs
    for field in ('rsp_definitions','imem_fetches','exception_roots','eret_returns','epc_reads','epc_writes'):
        assert report[field] == (defs if field=='rsp_definitions' else expected[field]), field
    graph = report['dma_consumption']
    for field,key in (('writes','writers'),('fetches','fetches'),('promoted_requests','requests'),
        ('imem_installs','installs'),('dmem_installs','dmem_installs'),('pending_commits','pending_commits'),
        ('cache_fills','cache_fills'),('cached_fetches','cached_fetches'),('cache_invalidations','cache_invalidations'),
        ('cpu_writes','cpu_writes'),('tlb_generations','tlb_generations'),('context_writes','context_writes')):
        assert graph[field] == expected[key], field
    mapped = [f for f in graph['cached_fetches'] if 'mapping' in f]
    assert [f['word'] for f in mapped] == [0x21,0x21,13,0]
    assert mapped[0]['fill_ordinal'] == mapped[1]['fill_ordinal'] == 292
    assert 'context_write_ordinal' not in mapped[0]['mapping'] and mapped[1]['mapping']['context_write_ordinal'] == 358
    assert mapped[0]['physical'] == mapped[1]['physical'] == 0x6028 and mapped[0]['pc'] == mapped[1]['pc'] == 0xe028
    assert mapped[2]['fill_ordinal'] != 292 and mapped[2]['origins'][0]['write_ordinal'] == 318
    assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
