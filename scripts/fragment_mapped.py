"""Partition replayed mapped sources without splitting host or proof inputs."""
import json
from pathlib import Path


def partition_mapped(loads_path, map_path):
    loads = json.loads(Path(loads_path).read_text())
    if not any(l['encoding'] == 'ares_tlb' and int(l['size'], 0) > 0x1000
               and int(l['text_size'], 0) == int(l['size'], 0) for l in loads['loads']):
        return False
    program = json.loads(Path(map_path).read_text())
    result = []
    for load in loads['loads']:
        if (load['encoding'] != 'ares_tlb' or not load.get('slot') or
                int(load['text_size'], 0) != int(load['size'], 0)):
            result.append(load)
            continue
        start, size, physical, entry = (int(load[k], 0) for k in ('destination', 'size', 'physical', 'entry'))
        # An exact declaration identity selects placement metadata. It supplies
        # only partition policy; composition still authenticates every fragment.
        matches = [(image, declared['destination']['start'])
                   for image, context in program.get('load_images', {}).items()
                   for declared in context['loads']
                   if declared.get('linked') == start and declared['destination']['size'] == size
                   and declared['encoding'] == {'ares_tlb': dict(entry=entry, physical=physical, text_size=size)}]
        if len(matches) != 1:
            result.append(load)
            continue
        image, placed = matches[0]
        protected = [(address['pc'] - placed, address['pc'] - placed + function['source_size'])
                     for address, function in program.get('runtime_functions', [])
                     if address['image'] == image and placed <= address['pc'] < placed + size
                     and function.get('source_size')]
        # Conservatively keep whole known tables together, including candidate
        # evidence. Extra/stale ranges can only suppress cuts, never grant code.
        for evidence in program.get('evidence', {}).values():
            try:
                detail = json.loads(evidence['detail'])
            except (ValueError, TypeError):
                continue
            if not isinstance(detail, dict):
                continue
            table, count = detail.get('table_start', detail.get('source_cell')), detail.get('count', 1)
            if type(table) is int and type(count) is int and count > 0:
                for base in (placed, start):
                    if base <= table < base + size:
                        site = detail.get('site', {}).get('pc')
                        if type(site) is int and placed <= site < placed + size:
                            # The consuming native entry must bind the proof
                            # input too, even when it is on a different page.
                            protected.append((min(site - placed, table - base),
                                              max(site - placed + 8, table - base + 4 * count)))
                        else:
                            protected.append((0, size))
        cuts = [0, *[v - start for v in range((start | 0xfff) + 1, start + size, 0x1000)
                     if not any(lo < v - start < hi for lo, hi in protected)], size]
        for lo, hi in zip(cuts, cuts[1:]):
            result.append(dict(load, destination=hex(start + lo), physical=hex(physical + lo),
                               size=hex(hi - lo), text_size=hex(hi - lo)))
    if result == loads['loads'] or sum(bool(l.get('slot')) for l in result) > 1024:
        return False
    loads['loads'] = result
    loads['source'] += '; independent mapped fragments at 4 KiB boundaries, preserving known host/proof extents'
    Path(loads_path).write_text(json.dumps(loads, indent=2) + '\n')
    return True
