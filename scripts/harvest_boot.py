"""Recover missing executable images using a deterministic, input-free ares boot."""
import hashlib
import json
from pathlib import Path

from ares_boot import capture_many


def coverage(loads, base, size, slots=False):
    # The native scope replaces exception entry; IPL startup snapshots already
    # reserve this prefix (write_boot_state), so vectors are not new game text.
    return [(0x80000000, 0x80000400), (base, base + size)] + [(int(l['destination'], 0), int(l['destination'], 0) + int(l['size'], 0))
                                  for l in loads['loads'] if slots or not l.get('slot')]


def missing_targets(program, loads, base, size):
    covered = coverage(loads, base, size)
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
    # Finite map candidates cannot name a dynamically computed destination.
    # Observe its first uncovered RAM fetch without granting target closure.
    unknown_indirect = any(s.get('closed_proof') is None for s in program['indirect_sites'])
    if not targets and not tables and not unknown_indirect:
        return False
    try:
        entries = sorted(set(targets) | {site for site, _, _ in tables})
        # Calls only: a computed jr is often a return or an in-function jump,
        # whose target is no function start (ADR-0222).
        sites = sorted({s['site']['pc'] for s in program['indirect_sites']
                        if s.get('closed_proof') is None and s.get('link_register') is not None})
        captures = (capture_many(rom, entries, covered=coverage(loads, base, size, slots=True), sites=sites)
                    if unknown_indirect else capture_many(rom, entries))
    except ValueError as error:
        Path(receipt_path).write_text(json.dumps({'targets': targets, 'refusal': str(error)}, indent=2) + '\n')
        return False
    receipt = {'targets': targets, 'captures': []}
    added = False
    uncovered = next((c['uncovered_entry'] for c in captures if c.get('uncovered_entry') is not None), None)
    if uncovered is not None:
        targets = sorted(set(targets) | {uncovered})
        receipt['uncovered_entry'] = uncovered
    # Targets the unproven calls took: discovery roots, never certificates.
    roots = loads.setdefault('observed_roots', [])
    known = {(int(r['site'], 0), int(r['target'], 0)) for r in roots}
    observed = sorted({tuple(pair) for c in captures for pair in c.get('indirect_targets', [])} - known)
    if observed:
        receipt['observed_roots'] = observed
        roots.extend({'site': hex(site), 'target': hex(target)} for site, target in observed)
        loads['source'] += (f"; observed indirect call targets {[[hex(s), hex(t)] for s, t in observed]} in the same "
                            "ares replay (ADR-0222), discovery roots only")
        added = True
    # RAM the replay fills by PI DMA from the ROM, outside every image, is a
    # search input for ROM-derived RSP microcode only (ADR-0225).
    images = coverage(loads, base, size, slots=True)
    sources = loads.setdefault('rsp_sources', [])
    known = {(s['destination'], s['size'], s['rom']) for s in sources}
    dmas = [dma for c in captures for dma in c.get('pi_dma', [])]
    rom_size = Path(rom).stat().st_size if dmas else 0
    fresh = sorted({(0x80000000 | dram, n, cart - 0x10000000)
                    for dram, cart, n in dmas
                    if n and n % 4 == 0 and dram % 8 == 0 and dram + n <= 0x800000
                    and 0x10000000 <= cart and cart - 0x10000000 + n <= rom_size
                    and not any(lo < (0x80000000 | dram) + n and (0x80000000 | dram) < hi for lo, hi in images)})
    new = [s for s in ({'destination': hex(d), 'size': hex(n), 'rom': hex(r)} for d, n, r in fresh)
           if (s['destination'], s['size'], s['rom']) not in known]
    sources.extend(new)
    if new:
        receipt['rsp_sources'] = new
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
    if added or new:
        loads['loads'].sort(key=lambda l: int(l['destination'], 0))
        loads_path.write_text(json.dumps(loads, indent=2) + '\n')
    return added
