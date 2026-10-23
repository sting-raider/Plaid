"""Lowered CACHE and TagLo against pinned ares (ADR-0259)."""
import json
import os
import subprocess


OLD, NEW = 0x11223344, 0xAABBCCDD
LOG = 0x80001000


def _cache(op, base):
    return 47 << 26 | base << 21 | op << 16


def _dirty(T, address):
    """RAM holds OLD; the cached line holds NEW and is dirty."""
    A = T.A
    return [*T.poke(address | 0x20000000, OLD), *T.li(A.t0, address), A.lw(A.t1, 0, A.t0),
            *T.poke(address, NEW), *T.li(A.t0, address)]


def _log_uncached(T, address):
    A = T.A
    return [*T.li(A.t0, address | 0x20000000), A.lw(A.t1, 0, A.t0), A.sw(A.t1, 0, A.gp), A.addiu(A.gp, A.gp, 4)]


def _program(T, body):
    A = T.A
    mtc0 = lambda rt, rd: 0x40800000 | rt << 16 | rd << 11
    return [*T.li(A.sp, 0x80007F00), *T.li(A.gp, LOG), mtc0(A.zero, 28), mtc0(A.zero, 29), *body(T), *A.DONE]


def _written_back(T):
    A = T.A
    out = []
    # Hit Writeback, Index Writeback Invalidate and Hit Writeback Invalidate
    # each put the dirty line's NEW in RAM; I-cache operations change nothing.
    for i, op in enumerate((0x19, 0x01, 0x15)):
        address = 0x80004000 + i * 0x40
        out += [*_dirty(T, address), _cache(op, A.t0), *_log_uncached(T, address)]
    address = 0x80004100
    out += [*_dirty(T, address), _cache(0x00, A.t0), _cache(0x08, A.t0), _cache(0x10, A.t0),
            _cache(0x19, A.t0), *_log_uncached(T, address)]
    # Index Store Tag with TagLo 0 drops a clean line; RAM is unchanged.
    address = 0x80004140
    out += [*T.poke(address | 0x20000000, OLD), *T.li(A.t0, address), A.lw(A.t1, 0, A.t0),
            _cache(0x09, A.t0), *_log_uncached(T, address)]
    # a Hit operation on a line that is not resident does nothing
    address = 0x80004180
    out += [*T.poke(address | 0x20000000, OLD), *T.li(A.t0, address), _cache(0x15, A.t0),
            *_log_uncached(T, address)]
    return out


def _dropped(op):
    def body(T):
        # Hit Invalidate or Index Store Tag discards dirty NEW on hardware;
        # natively the line is lost, so the next access fails closed.
        address = 0x80004000
        return [*_dirty(T, address), _cache(op, T.A.t0), *_log_uncached(T, address)]
    return body


def _run(exe, cc, T, label, body, expect_lost):
    A, out = T.A, T.OUT
    # kernel mode with COP0 usable, as the ares oracle starts
    binary = T.build(exe, cc, label, _program(T, body), [],
                     ['-DPLAID_BOOT_STATUS=0x34000000u', '-DPLAID_BOOT_ENTRYHI=0ull'])
    run = subprocess.run([str(binary), '--dump', hex(LOG), '8'], capture_output=True, text=True, timeout=30)
    oracle = T.ROOT / 'target/native-slice/oracle/oracle'
    args = [str(oracle), str(out / f'{label}.bin'), hex(A.EXIT)]
    if os.name == 'nt':
        def linux(path):
            return subprocess.check_output(['wsl', '-d', 'Ubuntu', '--exec', 'wslpath', '-a', str(path)],
                                           text=True).strip()
        args = ['wsl', '-d', 'Ubuntu', '--exec', linux(oracle), linux(out / f'{label}.bin'), hex(A.EXIT)]
    reference = subprocess.run(args, capture_output=True, text=True, timeout=120)
    rows = [json.loads(line) for line in run.stdout.splitlines() if line.startswith('{')]
    stop = next(row for row in rows if 'stop' in row)
    words = next(row['words'] for row in rows if 'dump' in row)
    assert reference.returncode == 0, (reference.stdout, reference.stderr)
    expected = json.loads(reference.stdout)
    assert expected["pc"] == A.EXIT and expected.get('exception', 0) == 0, (label, expected)
    if expect_lost:
        # ares reads the OLD bytes hardware kept; native refuses the lost line
        assert expected['ram'][0] == OLD, (label, expected['ram'])
        assert run.returncode == 1 and stop['fault'] == 4 and words[0] == 0, (label, run.stdout, run.stderr)
        return
    assert run.returncode == 0 and stop['stop'] == 'exit' and stop['fault'] == 0, (label, run.stdout, run.stderr)
    assert words[:6] == [NEW, NEW, NEW, NEW, OLD, OLD], (label, [hex(w) for w in words])
    assert expected['ram'][:8] == words, (label, expected['ram'], words)


def run(exe, cc, T):
    _run(exe, cc, T, 'cache-ops', _written_back, False)
    _run(exe, cc, T, 'cache-ops-hit-invalidate', _dropped(0x11), True)
    _run(exe, cc, T, 'cache-ops-store-tag', _dropped(0x09), True)
    print('CACHE ops: write-back, invalidate, store-tag and I-cache forms match ares; discarded dirty lines fail closed')


if __name__ == '__main__':
    import shutil
    import test_runtime as T
    run(T.ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid'),
        os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang'), T)
