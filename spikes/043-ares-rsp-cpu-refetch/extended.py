"""Exact finite fixture contract and byte replay, including unclassified sinks.

Writer identity describes a measured storage effect, not ultimate ROM ancestry.
The phase contract is independently declared here rather than learned from the
observed trace. Equal payloads cannot justify dropping or moving a write.
"""
import copy
from verify import FIELDS


def expected_events():
    events = []
    cpu_context = rsp_context = rsp_pc = rsp_word = 0
    cpu_pc = 0

    def add(kind, phase, address=0, offset=0, size=0, value=0, write=False):
        nonlocal cpu_context, rsp_context
        ordinal = len(events) + 1
        if kind == 0:
            cpu_context = ordinal
        if kind == 3:
            rsp_context = ordinal
        events.append(dict(kind=kind, ordinal=ordinal, phase=phase,
            context=cpu_context, rsp_context=rsp_context, rsp_pc=rsp_pc,
            rsp_word=rsp_word, address=address, bank=0, offset=offset,
            bytes=size, pc=cpu_pc, value=value, write=write))
        if kind == 2:
            cpu_context = 0
        if kind == 5:
            rsp_context = 0

    fetches = {1: 0x34081111, 3: 0x34082222, 5: 0x34082222,
        7: 0x34083333, 9: 0x34083333, 11: 0x34083344,
        13: 0x34087744, 15: 0x34087744, 17: 0x34087744, 19: 0x34087744}
    # Decoded operation and actual primitive sinks are separate obligations.
    stores = {2: (0xac220000, 0, bytes.fromhex('34082222')),
        4: (0xac220000, 0, bytes.fromhex('34082222')),
        8: (0xac220000, 4, bytes.fromhex('34083333')),
        10: (0xa0220000, 3, bytes([0x44])),
        12: ((58 << 26) | (1 << 21) | (2 << 16), 2, bytes([0x77])),
        16: (0xa0220000, 3, bytes([0x44]))}
    for phase in range(1, 20):
        if phase in fetches or phase in (6, 18):
            address = 0x6000 if phase in (6, 18) else 0x04020000 if phase in (5, 19) else 0x04000000
            cpu_pc = 0xffffffffa0000000 | address
            add(0, phase, address)
            if phase in fetches:
                add(1, phase, address, size=4, value=fetches[phase])
            add(2, phase, address, size=4, value=fetches.get(phase, 0xae090000))
            if phase in (6, 18):
                value = 0x34083333 if phase == 6 else 0x34087744
                # The lower-level DMEM effect precedes the completed CPU SP write.
                add(6, phase, size=4, value=value, write=True)
                add(1, phase, 0x04000000, size=4, value=value, write=True)
            cpu_pc += 4
        elif phase in stores:
            word, offset, values = stores[phase]
            for rsp_pc, rsp_word in ((0, word), (4, 13)):
                add(3, phase)
                if rsp_pc == 0:
                    for index, value in enumerate(values):
                        add(4, phase, offset=offset+index, size=1, value=value, write=True)
                add(5, phase, rsp_pc+4, value=int(rsp_pc == 4))
            rsp_pc = rsp_word = 0
        else:
            assert phase == 14
            add(6, phase, offset=3, size=1, value=0x44, write=True)
    return events


