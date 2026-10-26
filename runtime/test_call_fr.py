"""ADR-0280: unknown-entry/call FPR layouts versus the pinned ares core."""
import json
import os
from pathlib import Path
import shutil
import subprocess

from test_cop0 import A

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'target/call-fr-contract'


def fixture():
    li = lambda reg, value: [A.lui(reg, value >> 16 & 65535), A.ori(reg, reg, value & 65535)]
    mode = lambda fr0: [*li(A.t0, 0x20000000 if fr0 else 0x24000000), 0x40886000]
    p = [*li(A.gp, 0x80001000), *mode(False)]
    for f in range(32):
        p += [*li(A.t0, 0x3f000000 + f * 0x10000), A.mtc1(A.t0, f)]
    for i, value in enumerate([0x3fa00000, 0, 0x3ff80000, 0]):
        p += [*li(A.t0, value), A.sw(A.t0, i * 4, A.gp)]
    for n, fr0 in enumerate([False, True, False]):
        p += [*mode(fr0), *li(A.a0, 0x80001040 + n * 64), A.jal('helper'), A.nop]
    # A callee changes FR and returns. The caller must reselect after the call.
    p += [A.jal('off'), A.nop, *li(A.a0, 0x80001100), A.jal('helper'), A.nop,
          *A.DONE, 'off', *mode(True), A.jr(A.ra), A.nop,
          'helper', A.lwc1(1, 0, A.gp), A.ldc1(3, 8, A.gp),
          *li(A.t2, 0xbf800000), A.mtc1(A.t2, 7),
          A.swc1(1, 0, A.a0), A.sdc1(3, 8, A.a0),
          A.dmfc1(A.t1, 3), A.sd(A.t1, 16, A.a0),
          A.fop(16, 0)(5, 7, 1), A.swc1(5, 24, A.a0),
          A.fop(17, 6)(9, 3), A.sdc1(9, 32, A.a0),
          A.fop(16, 33)(11, 1), A.fcmp(16, 2)(1, 1),
          A.addiu(A.t0, A.zero, 0), A.bc1t('taken'), A.nop,
          A.addiu(A.t0, A.zero, 1), 'taken', A.sw(A.t0, 40, A.a0),
          A.bc1fl('annulled'), A.addiu(A.t0, A.t0, 1), 'annulled',
          A.sw(A.t0, 44, A.a0), A.jr(A.ra), A.sdc1(11, 48, A.a0)]
    return A.assemble(p)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    exe = ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    raw = OUT / 'program.bin'
    raw.write_bytes(fixture())
    source = (ROOT / 'spikes/096-native-slice/driver.cpp').read_text()
    source = source.replace('  rdram.mapIdentity = 1;',
        '  for (unsigned i=0;i<32;i++) cpu.fpu.r[i].u64=0x3ff000003f800000ull + (u64)i*0x1000000001000ull;\n  rdram.mapIdentity = 1;')
    source = source.replace('a = 0x1000; a < 0x1100', 'a = 0; a < 0x10000').replace('a != 0x1000', 'a != 0')
    source = source.replace('  std::printf("]}\\n");',
        '  std::printf("],\\"status\\":%u}\\n", (unsigned)cpu.getControlRegister(12));')
    (OUT / 'driver.cpp').write_text(source)
    oracle = A.builder().build(OUT / 'driver.cpp', OUT / 'oracle')
    expected = json.loads(subprocess.check_output([str(oracle), str(raw), hex(A.EXIT)], text=True, timeout=120))
    native = (ROOT / 'spikes/096-native-slice/harness.c').read_text().replace('#include "runtime.c"', '#include <assert.h>')
    native = native.replace('  s.r[31] =',
        '  for (unsigned i=0;i<32;i++) s.f[i]=0x3ff000003f800000ull + (u64)i*0x1000000001000ull;\n'
        '  s.status_known=1; s.cp0_status=0x24000000; s.fr_mode=2; s.status_thread=THREAD;\n  s.r[31] =')
    native = native.replace('a = 0x1000; a < 0x1100', 'a = 0; a < 0x10000').replace('a != 0x1000', 'a != 0')
    native = native.replace('  printf("]}\\n");', '  printf("],\\"status\\":%u}\\n", s.cp0_status);')
    harness = OUT / 'harness.c'
    harness.write_text(native)
    binary = OUT / ('check.exe' if os.name == 'nt' else 'check')
    def run(thread=0):
        subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
            f'-DTHREAD={thread}', '-DPLAID_LOWERED="native.c"', f'-DPLAID_EXIT={A.EXIT}u',
            '-I', str(OUT), str(harness), '-lm', '-o', str(binary)], check=True)
        result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
        return result.returncode, json.loads(result.stdout)
    for fr0 in (False, True):
        subprocess.run([str(exe), 'lower-c', str(raw), hex(A.BASE), hex(A.BASE), hex(A.EXIT),
            str(OUT / 'native.c'), *(['--fr0'] if fr0 else [])], check=True, capture_output=True)
        generated = (OUT / 'native.c').read_text()
        for thread in (0, 0x80002000):
            code, actual = run(thread)
            assert code == 0 and actual == expected, (fr0, thread, code,
                {k: (actual.get(k), expected.get(k)) for k in actual if actual.get(k) != expected.get(k)})
        # Restoring the map-only selection must break the positive differential.
        needle = f'if (plaid_fp_fr0(s, {int(fr0)}))'
        assert needle in generated
        try:
            (OUT / 'native.c').write_text(generated.replace(needle, f'if ({int(fr0)})'))
            code, actual = run()
            assert code == 6 and actual['fault'] == 11, (code, actual)
        finally:
            (OUT / 'native.c').write_text(generated)
    # The entry has no Status writer, so test every source of live-layout state.
    raw.write_bytes(A.assemble([A.mfc1(A.t0, 1), A.jr(A.ra), A.nop]))
    for fr0 in (False, True):
        subprocess.run([str(exe), 'lower-c', str(raw), hex(A.BASE), hex(A.BASE), hex(A.EXIT),
            str(OUT / 'native.c'), *(['--fr0'] if fr0 else [])], check=True, capture_output=True)
        for known, status, mode, want_fr0 in ((1, 0x20000000, 2, True), (1, 0x24000000, 1, False),
                (0, 0, 1, True), (0, 0, 2, False), (0, 0, 0, fr0)):
            harness.write_text(native.replace('s.status_known=1; s.cp0_status=0x24000000; s.fr_mode=2;',
                f's.status_known={known}; s.cp0_status={status}; s.fr_mode={mode};'))
            code, actual = run()
            assert code == 0 and actual['regs'][A.t0] == (0x3ff00000 if want_fr0 else 0x3f801000), (known, status, mode, actual)
        # CU1 refusal leaves the whole state unchanged apart from fault reporting.
        harness.write_text(native.replace('s.cp0_status=0x24000000;', 's.cp0_status=0x04000000;').replace(
            '  if (plaid_run(&s)) {',
            '  static plaid_state before; before=s;\n  if (plaid_run(&s)) {\n'
            '    assert(s.fault==11 && s.fault_pc==0x80000000u);\n'
            '    s.fault=before.fault; s.fault_pc=before.fault_pc; s.pc=before.pc;\n'
            '    assert(!memcmp(&s,&before,sizeof s)); s.fault=11;'))
        code, actual = run()
        assert code == 6 and actual['fault'] == 11, (code, actual)
    harness.write_text(native)
    (OUT / 'receipt.json').write_text(json.dumps(dict(ares=A.builder().REV,
        matched=4, state=list(expected), calls=['FR1', 'FR0', 'FR1', 'callee changes FR'],
        live_layout_sources=10, mutation='map-only selection faults 11 in both defaults',
        cu1='whole state unchanged on refusal'), indent=2))
    print('PASS call FR: four full-state ares matches, both defaults/SDK contexts, live Status/mode/default, CU1 refusal; map-only mutations killed')


if __name__ == '__main__':
    main()
