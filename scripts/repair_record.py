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


def admit_records(loads, paths):
    """Caller-supplied record order defines generations; never scan captures."""
    doc = json.loads(loads.read_text())
    if doc.get('observed_images'):
        raise ValueError('repair records already admitted in loads')
    doc['observed_images'] = [dict(generation=n, record=json.loads(path.read_text()))
                              for n, path in enumerate(paths, 1)]
    loads.write_text(json.dumps(doc, indent=2) + '\n')


def native_manifest(program, verdict, residual):
    images = []
    for spec in program.get('load_images', {}).values():
        for generation, record in spec.get('observed', {}).items():
            load = next(l for l in spec['loads'] if l['encoding'] == {'observed': {'generation': int(generation)}})
            images.append(dict(image=record['sha256'], sha256=record['sha256'], generation=int(generation),
                               window_base=record['window_base'], window_size=record['window_size'],
                               observed_root=record['target_pc'], site_pc=record['site_pc'],
                               storage_base=load['destination']['start']))
    images.sort(key=lambda i: (i['generation'], i['image'], i['storage_base']))
    return dict(mode='residual-dispatch' if residual else ('observed-dispatch' if images else 'closed'),
                native_complete=not residual and not images,
                residual_sites=[f"{s['pc']:08x}" for s in verdict.get('residual_sites', [])],
                trapped_sites=[dict(pc=f"{b['site']['pc']:08x}", kind=b['kind']) for b in verdict.get('trapped_sites', [])],
                observed_images=images)
