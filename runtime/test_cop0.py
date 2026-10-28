"""ADR-0235: lowered COP0/TLB effects versus the exact pinned ares interpreter."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import ares_oracle
import importlib.util
import json
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'target/cop0-contract'
SPEC = importlib.util.spec_from_file_location('asm', ROOT / 'spikes/096-native-slice/run.py')
A = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A)


def fixture():
    cp = lambda sub, rt, rd: 16 << 26 | sub << 21 | rt << 16 | rd << 11
    li = lambda r, v: [A.lui(r, v >> 16 & 0xffff), A.ori(r, r, v & 0xffff)]
    write = lambda reg, value, wide=False: [*li(A.t0, value), cp(5 if wide else 4, A.t0, reg)]
    items = [A.lui(A.gp, 0x8000), A.ori(A.gp, A.gp, 0x1000)]
    items += [*li(A.t0, 0x3f800000), A.mtc1(A.t0, 2), A.mtc1(A.t0, 3)]
    # All entries have a known generation. Invalid global entries also probe.
    items += write(5, 0) + write(2, 1) + write(3, 1)
    for index in range(32):
        items += write(0, index) + write(10, 0x80000000 + index * 0x2000) + [0x42000002]
    # Irregular masks normalize at TLBWI, not at the staging register write.
    for index, mask in enumerate((0, 0x2000, 0x6000, 0x1fe000, 0x1ffe000)):
        items += write(0, index) + write(5, mask) + write(10, 0x7000005a + index * 0x2000000, True)
        items += write(2, 0xfc00101f, True) + write(3, 0xf800201f) + [0x42000002]
        items += [0x42000001, 0x42000002]  # equal rewrite advances native generation
        for reg in (0, 2, 3, 5, 10):
            items += [cp(1, A.t1, reg), A.sd(A.t1, 0, A.gp), A.addiu(A.gp, A.gp, 8)]
    # Wired=31 makes Random independent of the reference's sampling/timing model.
    items += write(6, 31) + write(5, 0) + write(10, 0x60000000)
    items += write(2, 0x1001f) + write(3, 0x1005f) + [0x42000006, 0x42000006]
    items += [cp(0, A.s6, 0), *li(A.t3, 0x60000000), *li(A.t0, 0x89abcdef),
              A.sw(A.t0, 0x40, A.t3), A.lw(A.s7, 0x40, A.t3)]
    # The committed even/odd pages must drive real memory transactions too.
    items += [*li(A.t3, 0x70000000), *li(A.t0, 0x13579bdf), A.sw(A.t0, 0x40, A.t3),
              A.sw(A.t0, 0x1040, A.t3), A.lw(A.t1, 0x40, A.t3), A.sw(A.t1, 0, A.gp),
              A.lw(A.t2, 0x1040, A.t3), A.sw(A.t2, 4, A.gp)]
    items += [A.addiu(A.gp, A.gp, 8)]
    # Hits at a valid and an invalid global entry, then a miss. Both DMFC0 and MFC0 observe probe failure.
    for hi in (0x78000012, 0x8000a055, 0x40000000):
        items += write(10, hi) + [0x42000008, cp(0, A.s0, 0), cp(1, A.s1, 0),
                                  A.sd(A.s0, 0, A.gp), A.sd(A.s1, 8, A.gp), A.addiu(A.gp, A.gp, 16)]
    # Six-bit Index: 32..63 makes TLBWI/TLBR no-ops on pinned ares.
    items += write(0, 63) + [0x42000002, 0x42000001]
    items += write(6, 0xffffffff) + [cp(0, A.s2, 6)]
    # Status reserved/readonly bits, both FR directions, and untouched FPR storage.
    for value in (0x20000000, 0x24000000, 0x24a80000, 0x24070000, 0x24400000):
        items += write(12, value) + [cp(0, A.s3, 12), cp(1, A.s4, 12)]
    items += [cp(0, 0, 12), *A.DONE]
    return items


DUMP_NATIVE = r'''  printf(",\"cp0\":[");
  { u32 regs[] = {0,2,3,5,6,10,12}; u64 v; unsigned i;
    for (i = 0; i < 7; i++) { assert(!plaid_cp0_read(&s, regs[i], &v, 0)); printf("%s%llu", i ? "," : "", (unsigned long long)v); }
    for (i = 0; i < 32; i++) { plaid_tlb_entry *e = &s.tlb[i];
      printf(",%u,%llu,%u,%u", e->mask, (unsigned long long)(SX32(e->hi) & 0xc00000ffffffe0ffull), e->lo[0], e->lo[1]); }
  }
  printf("]");
'''
DUMP_ARES = r'''  std::printf(",\"cp0\":[");
  { unsigned regs[] = {0,2,3,5,6,10,12};
    for (unsigned i = 0; i < 7; i++) std::printf("%s%llu", i ? "," : "", (unsigned long long)cpu.getControlRegister(regs[i]));
    auto saved = cpu.scc.tlb;
    for (unsigned i = 0; i < 32; i++) { cpu.scc.tlb = cpu.tlb.entry[i];
      for (unsigned reg : {5,10,2,3}) std::printf(",%llu", (unsigned long long)cpu.getControlRegister(reg)); }
    cpu.scc.tlb = saved;
  }
  std::printf("]");
'''


def oracle_build():
    return ares_oracle.build(OUT / 'driver.cpp', OUT / 'oracle')


def boundary_contract(exe, cc):
    # A runtime ABI does not certify guest COP0 staging-register side effects.
    program = OUT / 'boundary.bin'
    program.write_bytes(A.assemble([A.jal('host'), A.nop, 0x40020000, *A.DONE,
                                   'host', A.jr(A.ra), A.nop]))
    declaration = OUT / 'boundary.json'
    declaration.write_text(json.dumps(dict(format='plaid-runtime-functions-v0', source='synthetic CP0 boundary',
        functions=[dict(entry=hex(A.BASE + 20), name='host', callbacks=[])])))
    subprocess.run([str(exe), 'lower-c', str(program), hex(A.BASE), hex(A.BASE), hex(A.EXIT),
                    str(OUT / 'boundary.c'), str(declaration)], check=True)
    (OUT / 'boundary-check.c').write_text(r'''#include <assert.h>
#include "boundary.c"
static plaid_state s;
int plaid_rt_host(plaid_state *p) { (void)p; return 0; }
int main(void) {
  plaid_load_images(&s); s.status_known = 1; s.cp0_status = 0x24000000;
  s.cp0_known = 1; s.cp0_index = 7;
  assert(plaid_run(&s) && s.fault == 12 && s.fault_pc == 0x80000008);
  assert(s.cp0_known == 0 && s.cp0_index == 7);
  return 0;
}
''')
    binary = OUT / ('boundary-check.exe' if os.name == 'nt' else 'boundary-check')
    subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
                    str(OUT / 'boundary-check.c'), '-lm', '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True, timeout=30)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if '--oracle-build' in sys.argv:
        oracle_build()
        return
    exe = ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    raw = OUT / 'program.bin'
    raw.write_bytes(A.assemble(fixture()))
    subprocess.run([str(exe), 'lower-c', str(raw), hex(A.BASE), hex(A.BASE), hex(A.EXIT), str(OUT / 'native.c')], check=True)
    # Extend the project-owned spike096 reporters, leaving the oracle core unchanged.
    source = (ROOT / 'spikes/096-native-slice/driver.cpp').read_text()
    source = source.replace('cpu.context.setMode();', 'cpu.setControlRegister(12, 0x24000000); cpu.context.setMode();')
    source = source.replace('  std::printf("]}\\n");', '  std::printf("]");\n' + DUMP_ARES + '  std::printf("}\\n");')
    assert DUMP_ARES in source
    (OUT / 'driver.cpp').write_text(source)
    native = (ROOT / 'spikes/096-native-slice/harness.c').read_text()
    native = native.replace('#include "runtime.c"', '#include <assert.h>')
    native = native.replace('  s.r[31] =', '  s.status_known = 1; s.cp0_status = 0x24000000; s.fr_mode = 2;\n  s.r[31] =')
    native = native.replace('  printf("]}\\n");', '  printf("]");\n' + DUMP_NATIVE + '  printf("}\\n");')
    assert DUMP_NATIVE in native
    # Faults refuse before touching architectural state or RAM.
    checks = r'''  { static plaid_state before;
      u64 v; u32 fault_pc = 0x80000004;
      for (unsigned i = 0; i < 32; i++) assert(s.tlb_generation[i] == (i < 5 || i == 31 ? 3u : 1u));
      assert(s.r[22] == 4 && s.r[23] == SX32(0x89abcdefu));
      assert(s.ram[0x400040] == 0x89 && s.ram[0x400041] == 0xab && s.ram[0x400042] == 0xcd && s.ram[0x400043] == 0xef);
      { u32 known = s.cp0_known;
        s.cp0_wired = 31; s.cp0_known &= ~1u; before = s;
        assert(!plaid_cp0_tlbwr(&s, fault_pc));
        assert(s.cp0_index == 63 && !(s.cp0_known & 1u) && s.tlb_generation[31] == before.tlb_generation[31] + 1);
        s.tlb[31] = before.tlb[31]; s.tlb_generation[31] = before.tlb_generation[31];
        assert(!memcmp(&before, &s, sizeof s)); s.cp0_known = known;
      }
      assert(!plaid_cp0_write(&s, 12, 0x20000000, fault_pc));
      assert(s.fr_mode == 1 && s.cp0_status == 0x20000000);
      assert(!plaid_cp0_write(&s, 12, 0x24000000, fault_pc));
      assert(s.fr_mode == 2 && s.cp0_status == 0x24000000);
      before = s;
      assert(plaid_cp0_read(&s, 9, &v, fault_pc));
      assert(s.fault == 12 && s.fault_pc == fault_pc);
      s.fault = before.fault; s.fault_pc = before.fault_pc;
      assert(!memcmp(&before, &s, sizeof s));
      assert(plaid_cp0_write(&s, 12, 0x2400ff01, fault_pc));
      s.fault = before.fault; s.fault_pc = before.fault_pc;
      assert(!memcmp(&before, &s, sizeof s));
      #define REFUSE(expr) do { before = s; assert(expr); assert(s.fault == 12 && s.fault_pc == fault_pc); s.fault = before.fault; s.fault_pc = before.fault_pc; assert(!memcmp(&before, &s, sizeof s)); } while (0)
      for (unsigned wired = 0; wired < 64; wired++) {
        if (wired == 31) continue;
        s.cp0_wired = wired; s.cp0_known |= 1u << 6;
        REFUSE(plaid_cp0_tlbwr(&s, fault_pc));
      }
      s.cp0_wired = 31; s.cp0_known &= ~(1u << 6);
      REFUSE(plaid_cp0_tlbwr(&s, fault_pc));
      s.cp0_known |= 1u << 6;
      for (unsigned bit = 0; bit < 32; bit++) if ((1u << bit) & 0x42cu) {
        u32 known = s.cp0_known; s.cp0_known &= ~(1u << bit);
        REFUSE(plaid_cp0_tlbwr(&s, fault_pc)); s.cp0_known = known;
      }
      REFUSE(plaid_cp0_write(&s, 11, 0, fault_pc));
      REFUSE(plaid_cp0_write(&s, 12, 0x24000001, fault_pc));
      REFUSE(plaid_cp0_write(&s, 12, 0x25000000, fault_pc));
      REFUSE(plaid_cp0_write(&s, 12, 0x26000000, fault_pc));
      s.cp0_index = 0;
      s.cp0_entryhi = 0x100000000ull;
      REFUSE(plaid_cp0_tlbwi(&s, fault_pc));
      REFUSE(plaid_cp0_tlbwr(&s, fault_pc));
      s.cp0_entryhi = 0x70000000;
      s.cp0_tlb.lo[0] &= ~1u;
      REFUSE(plaid_cp0_tlbwi(&s, fault_pc));
      REFUSE(plaid_cp0_tlbwr(&s, fault_pc));
      s.cp0_tlb.lo[0] |= 1u;
      s.cp0_known = 0;
      REFUSE(plaid_cp0_tlbwi(&s, fault_pc));
      REFUSE(plaid_cp0_read(&s, 0, &v, fault_pc));
      s.cp0_known = 0x42d;
      s.tlb_generation[0] = 0;
      REFUSE(plaid_cp0_tlbr(&s, fault_pc));
      REFUSE(plaid_cp0_tlbp(&s, fault_pc));
      s.tlb_generation[0] = 1; s.tlb[0].mask = 0x2000;
      REFUSE(plaid_cp0_tlbr(&s, fault_pc));
      REFUSE(plaid_cp0_tlbp(&s, fault_pc));
      s.status_known = 0;
      REFUSE(plaid_cp0_write(&s, 12, 0x24000000, fault_pc));
      REFUSE(plaid_cp0_tlbwr(&s, fault_pc));
      s.status_known = 1; s.cp0_status |= 0x10;
      REFUSE(plaid_cp0_read(&s, 12, &v, fault_pc));
      s.cp0_status &= ~0x18u;
      #undef REFUSE
      s.fr_mode = 1; s.cp0_status &= ~0x04000000u;
      assert(!plaid_status_fp(&s, 0, 1));
      assert(plaid_status_fp(&s, fault_pc, 0) && s.fault == 11);
    }
'''
    native = native.replace('  return 0;\n}', checks + '  return 0;\n}')
    (OUT / 'harness.c').write_text(native)
    binary = OUT / ('check.exe' if os.name == 'nt' else 'check')
    subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
                    '-DPLAID_LOWERED="native.c"', f'-DPLAID_EXIT={A.EXIT}u', '-I', str(OUT),
                    str(OUT / 'harness.c'), '-lm', '-o', str(binary)], check=True)
    oracle = oracle_build()
    command = [str(oracle), str(raw), hex(A.EXIT)]
    expected = subprocess.run(command, capture_output=True, text=True, check=True, timeout=120)
    actual = subprocess.run([str(binary)], capture_output=True, text=True, check=True, timeout=30)
    a, e = json.loads(actual.stdout), json.loads(expected.stdout)
    assert a == e, {k: (a[k], e[k]) for k in a if a[k] != e[k]}
    generated = (OUT / 'native.c').read_text()
    guard = 's->cp0_wired != 31u'
    assert generated.count(guard) == 1
    try:
        (OUT / 'native.c').write_text(generated.replace(guard, '0'))
        mutant = OUT / ('check-unguarded.exe' if os.name == 'nt' else 'check-unguarded')
        subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
                        '-DPLAID_LOWERED="native.c"', f'-DPLAID_EXIT={A.EXIT}u', '-I', str(OUT),
                        str(OUT / 'harness.c'), '-lm', '-o', str(mutant)], check=True)
        changed = subprocess.run([str(mutant)], capture_output=True, text=True, timeout=30)
        assert changed.returncode != 0, 'removed Random-domain guard escaped the refusal contract'
        (OUT / 'removed-domain-guard.stderr').write_text(changed.stderr)
    finally:
        (OUT / 'native.c').write_text(generated)
    boundary_contract(exe, cc)
    (OUT / 'receipt.json').write_text(json.dumps(dict(format='plaid-cop0-contract-v0', ares=A.builder().REV, matched=list(a), forms=8), indent=2))
    print('PASS eight lowered COP0/TLB forms: GPR/FPR, PC, HI/LO, RAM, staging registers, all 32 TLB entries; Wired=31 TLBWR preserves Index; unknown/event/wider-domain state refuses atomically')


if __name__ == '__main__':
    main()
