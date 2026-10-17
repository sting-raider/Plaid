"""Classify a retained solve/map pair, optionally reading local captured images.

Usage: python research/classify-sweep-blockers.py solve.json map.json [BASE:image.bin ...]
Images are diagnostic outputs only; this script never supplies compiler inputs.
"""
import collections
import json
from pathlib import Path
import sys


def classify(verdict, program, images):
    rows = []
    for blocker in verdict['blockers']:
        site = blocker.get('site')
        pc = site['pc'] if site else None
        word = next((int.from_bytes(data[pc - base:pc - base + 4], 'big')
                     for base, data in images
                     if pc is not None and base <= pc <= base + len(data) - 4), None)
        blocks = [b for b in program['blocks'] if site and
                  b['start']['image'] == site['image'] and
                  b['start']['generation'] == site['generation'] and
                  b['start']['pc'] <= pc < b['start']['pc'] + b['size']]
        incoming = [e for e in program['direct_edges'] if e['target'] == site or
                    any(e['target'] == b['start'] for b in blocks)]
        indirect = [s for s in program['indirect_sites'] if s['site'] == site]
        effect = None
        if word is not None:
            op, rs = word >> 26, (word >> 21) & 31
            if op == 16:
                effect = {0: 'MFC0', 1: 'DMFC0', 4: 'MTC0', 5: 'DMTC0'}.get(rs, 'COP0/system')
                if rs in (0, 1, 4, 5):
                    register = (word >> 11) & 31
                    effect += ':' + {0: 'Index', 1: 'Random', 2: 'EntryLo0', 3: 'EntryLo1',
                                     5: 'PageMask', 6: 'Wired', 8: 'BadVAddr', 9: 'Count',
                                     10: 'EntryHi', 11: 'Compare', 12: 'Status', 13: 'Cause',
                                     14: 'EPC', 16: 'Config', 30: 'ErrorEPC'}.get(register, str(register))
                else:
                    effect = {0x42000001: 'TLBR', 0x42000002: 'TLBWI',
                              0x42000006: 'TLBWR', 0x42000008: 'TLBP',
                              0x42000018: 'ERET'}.get(word, effect)
            elif op == 47:
                effect = 'CACHE'
        rows.append(dict(kind=blocker['kind'], pc=f'{pc:08x}' if pc is not None else None,
                         word=f'{word:08x}' if word is not None else None, effect=effect,
                         detail=blocker['detail'], blocks=blocks,
                         incoming=incoming, indirect=indirect))
    assert len(rows) == len(verdict['blockers'])
    return dict(status=verdict['status'], total=len(rows),
                kinds=dict(sorted(collections.Counter(r['kind'] for r in rows).items())),
                effects=dict(sorted(collections.Counter(r['effect'] for r in rows if r['effect']).items())),
                blockers=rows)


if __name__ == '__main__':
    solve, mapping, *specs = sys.argv[1:]
    images = []
    for spec in specs:
        base, path = spec.split(':', 1)
        images.append((int(base, 0), Path(path).read_bytes()))
    print(json.dumps(classify(json.loads(Path(solve).read_bytes()),
                              json.loads(Path(mapping).read_bytes()), images), indent=2))
