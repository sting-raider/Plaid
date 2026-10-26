"""Lowered CACHE and TagLo against pinned ares (ADR-0259)."""
import json
import hashlib
import os
import subprocess


OLD, NEW = 0x11223344, 0xAABBCCDD
LOG = 0x80001000


def _cache(op, base):
    return 47 << 26 | base << 21 | op << 16


def _dirty(T, address):
    """RAM holds OLD; the cached line holds NEW and is dirty."""
    A = T.A
    return [*T.poke(address | 0x20000000, OLD), *T.li(A.t0, address), A.lw(A.t1, 0, A.t0),
            *T.poke(address, NEW), *T.li(A.t0, address)]


def _log_uncached(T, address):
    A = T.A
    return [*T.li(A.t0, address | 0x20000000), A.lw(A.t1, 0, A.t0), A.sw(A.t1, 0, A.gp), A.addiu(A.gp, A.gp, 4)]


def _program(T, body):
    A = T.A
    mtc0 = lambda rt, rd: 0x40800000 | rt << 16 | rd << 11
    return [*T.li(A.sp, 0x80007F00), *T.li(A.gp, LOG), mtc0(A.zero, 28), mtc0(A.zero, 29), *body(T), *A.DONE]


def _written_back(T):
    A = T.A
    out = []
    # Hit Writeback, Index Writeback Invalidate and Hit Writeback Invalidate
    # each put the dirty line's NEW in RAM; I-cache operations change nothing.
    for i, op in enumerate((0x19, 0x01, 0x15)):
        address = 0x80004000 + i * 0x40
        out += [*_dirty(T, address), _cache(op, A.t0), *_log_uncached(T, address)]
    address = 0x80004100
    out += [*_dirty(T, address), _cache(0x00, A.t0), _cache(0x08, A.t0), _cache(0x10, A.t0),
            _cache(0x19, A.t0), *_log_uncached(T, address)]
    # Index Store Tag with TagLo 0 drops a clean line; RAM is unchanged.
    address = 0x80004140
    out += [*T.poke(address | 0x20000000, OLD), *T.li(A.t0, address), A.lw(A.t1, 0, A.t0),
            _cache(0x09, A.t0), *_log_uncached(T, address)]
    # a Hit operation on a line that is not resident does nothing
    address = 0x80004180
    out += [*T.poke(address | 0x20000000, OLD), *T.li(A.t0, address), _cache(0x15, A.t0),
            *_log_uncached(T, address)]
    return out


def _dropped(op):
    def body(T):
        # Hit Invalidate or Index Store Tag discards dirty NEW on hardware;
        # natively the line is lost, so the next access fails closed.
        address = 0x80004000
        return [*_dirty(T, address), _cache(op, T.A.t0), *_log_uncached(T, address)]
    return body


def _cde_full(T):
    A, address = T.A, 0x80004000
    out = [w for i in range(4) for w in T.poke((address + i * 4) | 0x20000000, OLD)]
    out += [*T.li(A.t0, address), _cache(0x0d, A.t0)]
    for i in range(4):
        out += T.poke(address + i * 4, NEW + i)
    out += [*T.li(A.t0, address), _cache(0x19, A.t0)]
    for i in range(4):
        out += _log_uncached(T, address + i * 4)
    return out


def _cde_retained(stale=False, same=False):
    def body(T):
        A, victim, address = T.A, 0x80004000, 0x80006000
        out = _dirty(T, victim)
        if stale:
            out += [_cache(0x19, A.t0), *T.poke(victim | 0x20000000, OLD)]
        if same:
            address = victim
        out += [*T.li(A.t0, address), _cache(0x0d, A.t0), A.lw(A.t1, 0, A.t0),
                A.sw(A.t1, 0, A.gp), A.addiu(A.gp, A.gp, 4)]
        # Dirty victim is in RAM before the new line is written. On a hit,
        # writeback makes the same line safe to inspect uncached.
        if same:
            out += [_cache(0x19, A.t0)]
        out += _log_uncached(T, victim)
        for i in range(4):
            out += T.poke(address + i * 4, NEW + i)
        out += [*T.li(A.t0, address), _cache(0x15, A.t0)]
        for i in range(4):
            out += _log_uncached(T, address + i * 4)
        return out
    return body


