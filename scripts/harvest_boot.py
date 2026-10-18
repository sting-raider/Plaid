"""Recover missing executable images using a deterministic, input-free ares boot."""
import hashlib
import json
from pathlib import Path

from ares_boot import capture_many


def missing_targets(program, loads, base, size):
    covered = [(base, base + size)] + [(int(l['destination'], 0), int(l['destination'], 0) + int(l['size'], 0))
                                      for l in loads['loads'] if not l.get('slot')]
    targets = {e['target']['pc'] for e in program['direct_edges']}
    for site in program['indirect_sites']:
        for name in ('candidates', 'observed'):
            targets.update(c[0]['pc'] for c in site[name])
    return sorted(t for t in targets if 0x80000000 <= t < 0x80800000 and t % 4 == 0
                  and not any(lo <= t < hi for lo, hi in covered))


def missing_tables(program):
    """(site, start, end) of jump tables whose words no image supplies."""
    out = []
    for item in program.get('unresolved', []):
        if item['kind'] == 'pointer_table_source_missing':
            table = json.loads(program['evidence'][item['evidence'][0]]['detail'])
            out.append((item['site']['pc'], table['table_start'], table['table_start'] + 4 * table['count']))
    return out


def harvest(rom, loads_path, map_path, info, receipt_path):
    """Append source-derived declarations; callers must rediscover and solve."""
    loads_path = Path(loads_path)
    loads = json.loads(loads_path.read_text())
    program = json.loads(Path(map_path).read_text())
    base, size = info['header']['boot_address'], info.get('boot_image_size') or 0x100000
    targets = missing_targets(program, loads, base, size)
    # A table is read when its jump site runs: capture there (ADR-0197).
    tables = missing_tables(program)
    if not targets and not tables:
        return False
    try:
        captures = capture_many(rom, sorted(set(targets) | {site for site, _, _ in tables}))
    except ValueError as error:
        Path(receipt_path).write_text(json.dumps({'targets': targets, 'refusal': str(error)}, indent=2) + '\n')
        return False
    receipt = {'targets': targets, 'captures': []}
    added = False
    for capture in captures:
        receipt['captures'].append({k: v for k, v in capture.items() if k != 'bytes'})
        if 'bytes' not in capture:
            continue
        data = bytes(capture['bytes'])
        lo, hi = capture['destination'], capture['destination'] + len(data)
        pieces = [(lo, hi)]
        # Preserve static inference and earlier snapshots byte-for-byte.
        covered = [(base, base + size)] + [(int(l['destination'], 0), int(l['destination'], 0) + int(l['size'], 0))
                                          for l in loads['loads']]
        for start, end in covered:
            pieces = [(a, b) for left, right in pieces
                      for a, b in ((left, min(right, start)), (max(left, end), right)) if a < b]
        for start, end in pieces:
            if not any(start <= t < end for t in targets) and not any(start < hi and lo < end for _, lo, hi in tables):
                continue
            image = data[start - lo:end - lo]
            loads['loads'].append({'destination': hex(start), 'size': hex(end - start), 'rom': '0x0',
                                   'encoding': 'ares_boot', 'entry': hex(capture['entry'])})
            loads['source'] += (f"; ROM-only boot execution/ares-v1: ROM sha256 {capture['rom_sha256']}; "
                                f"ares {capture['revision']}; reset/PIF, NTSC, CIC {capture['cic']}, neutral controller 1; "
                                f"entry {capture['entry']:08x}; {capture['steps']} instructions; "
                                f"budget {capture['budget']} instruction calls/3600 VI; consumed ROM ranges (PI requests only) {capture['consumed_rom']}; "
                                f"PI DMA ranges {capture['pi_dma']}; "
                                f"CPU writes {capture['cpu_writes']}; output sha256 {hashlib.sha256(image).hexdigest()}; "
                                "replayed during composition, content-guarded at native entry")
            added = True
    Path(receipt_path).write_text(json.dumps(receipt, indent=2) + '\n')
    if added:
        loads['loads'].sort(key=lambda l: int(l['destination'], 0))
        loads_path.write_text(json.dumps(loads, indent=2) + '\n')
    return added
