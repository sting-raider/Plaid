"""Finite expected reports from the synthetic exact-reference store probes."""
from pathlib import Path
import copy
import json


def expected():
    return json.loads(Path(__file__).with_name('expected.json').read_text(encoding='utf8'))


def exact(actual, control):
    assert type(actual) is type(control)
    if type(control) is dict:
        assert actual.keys() == control.keys()
        for key in control:
            exact(actual[key], control[key])
    elif type(control) is list:
        assert len(actual) == len(control)
        for item, reference in zip(actual, control):
            exact(item, reference)
    else:
        assert actual == control


def verify(data):
    exact(data, expected())
    return dict(schema_version=0, probe_count=29, scalar_probes=4, vector_probes=25,
        aligned_srv_changed_bytes=0, nonaligned_srv_changed_bytes=15,
        hardware_behavior_certified=False, rsp_recompiler_certified=False,
        producer_census_certified=False, executable_lifetime_certified=False,
        native_complete=False)


def reject_forgeries(data):
    cases = []
    for index in range(29):
        for key, value in [('instruction', 13), ('base', 0x5000),
            ('dmem_sha256', 'f'*64), ('changed_dmem', 4096)]:
            forged = copy.deepcopy(data)
            forged['probes'][index][key] = value
            cases.append((f'probe_{index}_{key}', forged))
    for label, field, value in [('wrong_final_imem', 'imem_sha256', '0'*64),
        ('wrong_final_dmem', 'dmem_sha256', '0'*64), ('wrong_count', 'probe_count', 28)]:
        forged = copy.deepcopy(data)
        forged[field] = value
        cases.append((label, forged))
    forged = copy.deepcopy(data)
    forged['probes'][14]['changed_dmem'] = False
    cases.append(('boolean_zero_length', forged))
    forged = copy.deepcopy(data)
    forged['probes'][0]['extra'] = True
    cases.append(('unknown_field', forged))
    forged = copy.deepcopy(data)
    forged['probes'][0], forged['probes'][1] = forged['probes'][1], forged['probes'][0]
    cases.append(('reordered_probes', forged))
    rejected = []
    for name, forged in cases:
        try:
            verify(forged)
        except AssertionError:
            rejected.append(name)
        else:
            raise AssertionError('forged report accepted: '+name)
    return rejected
