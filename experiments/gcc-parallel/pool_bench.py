"""Cold wall time of native.compile_all over one build directory's C units (no object cache).
usage: python pool_bench.py <dir holding <name>.c and <name>.part*.c>"""
import subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import native
root = Path(sys.argv[1])
for stale in list(root.glob('*.o')) + list(root.glob('*.sha256')):
    stale.unlink()
units = [root / f'{root.name}.c', *sorted(root.glob(f'{root.name}.part*.c'))]
cc = ['gcc', '-O1', '-std=gnu11', '-w', '-DPLAID_SAFEPOINTS']
started = time.perf_counter()
native.compile_all([(u, cc, b'') for u in units], subprocess.check_output(['gcc', '--version']))
print(f'{root.name}: {len(units)} units, {native.compile_workers()} workers, {time.perf_counter() - started:.1f} s wall')
