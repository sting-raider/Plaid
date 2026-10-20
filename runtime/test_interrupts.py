"""Synthetic IE restoration under the runtime ABI and pinned ares instructions."""
import hashlib
import json
import os
import shutil
import subprocess


def run(exe, cc, T):
    A, out = T.A, T.OUT
    out.mkdir(parents=True, exist_ok=True)
    program = [*T.li(A.sp, 0x80007F00), *T.li(A.gp, 0x80001000)]
    for register in range(A.s2, A.s7 + 1):
        program += T.li(register, 0x81234000 + register)
    program += [*T.li(A.fp, 0x89ABCDEF), *T.li(A.t2, 0x13579BDF), A.mthi(A.t2),
                *T.li(A.t2, 0x2468ACE0), A.mtlo(A.t2)]

    def observe(offset, saved=None):
        return [*T.call('__osDisableInt'), A.sw(A.v0, offset, A.gp),
                *([A.addu(saved, A.v0, A.zero)] if saved is not None else [])]

    program += [*T.call('__osRestoreInt', 1), *observe(0, A.s0), *observe(4, A.s1),
                *T.call('__osRestoreInt', 0), *observe(8),
                *T.call('__osRestoreInt', 1), *T.call('__osRestoreInt', 0), *observe(12),
                A.addu(A.a0, A.s0, A.zero), A.jal('__osRestoreInt'), A.nop, *observe(16),
                A.addu(A.a0, A.s1, A.zero), A.jal('__osRestoreInt'), A.nop, *observe(20),
                *T.call('__osRestoreInt', 1), *T.call('__osRestoreInt', 1), *observe(24),
                *T.call('__osRestoreInt', 0), *observe(28)]
    for index, register in enumerate([*range(A.s0, A.s7 + 1), A.gp, A.sp, A.fp]):
        program.append(A.sd(register, 0x40 + index * 8, A.gp))
    program += [A.mfhi(A.t2), A.sd(A.t2, 0x98, A.gp),
                A.mflo(A.t2), A.sd(A.t2, 0xA0, A.gp), *A.DONE]
    # Independent synthetic reference routines. Native lowering substitutes the
    # declared runtime boundaries; only the analysis-time oracle runs COP0.
    mfc0 = lambda r: 0x40000000 | r << 16 | 12 << 11
    mtc0 = lambda r: 0x40800000 | r << 16 | 12 << 11
    program += ['__osDisableInt', mfc0(A.t0), A.andi(A.v0, A.t0, 1),
                A.addiu(A.t1, A.zero, -2), A.and_(A.t0, A.t0, A.t1), mtc0(A.t0),
                A.nop, A.nop, A.jr(A.ra), A.nop,
                '__osRestoreInt', mfc0(A.t0), A.or_(A.t0, A.t0, A.a0), mtc0(A.t0),
                A.nop, A.nop, A.jr(A.ra), A.nop]
    native = T.build(exe, cc, 'interrupt-restore', program, ['__osDisableInt', '__osRestoreInt'])
    raw = out / 'interrupt-restore.bin'
    oracle = T.ROOT / 'target/native-slice/oracle/oracle'
    if os.name == 'nt':
        def linux(path):
            return subprocess.check_output(['wsl', '-d', 'Ubuntu', '--exec', 'wslpath', '-a', str(path)], text=True).strip()
        if not oracle.exists():
            subprocess.run(['wsl', '-d', 'Ubuntu', '--exec', 'python3', linux(T.ROOT / 'spikes/096-native-slice/run.py'), '--oracle', '--build-only'], check=True)
        command = ['wsl', '-d', 'Ubuntu', '--exec', linux(oracle), linux(raw), hex(A.EXIT)]
    else:
        if not oracle.exists():
            A.builder().build(T.ROOT / 'spikes/096-native-slice/driver.cpp', oracle.parent)
        command = [str(oracle), str(raw), hex(A.EXIT)]
    metadata = json.loads((oracle.parent / 'build.json').read_text())
    assert metadata['revision'] == A.builder().REV
    for key, source in [('driver', '096-native-slice'), ('fixture_driver', '003-ares-oracle')]:
        assert metadata[key] == hashlib.sha256((T.ROOT / f'spikes/{source}/driver.cpp').read_bytes()).hexdigest()
    reference = subprocess.run(command, capture_output=True, text=True, timeout=120)
    assert reference.returncode == 0, (reference.stdout, reference.stderr)
    state = json.loads(reference.stdout)
    expected = [1, 0, 0, 1, 1, 0, 1, 0]
    assert state['pc'] == A.EXIT and state['ram'][:8] == expected, state
    (out / 'interrupt-restore-oracle.json').write_text(json.dumps(state, indent=2))
    actual = subprocess.run([str(native), '--dump', '0x80001000', '64'], capture_output=True, text=True, timeout=30)
    rows = [json.loads(line) for line in actual.stdout.splitlines() if line.startswith('{')]
    stop = next(row for row in rows if 'stop' in row)
    memory = next(row['words'] for row in rows if 'dump' in row)
    assert actual.returncode == 0 and stop['stop'] == 'exit' and stop['fault'] == 0, (actual.stdout, actual.stderr)
    assert memory == state['ram'], (memory, state['ram'])
    print('interrupt restore: enabled/disabled zero, nested and repeated restore; RAM, ABI-preserved GPR/HI/LO and normal exit match pinned ares')
    events = out / ('interrupt-events.exe' if os.name == 'nt' else 'interrupt-events')
    subprocess.run([cc, '-O2', '-std=gnu11', '-Wall', '-Werror', '-Wno-unused-label', '-Wno-unused-function',
                    '-DPLAID_SAFEPOINTS', '-DPLAID_LOWERED="interrupt-restore.c"', '-I', str(out),
                    str(T.ROOT / 'runtime/test_interrupts.c'), '-pthread', '-o', str(events)], check=True)
    subprocess.run([str(events)], check=True, timeout=30)


if __name__ == '__main__':
    import test_runtime as T
    run(T.ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid'),
        os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang'), T)
