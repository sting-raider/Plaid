"""Mutations applied to both independent fixture data and measured captures."""
import copy
from verify import verify


def cases(data):
    def change(index, **fields):
        result = copy.deepcopy(data)
        result['events'][index].update(fields)
        return result

    result = [
        ('equal_payload_wrong_source', change(2, dram=0x1004)),
        ('skipped_poison_join', change(14, dram=0x3008)),
        ('wrong_wrap_sink', change(22, dmem=0xff8)),
        ('invented_oob_source', change(24, dram=0x1000)),
        ('wrong_cpu_identity', change(26, origin_cpu=False)),
        ('boolean_ordinal', change(0, seq=True)),
        ('unknown_source_field', change(0, untrusted_source='fabricated')),
        ('wrong_payload_width', change(9, bytes=8)),
    ]
    wrong = copy.deepcopy(data)
    wrong['events'][13]['value'] = wrong['events'][15]['value'] = 0xdecafbad
    result.append(('matched_wrong_second_row_payload', wrong))
    missing = copy.deepcopy(data)
    del missing['events'][8]
    for index, event in enumerate(missing['events'], 1):
        event['seq'] = index
    result.append(('deleted_read_renumbered', missing))
    duplicate = copy.deepcopy(data)
    duplicate['events'][1]['seq'] = duplicate['events'][0]['seq']
    result.append(('duplicate_ordinal', duplicate))
    state = copy.deepcopy(data)
    state['state']['checkpoints'][5] ^= 1
    result.append(('changed_checkpoint', state))
    return result


def check(data):
    rejected = []
    for name, forged in cases(data):
        try:
            verify(forged)
        except AssertionError:
            rejected.append(name)
        else:
            raise AssertionError('forged finite capture accepted: '+name)
    return rejected
