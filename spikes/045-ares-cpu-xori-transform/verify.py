"""Strict three-context XORI provenance, explicitly separate from copy mode."""
from pathlib import Path
import copy
import importlib.util

spec = importlib.util.spec_from_file_location('copy_history_contract',
    Path(__file__).resolve().parents[1]/'044-ares-cpu-copy-dataflow/verify.py')
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)


def replay(data):
    contexts, _ = shared.replay(data, allow_xori=True)
    certificates = []
    for index in range(2, len(contexts)):
        load, transform, store = contexts[index-2:index+1]
        lop, _, lr, _ = shared.decode(load['begin']['word'])
        top, ts, tr, _ = shared.decode(transform['begin']['word'])
        sop, _, sr, _ = shared.decode(store['begin']['word'])
        if not (lop in (0x23, 0x27) and top == 0x0e and sop == 0x2b
                and lr != 0 and lr == ts == tr == sr
                and load['begin']['phase'] == transform['begin']['phase'] == store['begin']['phase']
                and len(load['scalars']) == 1):
            continue
        read, write = load['scalars'][0], store['scalars'][0]
        mask = transform['begin']['word'] & 0xffff
        assert write['value'] == read['value'] ^ mask
        certificates.append(dict(phase=store['begin']['phase'],
            load_context=load['begin']['context'], transform_context=transform['begin']['context'],
            store_context=store['begin']['context'], source=read['address'], destination=write['address'],
            source_word=read['value'], xor_imm=mask, result_word=write['value'],
            load_opcode='LW' if lop == 0x23 else 'LWU',
            byte_expr=[dict(source=read['address']+offset, destination=write['address']+offset,
                xor=(mask >> (8*(3-offset))) & 0xff) for offset in range(4)]))
    return contexts, certificates


def verify(data):
    contexts, certificates = replay(data)
    assert [(c['phase'], c['load_opcode'], c['source'], c['destination'], c['xor_imm'], c['result_word'])
        for c in certificates] == [(1, 'LW', 0x1000, 0x2000, 0x00ff, 0x89abcd10),
            (2, 'LWU', 0x1000, 0x2004, 0xf00f, 0x89ab3de0),
            (3, 'LW', 0x1000, 0x2008, 0, 0x12345678),
            (4, 'LW', 0x1000, 0x200c, 0xff, 0x89abcd10)]
    assert [sum(c['begin']['phase'] == phase for c in contexts) for phase in range(1, 8)] == [3, 3, 3, 4, 3, 3, 1]
    assert not contexts[-1]['scalars']
    facts = data['facts']
    assert [facts['d'+str(n)] for n in range(1, 7)] == [0x89abcd10, 0x89ab3de0, 0x12345678, 0x89abcd10, 0x89abcd10, 0x1234]
    assert [facts['p'+str(n)] for n in range(1, 4)] == [0xffffffff89abcd10, 0x89ab3de0, 0x12345678]
    assert facts['failed_t0'] == 0xfeedface and facts['final_exception'] == 4
    zero = certificates[2]
    assert zero['xor_imm'] == 0 and len({zero[k] for k in ('load_context', 'transform_context', 'store_context')}) == 3
    assert [expr['xor'] for expr in certificates[0]['byte_expr']] == [0, 0, 0, 0xff]
    assert [expr['xor'] for expr in certificates[1]['byte_expr']] == [0, 0, 0xf0, 0x0f]
    naive = []
    for index, context in enumerate(contexts):
        if shared.decode(context['begin']['word'])[0] != 0x2b or index == 0:
            continue
        previous = contexts[index-1]
        if shared.decode(previous['begin']['word'])[0] != 0x0e:
            continue
        write = context['scalars'][0]
        mask = previous['begin']['word'] & 0xffff
        sources = [effect['address'] for earlier in contexts[:index-1] for effect in earlier['scalars']
            if not effect['write'] and effect['value'] ^ mask == write['value']]
        if sources:
            naive.append(dict(phase=context['begin']['phase'], sources=sources, destination=write['address']))
    assert set(next(c for c in naive if c['phase'] == 4)['sources']) == {0x1000, 0x1100}
    assert 0x1000 in next(c for c in naive if c['phase'] == 5)['sources']
    return dict(scope='adjacent_interpreted_identity_rdram_xori_transform', certificates=certificates,
        naive_transform_matches=naive, instruction_contexts=len(contexts), scalar_effects=len(data['scalar_events']),
        general_dataflow_certified=False, executable_lifetime_certified=False, native_complete=False)


def reject_forgeries(data):
    histories = []
    for name in ('register_discontinuity', 'nonsequential_pc', 'cached_address'):
        forged = copy.deepcopy(data)
        for event in forged['instruction_events']:
            if event['phase'] != 1:
                continue
            opcode = shared.decode(event['word'])[0]
            if name == 'register_discontinuity' and opcode in (0x0e, 0x2b):
                event['gpr'][8] ^= 1 << 32
            elif name == 'nonsequential_pc' and opcode == 0x0e:
                event['pc'] += 0x100
            elif name == 'cached_address':
                event['gpr'][17] = 0xffffffff80002000
        histories.append(forged)
    for field, value in [('address', 0x1100), ('context', 0), ('bytes', 8),
            ('uncached_cpu', False), ('write', 0), ('value', 1 << 32), ('extra', 0)]:
        forged = copy.deepcopy(data)
        next(e for e in forged['scalar_events'] if e['phase'] == 1 and not e['write'])[field] = value
        histories.append(forged)
    for opcode, shift in ((0x0e, 21), (0x2b, 16)):
        forged = copy.deepcopy(data)
        for event in forged['instruction_events']:
            if event['phase'] == 1 and shared.decode(event['word'])[0] == opcode:
                event['word'] = (event['word'] & ~(31 << shift)) | (9 << shift)
        histories.append(forged)
    forged = copy.deepcopy(data)
    begin = next(e for e in forged['instruction_events'] if e['phase'] == 7 and e['begin'])
    for collection in ('instruction_events', 'scalar_events'):
        for event in forged[collection]:
            if event['ordinal'] > begin['ordinal']:
                event['ordinal'] += 1
    forged['scalar_events'].append(dict(ordinal=begin['ordinal']+1, context=begin['context'], phase=7,
        pc=begin['pc'], write=False, address=0x1001, bytes=4, uncached_cpu=True, value=0x89abcdef))
    histories.append(forged)
    for forged in histories:
        try:
            replay(forged)
        except AssertionError:
            continue
        raise AssertionError('forged transformed history accepted')
    return len(histories)
