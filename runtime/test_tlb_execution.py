"""Synthetic native execution of TLB-bound code, checked against pinned ares."""
from pathlib import Path
import importlib.util
import json
import os
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SLICE = ROOT / 'spikes/096-native-slice'
OUT = ROOT / 'target/tlb-execution-contract'
BASE, EXIT = 0x80000000, 0x80000F00
E0, E1 = 0xE0000000, 0xE0200000
P0, P1, P_ALIAS = 0x00200000, 0x00202000, 0x00204000
PC = 0x80000000


def _module_words(A):
    # E0000000: save caller RA, JAL E0200000, set v0 in the delay slot,
    # then add one and return. E0200000 captures virtual RA and adds three.
    return ([A.addiu(A.sp, A.sp, -16), A.sw(A.ra, 12, A.sp),
             3 << 26 | (E1 >> 2 & 0x03FFFFFF), A.addiu(A.v0, A.zero, 7),
             A.addiu(A.v0, A.v0, 1), A.lw(A.ra, 12, A.sp),
             A.jr(A.ra), A.addiu(A.sp, A.sp, 16)],
            [A.addu(A.v1, A.ra, A.zero), A.lui(A.at, 0xE020), A.lw(A.at, 0x20, A.at),
             A.jr(A.at), A.addiu(A.v0, A.v0, 3), 0, 0, 0,
             lambda pc, labels: labels['leaf']])


def _entry(A, index, virtual, physical):
    def li(reg, value):
        return [A.lui(reg, value >> 16), A.ori(reg, reg, value & 0xFFFF)]

    def lo(pa):
        return pa >> 6 | 3 << 3 | 1 << 2 | 1 << 1 | 1

    return [*li(A.a0, index), *li(A.a1, 0), *li(A.a2, virtual),
            *li(A.a3, lo(physical)), *li(A.t0, lo(physical + 0x1000)),
            A.sw(A.t0, 16, A.sp), A.jal('map'), A.nop]


def _copy(A, label, source_label, destination, words):
    def li(reg, value):
        return [A.lui(reg, value >> 16), A.ori(reg, reg, value & 0xFFFF)]

    return [A.lui(A.s0, 0xA000), A.LO(A.s0, A.s0, source_label),
            *li(A.s1, 0xA0000000 | destination),
            A.addiu(A.t0, A.zero, words), label,
            A.lw(A.t1, 0, A.s0), A.sw(A.t1, 0, A.s1),
            A.addiu(A.s0, A.s0, 4), A.addiu(A.s1, A.s1, 4),
            A.addiu(A.t0, A.t0, -1), A.bgtz(A.t0, label), A.nop]


def _fixture(A):
    one, two = _module_words(A)
    mtc0 = lambda rt, rd: 0x40800000 | rt << 16 | rd << 11
    items = [A.lui(A.sp, 0x8000), A.ori(A.sp, A.sp, 0x7F00),
             *_copy(A, 'copy0', 'module0', P0, len(one)),
             *_copy(A, 'copy1', 'module1', P1, len(two)),
             *_entry(A, 0, E0, P0), *_entry(A, 1, E1, P1),
             A.lui(A.t9, 0xE000), A.jalr(A.ra, A.t9), A.nop,
             A.lui(A.gp, 0x8000), A.sw(A.v0, 0x1000, A.gp),
             A.sw(A.v1, 0x1004, A.gp), *A.DONE,
             'map', mtc0(A.a0, 0), mtc0(A.a1, 5), mtc0(A.a2, 10),
             mtc0(A.a3, 2), A.lw(A.t0, 16, A.sp), mtc0(A.t0, 3),
             0x42000002, A.nop, A.jr(A.ra), A.nop,
             'leaf', A.jr(A.ra), A.nop, 'module0', *one, 'module1', *two]
    raw = A.assemble(items)
    labels = A.label_pcs(items)
    start = labels['module1'] - BASE
    two = [int.from_bytes(raw[at:at+4], 'big') for at in range(start, start + len(two)*4, 4)]
    return raw, labels, one, two


