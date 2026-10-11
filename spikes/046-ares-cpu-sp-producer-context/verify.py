"""Controlled actual CPU decoder / SP Word source witnesses and byte replay."""
import copy

FIELDS = {'kind','ordinal','context','phase','pc','word','address','bank','offset','value',
    'exception','cop_error','fr','cu1','cpu','gpr','fpr'}
WORDS = {1:0xac220000, 2:0xac220000, 3:0xa0220001, 4:0xe4200000,
    5:0xe4210000, 6:0xe4210000, 7:0xe4210000}
CODE_PC = 0xffffffffa0006000
FINAL_IMEM = list(bytes.fromhex('778800005566778811223344ddeeff00'))


def integer(value, bits):
    assert type(value) is int and 0 <= value < 1 << bits


def source_effect(begin):
    word = begin['word']
    opcode, base, source = word >> 26, (word >> 21) & 31, (word >> 16) & 31
    immediate = word & 0xffff
    if immediate & 0x8000:
        immediate -= 0x10000
    virtual = (begin['gpr'][base]+immediate) & ((1 << 64)-1)
    assert 0xffffffffa4000000 <= virtual <= 0xffffffffa403ffff
    physical = virtual & 0x1fffffff
    if opcode == 0x2b:
        assert physical % 4 == 0
        payload = begin['gpr'][source] & 0xffffffff
        operand = dict(kind='gpr', register=source, bits=begin['gpr'][source])
    elif opcode == 0x28:
        payload = (begin['gpr'][source] << (24-8*(physical & 3))) & 0xffffffff
        operand = dict(kind='gpr', register=source, bits=begin['gpr'][source])
    else:
        assert opcode == 0x39 and begin['cu1'] and physical % 4 == 0
        selected = source if begin['fr'] else source & ~1
        shift = 0 if begin['fr'] or not source & 1 else 32
        payload = (begin['fpr'][selected] >> shift) & 0xffffffff
        operand = dict(kind='fpr', register=selected, shift=shift, bits=begin['fpr'][selected])
    return physical, payload, operand