def verify_extended(events):
    expected = expected_events()
    assert len(events) == len(expected) == 78
    for observed, required in zip(events, expected):
        assert set(observed) == FIELDS
        assert all(type(observed[key]) is int and 0 <= observed[key] < (1 << 64)
            for key in FIELDS - {'write'})
        assert type(observed['write']) is bool
        assert observed == required, (observed, required)

    backing = bytearray(bytes.fromhex('3408111134083333'))
    writers = [None] * 8
    samples = []
    for index, event in enumerate(events):
        kind, offset, size = event['kind'], event['offset'], event['bytes']
        if kind in (4, 6) or kind == 1 and event['write']:
            assert 0 <= offset < offset + size <= len(backing)
            backing[offset:offset+size] = event['value'].to_bytes(size, 'big')
            writers[offset:offset+size] = [event['ordinal'] if kind != 6 else None] * size
            if kind == 1:
                previous = events[index-1]
                assert previous['kind'] == 6 and previous['phase'] == event['phase']
                assert all(previous[key] == event[key] for key in ('offset', 'bytes', 'value', 'pc'))
        elif kind == 1:
            assert event['value'] == int.from_bytes(backing[offset:offset+size], 'big')
            samples.append(dict(phase=event['phase'], physical=event['address'],
                word=event['value'], read_ordinal=event['ordinal'],
                writer_ordinals=list(writers[offset:offset+size])))

    by_phase = {sample['phase']: sample for sample in samples}
    assert by_phase[1]['writer_ordinals'] == [None]*4
    assert by_phase[3]['writer_ordinals'] != by_phase[5]['writer_ordinals']
    assert by_phase[7]['writer_ordinals'] == by_phase[9]['writer_ordinals']
    assert len(set(by_phase[13]['writer_ordinals'])) == 3
    assert by_phase[15]['writer_ordinals'][:3] == by_phase[13]['writer_ordinals'][:3]
    assert by_phase[15]['writer_ordinals'][3] is None
    assert by_phase[17]['writer_ordinals'][3] is not None
    assert by_phase[17]['word'] == by_phase[19]['word']
    assert by_phase[17]['writer_ordinals'] != by_phase[19]['writer_ordinals']
    assert len(set(by_phase[19]['writer_ordinals'])) == 1
    return dict(scope='finite_partial_vector_foreign_rsp_cpu_refetch', records=len(events),
        samples=samples, rsp_primitive_writes=sum(e['kind'] == 4 for e in events),
        cpu_word_writes=2, foreign_sinks=3, mutation_coverage_certified=False,
        executable_lifetime_certified=False, native_complete=False)


def reject_extended_forgeries(events):
    histories = []
    for field, value in [('rsp_context', 0), ('context', 1), ('offset', 4),
            ('value', 256), ('bytes', 4), ('bank', 1), ('rsp_word', 13),
            ('pc', 0), ('extra', 0), ('write', 1), ('ordinal', True)]:
        forged = copy.deepcopy(events)
        next(e for e in forged if e['kind'] == 4)[field] = value
        histories.append(forged)
    for phase, kind in ((4, 4), (14, 6), (18, 6)):
        forged = copy.deepcopy(events)
        old = next(e for e in forged if e['phase'] == phase and e['kind'] == kind)['ordinal']
        forged.pop(old-1)
        for event in forged:
            if event['ordinal'] > old:
                event['ordinal'] -= 1
            for field in ('context', 'rsp_context'):
                if event[field] > old:
                    event[field] -= 1
        histories.append(forged)
    # Equal-valued neighbor and unclassified same-value byte cannot steal identity.
    for phase, kind, offset in ((8, 4, 0), (14, 6, 7), (12, 4, 3)):
        forged = copy.deepcopy(events)
        next(e for e in forged if e['phase'] == phase and e['kind'] == kind)['offset'] = offset
        histories.append(forged)
    for forged in histories:
        try:
            verify_extended(forged)
        except AssertionError:
            continue
        raise AssertionError('forged extended history accepted')
    return len(histories)


def demonstrate_value_only_failures(events):
    """Three causal forgeries preserve every fetched payload under a weak replay."""
    histories = []
    deleted = copy.deepcopy(events)
    deleted.pop(next(i for i, e in enumerate(deleted) if e['phase'] == 4 and e['kind'] == 4))
    histories.append(deleted)
    for phase, kind, offset in ((8, 4, 0), (14, 6, 7)):
        moved = copy.deepcopy(events)
        next(e for e in moved if e['phase'] == phase and e['kind'] == kind)['offset'] = offset
        histories.append(moved)
    for forged in histories:
        backing = bytearray(bytes.fromhex('3408111134083333'))
        for event in forged:
            kind, offset, size = event['kind'], event['offset'], event['bytes']
            if kind in (4, 6) or kind == 1 and event['write']:
                backing[offset:offset+size] = event['value'].to_bytes(size, 'big')
            elif kind == 1:
                assert event['value'] == int.from_bytes(backing[offset:offset+size], 'big')
        try:
            verify_extended(forged)
        except AssertionError:
            continue
        raise AssertionError('value-preserving causal forgery accepted')
    return len(histories)
