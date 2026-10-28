"""Context writes establish PTEBase without inventing read-only BadVPN state."""
import json
import os
from pathlib import Path
import shutil
import subprocess

from test_cop0 import A, ares_oracle

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'target/context-contract'
SEED = 0x123456789AD43210
MASK = 0xFFFFFFFFFF800000


def constant(value):
    words = [A.ori(A.t0, A.zero, value >> 48 & 0xFFFF)]
    for shift in (32, 16, 0):
        words += [A.dsll(A.t0, A.t0, 16), A.ori(A.t0, A.t0, value >> shift & 0xFFFF)]
    return words


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    exe = ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    source = (ROOT / 'spikes/096-native-slice/driver.cpp').read_text()
    seed = (f'cpu.setControlRegister(12, 0x24000000); '
            f'cpu.setControlRegister(4, 0x{SEED:x}ull); '
            f'cpu.scc.context.badVirtualAddress = 0x{(SEED >> 4) & 0x7ffff:x}; ')
    source = source.replace('cpu.context.setMode();', seed + 'cpu.context.setMode();')
    source = source.replace('  std::printf("]}\\n");',
                            '  std::printf("],\\"context\\":%llu}\\n", (unsigned long long)cpu.getControlRegister(4));')
    (OUT / 'driver.cpp').write_text(source)
    oracle = ares_oracle.build(OUT / 'driver.cpp', OUT / 'oracle')
    cases = [(wide, value, zero) for wide in (False, True)
             for value, zero in ((0, False), (0xFFFFFFFF, False),
                                 (0xFEDCBA9876ABCDEF, False), (0xFFFFFFFFFFFFFFFF, True))]
    for index, (wide, value, zero) in enumerate(cases):
        raw = OUT / 'program.bin'
        cp = 16 << 26 | (5 if wide else 4) << 21 | (A.zero if zero else A.t0) << 16 | 4 << 11
        words = [*constant(value), cp, A.nop, A.lui(A.gp, 0x8000),
                 A.ori(A.gp, A.gp, 0x1000), A.sd(A.t0, 0, A.gp), *A.DONE]
        raw.write_bytes(A.assemble(words))
        subprocess.run([str(exe), 'lower-c', str(raw), hex(A.BASE), hex(A.BASE), hex(A.EXIT),
                        str(OUT / 'native.c')], check=True)
        native = (ROOT / 'spikes/096-native-slice/harness.c').read_text()
        native = native.replace('#include "runtime.c"', '#include <assert.h>')
        native = native.replace('  s.r[31] =',
                                f'  s.status_known = 1; s.cp0_status = 0x24000000; s.fr_mode = 2; s.cp0_context = 0x{SEED:x}ull;\n  s.r[31] =')
        native = native.replace('  printf("]}\\n");',
                                '  printf("],\\"context\\":%llu}\\n", (unsigned long long)s.cp0_context);')
        checks = r'''  { static plaid_state before; u64 v = 0x12345678ull;
    const u32 pc = 0x80000004;
    #define REFUSE(expr) do { before=s; assert(expr); assert(s.fault==12 && s.fault_pc==pc); s.fault=before.fault; s.fault_pc=before.fault_pc; assert(!memcmp(&before,&s,sizeof s)); } while(0)
    assert(s.cp0_known & (1u << 4));
    /* A write cannot establish BadVPN, even when the payload sets those bits. */
    REFUSE(plaid_cp0_read(&s,4,&v,pc)); assert(v==0x12345678ull);
    s.cp0_known=0; REFUSE(plaid_cp0_read(&s,4,&v,pc));
    s.status_known=0; REFUSE(plaid_cp0_write(&s,4,0,pc));
    s.status_known=1; s.cp0_status |= 0x10u;
    REFUSE(plaid_cp0_write(&s,4,0,pc));
    #undef REFUSE
  }
'''
        native = native.replace('  return 0;\n}', checks + '  return 0;\n}')
        (OUT / 'harness.c').write_text(native)
        binary = OUT / ('check.exe' if os.name == 'nt' else 'check')
        command = [cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
                   '-DPLAID_LOWERED="native.c"', f'-DPLAID_EXIT={A.EXIT}u', '-I', str(OUT),
                   str(OUT / 'harness.c'), '-lm', '-o', str(binary)]
        subprocess.run(command, check=True)
        expected = json.loads(ares_oracle.execute(oracle, raw, hex(A.EXIT), capture_output=True,
                                                 text=True, check=True, timeout=120).stdout)
        actual = json.loads(subprocess.check_output([str(binary)], text=True, timeout=30))
        assert actual == expected, (index, {k: (actual[k], expected[k]) for k in actual if actual[k] != expected[k]})
        # The pinned interpreter passes the full GPR payload for both forms.
        written = 0 if zero else value
        assert actual['context'] == (SEED & 0x7FFFF0) | (written & MASK)
        if index == 2:
            generated = (OUT / 'native.c').read_text()
            needle = '(s->cp0_context & 0x7ffff0ull) | (v & 0xffffffffff800000ull)'
            assert generated.count(needle) == 1
            try:
                (OUT / 'native.c').write_text(generated.replace(needle, 'v'))
                subprocess.run(command, check=True)
                mutant = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
                assert mutant.returncode or json.loads(mutant.stdout) != expected, 'unmasked Context write mutation survived'
            finally:
                (OUT / 'native.c').write_text(generated)
    (OUT / 'receipt.json').write_text(json.dumps(dict(ares=ares_oracle.REV, cases=len(cases), matched=list(actual),
        readonly_state='explicit independent synthetic seed, never inferred from a write', mutation='unmasked write killed'), indent=2))
    print('PASS Context: eight MTC0/DMTC0 full-state oracle matches, read-only bits preserved, unknown reads/privilege refuse atomically; write-mask mutation killed')


if __name__ == '__main__':
    main()
