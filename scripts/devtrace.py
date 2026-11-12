"""Differential device-boundary trace: native build against pinned ares (ADR-0329).

    python scripts/devtrace.py <rom.z64> <native exe> [--vis N] [--seconds S] [--keep DIR]
                               [--press <buttons>@<vi>:<frames>]...

Both sides log every RSP task start (type, physical data pointer, size, FNV
hash of the data bytes), every retrace's framebuffer origin, and every RDP
frame: the FNV hash of the command words up to each SYNC_FULL. The native run
uses --rsp-gfx, so its RDP commands come from the lowered microcode as ares's
come from its RSP. Native VIs are paced by wall time and ares VIs by guest
time, so streams are compared in order and by membership, not by VI number:
a native frame whose commands ares never produced is the lead to chase.
Audio tasks size themselves to elapsed time and diverge early by design.
Presses use the native runtime's syntax. Native runs first; each press then
starts in ares after the same number of RDP frames native had finished by its
VI, so it lands on the same game frame while the frames still match.
Traces derive from game data and stay local; only the summary is printed.
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
# ares_boot.capture_many's table (not imported: that file keys the replay cache).
CICS = {0x6170a4a1: '6101', 0x90bb6cb5: '6102', 0x0b050ee0: '6103', 0x98bc2c86: '6105', 0xacc8580a: '6106'}
TASK = re.compile(r'^task (\d+) data ([0-9a-f]+) size (\d+) hash ([0-9a-f]+) vi (\d+)', re.M)
ORIGIN = re.compile(r'^vi (\d+)(?: ns \d+)? origin ([0-9a-f]+)', re.M)
FRAME = re.compile(r'^rdp (\d+) commands (\d+) hash ([0-9a-f]+) vi (\d+)(?: ops(.*))?$', re.M)


def oracle():
    import ares_oracle
    directory = ROOT / 'target/ares-trace'
    directory.mkdir(parents=True, exist_ok=True)
    # The HLE boot table patches serialized state by offset, so the build
    # options must match ares_boot.build_oracle's (the RDP recipe adds no state).
    return ares_oracle.build(ROOT / 'scripts/ares_trace.cpp', directory,
                             raw_fetch_access=True, physical_fetch_access=True,
                             rdram_burst_access=True, rdram_scalar_access=True, pi_dma_access=True,
                             cpu_instruction_access=True, rdp_command_queue=True,
                             extra_sources=[ROOT / 'scripts/ares_hle_boot.hpp', ROOT / 'scripts/ares_hle_boot_tables.hpp'])


def parse(text):
    tasks = [(int(t), d, int(s), h) for t, d, s, h, _ in TASK.findall(text)]
    origins = []
    for _, o in ORIGIN.findall(text):
        if o != '00000000' and (not origins or origins[-1] != o):  # 0: VI not yet set up
            origins.append(o)
    frames = [(int(c), h, int(v), {int(k, 16): int(n) for k, n in (p.split(':') for p in ops.split())})
              for _, c, h, v, ops in FRAME.findall(text)]
    return tasks, origins, frames


def first_split(a, b):
    return next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), None)


def compare(native, ares):
    """Lines describing where the two parsed traces part; pure, so testable."""
    out = []
    for kind, name in ((1, 'graphics'), (2, 'audio')):
        n = [t for t in native[0] if t[0] == kind]
        a = [t for t in ares[0] if t[0] == kind]
        split = first_split(n, a)
        known = {t[3] for t in a}
        unseen = sum(t[3] not in known for t in n[:len(a)])
        where = 'none' if split is None else f'at task {split}: native {n[split][1:]} ares {a[split][1:]}'
        out.append(f'{name} tasks: native {len(n)} ares {len(a)}; first divergence {where}; '
                   f'{unseen} of the first {min(len(n), len(a))} native hashes never occur in ares')
    other = sorted({t[0] for t in native[0] + ares[0]} - {1, 2})
    if other:
        out.append(f'other task types seen: {other}')
    split = first_split(native[1], ares[1])
    out.append(f'framebuffers: native {len(native[1])} ares {len(ares[1])} changes; '
               + ('same order' if split is None else f'first differs at change {split}: native {native[1][split]} ares {ares[1][split]}'))
    n, a = native[2], ares[2]
    if n or a:
        known = {f[:2] for f in a}
        within = n[:len(a)]
        missing = [i for i, f in enumerate(within) if f[:2] not in known]
        split = first_split([f[:2] for f in n], [f[:2] for f in a])
        out.append(f'RDP frames: native {len(n)} ares {len(a)}; first divergence '
                   + ('none' if split is None else f'at frame {split}')
                   + f'; {len(missing)} of the first {len(within)} native frames never occur in ares'
                   + (f', first at frame {missing[0]} (native vi {within[missing[0]][2]}, {within[missing[0]][0]} commands)' if missing else ''))
        # Timing-seeded state (random stars, animation phase) breaks exact frame
        # equality; missing geometry still shows as a shifted per-second opcode
        # mean. Both VI clocks run at 60 Hz, but boot and loading take different
        # VI counts, so ares is shifted by the whole seconds (within 3) that best
        # match the per-second command counts. The last second is skipped (a
        # run's end lands mid-scene-change).
        seconds = lambda fs: {s: [f for f in fs if f[2] // 60 == s] for s in {f[2] // 60 for f in fs}}
        sn, sa = seconds(n), seconds(a)
        mean = lambda fs, op=None: sum(f[0] if op is None else f[3].get(op, 0) for f in fs) / len(fs)

        def cost(shift):
            pairs = [(s, s + shift) for s in sn if s + shift in sa]
            return sum(abs(mean(sn[x]) - mean(sa[y])) for x, y in pairs) / len(pairs) if len(pairs) > 3 else float('inf')
        shift = min(range(-3, 4), key=lambda d: (cost(d), abs(d)))
        shared = sorted(s for s in sn if s + shift in sa)[:-1]
        for s in shared:
            for op in sorted({op for f in sn[s] + sa[s + shift] for op in f[3]}):
                x, y = mean(sn[s], op), mean(sa[s + shift], op)
                if abs(x - y) > max(2.0, 0.1 * max(x, y)):
                    out.append(f'  second {s}: opcode {op:02x} per frame native {x:.1f} ares {y:.1f}')
        out.append(f'per-second opcode means compared over {len(shared)} seconds, ares shifted {shift:+d} s')
    return out


def ares_presses(presses, native_frames):
    """Re-key `<buttons>@<vi>:<frames>` from native VIs to native RDP frames done."""
    out = []
    for press in presses:
        buttons, rest = press.split('@')
        at, length = (int(x, 0) for x in rest.split(':'))
        out.append(f'{buttons}@{sum(f[2] < at for f in native_frames)}:{length}')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rom', type=Path)
    ap.add_argument('exe', type=Path)
    ap.add_argument('--vis', type=int, default=900, help='ares retraces to trace (60 per second)')
    ap.add_argument('--seconds', type=float, help='native run length (default: vis / 60)')
    ap.add_argument('--keep', type=Path, help='directory for both raw traces')
    ap.add_argument('--press', action='append', default=[], help='as the native runtime: <buttons>@<vi>:<frames>')
    a = ap.parse_args()
    data = a.rom.read_bytes()
    if data[:4] != bytes.fromhex('80371240'):
        sys.exit('devtrace needs a big-endian .z64 ROM')
    cic = CICS.get(zlib.crc32(data[0x40:0x1000]))
    if not cic:
        sys.exit('unsupported IPL3: no measured HLE boot state')
    keep = a.keep or Path(tempfile.mkdtemp(prefix='plaid-devtrace-'))
    keep.mkdir(parents=True, exist_ok=True)
    ares_log, native_log = keep / 'ares.trace', keep / 'native.trace'
    env = dict(os.environ, SDL_AUDIODRIVER='dummy', PLAID_TRACE_TASK='1', PLAID_TRACE_VI='1', PLAID_TRACE_RDP='1')
    seconds = a.seconds or a.vis / 60
    exe = oracle()
    presses = [arg for p in a.press for arg in ('--press', p)]
    with native_log.open('w') as err:
        subprocess.run([str(a.exe), '--rom', str(a.rom), '--stop-at', 'none', '--seconds', str(seconds), '--rsp-gfx', *presses],
                       stdout=subprocess.DEVNULL, stderr=err, env=env)
    native = parse(native_log.read_text(errors='replace'))
    subprocess.run([str(exe), str(a.rom), 'CIC-NUS-' + cic, str(a.vis), str(ares_log), *ares_presses(a.press, native[2])], check=True)
    for line in compare(native, parse(ares_log.read_text())):
        print(line)
    print('traces in', keep)


if __name__ == '__main__':
    main()
