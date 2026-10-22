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
    return sorted(t for t in targets if (t < 0x80800000 or t >= 0xc0000000) and t % 4 == 0
                  and not any(lo <= t < hi for lo, hi in covered))


def missing_tables(program):
    """(site, start, end) of jump tables whose words no image supplies."""
    out = []
    for item in program.get('unresolved', []):
        if item['kind'] == 'pointer_table_source_missing':
            table = json.loads(program['evidence'][item['evidence'][0]]['detail'])
            out.append((item['site']['pc'], table['table_start'], table['table_start'] + 4 * table['count']))
    return out


def repair_table_data(rom, loads, program, base, size, receipt_path):
    """A malformed early table snapshot is not executable-source evidence.

    Replay to its first use and supply only the table's data bytes. Composition
    repeats that fetch; native table checks still guard any accepted certificate.
    """
    tables = set()
    for item in program.get('unresolved', []):
        if item['kind'] == 'invalid_pointer_table_entry':
            table = json.loads(program['evidence'][item['evidence'][0]]['detail'])
            tables.add((item['site']['pc'], table['table_start'], table['count'] * 4))
    if not tables:
        return False
    bindings = replay_bindings(program, base, size)
    def runtime(pc):
        matches = {target + pc - start for start, target, length, _ in bindings
                   if start <= pc < start + length}
        if len(matches) != 1:
            raise ValueError(f'table use {pc:08x} has no unique replay address')
        return matches.pop()
    try:
        # Newly decoded cases can reveal another table that neutral input never
        # uses. An already authenticated data fetch can supply that same snapshot.
        entries = {int(l['entry'], 0) for l in loads['loads'] if l['encoding'] == 'ares_data'}
        if not entries:
            entries = {runtime(site) for site, _, _ in tables}
        captures = capture_many(rom, sorted(entries))
    except ValueError:
        return False
    additions = []
    for capture in captures:
        if 'bytes' not in capture:
            continue
        source = capture.get('physical_start', capture['destination'] & 0x1fffffff)
        data = bytes(capture['bytes'])
        for _, start, length in sorted(tables):
            # Fixed KSEG0 data only; mapped/slot table placement needs its own binding.
            physical = start - 0x80000000
            offset = physical - source
            if not (0 <= physical < physical + length <= 0x800000 and
                    0 <= offset < offset + length <= len(data)):
                continue
            payload = data[offset:offset + length]
            if any(int.from_bytes(payload[n:n+4], 'big') % 4 for n in range(0, length, 4)):
                continue
            load = dict(destination=hex(start), size=hex(length), rom='0x0', encoding='ares_data',
                        entry=hex(capture['entry']), physical=hex(physical))
            if load not in additions and load not in loads['loads']:
                additions.append(load)
    if not additions:
        return False
    # Preserve every supplied byte outside the data ranges. Unsupported source
    # encodings and conflicting data witnesses refuse instead of being overwritten.
    refined = loads['loads'][:]
    for data in additions:
        lo, hi = int(data['destination'], 0), int(data['destination'], 0) + int(data['size'], 0)
        pieces = []
        for load in refined:
            start, end = int(load['destination'], 0), int(load['destination'], 0) + int(load['size'], 0)
            if load.get('slot') or start >= hi or lo >= end:
                pieces.append(load)
                continue
            if load['encoding'] not in ('raw', 'ares_boot'):
                return False
            for a, b in ((start, min(end, lo)), (max(start, hi), end)):
                if a < b:
                    piece = dict(load, destination=hex(a), size=hex(b - a))
                    if load['encoding'] == 'raw':
                        piece['rom'] = hex(int(load['rom'], 0) + a - start)
                    pieces.append(piece)
        refined = pieces + [data]
    loads['loads'] = sorted(refined, key=lambda l: (bool(l.get('slot')), 0 if l.get('slot') else int(l['destination'], 0)))
    loads['source'] += '; first-use table data from whole-ROM ares reset replay; nonexecutable, native table guards required'
    Path(receipt_path).write_text(json.dumps({'table_data': additions,
        'captures': [{k: v for k, v in c.items() if k != 'bytes'} for c in captures]}, indent=2) + '\n')
    return True


def replay_bindings(program, base, size):
    """Map declared storage to execution addresses; ROM spans guard slot identity.

    Compressed/relocating overlays without a fixed linked source are deliberately
    unsupported here. They cannot acquire observations by numeric coincidence.
    """
    if len(program.get('load_images', {})) > 1:
        raise ValueError('replay requires one unambiguous composed load image')
    bindings = []
    for spec in program.get('load_images', {}).values():
        bindings.append([spec['base']['start'], spec['base']['start'], spec['base']['size'], None])
        for load in spec['loads']:
            start, length = load['destination']['start'], load['destination']['size']
            linked = load.get('linked')
            source = None
            if load.get('relocatable'):
                encoding = load['encoding']
                source = -1
                if linked is not None and encoding == 'raw':
                    source = load['source']
                elif linked is not None and isinstance(encoding, dict):
                    for kind in ('segment', 'tlb_raw'):
                        if kind in encoding:
                            length = encoding[kind]['text_size']
                            source = load['source']
                    if 'ares_tlb' in encoding:
                        # Its reset replay authenticates bytes during composition;
                        # until replay projection can recheck them, do not observe calls.
                        source = -1
                if linked is None:
                    # Unknown runtime placement: never observe the synthetic PC.
                    continue
            bindings.append([start, linked if linked is not None else start, length, source])
    if not bindings:
        bindings.append([base, base, size, None])
    return sorted(set(tuple(b) for b in bindings), key=lambda b: (*b[:3], -2 if b[3] is None else b[3]))


