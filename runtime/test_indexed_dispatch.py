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


def _preheader_fixture(A):
    items = [A.lui(A.t1, 0x8000),
             lambda pc, labels: A.addiu(A.t1, A.t1, labels['table'] & 0xFFFF),
             A.lui(A.s0, 0x8000),
             lambda pc, labels: A.addiu(A.s0, A.s0, labels['inputs'] & 0xFFFF),
             'retry', A.lw(A.a0, 0, A.s0), A.sltiu(A.t4, A.a0, 3),
             A.beq(A.t4, A.zero, 'retry'), A.addiu(A.s0, A.s0, 4),
             A.sll(A.t2, A.a0, 2), A.addu(A.t3, A.t1, A.t2),
             A.lw(A.v0, 0, A.t3), A.jr(A.v0), A.nop,
             'case0', A.addiu(A.s1, A.zero, 1), A.j('done'), A.nop,
             'case1', A.addiu(A.s1, A.zero, 10), A.j('done'), A.nop,
             'case2', A.addiu(A.s1, A.zero, 100), 'done',
             A.lui(A.gp, 0x8000), A.sw(A.s1, 0x1000, A.gp), *A.DONE,
             'table', *[lambda pc, labels, i=i: labels[f'case{i}'] for i in range(3)],
             'inputs', 4, 1]
    return A.assemble(items)


def _captured_fixture(A):
    items = [A.lui(A.s0, 0x8000),
             lambda pc, labels: A.addiu(A.s0, A.s0, labels['inputs'] & 0xFFFF),
             A.lw(A.a0, 0, A.s0), A.addiu(A.s0, A.s0, 4),
             A.sltiu(A.t4, A.a0, 3), A.lui(A.t1, 0x8000),
             lambda pc, labels: A.addiu(A.t1, A.t1, labels['table'] & 0xFFFF),
             A.sll(A.t2, A.a0, 2), A.addu(A.t3, A.t1, A.t2),
             'retry', A.lw(A.v1, 0, A.s0), A.addiu(A.a0, A.a0, 1),
             A.beq(A.v1, A.zero, 'retry'), A.addiu(A.s0, A.s0, 4),
             A.beq(A.t4, A.zero, 'default'), A.nop,
             A.lw(A.v0, 0, A.t3), A.jr(A.v0), A.nop,
             'case0', A.addiu(A.s1, A.zero, 1), A.j('done'), A.nop,
             'case1', A.addiu(A.s1, A.zero, 10), A.j('done'), A.nop,
             'case2', A.addiu(A.s1, A.zero, 100), A.j('done'), A.nop,
             'default', A.addiu(A.s1, A.zero, 1000), 'done',
             A.lui(A.gp, 0x8000), A.sw(A.s1, 0x1000, A.gp), *A.DONE,
             'table', *[lambda pc, labels, i=i: labels[f'case{i}'] for i in range(3)],
             'inputs', 1, 0, 1]
    return A.assemble(items)


def _case_backedge_fixture(A, chain=0):
    # Each decoded case returns to the guarded header with the initialized
    # table base intact. These roots are internal indirect edges.
    items = [A.lui(A.t1, 0x8000),
             lambda pc, labels: A.addiu(A.t1, A.t1, labels['table'] & 0xFFFF),
             A.lui(A.s0, 0x8000),
             lambda pc, labels: A.addiu(A.s0, A.s0, labels['inputs'] & 0xFFFF),
             'retry', A.lw(A.a0, 0, A.s0), A.sltiu(A.t4, A.a0, 2),
             A.beq(A.t4, A.zero, 'done'), A.addiu(A.s0, A.s0, 4),
             A.sll(A.t2, A.a0, 2), A.addu(A.t3, A.t1, A.t2),
             A.lw(A.v0, 0, A.t3), A.jr(A.v0), A.nop,
             'case0', A.addiu(A.s1, A.s1, 1), A.j('chain0' if chain else 'retry'), A.nop,
             'case1', A.addiu(A.s1, A.s1, 10), A.j('retry'), A.nop,
             *[word for n in range(chain) for word in
               [f'chain{n}', A.j(f'chain{n + 1}' if n + 1 < chain else 'retry'), A.nop]],
             'done', A.lui(A.gp, 0x8000), A.sw(A.s1, 0x1000, A.gp), *A.DONE,
             'table', *[lambda pc, labels, i=i: labels[f'case{i}'] for i in range(2)],
             'inputs', 0, 1, 2]
    return A.assemble(items)


