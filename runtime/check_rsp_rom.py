"""Compare saved IMEM snapshots with a ROM-derived registry, without using them
to discover or lower text. Trailing initialized zero padding is excluded.

    python runtime/check_rsp_rom.py <rsp-files.json> <snapshot directory>

Word coverage is an oracle for the retained snapshots, not a reachability proof.
"""
import hashlib
import json
import sys
from pathlib import Path


def check(manifest, snapshots):
    manifest = Path(manifest)
    data = json.loads(manifest.read_text())
    assert data['schema'] in ('plaid-rsp-rom-v0', 'plaid-rsp-rom-v1')
    words = [set() for _ in range(1024)]
    for text in data['texts']:
        raw = (manifest.parent / (text['name'] + '.bin')).read_bytes()
        assert len(raw) == text['size'] and hashlib.sha256(raw).hexdigest() == text['sha256']
        for offset in range(0, len(raw), 4):
            words[(text['imem'] + offset) // 4].add(raw[offset:offset + 4])
    results = []
    for snapshot in sorted(Path(snapshots).glob('imem-*.bin')):
        raw = snapshot.read_bytes()
        assert len(raw) == 4096, snapshot
        end = (len(raw.rstrip(b'\0')) + 3) & ~3
        missing = [pc for pc in range(0, end, 4) if raw[pc:pc + 4] not in words[pc // 4]]
        results.append(dict(snapshot=snapshot.name, sha256=hashlib.sha256(raw).hexdigest(),
                            words=end // 4, missing_words=len(missing),
                            first_missing=missing[:8], covered=not missing))
    return dict(texts=len(data['texts']), snapshots=len(results),
                covered=sum(r['covered'] for r in results), results=results)


if __name__ == '__main__':
    report = check(*sys.argv[1:])
    print(json.dumps(report, indent=2))
    sys.exit(0 if report['snapshots'] and report['covered'] == report['snapshots'] else 1)
