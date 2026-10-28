"""Runtime callbacks retain virtual pointers and select guarded native sources."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

import test_tlb_execution as T

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'target/mapped-callback-contract'


def contract(mapped_callee=False):
    spec = importlib.util.spec_from_file_location('mapped_callback_asm', T.SLICE / 'run.py')
    A = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(A)
    exe = Path(os.environ.get('PLAID_EXE', ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')))
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    original = T._module_words
    callback = [A.addiu(A.v0, A.zero, 7), A.addu(A.v1, A.ra, A.zero), A.jr(A.ra), A.addiu(A.v0, A.v0, 3)]
    # A direct JAL into a mapped ABI must originate in its virtual jump region.
    # Keep the caller and callback separate entries in the first source.
    caller = [A.addiu(A.sp, A.sp, -16), A.sw(A.ra, 12, A.sp),
              A.lui(A.a2, T.E0 >> 16), A.ori(A.a2, A.a2, 0x40),
              3 << 26 | (T.E1 >> 2 & 0x03ffffff), A.nop,
              A.lw(A.ra, 12, A.sp), A.jr(A.ra), A.addiu(A.sp, A.sp, 16)]
    caller += [A.nop] * (16 - len(caller))
    caller[12:15] = [A.addiu(A.v0, A.zero, 99), A.jr(A.ra), A.nop]
    T._module_words = lambda A: (
        (caller + callback if mapped_callee else callback),
        ([A.jr(A.a2), A.nop] if mapped_callee else
         [A.addiu(A.v0, A.zero, 99), A.jr(A.ra), A.nop]))
    try:
        raw, labels, one, two = T._fixture(A)
    finally:
        T._module_words = original
    raw = bytearray(raw)
    marker = A.jalr(A.ra, A.t9).to_bytes(4, 'big')
    assert raw.count(marker) == 1
    at = raw.index(marker)
    callee = T.E1 if mapped_callee else labels['leaf']
    if not mapped_callee:
        raw[at - 4:at] = A.lui(A.a2, T.E0 >> 16).to_bytes(4, 'big')
        raw[at:at + 4] = (3 << 26 | (callee >> 2 & 0x03ffffff)).to_bytes(4, 'big')
    pos = labels['leaf'] - T.BASE
    raw[pos:pos + 4] = A.jr(A.a2).to_bytes(4, 'big')
    OUT.mkdir(parents=True, exist_ok=True)
    for alternate in (False, True):
        directory = OUT / (('mapped-callee-' if mapped_callee else '') + ('alternates' if alternate else 'single'))
        directory.mkdir(exist_ok=True)
        program = directory / 'program.bin'
        program.write_bytes(raw)
        source = directory / 'input.z64'
        rom = bytearray(0x1000)
        rom[:4] = bytes.fromhex('80371240')
        rom.extend(raw)
        source.write_bytes(rom)
        declarations = [dict(destination=hex(v), size=hex(len(words) * 4),
            rom=hex(0x1000 + labels[label] - T.BASE), encoding='tlb_raw', slot=True,
            text_size=hex(len(words) * 4)) for v, words, label in
            [(T.E0, one, 'module0'), (T.E1, two, 'module1')]]
        if mapped_callee:
            caller_source = declarations[0]
            declarations = [dict(caller_source, size='0x40', text_size='0x40'),
                            dict(caller_source, destination=hex(T.E0 + 0x40), size='0x10', text_size='0x10',
                                 rom=hex(int(caller_source['rom'], 0) + 0x40)), declarations[1]]
        if alternate:
            declarations.append(dict(declarations[1], rom=hex(0x1000 + labels['module0'] - T.BASE + 0x30),
                                     size='0xc', text_size='0xc') if mapped_callee else
                                dict(declarations[-1], destination=hex(T.E0)))
        loads = directory / 'loads.json'
        loads.write_text(json.dumps(dict(format='plaid-loads-v0', source='synthetic mapped callback sources', loads=declarations)))
        runtime = directory / 'runtime.json'
        functions = [dict(entry=hex(labels['map']), name='map', callbacks=[])]
        if not mapped_callee:
            functions.append(dict(entry=hex(callee), name='invoke', callbacks=['a2']))
        runtime.write_text(json.dumps(dict(format='plaid-runtime-functions-v0', source='synthetic callback ABI', functions=functions)))
        mapping, native = directory / 'map.json', directory / 'native.c'
        def plaid(*args):
            result = subprocess.run([str(exe), *map(str, args)], capture_output=True, text=True)
            assert result.returncode == 0, (args, result.stdout, result.stderr)
            return result
        plaid('discover', source, '0x1000', hex(T.BASE), hex(len(raw)), hex(T.BASE), mapping, runtime,
              '--loads', loads, '--address-taken')
        if mapped_callee:
            document = json.loads(mapping.read_text())
            placed = next(load['destination']['start'] for context in document['load_images'].values()
                          for load in context['loads'] if load.get('linked') == T.E1)
            functions.append(dict(entry=hex(placed), name='invoke', callbacks=['a2'], size=len(two) * 4))
            runtime.write_text(json.dumps(dict(format='plaid-runtime-functions-v0', source='synthetic placed callback ABI', functions=functions)))
            plaid('discover', source, '0x1000', hex(T.BASE), hex(len(raw)), hex(T.BASE), mapping, runtime,
                  '--loads', loads, '--address-taken')
        if alternate:
            original_map = mapping.read_text()
            incomplete = json.loads(original_map)
            sources = next(iter(incomplete['load_images'].values()))['loads']
            entries = [load['destination']['start'] for load in sources if load.get('linked') == T.E0 + (0x40 if mapped_callee else 0)]
            assert len(entries) == 2
            missing = entries[-1]
            incomplete['blocks'] = [b for b in incomplete['blocks'] if b['start']['pc'] != missing]
            try:
                mapping.write_text(json.dumps(incomplete))
                report = json.loads(plaid('solve', source, mapping, '--residual-dispatch').stdout)
                assert any(b['kind'] == 'unresolved_runtime_callback' for b in report['blockers']), report
            finally:
                mapping.write_text(original_map)
        plaid('lower-map', source, mapping, hex(T.BASE), hex(T.EXIT), native)
        harness = T._native_harness(one, two, labels)
        prefix = harness.split('int main(void)')[0]
        serializer = harness[harness.index('  printf("{'):harness.index('  /* Inactive remap')]
        helper = '''static int damage;
int plaid_rt_invoke(plaid_state *s) {
  if (damage == 1 || damage == 2) s->ram[0x200000 + (damage == 1 ? 0 : 8)] ^= 1u;
  if (damage == 3 && plaid_tlb_clear(s, 0x80000000u)) return 1;
  if (damage == 4) s->r[6] += 4;
  return plaid_enter(s, (u32)s->r[6], s->r[31]);
}
'''
        if mapped_callee:
            helper = helper.replace('0x200000 +', '0x200040 +')
        (directory / 'harness.c').write_text(prefix + helper + f'''int main(int argc, char **argv) {{
  static plaid_state s;
  damage = argc > 1 ? argv[1][0] - '0' : 0;
  plaid_load_images(&s); s.r[31] = SX32(0x{T.EXIT:08x}u);
  if (plaid_run(&s)) {{ printf("{{\\"fault\\":%u,\\"fault_pc\\":%u,\\"v0\\":%llu}}\\n", s.fault, s.fault_pc, (unsigned long long)s.r[2]); return 6; }}
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
        for damage in (1, 2, 3, 4):
            bad = subprocess.run([str(binary), str(damage)], capture_output=True, text=True, timeout=30,
                                 env={**os.environ, 'SDL_AUDIODRIVER': 'dummy'})
            result = json.loads(bad.stdout)
            expected_fault = dict(fault=2, fault_pc=0x80000000, v0=0) if mapped_callee and damage == 3 else dict(fault=3, fault_pc=1, v0=0)
            assert bad.returncode == 6 and result == expected_fault, bad.stdout
            refusals.append(dict(damage=damage, result=result))
        (directory / 'refusal.json').write_text(json.dumps(refusals, indent=2))
        if not alternate:
            generated = native.read_text()
            guard = 'if (!plaid_ovls[k].verify(s->ram, PLAID_RAM_SIZE, b)) continue;'
            assert generated.count(guard) == 1
            try:
                native.write_text(generated.replace(guard, 'if (0) continue;'))
                build()
                bad = subprocess.run([str(binary), '2'], capture_output=True, text=True, timeout=30,
                                     env={**os.environ, 'SDL_AUDIODRIVER': 'dummy'})
                assert bad.returncode == 0, (bad.stdout, bad.stderr)
                assert json.loads(bad.stdout)['regs'][2] == 10
            finally:
                native.write_text(generated)
    print(f'PASS mapped callbacks ({"mapped" if mapped_callee else "fixed"} callee): two full-state pinned-ares matches, independent alternate selection and entry/interior corruption, missing mapping and non-entry refusal before guest effects; removed-source-guard mutation detected')


def main():
    contract()
    contract(True)


if __name__ == '__main__':
    main()