def _cde_unknown(partial=False, writeback=False):
    def body(T):
        A, address = T.A, 0x80004000
        out = [*T.poke(address | 0x20000000, OLD), *T.li(A.t0, address), _cache(0x0d, A.t0)]
        if partial:
            out += [*T.poke(address, NEW), A.lw(A.t1, 0, A.t0),
                    A.sw(A.t1, 0, A.gp), A.addiu(A.gp, A.gp, 4)]
        if writeback:
            out += [_cache(0x15, A.t0), *_log_uncached(T, address + 4)]
        else:
            out += [A.lw(A.t1, 4 if partial else 0, A.t0), A.sw(A.t1, 0, A.gp)]
        return out
    return body


def _cde_lost(op, partial=False, writeback=False, allocate=True):
    def body(T):
        A, address = T.A, 0x80004000
        out = [*_dirty(T, address), _cache(op, A.t0)]
        if allocate:
            out += [_cache(0x0d, A.t0)]
        for i in range(1 if partial else 4):
            out += T.poke(address + 4 * i, NEW + i)
        if partial:
            out += [A.lw(A.t1, 0, A.t0), A.sw(A.t1, 0, A.gp), A.addiu(A.gp, A.gp, 4)]
        if writeback or not partial:
            out += [*T.li(A.t0, address), _cache(0x15, A.t0)]
            if partial:
                out += _log_uncached(T, address + 4)
            else:
                for i in range(4):
                    out += _log_uncached(T, address + 4 * i)
        else:
            out += [A.lw(A.t1, 4, A.t0)]
        return out
    return body


def _cde_recycle(T):
    A, address = T.A, 0x80004000
    # Like a reused object: only some fields were initialized before eviction.
    out = [*T.li(A.t0, address), _cache(0x0d, A.t0), *T.poke(address, OLD),
           _cache(0x19, A.t0), _cache(0x0d, A.t0)]
    for i in range(4):
        out += T.poke(address + 4 * i, NEW + i)
    out += [*T.li(A.t0, address), _cache(0x15, A.t0)]
    for i in range(4):
        out += _log_uncached(T, address + 4 * i)
    return out


def _cde_known_refill(T, unknown=False):
    A, address = T.A, 0x80004000
    out = [*T.li(A.t0, address), _cache(0x0d, A.t0), *T.poke(address, NEW),
           _cache(0x15, A.t0), A.lw(A.t1, 0, A.t0),
           A.sw(A.t1, 0, A.gp), A.addiu(A.gp, A.gp, 4),
           *T.poke(address + 4, NEW + 1), _cache(0x15, A.t0)]
    for i in range(2):
        out += _log_uncached(T, address + 4 * i)
    if unknown:
        out += [*T.li(A.t0, address), A.lw(A.t1, 8, A.t0)]
    return out


