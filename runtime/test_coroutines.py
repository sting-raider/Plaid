"""Native structural jumps: self-unwind, edited entry/stack, yield and exit."""
import json
import os
import re
import subprocess

LOG, INDEX = 0x80001000, 0x80001100
SCHED, WORKER, LOCAL = 0x80002000, 0x80002100, 0x80002200


def bodies(A, nonzero=True):
    regs = [A.sp, A.ra, *range(A.s0, A.s7 + 1), A.fp]
    save = [A.sw(r, i * 4, A.a0) for i, r in enumerate(regs)]
    load = [A.lw(r, i * 4, A.a0) for i, r in enumerate(regs)]
    save += [A.swc1(r, (r - 9) * 4, A.a0) for r in range(20, 32)]
    load += [A.lwc1(r, (r - 9) * 4, A.a0) for r in range(20, 32)]
    save += [A.jr(A.ra), A.or_(A.v0, A.zero, A.zero)]
    load += [A.or_(A.v0, A.a1, A.zero)]
    if nonzero:
        load += [A.bne(A.v0, A.zero, 'jump_return'), A.nop, A.addiu(A.v0, A.zero, 1)]
    load += ['jump_return', A.jr(A.ra), A.nop]
    return ['save', *save, 'restore', *load]


def program(T, authored=False, retarget=False):
    A = T.A

    def log(reg):
        return [*T.li(A.t8, INDEX), A.lw(A.t9, 0, A.t8), A.sll(A.t7, A.t9, 2),
                *T.li(A.t6, LOG), A.addu(A.t7, A.t7, A.t6), A.sw(reg, 0, A.t7),
                A.addiu(A.t9, A.t9, 1), A.sw(A.t9, 0, A.t8)]

    return [
        *T.li(A.sp, 0x80007F00), *T.li(A.s0, 0x11223344),
        # Mutable RAM source forces the shared residual call dispatcher. The
        # setjmp builtin must still be emitted in this caller's own frame.
        *([*T.call('save', LOCAL)] if retarget else [
        *T.li(A.a0, LOCAL), *T.li(A.t0, 0x80002300),
        A.lui(A.t9, 0x8000), A.LO(A.t9, A.t9, 'save'), A.sw(A.t9, 0, A.t0),
        A.lw(A.t9, 0, A.t0), A.jalr(A.ra, A.t9), A.nop]),
        A.bne(A.v0, A.zero, 'self_resumed'), A.nop,
        # Two discarded lowered frames, with no reachable return from restore.
        A.jal('abandon_outer'), A.nop, 0x0000000D,
        'self_resumed', *log(A.v0), *log(A.s0),
        # Writing abandoned text must succeed: mutation missing unpin faults 2.
        A.lui(A.t0, 0x8000), A.LO(A.t0, A.t0, 'abandon_after'), A.sw(A.zero, 0, A.t0),
        A.lui(A.t0, 0x8000), A.LO(A.t0, A.t0, 'abandon_inner'), A.sw(A.zero, 0, A.t0),
        *([*T.poke(WORKER, 0x8000FF00), *T.li(A.t0, WORKER),
           A.lui(A.t1, 0x8000), A.LO(A.t1, A.t1, 'worker'), A.sw(A.t1, 4, A.t0)]
          if authored else [A.jal('create'), A.nop]),
        'scheduler_save', *T.call('save', SCHED), 'scheduler_ready', A.bne(A.v0, A.zero, 'scheduler_resumed'), A.nop,
        *T.call('restore', WORKER, 7), 0x0000000D,
        'scheduler_resumed', *log(A.v0),
        *T.li(A.t0, 2), A.beq(A.v0, A.t0, 'finished'), A.nop,
        # Reuse the live scheduler save across several host-context handoffs.
        *([*T.li(A.t0, WORKER), A.lui(A.t1, 0x8000), A.LO(A.t1, A.t1, 'replacement'),
           A.sw(A.t1, 4, A.t0)] if retarget else []),
        *T.call('restore', WORKER, 7), 0x0000000D,
        'finished', *A.DONE,
        'abandon_outer', A.addiu(A.sp, A.sp, -16), A.jal('abandon_inner'), A.nop, 'abandon_after', 0x0000000D,
        'abandon_inner', *T.li(A.s0, 0xDEADBEEF), *T.call('restore', LOCAL, 0), 0x0000000D,
        'create', A.addiu(A.sp, A.sp, -16), A.sw(A.ra, 0, A.sp),
        *T.call('save', WORKER),
        *T.li(A.t0, WORKER), *T.li(A.t1, 0x8000FF00), A.sw(A.t1, 0, A.t0),
        A.lui(A.t1, 0x8000), A.LO(A.t1, A.t1, 'worker'), A.sw(A.t1, 4, A.t0),
        A.lw(A.ra, 0, A.sp), A.jr(A.ra), A.addiu(A.sp, A.sp, 16),
        'worker', *log(A.sp), *T.li(A.s0, 0x55667788),
        *T.li(A.t0, 0x3F800000), A.mtc1(A.t0, 20),
        A.jal('sleep'), A.nop, *log(A.v0), *log(A.s0),
        A.mfc1(A.t0, 20), *log(A.t0),
        # Exit has no live save frame in this context: release the stack.
        *T.call('restore', SCHED, 2), 0x0000000D,
        'sleep', A.addiu(A.sp, A.sp, -16), A.sw(A.ra, 0, A.sp),
        *T.call('save', WORKER), A.bne(A.v0, A.zero, 'woke'), A.nop,
        *T.call('restore', SCHED, 1), 0x0000000D,
        'woke', A.lw(A.ra, 0, A.sp), A.jr(A.ra), A.addiu(A.sp, A.sp, 16),
        *(['replacement', *log(A.v0), *log(A.s0), A.mfc1(A.t0, 20), *log(A.t0),
        # The retargeted context must never execute its suspended native body
        # again, so all of that body's pins must already have been released.
        A.lui(A.t0, 0x8000), A.LO(A.t0, A.t0, 'sleep'), A.sw(A.zero, 0, A.t0),
        *T.call('restore', SCHED, 2), 0x0000000D] if retarget else []),
        *bodies(A),
    ]