def _preserved_base_fixture(A, guarded_break=False, abort=False):
    # A leaf writes other registers and RAM; the nested caller spills/restores
    # RA. Both preserve s1 because none of their instructions writes it.
    items = [A.lui(A.s1, 0x8000),
             lambda pc, labels: A.addiu(A.s1, A.s1, labels['table'] & 0xFFFF),
             A.lui(A.s0, 0x8000),
             lambda pc, labels: A.addiu(A.s0, A.s0, labels['inputs'] & 0xFFFF),
             A.lui(A.s2, 0x8000), A.addiu(A.s2, A.s2, 0x1010),
             A.lui(A.sp, 0x8000), A.addiu(A.sp, A.sp, 0x1020),
             'retry', A.lw(A.a0, 0, A.s0), A.sltiu(A.t4, A.a0, 2),
             A.beq(A.t4, A.zero, 'done'), A.addiu(A.s0, A.s0, 4),
             A.sll(A.t2, A.a0, 2), A.addu(A.t3, A.s1, A.t2),
             A.lw(A.v0, 0, A.t3), A.jr(A.v0), A.nop,
             'case0', A.jal('leaf'), A.nop, A.addiu(A.s4, A.s4, 1), A.j('retry'), A.nop,
             'case1', A.jal('nested'), A.nop, A.addiu(A.s4, A.s4, 10), A.j('retry'), A.nop,
             'done', A.lui(A.gp, 0x8000), A.sw(A.s4, 0x1000, A.gp), *A.DONE,
             'leaf', *([A.addiu(A.t7, A.zero, 0 if abort else 3),
                        A.beq(A.a0, A.t7, 'abort'), A.nop] if guarded_break else []),
             A.addiu(A.v0, A.zero, 42), A.sw(A.v0, 0, A.s2),
             A.jr(A.ra), A.addiu(A.v1, A.v1, 1),
             *(['abort', 0x0007000D] if guarded_break else []),
             'nested', A.addiu(A.sp, A.sp, -8), A.sw(A.ra, 4, A.sp),
             A.jal('leaf'), A.nop, A.lw(A.ra, 4, A.sp), A.jr(A.ra), A.addiu(A.sp, A.sp, 8),
             'table', *[lambda pc, labels, i=i: labels[f'case{i}'] for i in range(2)],
             'inputs', 0, 1, 2]
    return A.assemble(items)



