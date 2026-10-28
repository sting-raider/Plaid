"""Declared fixed loads retain verification and revocation past index 63."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

import test_tlb_execution as T

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'target/load-capacity-contract'


def main():
    spec = importlib.util.spec_from_file_location('load_capacity_asm', T.SLICE / 'run.py')
    A = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(A)
    A.EXIT = T.EXIT
    exe = ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    for count in (65, 251, 252):
        directory = OUT / str(count)
        directory.mkdir(parents=True, exist_ok=True)
        destination = 0x80010000 + (count - 1) * 0x20
        li = lambda reg, value: [A.lui(reg, value >> 16), A.ori(reg, reg, value & 0xffff)]
        # Initialize through KSEG1 so the next instruction fetch sees the writes.
        items = [*li(A.t0, A.BASE + 0x100), *li(A.t1, destination | 0x20000000)]
        for offset in range(0, 16, 4):
            items += [A.lw(A.t2, offset, A.t0), A.sw(A.t2, offset, A.t1)]
        items += [3 << 26 | (destination >> 2 & 0x03ffffff), A.nop,
                  *li(A.gp, 0x80001000), A.sw(A.v0, 0, A.gp), *A.DONE]
        raw = bytearray(A.assemble(items))
        raw[0x100:0x110] = A.assemble([A.addiu(A.v0, A.zero, 7), A.jr(A.ra), A.nop, A.nop])[:16]
        program = directory / 'program.bin'
        program.write_bytes(raw)
        rom = bytearray(0x1000)
        rom[:4] = bytes.fromhex('80371240')
        rom.extend(raw)
        source = directory / 'input.z64'
        source.write_bytes(rom)
        loads = directory / 'loads.json'
        loads.write_text(json.dumps(dict(format='plaid-loads-v0', source='synthetic fixed load capacity', loads=[
            dict(destination=hex(0x80010000 + index * 0x20), size='0x10', rom='0x1100', encoding='raw')
            for index in range(count)])))
        mapping, generated = directory / 'map.json', directory / 'native.c'
        subprocess.run([str(exe), 'discover', str(source), '0x1000', hex(A.BASE), hex(len(raw)),
                        hex(A.BASE), str(mapping), '--loads', str(loads)], check=True, capture_output=True, text=True)
        lower = subprocess.run([str(exe), 'lower-map', str(source), str(mapping), hex(A.BASE), hex(T.EXIT),
                                str(generated)], capture_output=True, text=True)
        if count == 252:
            assert lower.returncode != 0 and 'at most 251 declared loads' in lower.stderr, lower.stderr
            continue
        assert lower.returncode == 0, lower.stderr
        harness = (T.SLICE / 'harness.c').read_text().replace('#include "runtime.c"', '#include <assert.h>')
        checks = f'''  {{ static plaid_state before;
  assert(s.load_ok[{count - 1}] && s.prot[0x{destination & 0x1fffffff:x}u >> 2] == {count + 1});
  assert(!plaid_protected(&s, 0x{destination & 0x1fffffff:x}u, 4, 0x{A.BASE:08x}u));
  assert(!s.load_ok[{count - 1}]);
  s.ram[0x{destination & 0x1fffffff:x}u] ^= 1u; before = s;
  assert(plaid_verify_load(&s, {count - 1}, 0x{A.BASE:08x}u) && s.fault == 8);
  s.fault = before.fault; s.fault_pc = before.fault_pc;
  assert(!memcmp(&before, &s, sizeof s));
  }}
'''
        harness = harness.replace('  return 0;\n}', checks + '  return 0;\n}')
        (directory / 'harness.c').write_text(harness)
        binary = directory / 'check.exe'
        subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
                        '-DPLAID_LOWERED="native.c"', f'-DPLAID_EXIT={T.EXIT}u', '-I', str(directory),
                        str(directory / 'harness.c'), '-lm', '-o', str(binary)], check=True)
        actual = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30,
                                env={**os.environ, 'SDL_AUDIODRIVER': 'dummy'})
        expected = T._ares_run(program)
        assert actual.returncode == expected.returncode == 0, (actual.stdout, actual.stderr, expected.stderr)
        assert json.loads(actual.stdout) == json.loads(expected.stdout), (actual.stdout, expected.stdout)
        (directory / 'state.json').write_text(actual.stdout)
    print('PASS fixed load capacity: 65/251-load full-state ares matches, highest tag verification/revocation and corrupt-source refusal; 252 loads refuse before tag collision')


if __name__ == '__main__':
    main()
