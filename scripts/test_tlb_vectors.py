"""Natural vector declarations preserve provenance and existing fixed sources."""
import copy
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from harvest_boot import harvest_vectors


def main():
    with tempfile.TemporaryDirectory(prefix='plaid-vectors-') as temporary:
        directory = Path(temporary)
        loads, receipt = directory / 'loads.json', directory / 'receipt.json'
        initial = dict(source='synthetic', loads=[dict(destination='0x60000000', size='0x8',
                       rom='0x1000', encoding='tlb_raw', text_size='0x8', slot=True)])
        captures = [dict(entry=pc, destination=pc, bytes=[0] * size, steps=100 + offset)
                    for offset, (pc, size) in enumerate(((0x80000000, 0x90), (0x80000180, 16)))]
        loads.write_text(json.dumps(initial))
        with patch('harvest_boot.capture_many', return_value=captures) as capture:
            assert harvest_vectors('synthetic.z64', loads, receipt)
            capture.assert_called_once_with('synthetic.z64', [0x80000000, 0x80000180], exact=True)
            before = loads.read_bytes()
            assert not harvest_vectors('synthetic.z64', loads, receipt)
            assert loads.read_bytes() == before
        declared = json.loads(loads.read_text())
        assert declared['loads'][0] == initial['loads'][0]
        assert [load['entry'] for load in declared['loads'][1:]] == ['0x80000000', '0x80000180']
        for change in (dict(destination=1), dict(bytes=[True] * 16), dict(bytes=[0] * 3),
                       dict(physical_start=0), dict(counterfactual={}), dict(destination=0x7ffffffc)):
            loads.write_text(json.dumps(initial))
            bad = dict(captures[0], **change)
            with patch('harvest_boot.capture_many', return_value=[bad]):
                assert not harvest_vectors('synthetic.z64', loads, receipt)
            assert json.loads(loads.read_text()) == initial
            assert json.loads(receipt.read_text())['refusals']
        overlap = copy.deepcopy(initial)
        overlap['loads'].append(dict(destination='0x80000004', size='0x4', rom='0x10', encoding='raw'))
        loads.write_text(json.dumps(overlap))
        with patch('harvest_boot.capture_many', return_value=captures[:1]):
            assert not harvest_vectors('synthetic.z64', loads, receipt)
        assert json.loads(loads.read_text()) == overlap
        loads.write_text(json.dumps(dict(source='synthetic', loads=[])))
        with patch('harvest_boot.capture_many', side_effect=AssertionError('unneeded oracle')):
            assert not harvest_vectors('synthetic.z64', loads, receipt)
    print('PASS natural vector declarations: exact fetches, original source identities, no mapping preload, malformed/overlap refusal')


if __name__ == '__main__':
    main()
