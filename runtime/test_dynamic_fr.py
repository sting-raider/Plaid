"""ADR-0276: native FR data flow and canonical FPR bits versus pinned ares."""
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
OUT = ROOT / 'target/dynamic-fr-contract'


def scheduler_contract(exe, cc):
    import test_runtime as T
    T.OUT.mkdir(parents=True, exist_ok=True)
    glob, one, two, log = 0x80004000, 0x80002000, 0x80002200, 0x80003000
    names = ['osCreateThread', 'osStartThread', '__osGetSR', 'osSetIntMask', 'osSetThreadPri']
    on = [0x40086000, A.lui(A.t1, 0x0400), A.or_(A.t0, A.t0, A.t1), 0x40886000]
    off = [0x40086000, *T.li(A.t1, 0xfbffffff), A.and_(A.t0, A.t0, A.t1), 0x40886000]
    def status(offset):
        return [*T.call('__osGetSR'), *T.li(A.t0, log), A.sw(A.v0, offset, A.t0)]
    program = [*T.li(A.sp, 0x80007f00), *T.poke(glob, 0x003fff01),
        *T.call('osCreateThread', one, 1, 'one', 0, 0x80010000, 10),
        *T.call('osStartThread', one), *A.DONE,
        'one', *on, *T.li(A.t2, 0x12345678), A.mtc1(A.t2, 1),
        *T.call('osCreateThread', two, 2, 'two', 0, 0x80018000, 20),
        *T.call('osStartThread', two), *status(4),
        *on, A.mfc1(A.t2, 1), *T.li(A.t0, log), A.sw(A.t2, 8, A.t0),
        *off, A.mfc1(A.t2, 1), *T.li(A.t0, log), A.sw(A.t2, 12, A.t0), *status(16), *A.DONE,
        'two', *status(0), *T.li(A.t2, 0x76543210), A.mtc1(A.t2, 1),
        *T.call('osSetThreadPri', 0, 1), *A.DONE]
    for name in names:
        program += [name, A.jr(A.ra), A.nop]
    binary = T.build(exe, cc, 'dynamic-fr-threads', program, names,
        status_globals={'osCreateThread': glob, 'osSetIntMask': glob}, fr0=True)
    r = subprocess.run([str(binary), '--dump', hex(log), '5'], capture_output=True, text=True, timeout=30)
    rows = [json.loads(l) for l in r.stdout.splitlines() if l.startswith('{')]
    stop = next(v for v in rows if 'stop' in v)
    assert r.returncode == 0 and stop['fault'] == 0, (r.stdout, r.stderr)
    assert next(v['words'] for v in rows if 'dump' in v) == [0xff01, 0x2400ff01, 0x12345678, 0, 0x2000ff01], rows


def fixture(branch=False, taken=False):
    cp = lambda sub, rt: 16 << 26 | sub << 21 | rt << 16 | 12 << 11
    li = lambda r, v: [A.lui(r, v >> 16), A.ori(r, r, v & 0xffff)]
    on = [cp(0, A.t0), A.lui(A.t1, 0x0400), A.or_(A.t0, A.t0, A.t1)]
    off = [cp(0, A.t0), *li(A.t1, 0xfbffffff), A.and_(A.t0, A.t0, A.t1), cp(4, A.t0)]
    items = [*li(A.gp, 0x80001000), *li(A.t0, 0x20000000), cp(4, A.t0)]
    # FR0 odd transfers change high halves, leaving hidden odd slots intact.
    for f in range(32):
        items += [*li(A.t2, 0x3f000000 + f * 0x10000), A.mtc1(A.t2, f)]
    items += [*on]
    if branch:
        items += [A.addiu(A.t3, A.zero, int(taken)), A.bnel(A.t3, A.zero, 'join'), cp(4, A.t0),
                  # Untaken likely slot is annulled; establish FR1 explicitly.
                  *on, cp(4, A.t0), 'join']
    else:
        items += [A.j('join'), cp(4, A.t0), 'join']  # Status write in a real delay slot
    # Read FR0 writes as FR1, including independent hidden odd registers.
    for n, f in enumerate((0, 1, 2, 3, 30, 31)):
        items += [A.dmfc1(A.s0, f), A.sd(A.s0, n * 8, A.gp)]
    # Independent FR1 odd 64-bit loads/stores and arithmetic destinations.
    items += [A.ldc1(1, 0, A.gp), A.ldc1(3, 16, A.gp), A.fop(17, 0)(5, 1, 3),
              A.sdc1(5, 48, A.gp), A.mtc1(A.t2, 31), *off]
    for n, f in enumerate((0, 1, 2, 3, 30, 31)):
        items += [A.dmfc1(A.s1, f), A.sd(A.s1, 64 + n * 8, A.gp),
                  A.mfc1(A.s2, f), A.sw(A.s2, 112 + n * 4, A.gp)]
    # Same loop traverses both switches twice; source/ft/fd odd rules in FR0.
    items += [A.addiu(A.t4, A.zero, 2), 'loop', *on, cp(4, A.t0),
              A.mtc1(A.t2, 7), A.fop(16, 0)(9, 7, 7), *off,
              A.fop(16, 0)(11, 1, 2), A.swc1(11, 144, A.gp),
              A.addiu(A.t4, A.t4, -1), A.bne(A.t4, A.zero, 'loop'), A.nop,
              *on, cp(4, A.t0), A.sdc1(31, 152, A.gp), *off, *A.DONE]
    return A.assemble(items)


