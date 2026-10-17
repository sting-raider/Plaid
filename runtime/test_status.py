"""SDK mask/Status words against independent COP0 + MI operations on pinned ares."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


def run(exe, cc, T):
    A, out = T.A, T.OUT
    T.build(exe, cc, 'status-fixture', list(A.DONE), [])
    cases = []
    for i in range(256):
        status = [0xff01, 0xff00, 0x20005501, 0x8000aa01][i % 4]
        global_mask = [0x003fff01, 0x0015b501, 0, 0x002a4a01][i // 4 % 4]
        requested = ((i & 63) << 16) | ((1 << (i // 32)) << 8) | (i & 1)
        cases.append((status, i * 17 & 63, global_mask, requested))
    (out / 'status-cases.h').write_text('static const u32 status_cases[][4] = {\n' +
        ',\n'.join('{' + ','.join(hex(v) + 'u' for v in c) + '}' for c in cases) + '\n};\n')
    native = out / ('status-contract.exe' if os.name == 'nt' else 'status-contract')
    subprocess.run([cc, '-O2', '-std=gnu11', '-Wall', '-Werror', '-Wno-unused-label', '-Wno-unused-function',
                    '-DPLAID_SAFEPOINTS', '-DPLAID_LOWERED="status-fixture.c"', '-I', str(out),
                    str(T.ROOT / 'runtime/test_status.c'), '-pthread', '-o', str(native)], check=True)
    oracle = T.ROOT / 'target/native-slice/oracle/oracle'
    def linux(path):
        return subprocess.check_output(['wsl', '-d', 'Ubuntu', '--exec', 'wslpath', '-a', str(path)], text=True).strip()
    if not oracle.exists():
        if os.name == 'nt':
            subprocess.run(['wsl', '-d', 'Ubuntu', '--exec', 'python3', linux(T.ROOT / 'spikes/096-native-slice/run.py'), '--oracle'], check=True)
        else:
            A.builder().build(T.ROOT / 'spikes/096-native-slice/driver.cpp', oracle.parent)
    metadata = json.loads((oracle.parent / 'build.json').read_text())
    assert metadata['revision'] == A.builder().REV
    for key, source in [('driver', '096-native-slice'), ('fixture_driver', '003-ares-oracle')]:
        assert metadata[key] == hashlib.sha256((T.ROOT / f'spikes/{source}/driver.cpp').read_bytes()).hexdigest()
    mfc0 = lambda r: 0x40006000 | r << 16
    mtc0 = lambda r: 0x40806000 | r << 16
    command = lambda mask: sum((2 if mask >> bit & 1 else 1) << (2 * bit) for bit in range(6))
    raw = out / 'status-reference.bin'
    oracle_args = [str(oracle), str(raw), hex(A.EXIT)]
    if os.name == 'nt':
        oracle_args = ['wsl', '-d', 'Ubuntu', '--exec', linux(oracle), linux(raw), hex(A.EXIT)]
    def reference_state(program, invalid=None):
        program = [A.j('reference_body'), A.nop] + [A.nop] * (0x2000 // 4 - 2) + ['reference_body'] + program
        labels = A.label_pcs(program)
        words, pc = [], A.BASE
        for item in program:
            if isinstance(item, str): continue
            words.append((item(pc, labels) if callable(item) else item) & 0xffffffff)
            pc += 4
        raw.write_bytes(b''.join(word.to_bytes(4, 'big') for word in words))
        result = subprocess.run(oracle_args, capture_output=True, text=True, timeout=120)
        if invalid:
            assert result.returncode == 6 and invalid in result.stderr, (result.stdout,result.stderr)
            return None
        assert result.returncode == 0, (result.stdout, result.stderr)
        state = json.loads(result.stdout)
        assert state['pc'] == A.EXIT
        return state
    acknowledge = [word for address, value in [(0xa4040010, 8), (0xa4800018, 0),
                    (0xa450000c, 0), (0xa4400010, 0), (0xa4600010, 2), (0xa4300000, 0x800)]
                   for word in T.poke(address, value)]
    from status_reference import context_program
    context = reference_state(acknowledge + context_program(T))['ram']
    for status, marker in [(0xff02,'exl=1'), (0xff04,'erl=1')]:
        reference_state([*T.li(A.t0,status),mtc0(A.t0),A.nop,A.nop,*A.DONE], invalid=marker)
    results = []
    for batch in range(16):
        # Keep executable text clear of the fixed oracle RAM output slice.
        program = []
        for register in range(A.s0, A.s7 + 1):
            program += T.li(register, 0x12340000 + register)
        # Power/reset device conditions are outside this isolated mask test.
        # Acknowledge all six MI sources before enabling any CPU/MI mask.
        program += acknowledge
        program += T.li(A.gp, 0x80001000)
        for n, (status, mi, global_mask, requested) in enumerate(cases[batch * 16:batch * 16 + 16]):
            # Independent reference: architectural reads/writes plus six MI
            # clear/set command pairs, with no runtime replacement or SDK code.
            program += [*T.li(A.t0, status), mtc0(A.t0), A.nop, A.nop,
                        *T.poke(0xa430000c, command(mi)), mfc0(A.t0),
                        A.andi(A.t2, A.t0, 0xff01), *T.li(A.t1, (~global_mask) & 0xff00),
                        A.or_(A.t2, A.t2, A.t1), *T.li(A.t3, 0xa430000c), A.lw(A.t4, 0, A.t3)]
            skip = f'no_mi_{n}'
            program += [A.beq(A.t4, A.zero, skip), A.nop,
                        *T.li(A.t1, (~(global_mask >> 16)) & 63), A.or_(A.t4, A.t4, A.t1),
                        A.sll(A.t4, A.t4, 16), A.or_(A.t2, A.t2, A.t4), skip,
                        A.sw(A.t2, n * 16, A.gp), *T.li(A.t1, 0xffff00ff),
                        A.and_(A.t0, A.t0, A.t1), *T.li(A.t1, requested & global_mask & 0xff00),
                        A.or_(A.t0, A.t0, A.t1), mtc0(A.t0), A.nop, A.nop,
                        *T.poke(0xa430000c, command((requested & global_mask) >> 16)),
                        mfc0(A.v0), A.sw(A.v0, n * 16 + 4, A.gp),
                        A.sra(A.t1, A.v0, 31), A.sw(A.t1, n * 16 + 8, A.gp),
                        A.lw(A.t1, 0, A.t3), A.sw(A.t1, n * 16 + 12, A.gp)]
        program += A.DONE
        expected = reference_state(program)
        actual = subprocess.run([str(native), str(batch)], capture_output=True, text=True, timeout=30)
        assert actual.returncode == 0, (actual.stdout, actual.stderr)
        record = json.loads(actual.stdout)
        observed = record['words']
        assert context[:30] == record['context'] and not any(context[30:]), (context, record['context'])
        assert expected['pc'] == A.EXIT and expected['ram'] == observed, (batch, expected['ram'], observed)
        assert all(expected['regs'][r] == 0x12340000 + r for r in range(A.s0, A.s7 + 1))
        results.append(dict(batch=batch, words=observed))
    (out / 'status-differential.json').write_text(json.dumps(results, indent=2))
    print('Status/masks: 256 pinned-ares cases; CPU IM/IE, six MI bits, global inhibition, signed MFC0; context, saved state, CU1/FR and pending events')
    from test_status_threads import run as threads
    threads(exe, cc, T)


if __name__ == '__main__':
    import test_runtime as T
    run(T.ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid'),
        os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang'), T)
