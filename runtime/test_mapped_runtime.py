"""Mapped host-runtime calls require an independently guarded source extent."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

import test_tlb_execution as T

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'target/mapped-runtime-contract'


def main(direct=False):
    spec = importlib.util.spec_from_file_location('mapped_runtime_asm', T.SLICE / 'run.py')
    A = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(A)
    exe = Path(os.environ.get('PLAID_EXE', ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')))
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    original = T._module_words
    T._module_words = lambda A: (
        [A.addiu(A.v0, A.zero, 7), A.addu(A.v1, A.ra, A.zero), A.jr(A.ra), A.addiu(A.v0, A.v0, 3)],
        [A.addiu(A.sp, A.sp, -16), A.sw(A.ra, 12, A.sp), 3 << 26 | (T.E0 >> 2 & 0x03ffffff),
         A.nop, A.lw(A.ra, 12, A.sp), A.jr(A.ra), A.addiu(A.sp, A.sp, 16)] if direct
        else [A.addiu(A.v0, A.zero, 99), A.jr(A.ra), A.nop])
    try:
        raw, labels, one, two = T._fixture(A)
    finally:
        T._module_words = original
    if direct:
        old, new = A.lui(A.t9, T.E0 >> 16).to_bytes(4, 'big'), A.lui(A.t9, T.E1 >> 16).to_bytes(4, 'big')
        assert raw.count(old) == 1
        raw = raw.replace(old, new)
    directory = OUT / ('direct' if direct else 'indirect')
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / 'input.z64'
    rom = bytearray(0x1000)
    rom[:4] = bytes.fromhex('80371240')
    rom.extend(raw)
    source.write_bytes(rom)
    program = directory / 'program.bin'
    program.write_bytes(raw)
    loads = directory / 'loads.json'
    loads.write_text(json.dumps(dict(format='plaid-loads-v0', source='synthetic mapped runtime sources', loads=[
        dict(destination=hex(v), size=hex(len(words) * 4), rom=hex(0x1000 + labels[label] - T.BASE),
             encoding='tlb_raw', slot=True, text_size=hex(len(words) * 4))
        for v, words, label in [(T.E0, one, 'module0'), (T.E1, two, 'module1')]])))
    runtime = directory / 'runtime.json'
    declarations = [dict(entry=hex(labels['map']), name='map', callbacks=[]),
                    dict(entry='0x80800000', name='mapped', callbacks=[], size=len(one) * 4)]
    runtime.write_text(json.dumps(dict(format='plaid-runtime-functions-v0', source='synthetic runtime ABI', functions=declarations)))
    mapping, native = directory / 'map.json', directory / 'native.c'
    def plaid(*args):
        result = subprocess.run([str(exe), *map(str, args)], capture_output=True, text=True)
        assert result.returncode == 0, (args, result.stdout, result.stderr)
        return result
    plaid('discover', source, '0x1000', hex(T.BASE), hex(len(raw)), hex(T.BASE), mapping, runtime,
          '--loads', loads, '--address-taken')
    plaid('lower-map', source, mapping, hex(T.BASE), hex(T.EXIT), native)
    doc = json.loads(mapping.read_text())
    assert not any(b['start']['pc'] == 0x80800000 for b in doc['blocks'])
    original_map = mapping.read_text()
    try:
        for extent in (None, 0, 2, len(one) * 4 + 4):
            broken = json.loads(original_map)
            function = next(f for a, f in broken['runtime_functions'] if a['pc'] == 0x80800000)
            if extent is None:
                function.pop('source_size', None)
            else:
                function['source_size'] = extent
            mapping.write_text(json.dumps(broken))
            refused = subprocess.run([str(exe), 'lower-map', str(source), str(mapping), hex(T.BASE), hex(T.EXIT), str(native)],
                                     capture_output=True, text=True)
            assert refused.returncode != 0 and ('runtime_source_extent' in refused.stderr or 'invalid runtime source extent' in refused.stderr), refused.stderr
    finally:
        mapping.write_text(original_map)
    harness = T._native_harness(one, two, labels)
    prefix = harness.split('int main(void)')[0]
    prefix = prefix.replace('static const u8 raw0', 'static int damage, calls;\nstatic const u8 raw0')
    prefix = prefix.replace('if (!result && (u32)s->r[4] == 1u) {', '''if (!result && (u32)s->r[4] == 1u) {
      if (damage == 1 || damage == 2) s->ram[0x200000 + (damage == 1 ? 0 : 8)] ^= 1u;
      if (damage == 3 && plaid_tlb_clear(s, 0x80000000u)) return 1;''')
    serializer = harness[harness.index('  printf("{'):harness.index('  /* Inactive remap')]
    helper = '''int plaid_rt_mapped(plaid_state *s) {
  if (damage == 4 && plaid_runtime_write(s, 0x200008u, 4, 0xe0000000u)) return 1;
  if (damage == 5 && plaid_tlb_clear(s, 0xe0000000u)) return 1;
  calls++; s->r[2] = 10; s->r[3] = s->r[31]; return 0;
}
'''
    (directory / 'harness.c').write_text(prefix + helper + f'''int main(int argc, char **argv) {{
  static plaid_state s;
  damage = argc > 1 ? argv[1][0] - '0' : 0;
  plaid_load_images(&s); s.r[31] = SX32(0x{T.EXIT:08x}u);
  if (plaid_run(&s)) {{ printf("{{\\"fault\\":%u,\\"calls\\":%d}}\\n", s.fault, calls); return 6; }}
  assert(calls == 1);
{serializer}
  return 0;
}}
''')
    binary = directory / 'check.exe'
    def build():
        subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label', '-Wno-unused-function',
                        '-Wno-unused-const-variable', '-I', str(directory), str(directory / 'harness.c'), '-o', str(binary)], check=True)
    build()
    actual = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30,
                            env={**os.environ, 'SDL_AUDIODRIVER': 'dummy'})
    expected = T._ares_run(program)
    assert actual.returncode == expected.returncode == 0, (actual.stdout, actual.stderr, expected.stderr)
    assert json.loads(actual.stdout) == json.loads(expected.stdout), (actual.stdout, expected.stdout)
    (directory / 'state.json').write_text(actual.stdout)
    refusals = []
    for damage in (1, 2, 3, 4, 5):
        bad = subprocess.run([str(binary), str(damage)], capture_output=True, text=True, timeout=30,
                             env={**os.environ, 'SDL_AUDIODRIVER': 'dummy'})
        result = json.loads(bad.stdout)
        assert bad.returncode == 6 and result == dict(fault=3 if damage <= 3 else 2, calls=0), bad.stdout
        refusals.append(result)
    (directory / 'refusal.json').write_text(json.dumps(refusals))
    if not direct:
        generated = native.read_text()
        pin = 'plaid_text_pin(s, &frame); r = plaid_rt_mapped(s); plaid_text_unpin(s, &frame);'
        assert generated.count(pin) == 1
        try:
            native.write_text(generated.replace(pin, '(void)frame; r = plaid_rt_mapped(s);'))
            build()
            bad = subprocess.run([str(binary), '4'], capture_output=True, text=True, timeout=30,
                                 env={**os.environ, 'SDL_AUDIODRIVER': 'dummy'})
            assert bad.returncode == 0, (bad.stdout, bad.stderr)
            assert json.loads(bad.stdout)['pc'] == T.EXIT
            (directory / 'removed-pin-mutation.json').write_text(bad.stdout)
        finally:
            native.write_text(generated)
            build()
        main(True)
        print('PASS mapped runtime: direct/indirect full-state pinned-ares matches, no decoded HLE body, complete extents required; entry/interior corruption, absent mapping and active source writes/remaps refuse before host effects; removed-pin mutation detected')


if __name__ == '__main__':
    main()
