"""Renamed constant table bases retain native target/data guards."""
from pathlib import Path
import importlib.util
import json
import os
import shutil
import subprocess

from test_tlb_execution import _ares_run

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'target/table-base-contract'


def main():
    spec = importlib.util.spec_from_file_location('table_asm', ROOT / 'spikes/096-native-slice/run.py')
    a = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(a)
    OUT.mkdir(parents=True, exist_ok=True)
    exe = ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    binary = OUT / ('check.exe' if os.name == 'nt' else 'check')

    def fixture(selector, tamper=False):
        # The old LUI register is reused for the scale, as ordinary compilers do.
        items = [a.addiu(a.a0, 0, selector), a.lui(a.v0, 0x8000),
                 lambda pc, labels: a.addiu(a.t4, a.v0, labels['table'] & 0xffff),
                 a.lui(a.gp, 0x8000),
                 a.ori(a.gp, a.gp, 0x1000)]
        if tamper:
            items += [a.sw(a.zero, 4, a.t4)]
        items += [a.I(11, a.v0, a.a0, 3), a.beq(a.v0, 0, 'default'),
                  a.sll(a.v0, a.a0, 2), a.addu(a.v0, a.v0, a.t4),
                  a.lw(a.v0, 0, a.v0), a.jr(a.v0), a.addiu(a.t5, a.t5, 1),
                  'one', a.addiu(a.s0, 0, 41), a.j('done'), a.sw(a.s0, 0, a.gp),
                  'two', a.addiu(a.s0, 0, 42), a.j('done'), a.sw(a.s0, 0, a.gp),
                  'default', a.addiu(a.s0, 0, 99), a.sw(a.s0, 0, a.gp),
                  'done', *a.DONE, 'table',
                  lambda pc, labels: labels['one'], lambda pc, labels: labels['two'],
                  lambda pc, labels: labels['one']]
        return a.assemble(items), a.label_pcs(items)

    def compile_run():
        subprocess.run([cc, '-O2', '-std=c11', '-DPLAID_LOWERED="native.c"',
                        f'-DPLAID_EXIT={a.EXIT}u', '-I', str(OUT),
                        str(ROOT / 'spikes/096-native-slice/harness.c'), '-o', str(binary)],
                       check=True, capture_output=True)
        return subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)

    matched = 0
    for selector in (0, 1, 2, 3, 0xffff):
        raw, _ = fixture(selector)
        path = OUT / 'program.bin'
        path.write_bytes(raw)
        subprocess.run([str(exe), 'lower-c', str(path), hex(a.BASE), hex(a.BASE),
                        hex(a.EXIT), str(OUT / 'native.c')], check=True, capture_output=True)
        actual, expected = compile_run(), _ares_run(path)
        assert actual.returncode == expected.returncode == 0, (actual.stdout, expected.stderr)
        assert json.loads(actual.stdout) == json.loads(expected.stdout), (selector, actual.stdout, expected.stdout)
        state = json.loads(actual.stdout)
        assert state['ram'][0] == (99 if selector >= 3 else 42 if selector == 1 else 41)
        assert state['regs'][a.t5] == (selector < 3)
        matched += 1

    raw, labels = fixture(1, True)
    path.write_bytes(raw)
    subprocess.run([str(exe), 'lower-c', str(path), hex(a.BASE), hex(a.BASE),
                    hex(a.EXIT), str(OUT / 'native.c')], check=True, capture_output=True)
    actual = compile_run()
    assert actual.returncode == 6 and json.loads(actual.stdout)['fault'] == 2, actual.stdout
    generated = (OUT / 'native.c').read_text()
    # Removing the proof-data write guard must let the corrupt table reach
    # the still-closed native target guard, changing the expected fault.
    start = labels['table'] & 0x1fffffff
    marker = f'{{{start}, {start + 12}, -2}}'
    assert generated.count(marker) == 1
    (OUT / 'native.c').write_text(generated.replace(marker, '{8384512, 8384524, -2}', 1))
    try:
        mutated = compile_run()
        assert mutated.returncode == 6 and json.loads(mutated.stdout)['fault'] == 3, mutated.stdout
    finally:
        (OUT / 'native.c').write_text(generated)
    (OUT / 'receipt.json').write_text(json.dumps(dict(matched=matched,
        reference='ares 9408cb43d4948fc3ea6e152a307a34348df3fe04',
        compared=list(state), guarded_write=2, mutation_fault=3), indent=2))
    print(f'PASS table base: {matched} full-state ares matches; proof-data write fault2; guard mutation fault3')


if __name__ == '__main__':
    main()
