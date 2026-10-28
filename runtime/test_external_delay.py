"""Branch delay slots fetch from independently mapped native source fragments."""
import importlib.util
import json
import os
import re
from pathlib import Path
import shutil
import subprocess

import test_tlb_execution as T

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'target/external-delay-contract'


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
        for case in ['jal', 'jalr', 'ordinary-taken', 'ordinary-untaken',
                     'likely-taken', 'likely-untaken', 'link-taken', 'link-untaken',
                     'link-likely-taken', 'link-likely-untaken', 'store-slot', 'load-slot', 'fpu-slot']:
            directory = OUT / case
            directory.mkdir(parents=True, exist_ok=True)

            def modules(A):
                main = T.E0 + 0xffc
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
                    first += [A.nop] * (1021 - len(first))
                    return first + [A.lui(A.t9, T.E0 >> 16), A.ori(A.t9, A.t9, 0x20),
                                    A.jalr(A.ra, A.t9)], [A.addiu(A.v0, A.v0, 7)] + second
                elif case.startswith('link'):
                    rt = (19 if 'likely' in case else 17) if case.endswith('-taken') else (18 if 'likely' in case else 16)
                    transfer = 1 << 26 | rt << 16
                    transfer |= ((T.E0 + 16 - (main + 4)) // 4) & 0xffff
                    second[1] = A.addiu(A.v0, A.v0, 3)
                else:
                    taken = case.endswith('-taken') or case in ('store-slot', 'load-slot', 'fpu-slot')
                    transfer = (20 if case.startswith('likely') else 4) << 26 | A.v0 << 21
                    transfer |= (A.zero if taken else A.sp) << 16
                    transfer |= ((T.E0 + 16 - (main + 4)) // 4) & 0xffff
                    # Both arms restore the entering return address/stack.
                    first[4:6] = [A.addiu(A.v0, A.zero, 40), A.lw(A.ra, 12, A.sp),
                                  A.jr(A.ra), A.addiu(A.sp, A.sp, 16)]
                    second[1] = A.addiu(A.v0, A.v0, 3)
                first += [A.nop] * (1023 - len(first))
                slot = A.addiu(A.v0, A.v0, 7)
                if case == 'store-slot':
                    first[3] = A.lui(A.t7, 0x8000)
                    slot = A.sw(A.ra, 0x1008, A.t7)
                elif case == 'load-slot':
                    slot = A.lw(A.s4, 12, A.sp)
                elif case == 'fpu-slot':
                    slot = A.mtc1(A.ra, 2)
                return first + [transfer], [slot] + second

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
            if case in ('jal', 'jalr'):
                # Separate the continuation's analysis storage as well as its
                # physical backing; PC+8 must not name this unused alternate.
                declarations = json.loads(loads.read_text())
                declarations['loads'].insert(1, dict(destination='0x60000000', size='0x10',
                    rom=hex(0x1000 + labels['module0'] - T.BASE), encoding='tlb_raw',
                    slot=True, text_size='0x10'))
                loads.write_text(json.dumps(declarations))
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
            prefix = prefix.replace('static const u8 raw0', 'static int damage;\nstatic const u8 raw0')
            marker = '  return result;\n}'
            assert prefix.count(marker) == 1
            prefix = prefix.replace(marker, f'''  if (!result && damage == 1) s->ram[0x{T.P1:08x}u] ^= 1u;
  if (!result && damage == 2) {{ e.lo[1] &= ~2u; result = plaid_tlb_write(s, 0, e, 0x{labels['map']:08x}u); }}
  return result;
}}''')
            serializer = harness[harness.index('  printf("{'):harness.index('  /* Inactive remap')]
            (directory / 'harness.c').write_text(prefix + f'''int main(int argc, char **argv) {{
  static plaid_state s;
  damage = argc > 1 ? argv[1][0] - '0' : 0;
  plaid_load_images(&s); s.r[31] = SX32(0x{T.EXIT:08x}u);
  if (plaid_run(&s)) {{ printf("{{\\"fault\\":%u,\\"pc\\":%u,\\"v0\\":%llu,\\"s4\\":%llu,\\"written\\":%u}}\\n", s.fault, s.fault_pc, (unsigned long long)s.r[2], (unsigned long long)s.r[20], s.ram[0x1008]); return 6; }}
{serializer}
  return 0;
}}
''')
            binary = directory / 'check.exe'
            def run_native(*args):
                subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
                    '-Wno-unused-function', '-Wno-unused-const-variable', '-I', str(directory),
                    str(directory / 'harness.c'), '-o', str(binary)], check=True)
                return subprocess.run([str(binary), *args], capture_output=True, text=True, timeout=30,
                                      env={**os.environ, 'SDL_AUDIODRIVER': 'dummy'})

            actual = run_native()
            program = directory / 'program.bin'
            program.write_bytes(raw)
            expected = subprocess.run([str(oracle), str(program), hex(T.EXIT)],
                                      capture_output=True, text=True, timeout=120)
            assert actual.returncode == expected.returncode == 0, (case, actual.stdout, actual.stderr, expected.stderr)
            assert json.loads(actual.stdout) == json.loads(expected.stdout), (case, actual.stdout, expected.stdout)
            (directory / 'state.json').write_text(expected.stdout)
            if case in ('store-slot', 'load-slot'):
                refusals = []
                for damage in ('1', '2'):
                    refused = subprocess.run([str(binary), damage], capture_output=True, text=True, timeout=30,
                                             env={**os.environ, 'SDL_AUDIODRIVER': 'dummy'})
                    state = json.loads(refused.stdout)
                    assert refused.returncode == 6 and state == dict(fault=3, pc=T.E1, v0=0, s4=0, written=0), state
                    refusals.append(state)
                (directory / 'refusal.json').write_text(json.dumps(refusals))
            if case == 'store-slot':
                generated = native.read_text()
                calls = re.findall(r'if \(D_[0-9a-f_]+\(s\)\) return 1;', generated)
                assert len(calls) == 1
                try:
                    native.write_text(generated.replace(calls[0], ''))
                    mutant = run_native()
                    assert mutant.returncode == 0 and json.loads(mutant.stdout) != json.loads(expected.stdout)
                    guard = 'if (!plaid_ovls[k].verify(s->ram, PLAID_RAM_SIZE, b)) continue;'
                    assert generated.count(guard) == 1
                    native.write_text(generated.replace(guard, 'if (0) continue;'))
                    mutant = run_native('1')
                    assert mutant.returncode == 0, (mutant.stdout, mutant.stderr)
                finally:
                    native.write_text(generated)
                    run_native()
    finally:
        T.E1, T.EXIT, T._module_words, T._entry, A.EXIT = original
    print('PASS independent delay slots: thirteen full-state pinned-ares comparisons; JAL/JALR, ordinary/likely/linking taken/untaken, FPR and load/store effects; corrupt-source and missing-odd-mapping refusals; missing-slot and removed-source-check mutations detected')


if __name__ == '__main__':
    main()
