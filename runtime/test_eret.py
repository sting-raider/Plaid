"""ADR-0237: lowered ERET versus pinned ares, with atomic refusal controls."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import ares_oracle
import json
import os
import shutil
import subprocess
from test_cop0 import A

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'target/eret-contract'


def fixture():
    cp = lambda sub, rt, rd: 16 << 26 | sub << 21 | rt << 16 | rd << 11
    items = [A.lui(A.gp, 0x8000), A.ori(A.gp, A.gp, 0x1000), A.addiu(A.t7, 0, 0)]
    for n, status in enumerate((0x24000002, 0x20000004, 0x24000006)):
        label = f'resume{n}'
        # Distinct registers retain an analysis path without inventing ERET
        # closure. The initialized t7 makes it untaken during execution.
        items += [A.bne(A.t7, 0, label), A.nop]
        for reg in (14, 30):
            selected = 30 if status & 4 else 14
            target = label if reg == selected else f'poison{n}'
            items += [A.lui(A.t0, 0x8000), A.LO(A.t0, A.t0, target), cp(4 if reg == 14 else 5, A.t0, reg)]
        items += [A.lui(A.t0, status >> 16), A.ori(A.t0, A.t0, status & 0xffff), cp(4, A.t0, 12),
                  A.I(48, A.t1, A.gp, 0), 0x42000018, f'poison{n}', 0xffffffff, label,
                  A.I(56, A.t1, A.gp, 0), A.sw(A.t1, n * 16 + 4, A.gp),
                  cp(0, A.t2, 12), A.sw(A.t2, n * 16 + 8, A.gp),
                  cp(1, A.t2, 14), A.sd(A.t2, n * 16 + 64, A.gp),
                  cp(1, A.t2, 30), A.sd(A.t2, n * 16 + 96, A.gp)]
    items += [A.lui(A.t0, 0x2400), cp(4, A.t0, 12), *A.DONE]
    return A.assemble(items)


CHECKS = r'''
  { static plaid_state before; u64 target = 0;
    #define REFUSE() do { before = s; assert(plaid_cp0_eret(&s, &target, 4)); assert(s.fault == 12 && s.fault_pc == 4); s.fault = before.fault; s.fault_pc = before.fault_pc; assert(!memcmp(&s, &before, sizeof s)); } while (0)
    s.llbit = 1; s.cp0_status = 0x24000002; s.cp0_known = 0; REFUSE();
    s.cp0_known = 1u << 14; s.cp0_epc = SX32(0x80000000u);
    s.status_known = 0; REFUSE(); s.status_known = 1;
    s.status_thread = 1; REFUSE(); s.status_thread = 0;
    s.cp0_status = 0x2400ff03; REFUSE();
    s.cp0_status = 0x24000012; REFUSE();
    s.cp0_status = 0x24000000; REFUSE();
    s.cp0_status = 0x24000006; REFUSE(); /* ErrorEPC must be independently known */
    s.cp0_status = 0x24000002; s.cp0_epc = 0x80000000ull; REFUSE();
    s.cp0_epc = SX32(0x80000001u); REFUSE();
    s.cp0_epc = SX32(0x80000000u);
    s.native_refill_active = 1; s.native_refill_epc = SX32(0x80000020u); REFUSE();
    s.native_refill_epc = s.cp0_epc; s.cp0_status = 0x24000006;
    s.cp0_known |= 1u << 30; s.cp0_error_epc = s.cp0_epc; REFUSE();
    s.native_refill_active = 0; s.cp0_status = 0x24000002;
    assert(!plaid_cp0_eret(&s, &target, 4));
    assert(target == SX32(0x80000000u) && s.pc == 0x80000000 && !s.llbit && s.cp0_status == 0x24000000);
    s.cp0_known = 1u << 30; s.cp0_error_epc = SX32(0x80000020u);
    s.cp0_status = 0x24000006; s.llbit = 1;
    assert(!plaid_cp0_eret(&s, &target, 4));
    assert(target == SX32(0x80000020u) && s.cp0_status == 0x24000002 && !s.llbit);
    #undef REFUSE
  }
'''


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if '--oracle-build' in sys.argv:
        ares_oracle.build(OUT / 'driver.cpp', OUT / 'oracle')
        return
    exe = ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    raw = OUT / 'program.bin'
    raw.write_bytes(fixture())
    cmd = [str(exe), 'lower-c', str(raw), hex(A.BASE), hex(A.BASE), hex(A.EXIT), str(OUT / 'native.c')]
    assert subprocess.run(cmd, capture_output=True).returncode != 0
    subprocess.run([*cmd, '--residual-dispatch'], check=True)
    source = (ROOT / 'spikes/096-native-slice/driver.cpp').read_text()
    source = source.replace('cpu.context.setMode();', 'cpu.setControlRegister(12, 0x24000000); cpu.context.setMode();')
    source = source.replace('  std::printf("]}\\n");', '  std::printf("],\\"status\\":%u,\\"llbit\\":%u}\\n", (unsigned)cpu.getControlRegister(12), (unsigned)cpu.scc.llbit);')
    (OUT / 'driver.cpp').write_text(source)
    native = (ROOT / 'spikes/096-native-slice/harness.c').read_text()
    native = native.replace('#include "runtime.c"', '#include <assert.h>')
    native = native.replace('  s.r[31] =', '  s.status_known = 1; s.cp0_status = 0x24000000; s.fr_mode = 2;\n  s.r[31] =')
    native = native.replace('  printf("]}\\n");', '  printf("],\\"status\\":%u,\\"llbit\\":%u}\\n", s.cp0_status, s.llbit);')
    native = native.replace('  return 0;\n}', CHECKS + '  return 0;\n}')
    (OUT / 'harness.c').write_text(native)
    binary = OUT / ('check.exe' if os.name == 'nt' else 'check')
    subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
                    '-DPLAID_LOWERED="native.c"', f'-DPLAID_EXIT={A.EXIT}u', '-I', str(OUT),
                    str(OUT / 'harness.c'), '-lm', '-o', str(binary)], check=True)
    oracle = ares_oracle.build(OUT / 'driver.cpp', OUT / 'oracle')
    command = [str(oracle), str(raw), hex(A.EXIT)]
    expected = subprocess.run(command, capture_output=True, text=True, check=True, timeout=120)
    actual = subprocess.run([str(binary)], capture_output=True, text=True, check=True, timeout=30)
    a, e = json.loads(actual.stdout), json.loads(expected.stdout)
    assert a == e, {k: (a[k], e[k]) for k in a if a[k] != e[k]}
    # Unknown native target faults after the architectural transition, without
    # executing the following guest word or falling back to a guest decoder.
    raw_unknown = OUT / 'unknown.bin'
    raw_unknown.write_bytes(A.assemble([0x42000018, 0xffffffff]))
    subprocess.run([str(exe), 'lower-c', str(raw_unknown), hex(A.BASE), hex(A.BASE),
                    hex(A.EXIT), str(OUT / 'unknown.c'), '--residual-dispatch'], check=True)
    (OUT / 'unknown-check.c').write_text(r'''#include <assert.h>
#include "unknown.c"
static plaid_state s;
int main(void) {
  plaid_load_images(&s); s.status_known = 1; s.cp0_status = 0x24000002;
  s.cp0_known = 1u << 14; s.cp0_epc = SX32(0x80000004u); s.llbit = 1;
  assert(plaid_run(&s) && s.fault == 3 && s.fault_pc == 0x80000000);
  assert(s.pc == 0x80000004 && s.cp0_status == 0x24000000 && !s.llbit);
  return 0;
}
''')
    unknown = OUT / ('unknown-check.exe' if os.name == 'nt' else 'unknown-check')
    subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
                    str(OUT / 'unknown-check.c'), '-lm', '-o', str(unknown)], check=True)
    subprocess.run([str(unknown)], check=True, timeout=30)
    (OUT / 'receipt.json').write_text(json.dumps(dict(ares=A.builder().REV, matched=list(a)), indent=2))
    print('PASS lowered ERET: EPC/ErrorEPC priority, EXL/ERL, LL/SC, FR, GPR/FPR/HI/LO, PC and RAM; unsupported states refuse atomically')


if __name__ == '__main__':
    main()
