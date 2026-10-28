"""Proven JR tails bind independent sources without changing the entering RA."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

import test_tlb_execution as T

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'target/mapped-tail-contract'


def main():
    spec = importlib.util.spec_from_file_location('mapped_tail_asm', T.SLICE / 'run.py')
    A = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(A)
    exe = Path(os.environ.get('PLAID_EXE', ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')))
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    original = T._module_words, A.assemble, A.label_pcs
    try:
        for mode in ('fixed', 'mapped', 'local'):
            fixed = mode == 'fixed'
            directory = OUT / mode
            directory.mkdir(parents=True, exist_ok=True)
            if fixed:
                T._module_words = lambda A: ([A.addiu(A.v0, A.zero, 7), A.jr(A.ra), A.addiu(A.v0, A.v0, 3)],
                                             [A.jr(A.ra), A.nop])
                marker = A.jalr(A.ra, A.t9)
                def rewrite(items):
                    result = []
                    for word in items:
                        result.extend([A.lui(A.ra, T.EXIT >> 16), A.ori(A.ra, A.ra, T.EXIT & 0xffff), A.jr(A.t9)]
                                      if word == marker else [word])
                    return result
                A.assemble = lambda items: original[1](rewrite(items))
                A.label_pcs = lambda items: original[2](rewrite(items))
            else:
                A.assemble, A.label_pcs = original[1:]
                T._module_words = (lambda A: (
                    [A.addiu(A.sp, A.sp, -16), A.sw(A.ra, 12, A.sp),
                     A.lui(A.t9, T.E0 >> 16), A.ori(A.t9, A.t9, 0x30),
                     A.nop, A.nop, A.nop, A.jr(A.t9), A.addiu(A.v0, A.zero, 7), A.nop, A.nop, A.nop,
                     A.addu(A.v1, A.ra, A.zero), A.addiu(A.v0, A.v0, 3), A.lw(A.ra, 12, A.sp),
                     A.jr(A.ra), A.addiu(A.sp, A.sp, 16)], [A.jr(A.ra), A.nop])) if mode == 'local' else lambda A: (
                    [A.addiu(A.sp, A.sp, -16), A.sw(A.ra, 12, A.sp), A.lui(A.t9, T.E1 >> 16),
                     A.jr(A.t9), A.addiu(A.v0, A.zero, 7)],
                    [A.addu(A.v1, A.ra, A.zero), A.addiu(A.v0, A.v0, 3), A.lw(A.ra, 12, A.sp),
                     A.jr(A.ra), A.addiu(A.sp, A.sp, 16)])
            raw, labels, one, two = T._fixture(A)
            program = directory / 'program.bin'
            program.write_bytes(raw)
            source = directory / 'input.z64'
            rom = bytearray(0x1000)
            rom[:4] = bytes.fromhex('80371240')
            rom.extend(raw)
            source.write_bytes(rom)
            loads = directory / 'loads.json'
            loads.write_text(json.dumps(dict(format='plaid-loads-v0', source='synthetic mapped JR tails', loads=[
                dict(destination=hex(v), size=hex(len(words) * 4), rom=hex(0x1000 + labels[label] - T.BASE),
                     encoding='tlb_raw', slot=True, text_size=hex(len(words) * 4))
                for v, words, label in [(T.E0, one, 'module0'), (T.E1, two, 'module1')]])))
            runtime = directory / 'runtime.json'
            runtime.write_text(json.dumps(dict(format='plaid-runtime-functions-v0', source='synthetic TLB ABI',
                functions=[dict(entry=hex(labels['map']), name='map', callbacks=[])])))
            mapping, native = directory / 'map.json', directory / 'native.c'
            def plaid(*args):
                p = subprocess.run([str(exe), *map(str, args)], capture_output=True, text=True)
                assert p.returncode == 0, (args, p.stdout, p.stderr)
                return p
            plaid('discover', source, '0x1000', hex(T.BASE), hex(len(raw)), hex(T.BASE), mapping,
                  runtime, '--loads', loads, '--address-taken')
            plaid('lower-map', source, mapping, hex(T.BASE), hex(T.EXIT), native, '--residual-dispatch')
            harness = T._native_harness(one, two, labels)
            prefix = harness.split('int main(void)')[0]
            prefix = prefix.replace('static const u8 raw0', 'static int damage;\nstatic const u8 raw0')
            prefix = prefix.replace('if (!result && (u32)s->r[4] == 1u) {',
                f'if (!result && (u32)s->r[4] == 1u) {{ if (damage) s->ram[0x{(T.P0 + 0x30 if mode == "local" else T.P0 if fixed else T.P1):08x}u] ^= 1u;')
            serializer = harness[harness.index('  printf("{'):harness.index('  /* Inactive remap')]
            (directory / 'harness.c').write_text(prefix + f'''int main(int argc, char **argv) {{
  static plaid_state s; damage = argc > 1;
  plaid_load_images(&s); s.r[31] = SX32(0x{T.EXIT:08x}u);
  if (plaid_run(&s)) {{ printf("{{\\"fault\\":%u,\\"pc\\":%u,\\"v0\\":%llu}}\\n", s.fault, s.fault_pc, (unsigned long long)s.r[2]); return 6; }}
{serializer}
  return 0;
}}
''')
            binary = directory / 'check.exe'
            subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label', '-Wno-unused-function',
                            '-Wno-unused-const-variable', '-I', str(directory), str(directory / 'harness.c'), '-o', str(binary)], check=True)
            actual = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30,
                                    env={**os.environ, 'SDL_AUDIODRIVER': 'dummy'})
            expected = T._ares_run(program)
            assert actual.returncode == expected.returncode == 0, (actual.stdout, actual.stderr, expected.stderr)
            assert json.loads(actual.stdout) == json.loads(expected.stdout), (actual.stdout, expected.stdout)
            (directory / 'state.json').write_text(actual.stdout)
            bad = subprocess.run([str(binary), 'damage'], capture_output=True, text=True, timeout=30,
                                 env={**os.environ, 'SDL_AUDIODRIVER': 'dummy'})
            assert bad.returncode == 6 and json.loads(bad.stdout)['fault'] == 3, bad.stdout
    finally:
        T._module_words, A.assemble, A.label_pcs = original
    print('PASS mapped JR tails: fixed/mapped/local virtual-target full-state ares matches, entering RA preserved, corrupt destination refuses')


if __name__ == '__main__':
    main()