def _native_harness(module0, module1, labels, preentry_tamper=False):
    def bytes_c(ws):
        return ','.join(f'0x{byte:02x}' for w in ws for byte in w.to_bytes(4, 'big'))
    def entry_lo(pa):
        return f'(({pa}u >> 6) | (3u << 3) | (1u << 2) | (1u << 1) | 1u)'
    tamper = f's->ram[0x{P1 + 0x20:08x}u] ^= 1u;' if preentry_tamper else ''
    rejected = f'''  assert(run_result != 0 && s.fault == 3);
  assert(find_tlb(&s, 1) < 0);
  assert(plaid_runtime_write(&s, 0x{P1 + 0x18:08x}u, 4, 0x{PC:08x}u) == 0);
  return 0;''' if preentry_tamper else ''

    return f'''#include <assert.h>
#include <stdio.h>
#include "native.c"
static const u8 raw0[] = {{{bytes_c(module0)}}};
static u32 byte_at(plaid_state *s, u32 p) {{
  u32 i = (p >> 4) & 0x1ffu;
  if (s->dtag[i] == ((p & ~0xfffu) | 1u) && (s->dstale[i] & (1u << (p & 15)))) return s->dold[i][p & 15];
  return s->ram[p];
}}
static int find_tlb(plaid_state *s, u32 n) {{
  u32 k;
  for (k = 0; k < PLAID_OVLS; k++) if (s->ovl_tlb[k] == n + 1) return (int)k;
  return -1;
}}
static void binding(plaid_state *s, int k, u32 index, u32 virt, u32 phys) {{
  assert(k >= 0 && s->ovl_ok[k]);
  assert(s->ovl_tlb[k] == index + 1);
  assert(s->ovl_delta[k] == virt - plaid_ovls[k].link);
  assert(s->ovl_backing[k] == phys - plaid_ovls[k].link);
}}
int plaid_rt_map(plaid_state *s) {{
  u64 lo1;
  if (plaid_load(s, s->r[29] + 16, 4, 0x{labels['map']:08x}u, &lo1)) return 1;
  s->r[8] = SX32((u32)lo1);
  plaid_tlb_entry e = {{(u32)s->r[5], (u32)s->r[6], {{(u32)s->r[7], (u32)lo1}}}};
  int result = plaid_tlb_write(s, (u32)s->r[4], e, 0x{labels['map']:08x}u);
  if (!result && (u32)s->r[4] == 1u) {{ {tamper} }}
  return result;
}}
int main(void) {{
  static plaid_state s;
  plaid_tlb_entry e, bad;
  plaid_tlb_entry before_tlb[32];
  u64 before_tlb_generation[32];
  u64 generation;
  u32 old_delta, old_backing, old_tlb;
  int k0, k1;
  plaid_load_images(&s); s.r[31] = SX32(0x{EXIT:08x}u);
  int run_result = plaid_run(&s);
{rejected}
  if (run_result || s.fault) {{ fprintf(stderr, "plaid_run=%d fault=%u pc=%08x fault_pc=%08x\\n", run_result, s.fault, s.pc, s.fault_pc); return 20; }}
  assert(s.pc == 0x{EXIT:08x}u && (u32)s.r[2] == 11);
  assert((u32)s.r[3] == 0xE0000010u);
  k0 = find_tlb(&s, 0); k1 = find_tlb(&s, 1);
  assert(k0 >= 0 && k1 >= 0 && s.ovl_active[k0] == 0 && s.ovl_active[k1] == 0);
  binding(&s, k0, 0, 0x{E0:08x}u, 0x{P0:08x}u);
  binding(&s, k1, 1, 0x{E1:08x}u, 0x{P1:08x}u);
  /* An earlier index cannot shadow another active binding or revoke this inactive one. */
  memcpy(before_tlb, s.tlb, sizeof before_tlb);
  memcpy(before_tlb_generation, s.tlb_generation, sizeof before_tlb_generation);
  u32 before_delta0 = s.ovl_delta[k0], before_backing0 = s.ovl_backing[k0], before_tlb0 = s.ovl_tlb[k0];
  u32 before_delta1 = s.ovl_delta[k1], before_backing1 = s.ovl_backing[k1], before_tlb1 = s.ovl_tlb[k1];
  u64 before_ovl_generation0 = s.ovl_generation[k0], before_ovl_generation1 = s.ovl_generation[k1];
  e = s.tlb[0]; e.hi = 0x{E1:08x}u; s.ovl_active[k1] = 1;
  assert(plaid_tlb_write(&s, 0, e, 0x{PC:08x}u) == 1 && s.fault == 2);
  assert(!memcmp(before_tlb, s.tlb, sizeof before_tlb));
  assert(!memcmp(before_tlb_generation, s.tlb_generation, sizeof before_tlb_generation));
  assert(s.ovl_ok[k0] && s.ovl_ok[k1] && !s.ovl_active[k0] && s.ovl_active[k1]);
  assert(s.ovl_delta[k0] == before_delta0 && s.ovl_backing[k0] == before_backing0 && s.ovl_tlb[k0] == before_tlb0 && s.ovl_generation[k0] == before_ovl_generation0);
  assert(s.ovl_delta[k1] == before_delta1 && s.ovl_backing[k1] == before_backing1 && s.ovl_tlb[k1] == before_tlb1 && s.ovl_generation[k1] == before_ovl_generation1);
  s.ovl_active[k1] = 0; s.fault = s.fault_pc = 0;
  /* Tail-pointer cells in module data are byte-bound and protected; nearby
     mutable data stays writable. Refusal happens before changing any bytes. */
  assert(s.prot[(0x{P1:08x}u + 0x20u) >> 2] == 255);
  assert(plaid_runtime_write(&s, 0x{P1:08x}u + 0x18u, 4, 0x{PC:08x}u) == 0 && s.ovl_ok[k1]);
  assert(plaid_runtime_write(&s, 0x{P1:08x}u + 0x20u, 4, 0x{PC:08x}u) == 1 && s.fault == 2 && s.ovl_ok[k1]);
  s.fault = s.fault_pc = 0;
  printf("{{\\"pc\\":%u,\\"regs\\":[", s.pc);
  for (int r = 0; r < 32; r++) printf("%s%llu", r ? "," : "", (unsigned long long)s.r[r]);
  printf("],\\"hi\\":%llu,\\"lo\\":%llu,\\"fpr\\":[", (unsigned long long)s.hi, (unsigned long long)s.lo);
  for (int r = 0; r < 32; r++) printf("%s%llu", r ? "," : "", (unsigned long long)s.f[r]);
  printf("],\\"fcc\\":%u,\\"fcsr\\":%u,\\"ram\\":[", s.fcc, s.fcsr | s.fcc << 23);
  for (u32 p = 0x1000; p < 0x1100; p += 4)
    printf("%s%u", p == 0x1000 ? "" : ",", byte_at(&s,p)<<24 | byte_at(&s,p+1)<<16 | byte_at(&s,p+2)<<8 | byte_at(&s,p+3));
  puts("]}}");

  /* Inactive remap to an identical physical copy and same-value TLBWI rebind. */
  memcpy(s.ram + 0x{P_ALIAS:08x}u, raw0, sizeof raw0);
  e = s.tlb[0]; e.lo[0] = {entry_lo(P_ALIAS)}; e.lo[1] = {entry_lo(P_ALIAS + 0x1000)};
  generation = s.ovl_generation[k0];
  assert(plaid_tlb_write(&s, 0, e, 0x{PC:08x}u) == 0 && !s.ovl_ok[k0]);
  assert(plaid_link(&s, 0x{E0:08x}u) == plaid_ovls[k0].link);
  assert(s.ovl_generation[k0] > generation);
  binding(&s, k0, 0, 0x{E0:08x}u, 0x{P_ALIAS:08x}u);
  generation = s.ovl_generation[k0];
  u64 tlb_generation = s.tlb_generation[0];
  assert(plaid_tlb_write(&s, 0, e, 0x{PC:08x}u) == 0 && !s.ovl_ok[k0]);
  assert(plaid_link(&s, 0x{E0:08x}u) == plaid_ovls[k0].link);
  assert(s.tlb_generation[0] == tlb_generation + 1 && s.ovl_generation[k0] > generation);
  binding(&s, k0, 0, 0x{E0:08x}u, 0x{P_ALIAS:08x}u);

  /* Active remaps, unmaps and text writes fail atomically with fault 2. */
  old_delta = s.ovl_delta[k0]; old_backing = s.ovl_backing[k0]; old_tlb = s.ovl_tlb[k0];
  generation = s.ovl_generation[k0]; e.lo[0] = {entry_lo(P_ALIAS + 0x2000)};
  s.ovl_active[k0] = 1;
  assert(plaid_tlb_write(&s, 0, e, 0x{PC:08x}u) == 1 && s.fault == 2);
  assert(s.tlb[0].lo[0] == {entry_lo(P_ALIAS)} && s.ovl_ok[k0] && s.ovl_active[k0] == 1);
  assert(s.ovl_delta[k0] == old_delta && s.ovl_backing[k0] == old_backing && s.ovl_tlb[k0] == old_tlb && s.ovl_generation[k0] == generation);
  s.fault = s.fault_pc = 0;
  assert(plaid_tlb_clear(&s, 0x{PC:08x}u) == 1 && s.fault == 2);
  assert(s.tlb[0].lo[0] == {entry_lo(P_ALIAS)} && s.ovl_ok[k0] && s.ovl_active[k0] == 1);
  s.fault = s.fault_pc = 0;
  assert(plaid_runtime_write(&s, 0x{P_ALIAS:08x}u, 4, 0x{PC:08x}u) == 1 && s.fault == 2 && s.ovl_ok[k0]);
  s.ovl_active[k0] = 0; s.fault = s.fault_pc = 0;
  assert(plaid_runtime_write(&s, 0x{P_ALIAS:08x}u, 4, 0x{PC:08x}u) == 0 && !s.ovl_ok[k0]);

  /* Invalid, ASID-specific, odd-page and unmapped targets never link to code. */
  memcpy(s.ram + 0x{P_ALIAS:08x}u, raw0, sizeof raw0);
  e = s.tlb[0]; e.lo[0] &= ~2u;
  assert(plaid_tlb_write(&s, 0, e, 0x{PC:08x}u) == 0 && !s.ovl_ok[k0]);
  u32 pa; u8 seg;
  assert(plaid_tlb(&s, 0x{E0:08x}u, 0, &pa, &seg) == 1);
  assert(plaid_link(&s, 0x{E0:08x}u) == 1);
  e = s.tlb[0]; e.hi = 0x{E0 | 1:08x}u; e.lo[0] &= ~1u; e.lo[1] &= ~1u;
  assert(plaid_tlb_write(&s, 0, e, 0x{PC:08x}u) == 0 && !s.ovl_ok[k0]);
  assert(plaid_link(&s, 0x{E0:08x}u) == 1);
  e = s.tlb[0]; e.hi = 0x{E0:08x}u; e.lo[1] &= ~2u;
  assert(plaid_tlb_write(&s, 0, e, 0x{PC:08x}u) == 0);
  assert(plaid_tlb(&s, 0x{E0 + 0x1000:08x}u, 0, &pa, &seg) == 1);
  assert(plaid_tlb(&s, 0x{E0 + 0x400000:08x}u, 0, &pa, &seg) == 1);
  e = s.tlb[0]; e.hi = 0x{E0:08x}u; e.lo[0] = {entry_lo(P_ALIAS)};
  memcpy(s.ram + 0x{P_ALIAS:08x}u, raw0, sizeof raw0); s.ram[0x{P_ALIAS:08x}u] ^= 1;
  assert(plaid_tlb_write(&s, 0, e, 0x{PC:08x}u) == 0 && !s.ovl_ok[k0]);
  assert(plaid_link(&s, 0x{E0:08x}u) == 1 && !s.ovl_ok[k0]);

  /* Generation overflow is rejected before either the TLB or binding changes. */
  bad = s.tlb[1]; generation = s.ovl_generation[k1];
  old_delta = s.ovl_delta[k1]; old_backing = s.ovl_backing[k1]; old_tlb = s.ovl_tlb[k1];
  u64 before_single_tlb_generation = s.tlb_generation[1];
  s.tlb_generation[1] = UINT64_MAX;
  assert(plaid_tlb_write(&s, 1, bad, 0x{PC:08x}u) == 1 && s.fault == 1);
  assert(!memcmp(&s.tlb[1], &bad, sizeof bad));
  assert(s.tlb_generation[1] == UINT64_MAX && s.ovl_ok[k1] && s.ovl_generation[k1] == generation);
  assert(s.ovl_delta[k1] == old_delta && s.ovl_backing[k1] == old_backing && s.ovl_tlb[k1] == old_tlb);

  /* Restore both inactive bindings, then make index 31 the late overflow. */
  s.tlb_generation[1] = before_single_tlb_generation;
  memcpy(s.ram + 0x{P_ALIAS:08x}u, raw0, sizeof raw0);
  e = s.tlb[0]; e.hi = 0x{E0:08x}u; e.lo[0] = {entry_lo(P_ALIAS)}; e.lo[1] = {entry_lo(P_ALIAS + 0x1000)};
  assert(plaid_tlb_write(&s, 0, e, 0x{PC:08x}u) == 0);
  assert(plaid_link(&s, 0x{E0:08x}u) == plaid_ovls[k0].link);
  binding(&s, k0, 0, 0x{E0:08x}u, 0x{P_ALIAS:08x}u);
  assert(s.ovl_ok[k1] && !s.ovl_active[k0] && !s.ovl_active[k1]);

  plaid_tlb_entry before_clear_tlb[32];
  u64 before_clear_generation[32];
  u64 before_clear_overlay0 = s.ovl_generation[k0], before_clear_overlay1 = s.ovl_generation[k1];
  u32 before_clear_delta0 = s.ovl_delta[k0], before_clear_backing0 = s.ovl_backing[k0], before_clear_tlb0 = s.ovl_tlb[k0];
  u32 before_clear_delta1 = s.ovl_delta[k1], before_clear_backing1 = s.ovl_backing[k1], before_clear_tlb1 = s.ovl_tlb[k1];
  s.tlb_generation[31] = UINT64_MAX;
  memcpy(before_clear_tlb, s.tlb, sizeof before_clear_tlb);
  memcpy(before_clear_generation, s.tlb_generation, sizeof before_clear_generation);
  for (u32 i = 0; i < 31; i++) assert(s.tlb_generation[i] != UINT64_MAX);
  assert(s.tlb_generation[31] == UINT64_MAX);
  s.fault = s.fault_pc = 0;
  assert(plaid_tlb_clear(&s, 0x{PC:08x}u) == 1 && s.fault == 1);
  assert(!memcmp(before_clear_tlb, s.tlb, sizeof before_clear_tlb));
  assert(!memcmp(before_clear_generation, s.tlb_generation, sizeof before_clear_generation));
  assert(s.ovl_ok[k0] && s.ovl_ok[k1]);
  assert(s.ovl_generation[k0] == before_clear_overlay0 && s.ovl_generation[k1] == before_clear_overlay1);
  assert(s.ovl_delta[k0] == before_clear_delta0 && s.ovl_backing[k0] == before_clear_backing0 && s.ovl_tlb[k0] == before_clear_tlb0);
  assert(s.ovl_delta[k1] == before_clear_delta1 && s.ovl_backing[k1] == before_clear_backing1 && s.ovl_tlb[k1] == before_clear_tlb1);
  s.tlb_generation[31] = 0; s.fault = s.fault_pc = 0;
  memcpy(before_clear_generation, s.tlb_generation, sizeof before_clear_generation);
  assert(plaid_tlb_clear(&s, 0x{PC:08x}u) == 0);
  for (u32 i = 0; i < 32; i++) {{
    assert(s.tlb_generation[i] == before_clear_generation[i] + 1);
    assert(s.tlb[i].mask == 0 && s.tlb[i].hi == 0x80000000u && !s.tlb[i].lo[0] && !s.tlb[i].lo[1]);
  }}
  assert(!s.ovl_ok[k0] && !s.ovl_ok[k1]);
  assert(plaid_link(&s, 0x{E0:08x}u) == 1 && plaid_link(&s, 0x{E1:08x}u) == 1);
  return 0;
}}
'''


