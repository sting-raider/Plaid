"""Bounded interpreted KSEG1 LW/LWU -> SW history verifier.

Authenticating a supplied finite history is separate from proving that a sensor
observed every instruction or that copied bytes will be executed later.
"""
import copy

INSTRUCTION_FIELDS = {'begin', 'ordinal', 'context', 'phase', 'pc', 'word', 'gpr'}
SCALAR_FIELDS = {'ordinal', 'context', 'phase', 'pc', 'write', 'address', 'bytes', 'uncached_cpu', 'value'}
MASK64 = (1 << 64)-1


def integer(value, bits=64):
    assert type(value) is int and 0 <= value < 1 << bits


def decode(word):
    immediate = word & 0xffff
    return word >> 26, (word >> 21) & 31, (word >> 16) & 31, immediate-0x10000 if immediate & 0x8000 else immediate


def uncached_address(register, immediate):
    address = (register+immediate) & MASK64
    # Only canonical sign-extended KSEG1, controlled identity RDRAM and Word alignment.
    assert 0xffffffffa0000000 <= address <= 0xffffffffbfffffff and address % 4 == 0
    physical = address & 0x1fffffff
    assert physical < 8*1024*1024
    return physical


def replay(data):
    instructions, scalars = data['instruction_events'], data['scalar_events']
    assert type(instructions) is list and type(scalars) is list
    merged = []
    for event in instructions:
        assert type(event) is dict and set(event) == INSTRUCTION_FIELDS
        assert type(event['begin']) is bool
        assert type(event['gpr']) is list and len(event['gpr']) == 32
        for value in event['gpr']:
            integer(value)
        assert event['gpr'][0] == 0
        for field in INSTRUCTION_FIELDS - {'begin', 'gpr'}:
            integer(event[field], 32 if field in ('word', 'phase') else 64)
        assert event['pc'] % 4 == 0
        merged.append(('instruction', event))
    for event in scalars:
        assert type(event) is dict and set(event) == SCALAR_FIELDS
        assert type(event['write']) is bool and type(event['uncached_cpu']) is bool
        for field in SCALAR_FIELDS - {'write', 'uncached_cpu'}:
            integer(event[field], 32 if field in ('phase', 'address') else 64)
        merged.append(('scalar', event))
    merged.sort(key=lambda entry: entry[1]['ordinal'])
    assert [event['ordinal'] for _, event in merged] == list(range(1, len(merged)+1))
    contexts, active = [], None
    for kind, event in merged:
        if kind == 'instruction':
            if event['begin']:
                assert active is None and event['context'] == event['ordinal']
                active = dict(begin=event, scalars=[])
            else:
                assert active is not None
                begin = active['begin']
                assert all(event[field] == begin[field] for field in ('context', 'phase', 'pc', 'word'))
                active['end'] = event
                contexts.append(active)
                active = None
        else:
            # Do not silently drop an out-of-instruction storage effect.
            assert active is not None
            assert all(event[field] == active['begin'][field] for field in ('context', 'phase', 'pc'))
            active['scalars'].append(event)
    assert active is None

    successful, certificates = {}, []
    for index, context in enumerate(contexts):
        begin, end, effects = context['begin'], context['end'], context['scalars']
        if index and contexts[index-1]['begin']['phase'] == begin['phase']:
            previous = contexts[index-1]
            assert previous['end']['gpr'] == begin['gpr']
            assert previous['end']['ordinal']+1 == begin['ordinal']
            assert previous['begin']['pc']+4 == begin['pc']
        opcode, base, register, immediate = decode(begin['word'])
        if opcode in (0x23, 0x27, 0x2b):
            if not effects:
                # Failed/unsupported operations give no positive origin witness.
                assert opcode in (0x23, 0x27) and end['gpr'] == begin['gpr']
                continue
            assert len(effects) == 1
            effect = effects[0]
            assert effect['uncached_cpu'] and effect['bytes'] == 4
            assert effect['address'] == uncached_address(begin['gpr'][base], immediate)
            integer(effect['value'], 32)
            assert effect['write'] == (opcode == 0x2b)
            if opcode in (0x23, 0x27):
                value = effect['value']
                if opcode == 0x23 and value & 0x80000000:
                    value |= 0xffffffff00000000
                expected = list(begin['gpr'])
                if register:
                    expected[register] = value
                assert end['gpr'] == expected
                # Loading zero has a real read but cannot define a causal GPR writer.
                if register:
                    successful[index] = dict(register=register, effect=effect, opcode=opcode)
            else:
                assert effect['value'] == begin['gpr'][register] & 0xffffffff
                assert end['gpr'] == begin['gpr']
                source = successful.get(index-1)
                if source and source['register'] == register:
                    previous = contexts[index-1]
                    # The phase contract and continuity checks establish captured adjacency.
                    assert previous['begin']['phase'] == begin['phase']
                    certificates.append(dict(phase=begin['phase'],
                        load_context=previous['begin']['context'], store_context=begin['context'],
                        source=source['effect']['address'], destination=effect['address'],
                        value=effect['value'], load_opcode='LW' if source['opcode'] == 0x23 else 'LWU'))
        else:
            # The fixed fixture permits only its tested non-memory decoys/gap.
            assert not effects
            expected = list(begin['gpr'])
            if opcode == 0x0d:  # ORI
                if register:
                    expected[register] = begin['gpr'][base] | (begin['word'] & 0xffff)
            else:
                assert begin['word'] == 0  # NOP
            assert end['gpr'] == expected
    return contexts, certificates


