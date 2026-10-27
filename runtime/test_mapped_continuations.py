"""Sequential mapped fragments retain independent bindings and guest PC/RA."""
import importlib.util
import json
import os
import re
from pathlib import Path
import shutil
import subprocess

import test_tlb_execution as T

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'target/mapped-continuation-contract'


def main():
    spec = importlib.util.spec_from_file_location('continuation_asm', T.SLICE / 'run.py')
    A = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(A)
    exe = Path(os.environ.get('PLAID_EXE', ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')))
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    oracle = A.builder().build(T.SLICE / 'driver.cpp', OUT / 'oracle')
    original = T.E1, T.EXIT, T._module_words, T._entry, A.EXIT
    T.E1, T.EXIT = T.E0 + 0x1000, 0x80003000
    A.EXIT = T.EXIT
    entry = T._entry

    def map_entry(A, index, virtual, physical):
        if index == 1:
            return []
        words = entry(A, index, virtual, physical)
        old = (T.P0 + 0x1000) >> 6 | 0x1f
        return [(w & 0xffff0000) | (T.P1 >> 6 | 0x1f) if isinstance(w, int)
                and w >> 26 == 13 and w >> 16 & 31 == A.t0 and w & 0xffff == old else w
                for w in words]

    T._entry = map_entry
    try:
        for case in ['linear', 'jal', 'jalr', 'ordinary-taken', 'ordinary-untaken',
                     'likely-taken', 'likely-untaken', 'link-untaken', 'link-likely-untaken']:
            directory = OUT / case
            directory.mkdir(parents=True, exist_ok=True)

            def modules(A):
                if case == 'linear':
                    return ([A.nop] * 1022 + [A.addiu(A.v0, A.zero, 7), A.addiu(A.v0, A.v0, 1)],
                            [A.addiu(A.v0, A.v0, 3), A.jr(A.ra), A.nop])
                main = T.E0 + 0xff8
                jump = 4 << 26 | ((main - (T.E0 + 12)) // 4 & 0xffff)
                first = [A.addiu(A.sp, A.sp, -16), A.sw(A.ra, 12, A.sp), jump, A.nop,
                         A.jr(A.ra), A.addiu(A.v0, A.v0, 3)]
                second = [A.addu(A.v1, A.ra, A.zero), A.addiu(A.v0, A.v0, 1),
                          A.lw(A.ra, 12, A.sp), A.jr(A.ra), A.addiu(A.sp, A.sp, 16)]
                if case == 'jal':
                    transfer = 3 << 26 | ((T.E0 + 16) >> 2 & 0x03ffffff)
                elif case == 'jalr':
                    first = [A.addiu(A.sp, A.sp, -16), A.sw(A.ra, 12, A.sp),
                             4 << 26 | ((main - 8 - (T.E0 + 12)) // 4 & 0xffff), A.nop,
                             A.nop, A.nop, A.jr(A.ra), A.addiu(A.v0, A.v0, 3)]
                    first[4:4] = [A.nop, A.nop]
                    first += [A.nop] * (1020 - len(first))
                    return first + [A.lui(A.t9, T.E0 >> 16), A.ori(A.t9, A.t9, 0x20),
                                    A.jalr(A.ra, A.t9), A.addiu(A.v0, A.v0, 7)], second
                elif case.startswith('link'):
                    transfer = 1 << 26 | (18 if 'likely' in case else 16) << 16
                    transfer |= ((T.E0 + 16 - (main + 4)) // 4) & 0xffff
                    second[1] = A.addiu(A.v0, A.v0, 3)
                else:
                    taken = case.endswith('-taken')
                    transfer = (20 if case.startswith('likely') else 4) << 26 | A.v0 << 21
                    transfer |= (A.zero if taken else A.sp) << 16
                    transfer |= ((T.E0 + 16 - (main + 4)) // 4) & 0xffff
                    # Both arms restore the entering return address/stack.
                    first[4:6] = [A.addiu(A.v0, A.zero, 40), A.lw(A.ra, 12, A.sp),
                                  A.jr(A.ra), A.addiu(A.sp, A.sp, 16)]
                    second[1] = A.addiu(A.v0, A.v0, 3)
                first += [A.nop] * (1022 - len(first))
                return first + [transfer, A.addiu(A.v0, A.v0, 7)], second

            T._module_words = modules
            raw, labels, one, two = T._fixture(A)
            rom = bytearray(0x1000)
            rom[:4] = bytes.fromhex('80371240')
            rom.extend(raw)
            source = directory / 'input.z64'
            source.write_bytes(rom)
            loads = directory / 'loads.json'
            loads.write_text(json.dumps(dict(format='plaid-loads-v0', source='synthetic sequential fragments',
                loads=[dict(destination=hex(v), size=hex(len(words) * 4),
                    rom=hex(0x1000 + labels[label] - T.BASE), encoding='tlb_raw', slot=True,
                    text_size=hex(len(words) * 4)) for v, words, label in
                    [(T.E0, one, 'module0'), (T.E1, two, 'module1')]])))
            runtime = directory / 'runtime.json'
            runtime.write_text(json.dumps(dict(format='plaid-runtime-functions-v0', source='synthetic TLBWI helper',
                functions=[dict(entry=hex(labels['map']), name='map', callbacks=[])])))
            mapping, native = directory / 'map.json', directory / 'native.c'

            def plaid(*args):
                return subprocess.run([str(exe), *map(str, args)], check=True, capture_output=True, text=True)

            plaid('discover', source, '0x1000', hex(T.BASE), hex(len(raw)), hex(T.BASE), mapping,
                  runtime, '--loads', loads, '--address-taken')
            plaid('lower-map', source, mapping, hex(T.BASE), hex(T.EXIT), native, '--residual-dispatch')
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
            def run_native():
                subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
                    '-Wno-unused-function', '-Wno-unused-const-variable', '-I', str(directory),
                    str(directory / 'harness.c'), '-o', str(binary)], check=True)
                return subprocess.run([str(binary)], capture_output=True, text=True, timeout=30,
                                      env={**os.environ, 'SDL_AUDIODRIVER': 'dummy'})

            actual = run_native()
            program = directory / 'program.bin'
            program.write_bytes(raw)
            expected = subprocess.run([str(oracle), str(program), hex(T.EXIT)],
                                      capture_output=True, text=True, timeout=120)
            assert actual.returncode == expected.returncode == 0, (case, actual.stdout, actual.stderr, expected.stderr)
            assert json.loads(actual.stdout) == json.loads(expected.stdout), (case, actual.stdout, expected.stdout)
            (directory / 'state.json').write_text(expected.stdout)
            if case in ('linear', 'jal', 'link-likely-untaken'):
                harness_path = directory / 'harness.c'
                original_harness = harness_path.read_text()
                marker = '  int result = plaid_tlb_write'
                assert original_harness.count(marker) == 1
                harness_path.write_text(original_harness.replace(marker,
                    f'  s->ram[0x{T.P1:08x}u] ^= 1u;\n' + marker))
                bad_source = run_native()
                assert bad_source.returncode == 6 and bad_source.stdout.startswith('fault 3 '), bad_source
                harness_path.write_text(original_harness)
                generated = native.read_text()
                pattern = rf'return plaid_call_\d+\(s, 0xffffffff{T.E1:08x}ull, ret, 0x[0-9a-f]+u\);'
                matches = list(re.finditer(pattern, generated))
                assert matches
                match = matches[0]
                native.write_text(generated[:match.start()] + match[0].replace(f'{T.E1:08x}', f'{T.E1 + 4:08x}')
                                  + generated[match.end():])
                wrong_continuation = run_native()
                assert wrong_continuation.returncode == 6 and wrong_continuation.stdout.startswith('fault 3 ')
                native.write_text(generated)
    finally:
        T.E1, T.EXIT, T._module_words, T._entry, A.EXIT = original
    print('PASS mapped continuations: nine full-state pinned-ares comparisons; '
          'independent physical bindings, changed-source refusal and wrong-continuation mutations')


if __name__ == '__main__':
    main()