def _ares_run(raw_path):
    oracle = Path(os.environ.get('PLAID_ARES_ORACLE', ROOT / 'target/native-slice/oracle/oracle'))
    build = oracle.parent / 'build.json'
    if not oracle.exists() or not build.exists():
        raise RuntimeError('pinned ares oracle is missing; build it with spikes/096-native-slice/run.py --oracle')
    spec = importlib.util.spec_from_file_location('ares_builder', ROOT / 'spikes/003-ares-oracle/run.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    if json.loads(build.read_text())['revision'] != builder.REV:
        raise AssertionError(f'ares oracle is not pinned revision {builder.REV}')
    if os.name == 'nt':
        def linux(path):
            return subprocess.check_output(['wsl', '-d', 'Ubuntu', '--exec', 'wslpath', '-a', str(path)], text=True).strip()
        cmd = ['wsl', '-d', 'Ubuntu', '--exec', linux(oracle), linux(raw_path), hex(EXIT)]
    else:
        cmd = [str(oracle), str(raw_path), hex(EXIT)]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


def main():
    spec = importlib.util.spec_from_file_location('tlb_asm', SLICE / 'run.py')
    A = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(A)
    OUT.mkdir(parents=True, exist_ok=True)
    exe = Path(os.environ.get('PLAID_EXE', ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')))
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    if not exe.exists() or not cc:
        raise RuntimeError('TLB execution contract requires plaid and a C compiler')

    raw, labels, module0, module1 = _fixture(A)
    rom = bytearray(0x1000)
    rom[:4] = bytes.fromhex('80371240')
    rom.extend(raw)
    source, loads, runtime, mapping, native_c = (OUT / n for n in
        ('input.z64', 'loads.json', 'runtime.json', 'map.json', 'native.c'))
    source.write_bytes(rom)
    loads.write_text(json.dumps({'format': 'plaid-loads-v0', 'source': 'synthetic TLB executable slots',
        'loads': [
            {'destination': hex(E0), 'size': hex(len(module0) * 4), 'rom': hex(0x1000 + labels['module0'] - BASE),
             'encoding': 'tlb_raw', 'slot': True, 'text_size': hex(len(module0) * 4)},
            {'destination': hex(E1), 'size': hex(len(module1) * 4), 'rom': hex(0x1000 + labels['module1'] - BASE),
             'encoding': 'tlb_raw', 'slot': True, 'text_size': hex(20)}]}))
    runtime.write_text(json.dumps({'format': 'plaid-runtime-functions-v0', 'source': 'synthetic ares MTC0/TLBWI stub',
        'functions': [{'entry': hex(labels['map']), 'name': 'map', 'callbacks': []}]}))

    def plaid(*args):
        return subprocess.run([str(exe), *map(str, args)], check=True, capture_output=True, text=True)

    plaid('discover', source, '0x1000', hex(BASE), hex(len(raw)), hex(BASE), mapping, runtime,
          '--loads', loads, '--address-taken')
    verdict = json.loads(plaid('solve', source, mapping, '--address-taken').stdout)
    assert verdict['status'] == 'closed', verdict['blockers']
    plaid('lower-map', source, mapping, hex(BASE), hex(EXIT), native_c)
    harness = OUT / 'harness.c'
    harness.write_text(_native_harness(module0, module1, labels))
    native = OUT / ('check.exe' if os.name == 'nt' else 'check')
    subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
                    '-Wno-unused-function', f'-DPLAID_LOWERED="{native_c.name}"', '-I', str(OUT), str(harness), '-o', str(native)], check=True)
    actual = subprocess.run([str(native)], capture_output=True, text=True, timeout=30)
    assert actual.returncode == 0, (actual.returncode, actual.stdout, actual.stderr)
    raw_path = OUT / 'program.bin'
    raw_path.write_bytes(raw)
    expected = _ares_run(raw_path)
    assert expected.returncode == 0, (expected.stdout, expected.stderr)
    assert json.loads(actual.stdout) == json.loads(expected.stdout), (actual.stdout, expected.stdout)
    tamper_harness = OUT / 'preentry-tamper.c'
    tamper_harness.write_text(_native_harness(module0, module1, labels, preentry_tamper=True))
    tamper_native = OUT / ('preentry-tamper.exe' if os.name == 'nt' else 'preentry-tamper')
    subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
                    '-Wno-unused-function', f'-DPLAID_LOWERED="{native_c.name}"', '-I', str(OUT), str(tamper_harness), '-o', str(tamper_native)], check=True)
    tampered = subprocess.run([str(tamper_native)], capture_output=True, text=True, timeout=30)
    assert tampered.returncode == 0, (tampered.returncode, tampered.stdout, tampered.stderr)
    # Exercise the replay-bound physical field with the same native program.
    # Equal content at another RAM address must not satisfy this binding.
    constrained, count = re.subn(r'(\{0x[0-9a-f]{8}u, \d+u, 1u, ' + str(E0) + r'u, )4294967295u,',
                                 lambda m: m[1] + str(P0) + 'u,', native_c.read_text())
    assert count == 1
    physical_c = OUT / 'physical.c'
    physical_c.write_text(constrained)
    physical_harness = OUT / 'physical-harness.c'
    prefix = _native_harness(module0, module1, labels).split('  /* An earlier index')[0]
    physical_harness.write_text(prefix.replace('#include "native.c"', '#include "physical.c"') + f'''
  memcpy(s.ram + {P_ALIAS}u, raw0, sizeof raw0);
  e = s.tlb[0]; e.lo[0] = ({P_ALIAS}u >> 6) | 31u;
  assert(plaid_tlb_write(&s, 0, e, {PC}u) == 0 && !s.ovl_ok[k0]);
  assert(plaid_link(&s, {E0}u) == 1 && !s.ovl_ok[k0]);
  return 0;
}}
''')
    physical_native = OUT / ('physical.exe' if os.name == 'nt' else 'physical')
    subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
                    '-Wno-unused-function', '-Wno-unused-variable', str(physical_harness), '-o', str(physical_native)], check=True)
    subprocess.run([str(physical_native)], check=True, timeout=30)
    print('PASS replay-bound physical source: correct mapping executes; equal bytes at a different physical address refuse')
    print('PASS TLB execution: full state matches pinned ares; remap/clear transactions, pre-entry guarded-data tamper, fail-closed mappings and writable unrelated data verified')


if __name__ == '__main__':
    main()
