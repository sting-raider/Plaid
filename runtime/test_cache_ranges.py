"""Signed lengths, line bounds and threshold behavior of D-cache runtime calls."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import ares_oracle
import json
import os
import shutil
import subprocess


OLD, NEW = 0x11223344, 0xAABBCCDD
BASE = 0x80004000
SENTINEL = 0xC0DECAFE


def _cache(op, base):
    return 47 << 26 | base << 21 | op << 16


def _wb_body(A):
    return [
        A.blez(A.a1, 'wb_return'), A.nop,
        A.addiu(A.t3, A.zero, 8192), A.sltu(A.t2, A.a1, A.t3),
        A.beq(A.t2, A.zero, 'wb_all'), A.nop,
        A.addu(A.t0, A.a0, A.zero), A.addu(A.t1, A.a0, A.a1),
        A.sltu(A.t2, A.t0, A.t1), A.beq(A.t2, A.zero, 'wb_return'), A.nop,
        A.addiu(A.t1, A.t1, -16), A.andi(A.t2, A.t0, 15), A.subu(A.t0, A.t0, A.t2),
        'wb_loop', _cache(0x19, A.t0), A.sltu(A.t2, A.t0, A.t1),
        A.bne(A.t2, A.zero, 'wb_loop'), A.addiu(A.t0, A.t0, 16),
        'wb_return', A.addu(A.v0, A.zero, A.zero), A.jr(A.ra), A.nop,
        'wb_all', A.lui(A.t0, 0x8000), A.addiu(A.t1, A.t0, 8192),
        A.addiu(A.t1, A.t1, -16),
        'wb_all_loop', _cache(0x01, A.t0), A.sltu(A.t2, A.t0, A.t1),
        A.bne(A.t2, A.zero, 'wb_all_loop'), A.addiu(A.t0, A.t0, 16),
        A.addu(A.v0, A.zero, A.zero), A.jr(A.ra), A.nop,
    ]


def _inval_body(A):
    return [
        A.blez(A.a1, 'inv_return'), A.nop,
        A.addiu(A.t3, A.zero, 8192), A.sltu(A.t2, A.a1, A.t3),
        A.beq(A.t2, A.zero, 'inv_all'), A.nop,
        A.addu(A.t0, A.a0, A.zero), A.addu(A.t1, A.a0, A.a1),
        A.sltu(A.t2, A.t0, A.t1), A.beq(A.t2, A.zero, 'inv_return'), A.nop,
        A.andi(A.t2, A.t0, 15), A.subu(A.t0, A.t0, A.t2),
        'inv_loop', A.sltu(A.t2, A.t0, A.a0), A.bne(A.t2, A.zero, 'inv_partial'), A.nop,
        A.addiu(A.t3, A.t0, 16), A.sltu(A.t2, A.t1, A.t3),
        A.bne(A.t2, A.zero, 'inv_partial'), A.nop,
        _cache(0x11, A.t0), A.j('inv_next'), A.nop,
        'inv_partial', _cache(0x15, A.t0),
        'inv_next', A.addiu(A.t0, A.t0, 16), A.sltu(A.t2, A.t0, A.t1),
        A.bne(A.t2, A.zero, 'inv_loop'), A.nop,
        'inv_return', A.addu(A.v0, A.zero, A.zero), A.jr(A.ra), A.nop,
        'inv_all', A.lui(A.t0, 0x8000), A.addiu(A.t1, A.t0, 8192),
        'inv_all_loop', _cache(0x01, A.t0), A.addiu(A.t0, A.t0, 16),
        A.bne(A.t0, A.t1, 'inv_all_loop'), A.nop,
        A.addu(A.v0, A.zero, A.zero), A.jr(A.ra), A.nop,
    ]


def _program(T, name, function, cases, probe='uncached'):
    A = T.A
    program = [*T.li(A.sp, 0x80007F00), *T.li(A.gp, 0x80001000)]
    for i, (size, offset) in enumerate(cases):
        address = BASE + i * 0x4000
        program += [*T.poke(address | 0x20000000, OLD), *T.li(A.t0, address), A.lw(A.t1, 0, A.t0),
                    *T.poke(address, NEW)]
        arg = 0xFFFFFFF0 if offset == 'wrap' else address + offset
        program += T.call(name, arg, size)
        if probe == 'cached':
            program += T.poke(0x80001000, SENTINEL)
            program += [*T.li(A.t0, address), A.lw(A.t1, 0, A.t0)]
        elif probe == 'uncached':
            program += [*T.li(A.t0, address | 0x20000000), A.lw(A.t1, 0, A.t0)]
        if probe in ('cached', 'uncached'):
            program += [A.sw(A.t1, 0, A.gp), A.addiu(A.gp, A.gp, 4)]
    if probe == 'noop-suite':
        address = BASE
        program += [*T.poke(address | 0x20000000, OLD), *T.li(A.t0, address), A.lw(A.t1, 0, A.t0),
                    *T.poke(address, NEW)]
        for size, arg in ((0, address), (0xFFFFFFFF, address), (0x80000000, address), (32, 0xFFFFFFF0)):
            program += T.call(name, arg, size)
            program += [*T.li(A.t0, address), A.lw(A.t1, 0, A.t0)]
        program += T.poke(0x80001000, SENTINEL)
        program += [*T.li(A.t0, address | 0x20000000), A.lw(A.t1, 0, A.t0)]
    program += [*T.A.DONE, name, *function(A)]
    return program


def _run(exe, cc, T, label, name, function, cases, *, probe='uncached', expect_fault=False):
    binary = T.build(exe, cc, label, _program(T, name, function, cases, probe), [name])
    run = subprocess.run([str(binary), '--dump', '0x80001000', '64'], capture_output=True, text=True, timeout=30)
    rows = [json.loads(line) for line in run.stdout.splitlines() if line.startswith('{')]
    stop = next(row for row in rows if 'stop' in row)
    words = next(row['words'] for row in rows if 'dump' in row)
    oracle = ares_oracle.default()
    image = T.OUT / f'{label}.bin'
    args = [str(oracle), str(image), hex(T.A.EXIT)]
    reference = subprocess.run(args, capture_output=True, text=True, timeout=120)
    assert reference.returncode == 0, (reference.stdout, reference.stderr)
    expected = json.loads(reference.stdout)
    if expect_fault:
        assert run.returncode == 1 and stop['stop'] == 'guest fault' and stop['fault'] == 4, (
            label, run.stdout, run.stderr)
        if label.endswith('noops') or label.endswith('line') or label.endswith('limit'):
            assert words[0] == SENTINEL, (label, hex(words[0]), run.stdout)
        assert expected['pc'] == T.A.EXIT and expected.get('exception', 0) == 0, (label, expected)
        return
    assert run.returncode == 0 and stop['stop'] == 'exit' and stop['fault'] == 0, (label, run.stdout, run.stderr)
    assert expected['pc'] == T.A.EXIT and expected.get('exception', 0) == 0, (label, expected)
    assert expected['ram'] == words, (label, expected['ram'], words)
    assert words[:len(cases)] == [NEW] * len(cases), (label, words[:len(cases)])


def run(exe, cc, T):
    wb_cases = ((8191, 0), (8192, 0), (1, 1), (16, 0), (32, 0))
    _run(exe, cc, T, 'cache-range-writeback', 'osWritebackDCache', _wb_body, wb_cases)
    _run(exe, cc, T, 'cache-range-writeback-noops', 'osWritebackDCache', _wb_body, (),
         probe='noop-suite', expect_fault=True)
    inval_cases = ((1, 1), (8192, 0))
    _run(exe, cc, T, 'cache-range-invalidate', 'osInvalDCache', _inval_body, inval_cases)
    _run(exe, cc, T, 'cache-range-invalidate-noops', 'osInvalDCache', _inval_body, (),
         probe='noop-suite', expect_fault=True)
    _run(exe, cc, T, 'cache-range-invalidate-line', 'osInvalDCache', _inval_body, ((16, 0),),
         probe='cached', expect_fault=True)
    _run(exe, cc, T, 'cache-range-invalidate-limit', 'osInvalDCache', _inval_body, ((8191, 0),),
         probe='cached', expect_fault=True)
    print('cache ranges: signed and wrapped no-ops, line edges, 8191/8192 threshold, and dirty-line fail-closed guard')


if __name__ == '__main__':
    import test_runtime as T
    run(T.ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid'),
        os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang'), T)
