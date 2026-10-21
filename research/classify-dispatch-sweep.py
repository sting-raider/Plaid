"""Count residual-solve blocker kinds per ROM build directory."""
import collections, json, subprocess, sys
from pathlib import Path

TREE = Path(sys.argv[1])
ROMS = Path(r'C:\Users\aliza\Documents\ROMs\N64')
for rom, name in [('Mario Kart 64 (USA).z64', 'mariokart64usa'), ('Star Fox 64 (USA) (Rev 1).z64', 'starfox64usarev1'),
                  ('Star Wars - Rogue Squadron (USA) (Rev 1).z64', 'starwarsroguesqu'), ('GoldenEye 007 (USA).z64', 'goldeneye007usa')]:
    m = TREE / 'target/native' / name / 'map.json'
    if not m.exists():
        print(rom, 'no map'); continue
    v = json.loads(subprocess.run([str(TREE / 'target/release/plaid'), 'solve', str(ROMS / rom), str(m), '--residual-dispatch'],
                                  capture_output=True, text=True).stdout)
    kinds = collections.Counter(b['kind'] for b in v['blockers'])
    details = collections.Counter(b.get('detail', '')[:90] for b in v['blockers'])
    print('==', rom, dict(kinds))
    for d, n in details.most_common(4):
        print('  ', n, d)