def run(exe, cc, T):
    os.environ['SDL_AUDIODRIVER'] = 'dummy'
    # The oracle image is linked at 80000000; COP0/COP1 start usable, FR=0.
    T.OUT.mkdir(parents=True, exist_ok=True)
    native = T.build(exe, cc, 'coroutines', program(T), [],
                     ['-DPLAID_BOOT_STATUS=0x30000000u', '-DPLAID_BOOT_ENTRYHI=0ull'], fr0=True, address_taken=True, residual_dispatch=True)
    result = subprocess.run([str(native), '--seconds', '5', '--dump', hex(LOG), '12'],
                            capture_output=True, text=True, timeout=30,
                            env={**os.environ, 'SDL_AUDIODRIVER': 'dummy'})
    rows = [json.loads(l) for l in result.stdout.splitlines() if l.startswith('{')]
    stop = next(r for r in rows if 'stop' in r)
    words = next(r['words'] for r in rows if 'dump' in r)
    assert result.returncode == 0 and stop['stop'] == 'exit' and stop['fault'] == 0, (result.stdout, result.stderr)
    assert words == [1, 0x11223344, 0x8000FF00, 1, 7, 0x55667788, 0x3F800000, 2, 0, 0, 0, 0], words
    # The driver explicitly chooses FR=0 and loads the image at 80000000.
    driver = T.OUT / 'coroutines-driver.cpp'
    driver.write_text((T.ROOT / 'spikes/096-native-slice/driver.cpp').read_text()
                      .replace('a = 0x1000; a < 0x1100', 'a = 0; a < 0x10000')
                      .replace('a != 0x1000', 'a != 0'))
    oracle = T.A.builder().build(driver, T.OUT / 'coroutines-oracle')
    command = [str(oracle), str(T.OUT / 'coroutines.bin'), hex(T.A.EXIT), 'fr0']
    expected = json.loads(subprocess.check_output(command, text=True, timeout=120))
    assert expected['pc'] == T.A.EXIT and expected['ram'][0x400:0x40C] == words, expected['pc']

    # Instrument a test-only copy for complete architectural state comparison.
    # Production runtime and oracle sources are never mutated by this test.
    report = r'''
  printf("{\"state\":{\"pc\":%u,\"regs\":[", S->pc);
  for (i = 0; i < 32; i++) printf("%s%llu", i ? "," : "", (unsigned long long)S->r[i]);
  printf("],\"hi\":%llu,\"lo\":%llu,\"fpr\":[", (unsigned long long)S->hi, (unsigned long long)S->lo);
  for (i = 0; i < 32; i++) printf("%s%llu", i ? "," : "", (unsigned long long)S->f[i]);
  printf("],\"fcc\":%u,\"fcsr\":%u,\"ram\":[", S->fcc, S->fcsr | S->fcc << 23);
  for (i = 0; i < 0x4000; i++) { unsigned p = 4 * i;
    unsigned w = (unsigned)S->ram[p] << 24 | (unsigned)S->ram[p+1] << 16 | (unsigned)S->ram[p+2] << 8 | S->ram[p+3];
    printf("%s%u", i ? "," : "", w); }
  printf("]}}\n");
'''
    runtime = (T.ROOT / 'runtime/plaid_rt.c').read_text()
    source = T.OUT / 'coroutines-probe.c'
    ownership = r'''
  { rt_context own = {0}, other = {0};
    plaid_native_frame target = {0,0,0,0,0,0,0}, first = {0,0,0,0,0,0,1},
                       foreign = {0,0,0,0,0,0,2}, last = {0,0,0,0,0,0,3};
    S->native_context = &own; plaid_text_pin(S, &target); plaid_text_pin(S, &first);
    S->native_context = &other; plaid_text_pin(S, &foreign);
    S->native_context = &own; plaid_text_pin(S, &last);
    if (jump_unwind(&own, &target, 0) || S->native_frames != &foreign || foreign.next != &target ||
        S->ovl_active[0] != 1 || S->ovl_active[1] || S->ovl_active[2] != 1 || S->ovl_active[3])
      finish(1, "context/overlay unwind contract failed");
    plaid_text_unpin(S, &foreign); plaid_text_unpin(S, &target);
    S->native_context = host_context;
  }
'''
    source.write_text(runtime.replace('  fflush(stdout);', report + '\n  fflush(stdout);')
                      .replace('  S->r[31] = THREAD_RETURN;', ownership + '\n  S->r[31] = THREAD_RETURN;'))
    probe = T.OUT / ('coroutines-probe.exe' if os.name == 'nt' else 'coroutines-probe')

    def compile_probe():
        subprocess.run([cc, '-O2', '-std=gnu11', '-Wall', '-Werror', '-Wno-unused-label', '-Wno-unused-function',
                        '-DPLAID_SAFEPOINTS', '-DPLAID_BOOT_STATUS=0x30000000u', '-DPLAID_BOOT_ENTRYHI=0ull',
                        '-DPLAID_LOWERED="coroutines.c"', '-I', str(T.OUT), '-I', str(T.ROOT / 'runtime'),
                        str(source), '-pthread', '-o', str(probe)], check=True)

    compile_probe()
    actual = subprocess.run([str(probe)], capture_output=True, text=True, timeout=30)
    assert actual.returncode == 0, (actual.stdout, actual.stderr)
    state = next(json.loads(l)['state'] for l in actual.stdout.splitlines() if l.startswith('{"state"'))
    assert state == expected, {k: (state[k], expected[k]) for k in state if k != 'ram' and state[k] != expected[k]}
    authored_reuse(exe, cc, T, oracle, report)

    # Removing context unwind leaves two suspended fixed-text pins. The guest
    # overwrite above must expose that regression, rather than silently pass.
    header = (T.ROOT / 'runtime/jumps.h').read_text()
    assert '      plaid_text_unpin(S, f);' in header
    (T.OUT / 'jumps-mutant.h').write_text(header.replace('      plaid_text_unpin(S, f);', '      plaid_native_frame *leak = malloc(sizeof *leak); *leak = *f; leak->jumps = NULL; plaid_text_unpin(S, f); plaid_text_pin(S, leak);'))
    source.write_text(runtime.replace('#include "jumps.h"', '#include "jumps-mutant.h"'))
    compile_probe()
    mutant = subprocess.run([str(probe)], capture_output=True, text=True, timeout=30)
    mutant_stop = next(json.loads(l) for l in mutant.stdout.splitlines() if l.startswith('{"stop"'))
    assert mutant.returncode == 1 and mutant_stop['fault'] == 2, (mutant.stdout, mutant.stderr)
    # Abandoned parked stacks cannot be reclaimed without a guest liveness
    # proof. Both resource caps must fault, rather than run without protection.
    for refusal in ('context_count = 256; new_context(&boot, 0, 0);', 'jump_count = 4096;'):
        source.write_text(runtime.replace('  S->r[31] = THREAD_RETURN;', refusal + '\n  S->r[31] = THREAD_RETURN;'))
        compile_probe()
        result = subprocess.run([str(probe)], capture_output=True, text=True, timeout=30)
        stop = next(json.loads(l) for l in result.stdout.splitlines() if l.startswith('{"stop"'))
        assert result.returncode == 1 and stop['fault'] == 13, (refusal, result.stdout, result.stderr)
    print('coroutines: edited entry/stack, caller continuation, self-unwind, yield and exit match pinned ares '
          '(all GPR/FPR/PC/HI/LO/FCSR and 64 KiB RAM); context/overlay ownership passes; missing-unpin mutation faults 2')
    negatives(exe, cc, T)
    scheduling(exe, cc, T, words)
    repeated_resumes(exe, cc, T, oracle)
    multiple_saves(exe, cc, T, oracle)
    authored_creation(exe, cc, T, oracle, words)
    retargeted_creation(exe, cc, T, oracle, words)
    lifecycle_refusals(exe, cc, T)


