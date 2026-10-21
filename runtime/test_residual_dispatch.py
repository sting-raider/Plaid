"""Residual dispatch (ADR-0218): an unprovable indirect jump closes only under
--residual-dispatch, runs lowered entries like pinned ares, and faults 3 elsewhere."""
from pathlib import Path
import importlib.util
import json
import os
import shutil
import subprocess

from test_tlb_execution import _ares_run

ROOT = Path(__file__).resolve().parents[1]
SLICE = ROOT / 'spikes/096-native-slice'
OUT = ROOT / 'target/residual-dispatch-contract'
BASE, EXIT = 0x80000000, 0x80000F00


def _fixture(A, offset):
    # `w` jumps to whatever the pointer-to-pointer cell names: no proof exists.
    items = [A.jal('leafa'), A.nop, A.jal('leafb'), A.nop,
             A.lui(A.t0, 0x8000), A.LO(A.t0, A.t0, 'ptr'), A.lw(A.a0, 0, A.t0),
             A.jal('w'), A.nop,
             A.lui(A.gp, 0x8000), A.sw(A.s1, 0x1000, A.gp), *A.DONE,
             'w', A.lw(A.v0, 0, A.a0), A.jr(A.v0), A.nop,
             'leafa', A.addiu(A.s1, A.s1, 1), A.jr(A.ra), A.nop,
             'leafb', A.addiu(A.s1, A.s1, 10), A.jr(A.ra), A.nop,
             'ptr', lambda pc, labels: labels['slot'],
             'slot', lambda pc, labels: labels['leafb'] + offset]
    return A.assemble(items)



def _table_fixture(A, unknown=False):
    # The independent address-taken entry skips the preheader's base setup.
    items = [A.jal('w'), A.nop, *A.DONE,
             'w', A.lui(A.t0, 0x8000),
             lambda pc, labels: A.addiu(A.t0, A.t0, labels['table'] & 0xFFFF),
             A.addiu(A.a0, A.zero, 1),
             'header', A.sltiu(A.t1, A.a0, 3), A.beq(A.t1, A.zero, 'done'), A.nop,
             A.sll(A.t2, A.a0, 2), A.addu(A.v0, A.t0, A.t2),
             A.lw(A.v0, 0, A.v0), A.jr(A.v0), A.nop,
             'case0', A.addiu(A.s1, A.s1, 1), A.j('done'), A.nop,
             'case1', A.addiu(A.s1, A.s1, 10), A.j('done'), A.nop,
             'done', A.lui(A.gp, 0x8000), A.sw(A.s1, 0x1000, A.gp), A.jr(A.ra), A.nop,
             'independent', A.j('header'), A.nop, A.jr(A.ra), A.nop,
             'table', lambda pc, labels: labels['case0'],
             lambda pc, labels: labels['case1'], lambda pc, labels: labels['case0'],
             lambda pc, labels: labels['independent']]
    # Runtime changes to an unlisted case must still fault at the jump.
    if unknown:
        pos = items.index('header')
        items[pos:pos] = [A.lui(A.t3, 0x8000), A.LO(A.t3, A.t3, 'case1'),
                         A.addiu(A.t3, A.t3, 4), A.sw(A.t3, 4, A.t0)]
    return A.assemble(items)


def _table_contract(A, exe, cc):
    for unknown in (False, True):
        name = 'partial-table-unknown' if unknown else 'partial-table'
        raw = OUT / f'{name}.bin'
        raw.write_bytes(_table_fixture(A, unknown))
        native_c = OUT / f'{name}.c'
        lower = [str(exe), 'lower-c', str(raw), hex(BASE), hex(BASE), hex(EXIT),
                 str(native_c), '--address-taken']
        native_c.unlink(missing_ok=True)
        refused = subprocess.run(lower, capture_output=True, text=True)
        assert refused.returncode != 0 and not native_c.exists(), (name, refused.stdout, refused.stderr)
        lowered = subprocess.run([*lower, '--residual-dispatch'], capture_output=True, text=True)
        assert lowered.returncode == 0, (name, lowered.stdout, lowered.stderr)
        native = OUT / (name + ('.exe' if os.name == 'nt' else ''))
        subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
                        f'-DPLAID_LOWERED="{native_c.name}"', f'-DPLAID_EXIT=0x{EXIT:x}u',
                        '-I', str(OUT), str(SLICE / 'harness.c'), '-o', str(native)], check=True)
        actual = subprocess.run([str(native)], capture_output=True, text=True, timeout=30)
        if unknown:
            site = raw.read_bytes().index(bytes.fromhex('00400008'))
            assert actual.returncode == 6 and json.loads(actual.stdout) == {'fault': 3, 'fault_pc': BASE + site}, actual.stdout
        else:
            expected = _ares_run(raw)
            assert actual.returncode == expected.returncode == 0, (actual.stdout, actual.stderr, expected.stderr)
            state = json.loads(actual.stdout)
            assert state == json.loads(expected.stdout), (actual.stdout, expected.stdout)
            assert state['pc'] == EXIT and state['regs'][17] == 10 and state['ram'][0] == 10

def main():
    spec = importlib.util.spec_from_file_location('residual_asm', SLICE / 'run.py')
    A = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(A)
    OUT.mkdir(parents=True, exist_ok=True)
    exe = Path(os.environ.get('PLAID_EXE', ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')))
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    if not exe.exists() or not cc:
        raise RuntimeError('residual dispatch contract requires plaid and a C compiler')
    for name, offset in [('entry', 0), ('non-entry', 4)]:
        raw = OUT / f'{name}.bin'
        raw.write_bytes(_fixture(A, offset))
        native_c = OUT / f'{name}.c'
        lower = [str(exe), 'lower-c', str(raw), hex(BASE), hex(BASE), hex(EXIT), str(native_c)]
        native_c.unlink(missing_ok=True)
        refused = subprocess.run(lower, capture_output=True, text=True)
        assert refused.returncode != 0 and not native_c.exists(), (name, refused.stdout, refused.stderr)
        lowered = subprocess.run([*lower, '--residual-dispatch'], capture_output=True, text=True)
        assert lowered.returncode == 0, (name, lowered.stdout, lowered.stderr)
        native = OUT / (f'{name}.exe' if os.name == 'nt' else name)
        subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
                        f'-DPLAID_LOWERED="{native_c.name}"', f'-DPLAID_EXIT=0x{EXIT:x}u',
                        '-I', str(OUT), str(SLICE / 'harness.c'), '-o', str(native)], check=True)
        actual = subprocess.run([str(native)], capture_output=True, text=True, timeout=30)
        if name == 'non-entry':
            site = raw.read_bytes().index(bytes.fromhex('00400008'))
            assert actual.returncode == 6 and json.loads(actual.stdout) == {'fault': 3, 'fault_pc': BASE + site}, actual.stdout
            continue
        expected = _ares_run(raw)
        assert actual.returncode == 0 and expected.returncode == 0, (actual.stdout, actual.stderr, expected.stderr)
        state = json.loads(actual.stdout)
        assert state == json.loads(expected.stdout), (actual.stdout, expected.stdout)
        assert state['pc'] == EXIT and state['regs'][17] == 21 and state['ram'][0] == 21
    _table_contract(A, exe, cc)
    print('PASS residual dispatch: unprovable jump refused by default, lowered entry matches pinned ares, non-entry target faults 3; partial-path table cases match ares and unlisted table targets fault 3')


if __name__ == '__main__':
    main()
