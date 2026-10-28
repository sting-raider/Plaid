"""ADR-0238: COP1 control registers are independent of the FPR layout."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import ares_oracle
import json
import os
import re
import shutil
import subprocess
from test_cop0 import A

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'target/fr-contract'


def fixture():
    items = [A.lui(A.gp, 0x8000), A.ori(A.gp, A.gp, 0x1000)]
    # Start FR=1, then write both FR values natively. No FPR access is needed.
    for n, status in enumerate((0x24000000, 0x20000000, 0x24000000)):
        items += [A.lui(A.t0, status >> 16), 0x40886000, A.nop, A.nop]
        for j, value in enumerate((0x01000800, 0x00800003, 0)):
            items += [A.cfc1(A.t1, 31), A.sw(A.t1, n * 32 + j * 8, A.gp),
                      A.lui(A.t0, value >> 16), A.ori(A.t0, A.t0, value & 0xffff),
                      A.ctc1(A.t0, 31), A.cfc1(A.t1, 31),
                      A.sw(A.t1, n * 32 + j * 8 + 4, A.gp)]
        items += [A.cfc1(A.t2, 0), A.sw(A.t2, n * 32 + 24, A.gp),
                  0x400b6000, A.sw(A.t3, n * 32 + 28, A.gp)]
    return A.assemble(items + A.DONE)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if '--oracle-build' in sys.argv:
        ares_oracle.build(OUT / 'driver.cpp', OUT / 'oracle')
        return
    exe = ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    raw = OUT / 'program.bin'
    raw.write_bytes(fixture())
    source = (ROOT / 'spikes/096-native-slice/driver.cpp').read_text()
    source = source.replace('  rdram.mapIdentity = 1;', '  for(unsigned i = 0; i < 32; i++) cpu.fpu.r[i].u64 = 0x1234567800000000ull + i;\n  rdram.mapIdentity = 1;')
    source = source.replace('cpu.context.setMode();', 'cpu.setControlRegister(12, 0x24000000); cpu.context.setMode();')
    source = source.replace('  std::printf("]}\\n");', '  std::printf("],\\"status\\":%u}\\n", (unsigned)cpu.getControlRegister(12));')
    (OUT / 'driver.cpp').write_text(source)
    oracle = ares_oracle.build(OUT / 'driver.cpp', OUT / 'oracle')
    command = [str(oracle), str(raw), hex(A.EXIT)]
    expected = json.loads(subprocess.check_output(command, text=True, timeout=120))
    for fr0 in (False, True):
        cmd = [str(exe), 'lower-c', str(raw), hex(A.BASE), hex(A.BASE), hex(A.EXIT), str(OUT / 'native.c')]
        subprocess.run(cmd + (['--fr0'] if fr0 else []), check=True)
        native = (ROOT / 'spikes/096-native-slice/harness.c').read_text()
        native = native.replace('#include "runtime.c"', '#include <assert.h>')
        native = native.replace('  plaid_load_images(&s);', '  plaid_load_images(&s);\n  for (unsigned i = 0; i < 32; i++) s.f[i] = 0x1234567800000000ull + i;')
        native = native.replace('  s.r[31] =', '  s.status_known = 1; s.cp0_status = 0x24000000; s.fr_mode = 2;\n  s.r[31] =')
        native = native.replace('  printf("]}\\n");', '  printf("],\\"status\\":%u}\\n", s.cp0_status);')
        (OUT / 'harness.c').write_text(native)
        binary = OUT / ('check.exe' if os.name == 'nt' else 'check')
        compile_cmd = [cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
                       '-DPLAID_LOWERED="native.c"', f'-DPLAID_EXIT={A.EXIT}u', '-I', str(OUT),
                       str(OUT / 'harness.c'), '-lm', '-o', str(binary)]
        subprocess.run(compile_cmd, check=True)
        actual = json.loads(subprocess.check_output([str(binary)], text=True, timeout=30))
        assert actual == expected, (fr0, {k: (actual[k], expected[k]) for k in actual if actual[k] != expected[k]})
        # Restoring the old FR check must break the same positive contract.
        generated = (OUT / 'native.c').read_text()
        needle = 'if (plaid_status_cop1(s, '
        assert needle in generated
        mutant = re.sub(r'plaid_status_cop1\(s, (0x[0-9a-f]+u)\)',
                        rf'plaid_status_fp(s, \1, {int(fr0)})', generated)
        (OUT / 'native.c').write_text(mutant)
        subprocess.run(compile_cmd, check=True)
        result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
        assert result.returncode == 6 and json.loads(result.stdout)['fault'] == 11, result
        (OUT / 'native.c').write_text(generated)
        subprocess.run(compile_cmd, check=True)
        assert json.loads(subprocess.check_output([str(binary)], text=True, timeout=30)) == expected
    (OUT / 'receipt.json').write_text(json.dumps(dict(ares=A.builder().REV, matched=list(expected),
        layouts=2, status_writes=3, mutation='old FR check faults 11 in both layouts'), indent=2))
    print('PASS COP1 control registers: both map layouts, native Status.FR transitions, full GPR/FPR/PC/HI/LO/FCSR/RAM; old FR-check mutations fault 11')


if __name__ == '__main__':
    main()