def _invariant_flag_fixture(A, index, calls=False):
    # An invalid captured index stays on the zero-flag loop path. The loop
    # never writes that flag; valid indices dispatch once and exit.
    items = [A.lui(A.s0, 0x8000), A.LO(A.s0, A.s0, 'input'), A.lw(A.a0, 0, A.s0),
             A.sltiu(A.s4, A.a0, 2), A.lui(A.v1, 0x8000),
             lambda pc, labels: A.addiu(A.v1, A.v1, labels['table'] & 0xFFFF),
             A.sll(A.v0, A.a0, 2), A.addu(A.s2, A.v0, A.v1),
             'header', A.beql(A.s4, A.zero, 'body'), A.nop,
             A.lw(A.v0, 0, A.s2), A.jr(A.v0), A.nop,
             'body', A.addiu(A.t0, A.t0, 1), A.addiu(A.t1, A.zero, 3),
             A.bne(A.t0, A.t1, 'header'), A.nop, A.j('done'), A.nop,
             'case0', A.addiu(A.s1, A.s1 if calls else A.zero, 1),
             *([A.jal('leaf'), A.nop] if calls else []), A.j('body' if calls else 'done'), A.nop,
             'case1', A.addiu(A.s1, A.s1 if calls else A.zero, 10),
             *([A.jal('leaf'), A.nop] if calls else []), A.j('body' if calls else 'done'), A.nop,
             'done', A.lui(A.gp, 0x8000), A.sw(A.s1, 0x1000, A.gp), *A.DONE,
             'leaf', A.addiu(A.a0, A.zero, 99), A.addiu(A.v1, A.zero, 85), A.jr(A.ra), A.nop,
             'table', *[lambda pc, labels, i=i: labels[f'case{i}'] for i in range(2)],
             'input', index]
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
                                      ('preheader', False, False),
                                      ('captured', False, False),
                                      ('case-backedges', False, False),
                                      ('long-case', False, False),
                                      ('flag-valid0', False, False),
                                      ('flag-valid1', False, False),
                                      ('flag-invalid', False, False),
                                      ('flag-call0', False, False),
                                      ('flag-call1', False, False),
                                      ('flag-call-invalid', False, False),
                                      ('preserved-base', False, False),
                                      ('preserved-break', False, False),
                                      ('callee-break', False, False),
                                      ('table-write', True, True)]:
        raw = OUT / f'{name}.bin'
        fixture = {'flag-valid0': lambda asm: _invariant_flag_fixture(asm, 0),
                   'flag-valid1': lambda asm: _invariant_flag_fixture(asm, 1),
                   'flag-invalid': lambda asm: _invariant_flag_fixture(asm, 3),
                   'flag-call0': lambda asm: _invariant_flag_fixture(asm, 0, True),
                   'flag-call1': lambda asm: _invariant_flag_fixture(asm, 1, True),
                   'flag-call-invalid': lambda asm: _invariant_flag_fixture(asm, 3, True),
                   'preheader': _preheader_fixture, 'captured': _captured_fixture,
                   'case-backedges': _case_backedge_fixture,
                   'long-case': lambda asm: _case_backedge_fixture(asm, 24),
                   'preserved-base': _preserved_base_fixture,
                   'preserved-break': lambda asm: _preserved_base_fixture(asm, True),
                   'callee-break': lambda asm: _preserved_base_fixture(asm, True, True)}.get(name)
        raw.write_bytes(fixture(A) if fixture else _fixture(A, variable, overwrite=overwrite))
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
        if name == 'callee-break':
            fault = json.loads(actual.stdout)
            words = raw.read_bytes()
            break_offset = words.index(bytes.fromhex('0007000d'))
            assert actual.returncode == 6 and fault == {'fault': 9, 'fault_pc': BASE + break_offset}, actual.stdout
            continue
        if overwrite:
            assert actual.returncode == 6 and json.loads(actual.stdout)['fault'] == 2, actual.stdout
            continue
        expected = _ares_run(raw)
        assert actual.returncode == expected.returncode == 0, (actual.stdout, actual.stderr, expected.stderr)
        state = json.loads(actual.stdout)
        assert state == json.loads(expected.stdout), (actual.stdout, expected.stdout)
        value = 11 if name in ('case-backedges', 'long-case', 'preserved-base', 'preserved-break') else 10 if name in ('preheader', 'captured') else 1111
        value = {'flag-valid0': 1, 'flag-valid1': 10, 'flag-invalid': 0,
                 'flag-call0': 3, 'flag-call1': 30, 'flag-call-invalid': 0}.get(name, value)
        accumulator = 20 if name in ('preserved-base', 'preserved-break') else 17
        assert state['pc'] == EXIT and state['regs'][accumulator] == value and state['ram'][0] == value
        if name in ('preserved-base', 'preserved-break'):
            assert state['ram'][4] == 42
        if name == 'captured':
            assert state['regs'][4] == 3
        if name in ('flag-call0', 'flag-call1'):
            assert state['regs'][4] == 99 and state['regs'][3] == 85

    bad = OUT / 'wrong-scale.bin'
    bad.write_bytes(_fixture(A, True, shift=3))
    rejected_c = OUT / 'wrong-scale.c'
    rejected_c.unlink(missing_ok=True)
    rejected = subprocess.run([str(exe), 'lower-c', str(bad), hex(BASE), hex(BASE),
                               hex(EXIT), str(rejected_c), '--address-taken'], capture_output=True, text=True)
    assert rejected.returncode != 0 and not rejected_c.exists(), (rejected.stdout, rejected.stderr)
    print('PASS indexed dispatch: scheduled, SLLV, preheader, captured, case-backedge, invariant-flag and preserved-base call loops match pinned ares; callee BREAK and table writes fault and wrong stride refuses emission')


if __name__ == '__main__':
    main()
