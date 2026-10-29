"""Random reads and TLBWR sampling versus pinned ares, for every Wired value."""
import json
import os
from pathlib import Path
import shutil
import subprocess

from test_cop0 import A, ares_oracle, DUMP_ARES, DUMP_NATIVE

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'target/random-contract'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    exe = ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')
    cc = os.environ.get('CC') or shutil.which('gcc')
    cp = lambda sub, rt, rd: 16 << 26 | sub << 21 | rt << 16 | rd << 11
    li = lambda r, v: [A.lui(r, v >> 16 & 0xffff), A.ori(r, r, v & 0xffff)]
    write = lambda rd, v: [*li(A.k0, v), cp(4, A.k0, rd)]
    items = [*write(5, 0), *write(2, 1), *write(3, 1)]
    for index in range(32):
        items += [*write(0, index), *write(10, 0x40000000 + index * 0x2000), 0x42000002]
    items += [cp(4, A.a0, 6), *write(10, 0x6000005a), *write(3, 0x805f), *li(A.gp, 0x80001000)]
    for index in range(64):
        items += [cp(0, A.t1, 1), A.sw(A.t1, index * 4, A.gp), *write(2, 0x801f + index * 64), 0x42000006]
    items += A.DONE
    raw = OUT / 'program.bin'
    raw.write_bytes(A.assemble(items))
    subprocess.run([str(exe), 'lower-c', str(raw), hex(A.BASE), hex(A.BASE), hex(A.EXIT), str(OUT / 'native.c')], check=True)
    oracle_source = (ROOT / 'spikes/096-native-slice/driver.cpp').read_text()
    oracle_source = oracle_source.replace('cpu.context.setMode();', 'cpu.setControlRegister(12,0x24000000); cpu.context.setMode();')
    oracle_source = oracle_source.replace('  cpu.pipeline.setPc(', '''  unsigned wired=std::strtoul(argv[3],nullptr,0);
  cpu.ipu.r[4].u64=wired;
  ares::Nintendo64::random.seed((n64)(42u+wired),(n64)(54u^wired));
  cpu.pipeline.setPc(''')
    oracle_source = oracle_source.replace('  std::printf("]}\\n");', '  std::printf("]");\n' + DUMP_ARES + '  std::printf("}\\n");')
    (OUT / 'driver.cpp').write_text(oracle_source)
    oracle = ares_oracle.build(OUT / 'driver.cpp', OUT / 'oracle')
    native = (ROOT / 'spikes/096-native-slice/harness.c').read_text()
    native = native.replace('#include "runtime.c"', '#include <assert.h>\n#include <stdlib.h>')
    native = native.replace('int main(void) {', 'int main(int argc, char **argv) { assert(argc==2); u32 wired=(u32)strtoul(argv[1],0,0);')
    native = native.replace('  s.r[31] =', '''  s.status_known=1; s.cp0_status=0x24000000; s.fr_mode=2;
  s.r[4]=wired; plaid_cp0_random_seed(&s,42u+wired,54u^wired);
  s.r[31] =''')
    native = native.replace('  printf("]}\\n");', '  printf("]");\n' + DUMP_NATIVE + '  printf("}\\n");')
    (OUT / 'harness.c').write_text(native)
    binary = OUT / 'check.exe'
    command = [cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label', '-Wno-unused-function',
               '-DPLAID_LOWERED="native.c"', f'-DPLAID_EXIT={A.EXIT}u', '-I', str(OUT), str(OUT / 'harness.c'), '-lm', '-o', str(binary)]
    subprocess.run(command, check=True)
    expected = []
    for wired in range(64):
        result = ares_oracle.execute(oracle, raw, hex(A.EXIT), str(wired), capture_output=True, text=True, check=True, timeout=30)
        state = json.loads(result.stdout)
        actual = json.loads(subprocess.check_output([str(binary), str(wired)], text=True, timeout=30))
        assert actual == state, (wired, {k: (actual[k], state[k]) for k in state if actual[k] != state[k]})
        assert all((wired <= value <= 31) if wired <= 31 else (0 <= value <= 63) for value in actual['ram'])
        expected.append(state)
    generated = (OUT / 'native.c').read_text()
    mutations = [('index >= 32u', 'index >= 64u'),
                 ('(32u - s->cp0_wired)', '32u'),
                 ('sample = (u64)plaid_cp0_random_step(s) << 32;', 'sample = 0;')]
    try:
        for old, new in mutations:
            assert old in generated
            (OUT / 'native.c').write_text(generated.replace(old, new))
            subprocess.run(command, check=True)
            wired = 32 if old == 'index >= 32u' else 2
            result = subprocess.run([str(binary), str(wired)], capture_output=True, text=True, timeout=30)
            assert result.returncode or json.loads(result.stdout) != expected[wired], old
    finally:
        (OUT / 'native.c').write_text(generated)
    print('PASS Random/Wired: 64 domains, 8192 reads/TLBWR samples, complete pinned-ares state; sampling mutations killed')


if __name__ == '__main__':
    main()