def _model_contract(cc, T):
    # The manual requires dirty after CDE; pinned ares instead clears its
    # dirty mask on a miss. Check this distinction without calling it agreement.
    source = T.OUT / 'cache-cde-model.c'
    source.write_text(r'''#include <assert.h>
#include "cache-cde-full.c"
static plaid_state s;
int main(void) {
  u64 value;
  s.status_known = 1; s.cp0_status = 0x34000000u;
  assert(!plaid_cache(&s, 13, SX32(0x80004000u), 0x100));
  assert(s.ddirty[0] && s.dunknown[0] == 0xffffu);
  /* Byte writes recover exactly those bytes; a partial halfword still faults. */
  assert(!plaid_store(&s, SX32(0x80004000u), 1, 0x12, 0x104));
  assert(!plaid_load(&s, SX32(0x80004000u), 1, 0x108, &value) && value == 0x12);
  assert(plaid_load(&s, SX32(0x80004000u), 2, 0x10c, &value) && s.fault == 4 && s.fault_pc == 0x10c);
  s.fault = 0;
  for (u32 b = 1; b < 16; b++) assert(!plaid_store(&s, SX32(0x80004000u + b), 1, b, 0x110));
  assert(!s.dunknown[0]);
  assert(!plaid_cache(&s, 13, SX32(0x80006000u), 0x114));
  assert(s.ddirty[0] && !s.dunknown[0]);
  assert(!plaid_load(&s, SX32(0x80006000u), 1, 0x118, &value) && value == 0x12);
  assert(!plaid_cache(&s, 25, SX32(0x80006000u), 0x11c));
  assert(s.ram[0x6000] == 0x12 && s.ram[0x600f] == 15);
  /* Lost destination RAM is never a fill source. Invalid slots are unknown. */
  assert(!plaid_store(&s, SX32(0x80006000u), 1, 0x12, 0x13c));
  plaid_ddrop(&s, 0);
  assert(s.line_lost[0x600]);
  assert(!plaid_cache(&s, 13, SX32(0x80006000u), 0x140));
  assert(!s.line_lost[0x600] && s.ddirty[0] && s.dunknown[0] == 0xffffu);
  assert(plaid_load(&s, SX32(0xa0006000u), 1, 0x144, &value) && s.fault == 4);
  assert(!plaid_store(&s, SX32(0x80006000u), 1, 0x34, 0x148));
  assert(!plaid_cache(&s, 25, SX32(0x80006000u), 0x14c));
  assert(s.line_lost[0x600] == 0xfffeu && s.dunknown[0] == 0xfffeu);
  /* A same-tag CDE after partial writeback must not recover unknown bytes. */
  assert(!plaid_cache(&s, 13, SX32(0x80006000u), 0x150));
  assert(s.dunknown[0] == 0xfffeu);
  assert(!plaid_load(&s, SX32(0x80006000u), 1, 0x154, &value) && value == 0x34);
  assert(plaid_load(&s, SX32(0x80006001u), 1, 0x158, &value) && s.fault == 4);
  for (u32 b = 1; b < 16; b++) assert(!plaid_store(&s, SX32(0x80006000u + b), 1, b, 0x15c));
  assert(!plaid_cache(&s, 21, SX32(0x80006000u), 0x160));
  assert(!s.line_lost[0x600]);
  assert(!plaid_load(&s, SX32(0xa000600fu), 1, 0x164, &value) && value == 15);
  /* A known dirty victim is retained, not filled from the lost destination. */
  assert(!plaid_store(&s, SX32(0x80006000u), 1, 0x56, 0x168));
  s.line_lost[0x400] = 1;
  assert(!plaid_cache(&s, 13, SX32(0x80004000u), 0x16c));
  assert(!s.line_lost[0x400] && !s.dunknown[0] && s.ddirty[0]);
  assert(!plaid_load(&s, SX32(0x80004000u), 1, 0x170, &value) && value == 0x56);
  assert(!plaid_cache(&s, 21, SX32(0x80004000u), 0x174));
  assert(!plaid_load(&s, SX32(0xa0004000u), 1, 0x178, &value) && value == 0x56);
  /* A mapped CDE uses the virtual index and translated physical tag. */
  s.tlb[0] = (plaid_tlb_entry){0, 0x00100000u, {0x11fu, 0x15fu}};
  assert(!plaid_cache(&s, 13, 0x00100000ull, 0x120));
  assert(s.dtag[0] == 0x4001u);
  /* Opposite-index physical alias, unmapped, noncanonical and non-RAM refuse. */
  s.tlb[0].lo[1] = 0x11fu;
  assert(plaid_cache(&s, 13, 0x00101000ull, 0x124) && s.fault == 4);
  assert(plaid_cache(&s, 13, 0x00200000ull, 0x128) && s.fault == 1);
  assert(plaid_cache(&s, 13, 0x80004000ull, 0x12c) && s.fault == 1);
  assert(plaid_cache(&s, 13, SX32(0x80800000u), 0x130) && s.fault == 1);
  s.cp0_status = 0x34000010u;
  assert(plaid_cache(&s, 13, SX32(0x80004000u), 0x134) && s.fault == 12);
  /* An eviction preserves known object fields without inventing its padding. */
  memset(&s, 0, sizeof s); s.status_known = 1; s.cp0_status = 0x34000000u;
  assert(!plaid_cache(&s, 13, SX32(0x80004000u), 0x180));
  for (u32 b = 0; b < 16; b++) if ((0xf0ffu >> b) & 1)
    assert(!plaid_store(&s, SX32(0x80004000u + b), 1, b, 0x184));
  assert(!plaid_cache(&s, 21, SX32(0x80004000u), 0x188));
  assert(s.line_lost[0x400] == 0x0f00u);
  assert(!plaid_load(&s, SX32(0xa000400cu), 4, 0x18c, &value) && value == 0x0c0d0e0fu);
  assert(!plaid_load(&s, SX32(0x80004000u), 4, 0x190, &value) && value == 0x00010203u);
  assert(!s.ddirty[0] && s.dunknown[0] == 0x0f00u && s.line_lost[0x400] == 0x0f00u);
  assert(plaid_load(&s, SX32(0x80004008u), 4, 0x194, &value) && s.fault == 4);
  assert(!plaid_store(&s, SX32(0x80004008u), 4, 0x11223344u, 0x198));
  assert(!s.dunknown[0] && !s.line_lost[0x400] && s.ddirty[0]);
  assert(!plaid_cache(&s, 21, SX32(0x80004000u), 0x19c));
  assert(!plaid_load(&s, SX32(0xa0004008u), 4, 0x1a0, &value) && value == 0x11223344u);
  s.line_lost[0x400] = 0xffffu; s.prot_ready = 1; s.prot[0x4000 >> 2] = 253;
  assert(plaid_cache(&s, 13, SX32(0x80004000u), 0x1a4) && s.fault == 2);
  assert(s.line_lost[0x400] == 0xffffu && !s.dtag[0]);
  return 0;
}
''')
    binary = T.OUT / ('cache-cde-model.exe' if os.name == 'nt' else 'cache-cde-model')
    subprocess.run([cc, '-O2', '-std=gnu11', '-Wall', '-Werror', '-Wno-unused-label',
                    '-Wno-unused-function', str(source), '-lm', '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True, timeout=30)


def _unknown_guard_mutation(cc, T):
    original = (T.OUT / 'cache-cde-full.c').read_text()
    guard = 'if (s->dunknown[i] & m) return plaid_fault(s, pc, 4);'
    assert original.count(guard) == 1
    (T.OUT / 'cache-cde-mutant.c').write_text(original.replace(guard, '/* mutated unknown-read guard */'))
    source = T.OUT / 'cache-cde-mutation.c'
    source.write_text('''#include "cache-cde-mutant.c"
static plaid_state s;
int main(void) {
  u64 value;
  s.status_known = 1; s.cp0_status = 0x34000000u;
  s.line_lost[0x400] = 1;
  if (plaid_cache(&s, 13, SX32(0x80004000u), 0x100)) return 2;
  return plaid_load(&s, SX32(0x80004000u), 1, 0x104, &value) && s.fault == 4 ? 0 : 1;
}
''')
    binary = T.OUT / ('cache-cde-mutation.exe' if os.name == 'nt' else 'cache-cde-mutation')
    subprocess.run([cc, '-O2', '-std=gnu11', '-w', str(source), '-lm', '-o', str(binary)], check=True)
    assert subprocess.run([str(binary)], timeout=30).returncode == 1, 'unknown-read guard mutation survived'


def _dma_contract(exe, cc, T):
    for writeback in (False, True):
        def body(T):
            A, address, handle = T.A, 0x80004000, 0x80005000
            out = [*_dirty(T, address), _cache(0x11, A.t0), _cache(0x0d, A.t0),
                   *T.poke(address, NEW)]
            if writeback:
                out += [*T.li(A.t0, address), _cache(0x15, A.t0)]
            return [*out, *T.poke(handle + 12, 0x08000000),
                    *T.call('osEPiRawStartDma', handle, 1, 0, address, 16)]
        label = f'cache-cde-dma-{writeback}'
        program = [*_program(T, body), 'osEPiRawStartDma', T.A.jr(T.A.ra), T.A.nop]
        binary = T.build(exe, cc, label, program, ['osEPiRawStartDma'],
                         ['-DPLAID_BOOT_STATUS=0x34000000u', '-DPLAID_BOOT_ENTRYHI=0ull'])
        result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
        stop = next(json.loads(line) for line in result.stdout.splitlines() if line.startswith('{"stop"'))
        assert result.returncode == 1 and stop['stop'] == "DMA reads RAM that differs from hardware's", (
            label, result.stdout, result.stderr)


def _run(exe, cc, T, label, body, expect_lost=False, values=None, reference_values=None):
    A, out = T.A, T.OUT
    # kernel mode with COP0 usable, as the ares oracle starts
    binary = T.build(exe, cc, label, _program(T, body), [],
                     ['-DPLAID_BOOT_STATUS=0x34000000u', '-DPLAID_BOOT_ENTRYHI=0ull'])
    run = subprocess.run([str(binary), '--dump', hex(LOG), '8'], capture_output=True, text=True, timeout=30)
    oracle = T.ROOT / 'target/native-slice/oracle/oracle'
    built = json.loads((oracle.parent / 'build.json').read_text())
    assert built['revision'] == T.A.builder().REV
    assert built['driver'] == hashlib.sha256((T.ROOT / 'spikes/096-native-slice/driver.cpp').read_bytes()).hexdigest()
    args = [str(oracle), str(out / f'{label}.bin'), hex(A.EXIT)]
    if os.name == 'nt':
        def linux(path):
            return subprocess.check_output(['wsl', '-d', 'Ubuntu', '--exec', 'wslpath', '-a', str(path)],
                                           text=True).strip()
        args = ['wsl', '-d', 'Ubuntu', '--exec', linux(oracle), linux(out / f'{label}.bin'), hex(A.EXIT)]
    reference = subprocess.run(args, capture_output=True, text=True, timeout=120)
    rows = [json.loads(line) for line in run.stdout.splitlines() if line.startswith('{')]
    stop = next(row for row in rows if 'stop' in row)
    words = next(row['words'] for row in rows if 'dump' in row)
    assert reference.returncode == 0, (reference.stdout, reference.stderr)
    expected = json.loads(reference.stdout)
    assert expected["pc"] == A.EXIT and expected.get('exception', 0) == 0, (label, expected)
    if expect_lost:
        # Refusal is intentionally stricter where no cache-byte witness exists.
        assert expected['ram'][:len(reference_values or [OLD])] == (reference_values or [OLD]), (label, expected['ram'])
        assert run.returncode == 1 and stop['fault'] == 4, (label, run.stdout, run.stderr)
        assert words[:len(values or [0])] == (values or [0]), (label, words)
        return
    assert run.returncode == 0 and stop['stop'] == 'exit' and stop['fault'] == 0, (label, run.stdout, run.stderr)
    values = values or [NEW, NEW, NEW, NEW, OLD, OLD]
    assert words[:len(values)] == values, (label, [hex(w) for w in words])
    assert expected['ram'][:8] == words, (label, expected['ram'], words)
    # Also verify complete CPU state and the oracle's complete log window,
    # independently of the SDK runtime's stop/dump reporting.
    harness = (T.ROOT / 'spikes/096-native-slice/harness.c').read_text().replace(
        'plaid_load_images(&s);',
        'plaid_load_images(&s); s.status_known = 1; s.cp0_status = 0x34000000u; '
        's.cp0_known = 1u << 10; s.cp0_entryhi = 0;')
    source = out / f'{label}-state.c'
    source.write_text(harness)
    state_exe = out / f'{label}-state{binary.suffix}'
    subprocess.run([cc, '-O2', '-std=gnu11', '-Wall', '-Werror', '-Wno-unused-label',
                    '-DPLAID_SAFEPOINTS', f'-DPLAID_LOWERED="{label}.c"', f'-DPLAID_EXIT={hex(A.EXIT)}u',
                    '-I', str(out), '-I', str(T.ROOT / 'spikes/096-native-slice'),
                    str(source), '-lm', '-o', str(state_exe)], check=True)
    actual = json.loads(subprocess.check_output([str(state_exe)], text=True, timeout=30))
    assert actual == expected, (label, {k: (actual[k], expected[k]) for k in actual if actual[k] != expected[k]})


def run(exe, cc, T):
    _run(exe, cc, T, 'cache-ops', _written_back, False)
    _run(exe, cc, T, 'cache-ops-hit-invalidate', _dropped(0x11), True)
    _run(exe, cc, T, 'cache-ops-store-tag', _dropped(0x09), True)
    _run(exe, cc, T, 'cache-cde-full', _cde_full, values=[NEW + i for i in range(4)])
    _run(exe, cc, T, 'cache-cde-recycle', _cde_recycle, values=[NEW + i for i in range(4)])
    _run(exe, cc, T, 'cache-cde-known-refill', _cde_known_refill, values=[NEW, NEW, NEW + 1])
    _run(exe, cc, T, 'cache-cde-unknown-refill', lambda T: _cde_known_refill(T, unknown=True), True,
         values=[NEW, NEW, NEW + 1, 0], reference_values=[NEW, NEW, NEW + 1, 0])
    for op in (0x11, 0x09):
        _run(exe, cc, T, f'cache-cde-lost-{op}', _cde_lost(op),
             values=[NEW + i for i in range(4)])
        for writeback in (False, True):
            _run(exe, cc, T, f'cache-cde-lost-{op}-partial-{writeback}',
                 _cde_lost(op, partial=True, writeback=writeback), True,
                 values=[NEW, 0], reference_values=[NEW, 0])
    _run(exe, cc, T, 'cache-store-lost', _cde_lost(0x11, allocate=False),
         values=[NEW + i for i in range(4)])
    _run(exe, cc, T, 'cache-store-lost-partial',
         _cde_lost(0x11, partial=True, allocate=False), True,
         values=[NEW, 0], reference_values=[NEW, 0])
    for label, body, victim in [('victim', _cde_retained(), NEW),
                                ('stale', _cde_retained(stale=True), OLD),
                                ('hit', _cde_retained(same=True), NEW)]:
        _run(exe, cc, T, f'cache-cde-{label}', body, values=[NEW, victim, *[NEW + i for i in range(4)]])
    _run(exe, cc, T, 'cache-cde-unknown', _cde_unknown(), True, reference_values=[0])
    _run(exe, cc, T, 'cache-cde-partial', _cde_unknown(partial=True), True,
         values=[NEW, 0], reference_values=[NEW, 0])
    _run(exe, cc, T, 'cache-cde-partial-wb', _cde_unknown(partial=True, writeback=True), True,
         values=[NEW, 0], reference_values=[NEW, 0])
    _model_contract(cc, T)
    _unknown_guard_mutation(cc, T)
    _dma_contract(exe, cc, T)
    print('CACHE ops: ares CPU/RAM agrees for writeback, CDE full writes, lost-line reuse, dirty victims, retained/stale bytes and hits; unknown reads/writeback fail closed; guard mutation killed')


if __name__ == '__main__':
    import shutil
    import test_runtime as T
    T.OUT.mkdir(parents=True, exist_ok=True)
    run(T.ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid'),
        os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang'), T)
