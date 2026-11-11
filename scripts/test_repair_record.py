from pathlib import Path
import hashlib
import json
import tempfile
from repair_record import write_record


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        raw = root / 'raw.json'
        data = bytes(range(256))
        capture = {'format': 'plaid-repair-raw-v0', 'fault': 3, 'site': '80000000',
                   'target': '80000080', 'vi': 17, 'physical_start': 0, 'bytes': data.hex()}
        raw.write_text(json.dumps(capture))
        first = write_record(raw, root / 'repair')
        record = json.loads(first.read_text())
        assert first.name == '0.json' and write_record(raw, root / 'repair').name == '1.json'
        assert record['sha256'] == hashlib.sha256(data).hexdigest()
        assert record['window_size'] == len(data) and record['target_pc'] == '80000080'
        assert record['stop_kind'] == 'indirect_target' and record['pi_dma'] is None
        capture['target'] = '80001000'
        raw.write_text(json.dumps(capture))
        try:
            write_record(raw, root / 'repair')
        except ValueError:
            pass
        else:
            raise AssertionError('out-of-window target accepted')
    print('PASS versioned repair record')


if __name__ == '__main__':
    main()
