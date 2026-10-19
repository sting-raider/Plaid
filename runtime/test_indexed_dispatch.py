"""Authored indexed JR loops: native state must match the pinned ares oracle."""
from pathlib import Path
import importlib.util
import json
import os
import shutil
import subprocess

from test_tlb_execution import _ares_run

ROOT = Path(__file__).resolve().parents[1]
SLICE = ROOT / 'spikes/096-native-slice'
OUT = ROOT / 'target/indexed-dispatch-contract'
BASE, EXIT = 0x80000000, 0x80000F00


def _fixture(A, variable_shift=False, shift=2, overwrite=False):
    # The pointer is computed before its guard. The loop also exercises the
    # unsigned rejection of -1 and every admitted table index.
    scaled = A.sllv(A.t2, A.a0, A.t5) if variable_shift else A.sll(A.t2, A.a0, 2)
    items = [A.addiu(A.t0, A.zero, 0), A.addiu(A.s1, A.zero, 0), 'loop',
             A.addiu(A.t5, A.zero, shift),
             A.addiu(A.a0, A.t0, -1), A.lui(A.t1, 0x8000),
             lambda pc, labels: A.addiu(A.t1, A.t1, labels['table'] & 0xFFFF),
             scaled, A.addu(A.t3, A.t1, A.t2), A.sltiu(A.t4, A.a0, 3),
             A.beq(A.t4, A.zero, 'default'), A.nop,
             A.lw(A.v0, 0, A.t3), A.addiu(A.a1, A.zero, 42), A.jr(A.v0), A.nop,
             'case0', A.addiu(A.s1, A.s1, 1), A.j('next'), A.nop,
             'case1', A.addiu(A.s1, A.s1, 10), A.j('next'), A.nop,
             'case2', A.addiu(A.s1, A.s1, 100), A.j('next'), A.nop,
             'default', A.addiu(A.s1, A.s1, 1000), 'next',
             A.addiu(A.t0, A.t0, 1), A.sltiu(A.t4, A.t0, 4),
             A.bne(A.t4, A.zero, 'loop'), A.nop,
             A.lui(A.gp, 0x8000), A.sw(A.s1, 0x1000, A.gp),
             *([A.sw(A.zero, 0, A.t1)] if overwrite else []), *A.DONE,
             'table', *[lambda pc, labels, i=i: labels[f'case{i}'] for i in range(3)]]
    return A.assemble(items)


def main():
    spec = importlib.util.spec_from_file_location('indexed_asm', SLICE / 'run.py')
    A = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(A)
    OUT.mkdir(parents=True, exist_ok=True)
    exe = Path(os.environ.get('PLAID_EXE', ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')))
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    if not exe.exists() or not cc:
        raise RuntimeError('indexed dispatch contract requires plaid and a C compiler')
    for name, variable, overwrite in [('precomputed', False, False), ('sllv', True, False),
                                      ('table-write', True, True)]:
        raw = OUT / f'{name}.bin'
        raw.write_bytes(_fixture(A, variable, overwrite=overwrite))
        native_c = OUT / f'{name}.c'
        lowered = subprocess.run([str(exe), 'lower-c', str(raw), hex(BASE), hex(BASE),
                                  hex(EXIT), str(native_c), '--address-taken'],
                                 capture_output=True, text=True)
        assert lowered.returncode == 0, (name, lowered.stdout, lowered.stderr)
        native = OUT / (f'{name}.exe' if os.name == 'nt' else name)
        subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
                        f'-DPLAID_LOWERED="{native_c.name}"', f'-DPLAID_EXIT=0x{EXIT:x}u',
                        '-I', str(OUT), str(SLICE / 'harness.c'), '-o', str(native)], check=True)
        actual = subprocess.run([str(native)], capture_output=True, text=True, timeout=30)
        if overwrite:
            assert actual.returncode == 6 and json.loads(actual.stdout)['fault'] == 2, actual.stdout
            continue
        expected = _ares_run(raw)
        assert actual.returncode == expected.returncode == 0, (actual.stdout, actual.stderr, expected.stderr)
        state = json.loads(actual.stdout)
        assert state == json.loads(expected.stdout), (actual.stdout, expected.stdout)
        assert state['pc'] == EXIT and state['regs'][17] == 1111 and state['ram'][0] == 1111

    bad = OUT / 'wrong-scale.bin'
    bad.write_bytes(_fixture(A, True, shift=3))
    rejected_c = OUT / 'wrong-scale.c'
    rejected_c.unlink(missing_ok=True)
    rejected = subprocess.run([str(exe), 'lower-c', str(bad), hex(BASE), hex(BASE),
                               hex(EXIT), str(rejected_c), '--address-taken'], capture_output=True, text=True)
    assert rejected.returncode != 0 and not rejected_c.exists(), (rejected.stdout, rejected.stderr)
    print('PASS indexed dispatch: precomputed/SLLV loops match pinned ares full state; table writes fault and wrong stride refuses emission')


if __name__ == '__main__':
    main()