def replay_sites(program, bindings):
    sites = set()
    for site in program['indirect_sites']:
        if site.get('closed_proof') is not None or site.get('link_register') is None:
            continue
        pc = site['site']['pc']
        matches = {runtime + pc - mapped for mapped, runtime, size, source in bindings
                   if mapped <= pc < mapped + size and source != -1}
        if len(matches) != 1:
            raise ValueError(f'open call {pc:08x} has no unique supported replay binding')
        runtime = matches.pop()
        sites.add(runtime)
        if 0x80000000 <= runtime < 0xc0000000:
            sites.add(runtime ^ 0x20000000)  # cached/uncached physical alias
    return sorted(sites)


def harvest(rom, loads_path, map_path, info, receipt_path):
    """Append source-derived declarations; callers must rediscover and solve."""
    loads_path = Path(loads_path)
    loads = json.loads(loads_path.read_text())
    program = json.loads(Path(map_path).read_text())
    base, size = info['header']['boot_address'], info.get('boot_image_size') or 0x100000
    if repair_table_data(rom, loads, program, base, size, receipt_path):
        loads_path.write_text(json.dumps(loads, indent=2) + '\n')
        return True
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
        bindings = replay_bindings(program, base, size)
        sites = replay_sites(program, bindings)
        captures = (capture_many(rom, entries, covered=coverage(loads, base, size, slots=True), sites=sites, bindings=bindings)
                    if unknown_indirect else capture_many(rom, entries))
    except ValueError as error:
        Path(receipt_path).write_text(json.dumps({'targets': targets, 'refusal': str(error)}, indent=2) + '\n')
        return False
    receipt = {'targets': targets, 'runtime_sites': sites, 'bindings': bindings, 'captures': []}
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
        if capture.get('raw_occupant'):
            # A full completed PI source, not a prefix search or numeric alias.
            data = Path(rom).read_bytes()
            width = {bytes.fromhex('37804012'): 2, bytes.fromhex('40123780'): 4}.get(data[:4], 1)
            if width != 1:
                canonical = bytearray(len(data))
                for lane in range(width):
                    canonical[lane::width] = data[width - 1 - lane::width]
                data = canonical
            start, source, length, entry = (capture[k] for k in ('destination', 'rom', 'size', 'entry'))
            canonical_entry = 0x80000000 | (entry & 0x1fffffff)
            if (start % 8 or length <= 0 or length % 4 or source < 0 or source % 2 or
                    not 0x80000000 <= start < start + length <= 0x80800000 or
                    not 0x80000000 <= entry < 0xc0000000 or
                    not start <= canonical_entry < start + length or entry % 4 or
                    source + length > len(data) or len(capture.get('bytes', [])) != length or
                    bytes(capture['bytes']) != data[source:source + length]):
                receipt['refusal'] = 'invalid completed PI occupant'
                continue
            load = {'destination': hex(start), 'size': hex(length), 'rom': hex(source),
                    'encoding': 'raw', 'slot': True}
            if load not in loads['loads']:
                loads['loads'].append(load)
                loads['source'] += (f"; completed PI raw occupant ROM {source:#x}..{source + length:#x} "
                                    f"at {start:#x}, load site {capture['load_site']:#x}, first fetch {entry:#x}; "
                                    f"ares {capture['revision']}, ROM sha256 {capture['rom_sha256']}, "
                                    f"output sha256 {hashlib.sha256(bytes(capture['bytes'])).hexdigest()}; "
                                    "native content binding required (ADR-0230)")
                added = True
            continue
        if 'bytes' not in capture:
            continue
        data = bytes(capture['bytes'])
        if 'physical_start' in capture:
            start, physical, entry = (capture[k] for k in ('destination', 'physical_start', 'entry'))
            if (not data or (start | physical | entry | len(data)) & 3 or
                    physical < 0 or physical + len(data) > 0x800000 or
                    not start <= entry < start + len(data) or
                    not (0 <= start < start + len(data) <= 0x80000000 or
                         0xc0000000 <= start < start + len(data) <= 0x100000000)):
                receipt['refusal'] = 'invalid mapped boot extent'
                continue
            load = dict(destination=hex(start), size=hex(len(data)), rom='0x0', encoding='ares_tlb',
                        entry=hex(entry), physical=hex(physical), text_size=hex(len(data)), slot=True)
            if load not in loads['loads']:
                loads['loads'].append(load)
                loads['source'] += (f"; mapped first fetch {entry:#x} from physical RAM {physical:#x}; "
                                    f"ares {capture['revision']}, ROM sha256 {capture['rom_sha256']}, "
                                    f"output sha256 {hashlib.sha256(data).hexdigest()}; "
                                    "whole-ROM replay and native mapping/content/generation guards required (ADR-0236)")
                added = True
            continue
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
        # Slot storage is allocated in declaration order. Append alternates so
        # previously source-bound observed roots keep their map placements.
        loads['loads'].sort(key=lambda l: (bool(l.get('slot')), 0 if l.get('slot') else int(l['destination'], 0)))
        loads_path.write_text(json.dumps(loads, indent=2) + '\n')
    return added