def unproven_join(exe, compile_run):
    # A single generated join can be entered in either mode. The analysis must
    # select the live layout, never carry the first predecessor's FR fact.
    program = [A.lui(A.t0, 0x2000), 0x40886000,
               A.beq(A.t3, A.zero, 'join'), A.nop,
               A.lui(A.t0, 0x2400), 0x40886000, 'join',
               A.mfc1(A.t2, 1), *A.DONE]
    raw = OUT / 'join.bin'
    raw.write_bytes(A.assemble(program))
    subprocess.run([str(exe), 'lower-c', str(raw), hex(A.BASE), hex(A.BASE), hex(A.EXIT),
        str(OUT / 'native.c'), '--fr0'], check=True, capture_output=True)
    harness = (OUT / 'harness.c').read_text()
    try:
        for taken in (0, 1):
            (OUT / 'harness.c').write_text(harness.replace('  s.r[31] =',
                f'  s.r[{A.t3}] = {taken};\n  s.r[31] ='))
            result = compile_run()
            actual = json.loads(result.stdout)
            assert result.returncode == 0 and actual['status'] == (0x24000000 if taken else 0x20000000), actual
            assert actual['regs'][A.t2] == (1 if taken else 0x12345678), actual
    finally:
        (OUT / 'harness.c').write_text(harness)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if '--oracle-build' in sys.argv:
        ares_oracle.build(OUT / 'driver.cpp', OUT / 'oracle')
        return
    exe = ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    source = (ROOT / 'spikes/096-native-slice/driver.cpp').read_text()
    source = source.replace('  rdram.mapIdentity = 1;',
        '  for(unsigned i = 0; i < 32; i++) cpu.fpu.r[i].u64 = 0x1234567800000000ull + i;\n  rdram.mapIdentity = 1;')
    source = source.replace('cpu.context.setMode();', 'cpu.setControlRegister(12, 0x24000000); cpu.context.setMode();')
    source = source.replace('  std::printf("]}\\n");', '  std::printf("],\\"status\\":%u}\\n", (unsigned)cpu.getControlRegister(12));')
    (OUT / 'driver.cpp').write_text(source)
    command = [str(ares_oracle.build(OUT / 'driver.cpp', OUT / 'oracle'))]
    native = (ROOT / 'spikes/096-native-slice/harness.c').read_text().replace('#include "runtime.c"', '#include <assert.h>')
    native = native.replace('  plaid_load_images(&s);',
        '  plaid_load_images(&s);\n  for (unsigned i = 0; i < 32; i++) s.f[i] = 0x1234567800000000ull + i;')
    native = native.replace('  s.r[31] =',
        '  s.status_known = 1; s.cp0_status = 0x24000000; s.fr_mode = 2; s.status_thread = THREAD;\n  s.r[31] =')
    native = native.replace('  printf("]}\\n");', '  printf("],\\"status\\":%u}\\n", s.cp0_status);')
    (OUT / 'harness.c').write_text(native)
    binary = OUT / ('check.exe' if os.name == 'nt' else 'check')
    def compile_run(thread=0):
        subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
            f'-DTHREAD={thread}', '-DPLAID_LOWERED="native.c"', f'-DPLAID_EXIT={A.EXIT}u',
            '-I', str(OUT), str(OUT / 'harness.c'), '-lm', '-o', str(binary)], check=True)
        return subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
    matched = 0
    for branch, taken in ((False, False), (True, False), (True, True)):
        raw = OUT / 'program.bin'
        raw.write_bytes(fixture(branch, taken))
        expected = json.loads(subprocess.check_output([*command, str(raw), hex(A.EXIT)], text=True, timeout=120))
        for fr0 in (False, True):
            subprocess.run([str(exe), 'lower-c', str(raw), hex(A.BASE), hex(A.BASE), hex(A.EXIT),
                str(OUT / 'native.c'), *(['--fr0'] if fr0 else [])], check=True, capture_output=True)
            generated = (OUT / 'native.c').read_text()
            for thread in (0, 0x80002000):
                result = compile_run(thread)
                actual = json.loads(result.stdout)
                assert result.returncode == 0 and actual == expected, (branch, taken, fr0, thread,
                    {k: (actual.get(k), expected.get(k)) for k in actual if actual.get(k) != expected.get(k)})
                matched += 1
            # A wrong inferred-layout guard must kill the positive differential.
            mutant, count = re.subn(r'(plaid_status_fp\(s, 0x[0-9a-f]+u, )0(\))', r'\g<1>1\2', generated, count=1)
            assert count == 1
            try:
                (OUT / 'native.c').write_text(mutant)
                result = compile_run()
                assert result.returncode == 6 and json.loads(result.stdout)['fault'] == 11, result
            finally:
                (OUT / 'native.c').write_text(generated)
    unproven_join(exe, compile_run)
    (OUT / 'receipt.json').write_text(json.dumps(dict(ares=A.builder().REV, matched=matched,
        state=list(expected), mutation='inferred FR1 guard inverted: fault 11',
        fixtures=['jump slot', 'likely annulled', 'likely taken'], layouts=2, contexts=2,
        unproven_join='FR0/FR1 select their live canonical FPR layout'), indent=2))
    scheduler_contract(exe, cc)
    print(f'PASS dynamic FR: {matched} native/ares full-state matches; FR0/FR1 aliasing, loops, slots, both defaults/SDK contexts; guard mutation killed')


if __name__ == '__main__':
    main()