def negatives(exe, cc, T):
    A = T.A
    prefix = [*T.li(A.sp, 0x80007F00)]
    cases = {
        'wrong-link': [*T.li(A.a0, LOCAL), A.jal('save'), A.addiu(A.ra, A.ra, 4), *A.DONE],
        'resumed-text': [A.j('begin'), A.nop,
                         'resumed', A.lui(A.t0, 0x8000), A.LO(A.t0, A.t0, 'protected'),
                         A.sw(A.zero, 0, A.t0), 'protected', *A.DONE,
                         'begin', *T.call('save', LOCAL), A.bne(A.v0, A.zero, 'resumed'), A.nop,
                         A.jal('abandon'), A.nop, 'never', A.j('never'), A.nop,
                         'abandon', *T.call('restore', LOCAL, 1), 0x0000000D],
        'unrecorded': [*T.call('restore', LOCAL, 1), *A.DONE],
        'edited-register': [*T.call('save', LOCAL), *T.poke(LOCAL + 8, 0xBAD),
                            *T.call('restore', LOCAL, 1), *A.DONE],
        'misaligned-stack': [*T.call('save', LOCAL), *T.poke(LOCAL, 0x80007004),
                              *T.call('restore', LOCAL, 1), *A.DONE],
        'misaligned-entry': [*T.call('save', LOCAL), *T.poke(LOCAL + 4, 0x80007002),
                              *T.call('restore', LOCAL, 1), *A.DONE],
        'expired-frame': [A.jal('expired'), A.nop, *T.call('restore', LOCAL, 1), *A.DONE,
                          'expired', A.addiu(A.sp, A.sp, -16), A.sw(A.ra, 0, A.sp),
                          *T.call('save', LOCAL), A.lw(A.ra, 0, A.sp),
                          A.jr(A.ra), A.addiu(A.sp, A.sp, 16)],
        'entry-returned': [A.jal('returns'), A.nop, *T.call('save', LOCAL), *T.li(A.t0, LOCAL),
                           A.lui(A.t1, 0x8000), A.LO(A.t1, A.t1, 'returns'), A.sw(A.t1, 4, A.t0),
                           *T.call('restore', LOCAL, 1), *A.DONE,
                           'returns', A.jr(A.ra), A.nop],
        'unknown-entry': [*T.call('save', LOCAL), *T.poke(LOCAL + 4, 0x80007000),
                          *T.call('restore', LOCAL, 1), *A.DONE],
    }
    for name, body in cases.items():
        binary = T.build(exe, cc, f'coroutines-{name}', prefix + body + bodies(A), [],
                         ['-DPLAID_BOOT_STATUS=0x30000000u', '-DPLAID_BOOT_ENTRYHI=0ull'],
                         fr0=True, address_taken=True, residual_dispatch=True)
        result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
        stop = next(json.loads(l) for l in result.stdout.splitlines() if l.startswith('{"stop"'))
        fault = {'unknown-entry': 3, 'wrong-link': 5, 'resumed-text': 2}.get(name, 13)
        assert result.returncode == 1 and stop['fault'] == fault, (name, result.stdout, result.stderr)
        if name == 'resumed-text':
            source = (T.OUT / 'coroutines-resumed-text.c').read_text()
            source, count = re.subn(r'if \(__builtin_setjmp\(jb\)\) \{ frame->ranges = R_[0-9a-f]+; frame->count = \d+u;',
                                    'if (__builtin_setjmp(jb)) {', source)
            assert count == 1
            (T.OUT / 'coroutines-repin-mutant.c').write_text(source)
            mutant = T.OUT / ('coroutines-repin-mutant.exe' if os.name == 'nt' else 'coroutines-repin-mutant')
            subprocess.run([cc, '-O2', '-std=gnu11', '-w', '-DPLAID_SAFEPOINTS',
                            '-DPLAID_BOOT_STATUS=0x30000000u', '-DPLAID_BOOT_ENTRYHI=0ull',
                            '-DPLAID_LOWERED="coroutines-repin-mutant.c"', '-I', str(T.OUT),
                            str(T.ROOT / 'runtime/plaid_rt.c'), '-pthread', '-o', str(mutant)], check=True)
            result = subprocess.run([str(mutant)], capture_output=True, text=True, timeout=30)
            # Missing re-pin incorrectly accepts a store into executing text.
            assert result.returncode == 0, (result.stdout, result.stderr)
    for name, status in [('cu1-off', 0x10000000), ('wrong-fr', 0x34000000)]:
        binary = T.build(exe, cc, f'coroutines-{name}', prefix + T.call('save', LOCAL) + list(A.DONE) + bodies(A), [],
                         [f'-DPLAID_BOOT_STATUS=0x{status:08x}u', '-DPLAID_BOOT_ENTRYHI=0ull'],
                         fr0=True, address_taken=True, residual_dispatch=True)
        result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
        stop = next(json.loads(l) for l in result.stdout.splitlines() if l.startswith('{"stop"'))
        assert result.returncode == 1 and stop['fault'] == 11, (name, result.stdout, result.stderr)
    # A stale owner's rt_thread slot also has a generation check. A live
    # continuation in another libultra thread must never be jumped to.
    runtime = ['osCreateThread', 'osStartThread']
    thread = 0x80005000
    body = [*T.call('save', LOCAL), *T.call('osCreateThread', thread, 1, 'cross', 0, 0x8000FF00, 10),
            *T.call('osStartThread', thread), *A.DONE,
            'cross', *T.call('restore', LOCAL, 1), *A.DONE, *bodies(A)]
    body += [item for name in runtime for item in [name, A.jr(A.ra), A.nop]]
    binary = T.build(exe, cc, 'coroutines-cross-thread', prefix + body, runtime,
                     ['-DPLAID_BOOT_STATUS=0x30000000u', '-DPLAID_BOOT_ENTRYHI=0ull'],
                     fr0=True, address_taken=True, residual_dispatch=True)
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
    stop = next(json.loads(l) for l in result.stdout.splitlines() if l.startswith('{"stop"'))
    assert result.returncode == 1 and stop['fault'] == 13, (result.stdout, result.stderr)
    strict = subprocess.run([str(exe), 'lower-c', str(T.OUT / 'coroutines.bin'), hex(A.BASE), hex(A.BASE),
                             hex(A.EXIT), str(T.OUT / 'coroutines-strict.c'), '--address-taken', '--fr0'],
                            capture_output=True, text=True, timeout=30)
    assert strict.returncode != 0 and 'nonlocal jumps require residual-dispatch' in strict.stderr, strict.stderr
    print('coroutines: unrecorded, edited register, expired frame, unknown entry, cross-thread and strict-mode refusals pass')