def verify(data):
    contexts, certificates = replay(data)
    assert [(c['phase'], c['load_opcode'], c['source'], c['destination']) for c in certificates] == [
        (1, 'LW', 0x1000, 0x2000), (2, 'LWU', 0x1000, 0x2004)]
    assert [sum(c['begin']['phase'] == phase for c in contexts) for phase in range(1, 7)] == [2, 2, 3, 3, 3, 1]
    assert not contexts[-1]['scalars']
    facts = data['facts']
    assert facts['d1'] == facts['d2'] == facts['d3'] == 0x89abcdef
    assert facts['d4'] == 0x1234 and facts['d5'] == 0x89abcdef
    assert facts['t0_lw'] == 0xffffffff89abcdef and facts['t0_lwu'] == 0x89abcdef
    assert facts['failed_t0'] == 0xfeedface and facts['final_exception'] == 4
    naive = []
    for write in data['scalar_events']:
        if not write['write']:
            continue
        matches = [read for read in data['scalar_events'] if not read['write']
            and read['ordinal'] < write['ordinal'] and read['value'] == write['value']]
        if matches:
            naive.append(dict(phase=write['phase'], source=matches[-1]['address'], destination=write['address']))
    assert any(match['phase'] == 3 and match['source'] == 0x1100 for match in naive)
    assert any(match['phase'] == 4 for match in naive) and any(match['phase'] == 5 for match in naive)
    return dict(scope='adjacent_interpreted_identity_rdram_word_copy', certificates=certificates,
        naive_value_matches=naive,
        instruction_contexts=len(contexts), scalar_effects=len(data['scalar_events']),
        general_dataflow_certified=False, executable_lifetime_certified=False, native_complete=False)


def reject_forgeries(data):
    histories = []
    for name in ('register_discontinuity', 'nonsequential_pc', 'cached_address'):
        forged = copy.deepcopy(data)
        pair = [e for e in forged['instruction_events'] if e['phase'] == 1 and decode(e['word'])[0] == 0x2b]
        for event in pair:
            if name == 'register_discontinuity':
                event['gpr'][8] ^= 1 << 32
            elif name == 'nonsequential_pc':
                event['pc'] += 0x100
            else:
                event['gpr'][17] = 0xffffffff80002000
        if name == 'nonsequential_pc':
            next(e for e in forged['scalar_events'] if e['phase'] == 1 and e['write'])['pc'] += 0x100
        histories.append(forged)
    for field, value in [('address', 0x1100), ('context', 0), ('bytes', 8),
            ('uncached_cpu', False), ('write', 0), ('value', 1 << 32), ('extra', 0)]:
        forged = copy.deepcopy(data)
        next(e for e in forged['scalar_events'] if e['phase'] == 1 and not e['write'])[field] = value
        histories.append(forged)
    forged = copy.deepcopy(data)
    pair = [e for e in forged['instruction_events'] if e['phase'] == 1 and decode(e['word'])[0] == 0x2b]
    for event in pair:
        event['word'] = (event['word'] & ~(31 << 16)) | (9 << 16)
    histories.append(forged)
    forged = copy.deepcopy(data)
    begin = next(e for e in forged['instruction_events'] if e['phase'] == 6 and e['begin'])
    for collection in ('instruction_events', 'scalar_events'):
        for event in forged[collection]:
            if event['ordinal'] > begin['ordinal']:
                event['ordinal'] += 1
    forged['scalar_events'].append(dict(ordinal=begin['ordinal']+1, context=begin['context'], phase=6,
        pc=begin['pc'], write=False, address=0x1001, bytes=4, uncached_cpu=True, value=0x89abcdef))
    histories.append(forged)
    for forged in histories:
        try:
            replay(forged)
        except AssertionError:
            continue
        raise AssertionError('forged adjacent-copy history accepted')
    return len(histories)
