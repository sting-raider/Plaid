"""Relative branches between independently placed mapped fragments versus ares."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

import test_tlb_execution as T

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'target/mapped-branch-contract'


def main():
    spec = importlib.util.spec_from_file_location('mapped_branch_asm', T.SLICE / 'run.py')
    A = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(A)
    exe = Path(os.environ.get('PLAID_EXE', ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')))
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    oracle = A.builder().build(T.SLICE / 'driver.cpp', OUT / 'oracle')
    original = T.E1, T._module_words
    T.E1 = T.E0 + 0x2000
    try:
        for linked, likely, taken in [(link, likely, taken) for link in [False, True]
                                     for likely in [False, True] for taken in [True, False]]:
            directory = OUT / f'{int(linked)}-{int(likely)}-{int(taken)}'
            directory.mkdir(parents=True, exist_ok=True)
            def modules(A):
                branch = (20 if likely else 4) << 26 | A.v0 << 21 | (0 if taken else A.sp) << 16
                if linked:
                    branch = 1 << 26 | A.v0 << 21 | ((17 if taken else 16) + 2 * likely) << 16
                branch |= ((T.E1 - (T.E0 + 12)) // 4) & 0xffff
                back = 4 << 26 | (((T.E0 + 16) - (T.E1 + 8)) // 4 & 0xffff)
                return ([A.addiu(A.sp, A.sp, -16), A.sw(A.ra, 12, A.sp),
                    branch, A.addiu(A.v0, A.v0, 7), A.addiu(A.v0, A.v0, 1),
                    A.lw(A.ra, 12, A.sp), A.jr(A.ra), A.addiu(A.sp, A.sp, 16)],
                    [A.addu(A.v1, A.ra, A.zero), A.jr(A.ra) if linked else back, A.addiu(A.v0, A.v0, 3)])
            T._module_words = modules
            raw, labels, one, two = T._fixture(A)
            rom = bytearray(0x1000)
            rom[:4] = bytes.fromhex('80371240')
            rom.extend(raw)
            source = directory / 'input.z64'
            source.write_bytes(rom)
            loads = directory / 'loads.json'
            loads.write_text(json.dumps({'format': 'plaid-loads-v0', 'source': 'synthetic mapped branches',
                'loads': [{'destination': hex(v), 'size': hex(len(words) * 4),
                    'rom': hex(0x1000 + labels[label] - T.BASE), 'encoding': 'tlb_raw',
                    'slot': True, 'text_size': hex(len(words) * 4)}
                    for v, words, label in [(T.E0, one, 'module0'), (T.E1, two, 'module1')]]}))
            runtime = directory / 'runtime.json'
            runtime.write_text(json.dumps({'format': 'plaid-runtime-functions-v0', 'source': 'synthetic TLBWI helper',
                'functions': [{'entry': hex(labels['map']), 'name': 'map', 'callbacks': []}]}))
            mapping, native = directory / 'map.json', directory / 'native.c'
            def plaid(*args):
                return subprocess.run([str(exe), *map(str, args)], check=True, capture_output=True, text=True)
            plaid('discover', source, '0x1000', hex(T.BASE), hex(len(raw)), hex(T.BASE), mapping,
                  runtime, '--loads', loads, '--address-taken')
            plaid('lower-map', source, mapping, hex(T.BASE), hex(T.EXIT), native, '--residual-dispatch')
            # Reuse the existing map helper and full CPU/FPR/output-RAM serializer.
            harness = T._native_harness(one, two, labels)
            prefix = harness.split('int main(void)')[0]
            serializer = harness[harness.index('  printf("{'):harness.index('  /* Inactive remap')]
            (directory / 'harness.c').write_text(prefix + f'''int main(void) {{
  static plaid_state s;
  plaid_load_images(&s); s.r[31] = SX32(0x{T.EXIT:08x}u);
  if (plaid_run(&s)) {{ printf("fault %u pc %08x\\n", s.fault, s.fault_pc); return 6; }}
{serializer}
  return 0;
}}
''')
            binary = directory / 'check.exe'
            def run():
                subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
                    '-Wno-unused-function', '-Wno-unused-const-variable', '-I', str(directory),
                    str(directory / 'harness.c'), '-o', str(binary)], check=True)
                return subprocess.run([str(binary)], capture_output=True, text=True, timeout=30,
                    env={**os.environ, 'SDL_AUDIODRIVER': 'dummy'})
            actual = run()
            raw_path = directory / 'program.bin'
            raw_path.write_bytes(raw)
            expected = subprocess.run([str(oracle), str(raw_path), hex(T.EXIT)],
                capture_output=True, text=True, timeout=120)
            assert expected.returncode == actual.returncode == 0, (actual.stdout, actual.stderr, expected.stderr)
            assert json.loads(actual.stdout) == json.loads(expected.stdout), (actual.stdout, expected.stdout)
            state = json.loads(expected.stdout)
            assert state['regs'][A.v0] == state['ram'][0] == (11 if taken else 1 if likely else 8)
            if taken:
                generated = native.read_text()
                # Invert only this newly admitted branch arm; the ares comparison
                # must detect its changed registers, output RAM and control flow.
                program = json.loads(mapping.read_text())
                placed = next(load['destination']['start']
                    for image in program['load_images'].values() for load in image['loads']
                    if load.get('linked') == T.E0)
                start = generated.index(f'\nL_{placed:08x}:')
                end = generated.find('\nL_', start + 1)
                end = end if end >= 0 else len(generated)
                body = generated[start:end]
                branch_arm = 'if (t)'
                assert branch_arm in body
                native.write_text(generated[:start] + body.replace(branch_arm, 'if (!t)', 1) + generated[end:])
                inverted = run()
                assert inverted.returncode != 0 or json.loads(inverted.stdout) != state, inverted
                native.write_text(generated)
                # Corrupt only the destination payload after the copy, before entry.
                harness_path = directory / 'harness.c'
                original_harness = harness_path.read_text()
                marker = 'int result = plaid_tlb_write'
                assert marker in original_harness
                harness_path.write_text(original_harness.replace(marker,
                    f'if ((u32)s->r[4] == 1u) s->ram[{T.P1}u] ^= 1u;\n  ' + marker))
                mutant = run()
                assert mutant.returncode == 6 and mutant.stdout.startswith('fault 3 '), mutant
                harness_path.write_text(original_harness)
            (directory / 'state.json').write_text(expected.stdout)
    finally:
        T.E1, T._module_words = original
    print('PASS mapped relative branches: 8 full-state pinned-ares comparisons; positive/negative displacements, linked/unlinked ordinary/likely taken/untaken; inverted branch mutation detected; corrupted destination refuses')


if __name__ == '__main__':
    main()