def scheduling(exe, cc, T, expected):
    t1, t2 = 0x80005000, 0x80005200
    A, marker = T.A, 0x80001160
    runtime = ['osCreateThread', 'osStartThread', 'osStopThread']
    guest = program(T)
    # A stopped higher-priority SDK thread keeps its native frames registered
    # while the other SDK thread changes coroutines twice.
    guest = ['coroutine_thread',
             *T.call('osCreateThread', t2, 2, 'other_thread', 0, 0x80017F00, 20),
             *T.call('osStartThread', t2), *guest]
    sleep = guest.index('sleep')
    guest[sleep + 3:sleep + 3] = T.call('osStartThread', t2)
    main = [*T.li(A.sp, 0x80027F00),
            *T.call('osCreateThread', t1, 1, 'coroutine_thread', 0, 0x80007F00, 10),
            *T.call('osStartThread', t1), *A.DONE, *guest,
            'other_thread', *T.poke(marker, 1), *T.call('osStopThread', 0),
            *T.poke(marker, 2), *T.call('osStopThread', 0), 0x0000000D]
    main += [item for name in runtime for item in [name, A.jr(A.ra), A.nop]]
    binary = T.build(exe, cc, 'coroutines-scheduling', main, runtime,
                     fr0=True, address_taken=True, residual_dispatch=True)
    result = subprocess.run([str(binary), '--dump', hex(LOG), '89'], capture_output=True, text=True, timeout=30)
    rows = [json.loads(l) for l in result.stdout.splitlines() if l.startswith('{')]
    stop = next(r for r in rows if 'stop' in r)
    words = next(r['words'] for r in rows if 'dump' in r)
    assert result.returncode == 0 and stop['fault'] == 0 and stop['stop'] == 'exit', (result.stdout, result.stderr)
    assert words[:12] == expected and words[(marker - LOG) // 4] == 2, words
    print('coroutines: SDK preemption/stop/resume runs only the active context and preserves other threads\' suspended frames')


def repeated_resumes(exe, cc, T, oracle):
    A, counter = T.A, 0x80001200
    regs = [A.sp, A.ra, *range(A.s0, A.s7 + 1), A.fp]
    seed = [w for r in regs[2:] for w in T.li(r, 0x12340000 + r)]
    seed += [w for r in range(20, 32) for w in [*T.li(A.t0, 0x3F800000 + r), A.mtc1(A.t0, r)]]
    clobber = [w for r in regs[2:] for w in T.li(r, 0xBAD00000 + r)]
    clobber += [w for r in range(20, 32) for w in [*T.li(A.t0, 0xDEAD0000 + r), A.mtc1(A.t0, r)]]
    # Three snapshots, including a repeated jump to the same still-live save;
    # the plain restore really returns zero when its argument is zero.
    p = [*T.li(A.sp, 0x80007F00), *seed, *T.call('save', LOCAL),
         *T.li(A.t0, counter), A.lw(A.t1, 0, A.t0), *T.li(A.t2, LOG),
         A.sll(A.t3, A.t1, 5), A.sll(A.t4, A.t1, 6), A.addu(A.t3, A.t3, A.t4), A.addu(A.t2, A.t2, A.t3),
         A.sw(A.v0, 0, A.t2)]
    p += [A.sw(r, 4 * (i + 1), A.t2) for i, r in enumerate(regs)]
    p += [w for r in range(20, 32) for w in [A.mfc1(A.t3, r), A.sw(A.t3, 4 * (r - 8), A.t2)]]
    p += [A.addiu(A.t1, A.t1, 1), A.sw(A.t1, 0, A.t0), A.addiu(A.t3, A.zero, 3),
          A.beq(A.t1, A.t3, 'done'), A.nop,
          A.addiu(A.a1, A.zero, 0), A.addiu(A.t3, A.zero, 1), A.beq(A.t1, A.t3, 'argument_ready'), A.nop,
          A.addiu(A.a1, A.zero, 7), 'argument_ready', *clobber, *T.li(A.sp, 0x80007000),
          *T.call('restore', LOCAL), 0x0000000D, 'done', *A.DONE, *bodies(A, nonzero=False)]
    for fr0 in (False, True):
        name = f'coroutines-repeat-fr{int(not fr0)}'
        binary = T.build(exe, cc, name, p, [],
                         [f'-DPLAID_BOOT_STATUS=0x{0x30000000 if fr0 else 0x34000000:08x}u',
                          '-DPLAID_BOOT_ENTRYHI=0ull'], fr0=fr0, address_taken=True, residual_dispatch=True)
        result = subprocess.run([str(binary), '--dump', hex(LOG), '72'], capture_output=True, text=True, timeout=30)
        rows = [json.loads(l) for l in result.stdout.splitlines() if l.startswith('{')]
        stop = next(r for r in rows if 'stop' in r)
        words = next(r['words'] for r in rows if 'dump' in r)
        expected = json.loads(subprocess.check_output([str(oracle), str(T.OUT / f'{name}.bin'), hex(A.EXIT),
                                                       *(['fr0'] if fr0 else [])], text=True, timeout=120))
        assert result.returncode == 0 and stop['fault'] == 0 and stop['stop'] == 'exit', (result.stdout, result.stderr)
        assert words == expected['ram'][0x400:0x448], (fr0, words, expected['ram'][0x400:0x448])
        assert [words[i] for i in (0, 24, 48)] == [0, 0, 7], words
    print('coroutines: repeated live-buffer restores, zero argument, every saved GPR/FPR and both FR layouts match ares')


def lifecycle_refusals(exe, cc, T):
    A = T.A
    t1, t2 = 0x80005000, 0x80005200
    cases = {
        'foreign-edit': ('scheduler_resumed', [*T.poke(WORKER, 0x8000EF00), *T.call('restore', WORKER, 1)], []),
        'repeat-created': ('worker', T.call('restore', WORKER, 1), []),
        'reuse-live': ('scheduler_resumed', T.call('osCreateThread', t1, 1, 'thread', 0, 0x80007F00, 10), ['osCreateThread']),
    }
    for name, (site, inject, rt) in cases.items():
        guest = program(T)
        i = guest.index(site)
        guest[i + 1:i + 1] = inject
        # A real libultra thread owns the two coroutine contexts.
        runtime = sorted(set(['osCreateThread', 'osStartThread', *rt]))
        p = [*T.li(A.sp, 0x80027F00), *T.call('osCreateThread', t1, 1, 'thread', 0, 0x80007F00, 10),
             *T.call('osStartThread', t1), *A.DONE, 'thread', *guest]
        p += [item for symbol in runtime for item in [symbol, A.jr(A.ra), A.nop]]
        binary = T.build(exe, cc, f'coroutines-{name}', p, runtime,
                         fr0=True, address_taken=True, residual_dispatch=True)
        result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
        stop = next(json.loads(l) for l in result.stdout.splitlines() if l.startswith('{"stop"'))
        assert result.returncode == 1 and stop['fault'] == 13, (name, result.stdout, result.stderr)
    # A normally returned owner can be reused, but its old saved template may
    # not create a coroutine in the next generation occupying that slot.
    old = 0x80004000
    runtime = ['osCreateThread', 'osStartThread']
    p = [*T.li(A.sp, 0x80027F00), *T.call('osCreateThread', t1, 1, 'old_thread', 0, 0x8000FF00, 20),
         *T.call('osStartThread', t1), *A.DONE,
         'old_thread', A.addiu(A.sp, A.sp, -16), A.sw(A.ra, 0, A.sp),
         *T.call('osCreateThread', t2, 2, 'coordinator', 0, 0x80017F00, 10),
         *T.call('osStartThread', t2), *T.call('save', old), *T.poke(old + 4, 0x80007000),
         A.lw(A.ra, 0, A.sp), A.jr(A.ra), A.addiu(A.sp, A.sp, 16),
         'coordinator', *T.call('osCreateThread', t1, 3, 'new_thread', 0, 0x8000FF00, 20),
         *T.call('osStartThread', t1), *A.DONE,
         'new_thread', *T.call('restore', old, 1), *A.DONE, *bodies(A)]
    p += [item for symbol in runtime for item in [symbol, A.jr(A.ra), A.nop]]
    binary = T.build(exe, cc, 'coroutines-generation', p, runtime, fr0=True, address_taken=True, residual_dispatch=True)
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
    stop = next(json.loads(l) for l in result.stdout.splitlines() if l.startswith('{"stop"'))
    assert result.returncode == 1 and stop['fault'] == 13, (result.stdout, result.stderr)
    print('coroutines: foreign/repeated creation edits, running thread reuse and stale slot generations refuse')


def authored_creation(exe, cc, T, oracle, expected):
    A = T.A
    p = program(T, authored=True)
    binary = T.build(exe, cc, 'coroutines-authored', p, [],
                     ['-DPLAID_BOOT_STATUS=0x30000000u', '-DPLAID_BOOT_ENTRYHI=0ull'],
                     fr0=True, address_taken=True, residual_dispatch=True)
    result = subprocess.run([str(binary), '--dump', '0x80000000', '16384'], capture_output=True, text=True, timeout=30)
    rows = [json.loads(l) for l in result.stdout.splitlines() if l.startswith('{')]
    stop = next(r for r in rows if 'stop' in r)
    ram = next(r['words'] for r in rows if 'dump' in r)
    oracle_state = json.loads(subprocess.check_output([str(oracle), str(T.OUT / 'coroutines-authored.bin'),
                                                      hex(A.EXIT), 'fr0'], text=True, timeout=120))
    assert result.returncode == 0 and stop['fault'] == 0 and ram[0x400:0x40C] == expected, (result.stdout[-3000:], result.stderr)
    assert ram == oracle_state['ram']
    print('coroutines: directly authored initial buffer enters only a lowered function; 64 KiB RAM matches ares')


def multiple_saves(exe, cc, T, oracle):
    A = T.A
    p = [*T.li(A.sp, 0x80007F00), *T.call('save', LOCAL), A.bne(A.v0, A.zero, 'done'), A.nop,
         *T.call('save', WORKER), *T.call('restore', LOCAL, 7), 0x0000000D,
         'done', *T.li(A.t0, LOG), A.sw(A.v0, 0, A.t0), *A.DONE, *bodies(A)]
    binary = T.build(exe, cc, 'coroutines-two-saves', p, [],
                     ['-DPLAID_BOOT_STATUS=0x30000000u', '-DPLAID_BOOT_ENTRYHI=0ull'],
                     fr0=True, address_taken=True, residual_dispatch=True)
    result = subprocess.run([str(binary), '--dump', '0x80000000', '16384'], capture_output=True, text=True, timeout=30)
    rows = [json.loads(l) for l in result.stdout.splitlines() if l.startswith('{')]
    ram = next(r['words'] for r in rows if 'dump' in r)
    expected = json.loads(subprocess.check_output([str(oracle), str(T.OUT / 'coroutines-two-saves.bin'),
                                                  hex(A.EXIT), 'fr0'], text=True, timeout=120))
    assert result.returncode == 0 and ram[0x400] == 7 and ram == expected['ram'], (result.stdout[-2000:], result.stderr)
    print('coroutines: two saved buffers in one caller resume the older continuation and match ares RAM')


def retargeted_creation(exe, cc, T, oracle, expected):
    A = T.A
    binary = T.build(exe, cc, 'coroutines-retargeted', program(T, retarget=True), [],
                     ['-DPLAID_BOOT_STATUS=0x30000000u', '-DPLAID_BOOT_ENTRYHI=0ull'],
                     fr0=True, address_taken=True, residual_dispatch=True)
    result = subprocess.run([str(binary), '--dump', '0x80000000', '16384'], capture_output=True, text=True, timeout=30)
    rows = [json.loads(l) for l in result.stdout.splitlines() if l.startswith('{')]
    ram = next(r['words'] for r in rows if 'dump' in r)
    oracle_state = json.loads(subprocess.check_output([str(oracle), str(T.OUT / 'coroutines-retargeted.bin'),
                                                      hex(A.EXIT), 'fr0'], text=True, timeout=120))
    assert result.returncode == 0 and ram[0x400:0x40C] == expected and ram == oracle_state['ram'], (result.stdout[-3000:], result.stderr)
    print('coroutines: retargeting a parked stack retires its last continuation and releases its text pins; RAM matches ares')


def authored_reuse(exe, cc, T, oracle, report):
    """One serialized template may author successive distinct entry/stack descriptors."""
    A, counter = T.A, 0x80001200
    seed = [w for reg in range(A.s0, A.s7 + 1) for w in T.li(reg, 0x12340000 + reg)]
    seed += [w for reg in range(20, 32) for w in [*T.li(A.t0, 0x3f800000 + reg), A.mtc1(A.t0, reg)]]
    p = [*T.li(A.sp, 0x80007f00), *T.li(A.t0, counter), A.lw(A.t1, 0, A.t0),
         A.bne(A.t1, A.zero, 'call_roots'), A.nop, *seed, *T.call('save', WORKER), *T.call('save', SCHED),
         *T.li(A.t0, counter), A.lw(A.t1, 0, A.t0), A.addiu(A.t2, A.zero, 3),
         A.beq(A.t1, A.t2, 'done'), A.nop, A.addiu(A.t1, A.t1, 1), A.sw(A.t1, 0, A.t0),
         A.addiu(A.t2, A.zero, 1), A.beq(A.t1, A.t2, 'author_one'), A.nop,
         A.addiu(A.t2, A.zero, 2), A.beq(A.t1, A.t2, 'author_two'), A.nop,
         'author_three', *T.li(A.t0, WORKER), *T.li(A.t1, 0x8000fd00), A.sw(A.t1, 0, A.t0),
         A.lui(A.t1, 0x8000), A.LO(A.t1, A.t1, 'worker_three'), A.sw(A.t1, 4, A.t0), A.j('enter'), A.nop,
         'author_two', *T.li(A.t0, WORKER), *T.li(A.t1, 0x8000fe00), A.sw(A.t1, 0, A.t0),
         A.lui(A.t1, 0x8000), A.LO(A.t1, A.t1, 'worker_two'), A.sw(A.t1, 4, A.t0), A.j('enter'), A.nop,
         'author_one', *T.li(A.t0, WORKER), *T.li(A.t1, 0x8000ff00), A.sw(A.t1, 0, A.t0),
         A.lui(A.t1, 0x8000), A.LO(A.t1, A.t1, 'worker_one'), A.sw(A.t1, 4, A.t0),
         'enter', *T.call('restore', WORKER, 7), 0x0000000d, 'done', *A.DONE,
         # Unknown mutable input retains these direct native function roots.
         'call_roots', A.jal('worker_one'), A.nop, A.jal('worker_two'), A.nop,
         A.jal('worker_three'), A.nop, 0x0000000d]
    for n, label in enumerate(['worker_one', 'worker_two', 'worker_three']):
        p += [label, *T.li(A.t0, LOG + 16 * n), A.sw(A.v0, 0, A.t0), A.sw(A.sp, 4, A.t0),
              A.sw(A.s0, 8, A.t0), A.swc1(21, 12, A.t0), *T.li(A.s0, 0xdeadbeef),
              *T.li(A.t0, 0x76543210), A.mtc1(A.t0, 21), *T.call('restore', SCHED, 1), 0x0000000d]
    p += bodies(A)
    name = 'coroutines-authored-reuse'
    T.build(exe, cc, name, p, [], ['-DPLAID_BOOT_STATUS=0x30000000u', '-DPLAID_BOOT_ENTRYHI=0ull'],
            fr0=True, address_taken=True, residual_dispatch=True)
    expected = json.loads(subprocess.check_output([str(oracle), str(T.OUT / f'{name}.bin'),
        hex(A.EXIT), 'fr0'], text=True, timeout=120))
    runtime = (T.ROOT / 'runtime/plaid_rt.c').read_text()
    source = T.OUT / 'coroutines-authored-reuse-probe.c'
    binary = T.OUT / ('coroutines-authored-reuse-check.exe' if os.name == 'nt' else 'coroutines-authored-reuse-check')
    for mutant in (False, True):
        text = runtime.replace('#include "status.h"', '#include "status.h"\nstatic unsigned context_count;')
        text = text.replace('  fflush(stdout);',
            '  printf("{\\"host_contexts\\":%u}\\n", context_count);\n' + report + '\n  fflush(stdout);')
        if mutant:
            header = (T.ROOT / 'runtime/jumps.h').read_text()
            needle = '    rt_context *old = j->owner;'
            assert header.count(needle) == 1
            (T.OUT / 'jumps-reuse-mutant.h').write_text(header.replace(needle, needle + '\n    if (!old) goto refused;'))
            text = text.replace('#include "jumps.h"', '#include "jumps-reuse-mutant.h"')
        source.write_text(text)
        subprocess.run([cc, '-O2', '-std=gnu11', '-w', '-DPLAID_SAFEPOINTS', '-DPLAID_BOOT_STATUS=0x30000000u',
            '-DPLAID_BOOT_ENTRYHI=0ull', f'-DPLAID_LOWERED="{name}.c"', '-I', str(T.OUT),
            '-I', str(T.ROOT / 'runtime'), str(source), '-pthread', '-o', str(binary)], check=True)
        actual = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
        rows = [json.loads(line) for line in actual.stdout.splitlines() if line.startswith('{')]
        stop = next(row for row in rows if 'stop' in row)
        if mutant:
            assert actual.returncode == 1 and stop['fault'] == 13, (actual.stdout[-2000:], actual.stderr)
        else:
            assert actual.returncode == 0 and stop['fault'] == 0, (actual.stdout[-2000:], actual.stderr)
            assert next(row['state'] for row in rows if 'state' in row) == expected
            assert next(row['host_contexts'] for row in rows if 'host_contexts' in row) == 1
    print('coroutines: three successive authored entry/stack descriptors in one buffer match full ares state; '
          'retired contexts released; one-use mutation killed')


if __name__ == '__main__':
    import shutil
    import test_runtime as T
    run(T.ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid'),
        os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang'), T)
