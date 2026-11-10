"""Convert a native fault snapshot into a bounded, content-addressed repair record."""
import hashlib
import json


def write_record(raw_path, directory):
    raw = json.loads(raw_path.read_text())
    if set(raw) != {'format', 'fault', 'site', 'target', 'vi', 'physical_start', 'bytes'} or raw['format'] != 'plaid-repair-raw-v0':
        raise ValueError('invalid raw repair capture')
    fault, vi, base = raw['fault'], raw['vi'], raw['physical_start']
    if type(fault) is not int or fault not in (3, 15) or type(vi) is not int or vi < 0 or type(base) is not int:
        raise ValueError('invalid repair capture metadata')
    if any(not isinstance(raw[k], str) or len(raw[k]) != 8 or any(c not in '0123456789abcdef' for c in raw[k]) for k in ('site', 'target')):
        raise ValueError('invalid repair capture address')
    site, target = int(raw['site'], 16), int(raw['target'], 16)
    data = bytes.fromhex(raw['bytes'])
    physical = target & 0x1fffffff
    if (not 0x80000000 <= target < 0xc0000000 or target & 3 or not data or
            base < 0 or base + len(data) > 0x800000 or len(data) > 0x20000 or
            not base <= physical < base + len(data) or (fault == 15 and site != target)):
        raise ValueError('invalid repair capture window')
    record = {'schema': 'plaid-repair-v1', 'stop_kind': 'indirect_target' if fault == 3 else 'local_trap',
              'site_pc': raw['site'], 'target_pc': raw['target'], 'vi': vi,
              'window_base': base, 'window_size': len(data), 'bytes': data.hex(),
              'sha256': hashlib.sha256(data).hexdigest(), 'pi_dma': None}
    directory.mkdir(parents=True, exist_ok=True)
    n = 0
    while True:
        path = directory / f'{n}.json'
        try:
            with path.open('x', encoding='utf-8', newline='\n') as f:
                json.dump(record, f, separators=(',', ':'))
                f.write('\n')
            return path
        except FileExistsError:
            n += 1