def verify(data):
    assert set(data) == {'initial_imem','events','checkpoints','final_imem'}
    for field in ('initial_imem','final_imem'):
        assert type(data[field]) is list and len(data[field]) == 16
        for value in data[field]:
            integer(value,8)
    assert data['initial_imem'] == list(range(0xa0,0xb0))
    assert type(data['checkpoints']) is list and len(data['checkpoints']) == 8
    assert all(type(checkpoint) is str for checkpoint in data['checkpoints'])
    backing = bytearray(data['initial_imem'])
    events = data['events']
    assert type(events) is list and len(events) == 21
    active = None
    begins, writes, witnesses, unknown = [], [], [], []
    for ordinal, event in enumerate(events,1):
        assert type(event) is dict and set(event) == FIELDS
        for field in FIELDS-{'fr','cu1','cpu','gpr','fpr'}:
            integer(event[field], 64 if field == 'pc' else 32)
        for field in ('fr','cu1','cpu'):
            assert type(event[field]) is bool
        for field in ('gpr','fpr'):
            assert type(event[field]) is list
            for value in event[field]:
                integer(value,64)
        assert event['ordinal'] == ordinal and event['cpu']
        if event['kind'] == 0:
            assert active is None and event['context'] == ordinal
            assert event['phase'] in WORDS and event['word'] == WORDS[event['phase']]
            assert event['pc'] == CODE_PC
            assert event['address'] == event['bank'] == event['offset'] == event['value'] == 0
            assert event['exception'] == event['cop_error'] == 0
            assert len(event['gpr']) == len(event['fpr']) == 32 and event['gpr'][0] == 0
            assert event['fr'] == (event['phase'] in (6,7))
            assert event['cu1'] == (event['phase'] in (4,5,6))
            active = dict(begin=event,effects=[])
            begins.append(event)
        elif event['kind'] == 1:
            assert event['gpr'] == event['fpr'] == [] and not event['fr'] and not event['cu1']
            assert event['exception'] == event['cop_error'] == 0
            assert 0x04000000 <= event['address'] <= 0x0403ffff
            assert event['bank'] == (event['address'] >> 12) & 1
            assert event['offset'] == event['address'] & 0xffc
            assert event['bank'] == 1 and event['offset']+4 <= len(backing)
            if active:
                begin = active['begin']
                assert all(event[field] == begin[field] for field in ('context','phase','word','pc'))
                address, payload, operand = source_effect(begin)
                assert event['address'] == address and event['value'] == payload
                active['effects'].append(event)
                witnesses.append(dict(context=begin['context'], effect_ordinal=ordinal,
                    phase=event['phase'], word=event['word'], physical=address, payload=payload, operand=operand))
            else:
                assert event['context'] == event['word'] == event['phase'] == 0
                assert event['pc'] == CODE_PC+4 and event['address'] == 0x04001000 and event['value'] == 0x55667788
                unknown.append(ordinal)
            backing[event['offset']:event['offset']+4] = event['value'].to_bytes(4,'big')
            writes.append(event)
        else:
            assert event['kind'] == 2 and active
            begin = active['begin']
            assert all(event[field] == begin[field] for field in ('context','phase','word','pc','gpr','fpr','fr','cu1'))
            assert event['address'] == event['bank'] == event['offset'] == event['value'] == 0
            fault = begin['word'] >> 26 == 0x39 and not begin['cu1']
            assert event['exception'] == (11 if fault else 0) and event['cop_error'] == int(fault)
            assert len(active['effects']) == (0 if fault else 1)
            active = None
    assert active is None and [begin['phase'] for begin in begins] == list(range(1,8))
    assert [event['phase'] for event in writes] == [1,2,0,3,4,5,6]
    assert [witness['payload'] for witness in witnesses] == [0x55667788,0x55667788,0x77880000,0x55667788,0x11223344,0xddeeff00]
    assert witnesses[0]['context'] != witnesses[1]['context']
    assert list(backing) == data['final_imem'] == FINAL_IMEM
    assert len(unknown) == 1
    return dict(scope='finite_actual_decoder_cpu_sp_word_producers', records=len(events),
        witnesses=witnesses, unknown_effect_ordinals=unknown, fault_without_sink=1,
        source_ancestry_certified=False, mutation_coverage_certified=False,
        executable_lifetime_certified=False, native_complete=False)


def reject_forgeries(data):
    histories = []
    for field, value in [('address',0x04000004),('offset',4096),('bank',0),('context',0),
            ('word',0xe4250000),('value',0),('cpu',False),('ordinal',True),('extra',0)]:
        forged = copy.deepcopy(data)
        next(e for e in forged['events'] if e['kind'] == 1 and e['phase'] == 4)[field] = value
        histories.append(forged)
    for field, value in [('word',0xe4250000),('fr',True),('cu1',False)]:
        forged = copy.deepcopy(data)
        for event in forged['events']:
            if event['phase'] == 4 and event['kind'] != 1:
                event[field] = value
        histories.append(forged)
    forged = copy.deepcopy(data)
    next(e for e in forged['events'] if e['phase'] == 0)['context'] = 4
    histories.append(forged)
    forged = copy.deepcopy(data)
    next(e for e in forged['events'] if e['phase'] == 7 and e['kind'] == 2)['exception'] = 0
    histories.append(forged)
    forged = copy.deepcopy(data)
    for event in forged['events']:
        if event['phase'] == 5 and event['kind'] != 1:
            event['fpr'][0] = 0x99aabbcc11223344
    histories.append(forged)
    forged = copy.deepcopy(data)
    forged['final_imem'][0] ^= 1
    histories.append(forged)
    for forged in histories:
        try:
            verify(forged)
        except AssertionError:
            continue
        raise AssertionError('forged CPU SP source witness accepted')
    return len(histories)
