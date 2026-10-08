/* SPDX-License-Identifier: ISC
 * Controlled D-cache store -> writeback lineage fixture for pinned ares.
 */
#ifndef PLAID_DCACHE_LINEAGE_SENSOR
#define PLAID_DCACHE_LINEAGE_SENSOR 1
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <cstdlib>
#include <nall/hash/sha256.hpp>
#if PLAID_DCACHE_LINEAGE_SENSOR
#include "observer.hpp"
#endif

static constexpr u32 A = 0x1000;
static constexpr u32 B = 0x3000;  // same D-cache virtual index as A, different physical tag
static constexpr u64 VA = 0xffffffff80001000ull;
static constexpr u64 VB = 0xffffffff80003000ull;
static constexpr u32 Mutated = 0xa1b2c3d4;
static constexpr u32 Original = 0x11111111;
static constexpr u32 Tail1 = 0x10203040;
static constexpr u32 Tail2 = 0x50607080;
static constexpr u32 Tail3 = 0x90a0b0c0;

static void set_lineage_observers(bool enabled) {
#if PLAID_DCACHE_LINEAGE_SENSOR
  plaidDcacheObserver = enabled ? plaid_dcache_observer : nullptr;
  plaidRdramBurstObserver = enabled ? plaid_lineage_burst_observer : nullptr;
#else
  (void)enabled;
#endif
}

static void put(u32 address, u32 word) {
  rdram.ram.write<Word>(address, word, RBusDevice::ARES_DEBUGGER);
}

static void put_line(u32 address, u32 first = Original) {
  put(address + 0, first);
  put(address + 4, Tail1);
  put(address + 8, Tail2);
  put(address + 12, Tail3);
}

static u32 backing_word(u32 address) {
  return rdram.ram.read<Word>(address, RBusDevice::ARES_DEBUGGER);
}

static void append_be(std::vector<u8>& bytes, u64 value, u32 width) {
  for(u32 i = width; i > 0; i--) bytes.push_back(value >> (8 * (i - 1)));
}

static void prepare_phase(u32 phase) {
  set_lineage_observers(false);
  cpu.dcache.power(false);
  cpu.icache.power(false);
  put_line(A);
  put_line(B);
  cpu.ipu.r[8].u64 = Mutated;
  cpu.ipu.r[9].u64 = 0;
  cpu.ipu.r[16].u64 = VA;
  cpu.ipu.r[17].u64 = VB;
  if(&cpu.dcache.line(VA) != &cpu.dcache.line(VB)) std::abort();
#if PLAID_DCACHE_LINEAGE_SENSOR
  plaidLineagePhase = phase;
#endif
}

static bool step_one() {
  if(cpu.instruction()) cpu.synchronize();
  return cpu.scc.cause.exceptionCode == 0;
}

int main(int argc, char** argv) {
  if(argc != 2 || (strcmp(argv[1], "plain") && strcmp(argv[1], "traced"))) return 2;
  bool traced = !strcmp(argv[1], "traced");
  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid D-cache lineage fixture");
  frontend.cartPak->setAttribute("region", "NTSC");
  frontend.cartPak->setAttribute("cic", "CIC-NUS-6102");
  frontend.cartPak->append("program.rom", 8192);
  Node::System root;
  if(!load(root, "[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak", "true");
  option("Deterministic Entropy", "true");
  option("Recompiler", "false");
  cartridgeSlot.port->allocate();
  cartridgeSlot.port->connect();
  ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;

  std::vector<u8> hidden(rdram.ram.size / 2);
  rdram.hidden.data = hidden.data();
  rdram.mapIdentity = 1;
  for(auto& reg : cpu.ipu.r) reg.u64 = 0;
  cpu.scc.status.errorLevel = cpu.scc.status.exceptionLevel = 0;
  cpu.context.setMode();

  // Four tiny cached guest programs. Their instruction-cache traffic is retained
  // in the trace as a decoy; only VR4300_DCACHE RDRAM bursts are lineage-eligible.
  put(0x6000, 0xae080000);  // SW t0,0(s0)
  put(0x6004, 0xbe190000);  // CACHE 0x19: D-cache hit write back,0(s0)

  put(0x6040, 0xae080000);  // SW t0,0(s0)
  put(0x6044, 0x8e290000);  // LW t1,0(s1): dirty same-index replacement

  put(0x6080, 0x8e080000);  // LW t0,0(s0): clean fill
  put(0x6084, 0x8e290000);  // LW t1,0(s1): clean same-index replacement

  put(0x60c0, 0xae080000);  // SW t0,0(s0)
  put(0x60c4, 0xbe110000);  // CACHE 0x11: D-cache hit invalidate (no writeback)
  put(0x60c8, 0x8e290000);  // LW t1,0(s1): replacement after the dropped dirty line

  // Phase 1: explicit CACHE hit-writeback. Backing must stay stale after SW,
  // then receive the full resident line inside writeBack().
  prepare_phase(1);
  set_lineage_observers(traced);
  cpu.pipeline.setPc(0xffffffff80006000ull);
  if(!step_one()) return 5;
  u32 explicitBefore = backing_word(A);
  u16 explicitDirtyBefore = cpu.dcache.line(VA).dirty;
  if(!step_one()) return 6;
  u32 explicitAfter = backing_word(A);
  u16 explicitDirtyAfter = cpu.dcache.line(VA).dirty;
  if(explicitBefore != Original || explicitAfter != Mutated || explicitDirtyBefore != 15 || explicitDirtyAfter != 0) return 7;

  // Phase 2: a normal cached miss to B must first write back dirty A, then fill B.
  prepare_phase(2);
  set_lineage_observers(traced);
  cpu.pipeline.setPc(0xffffffff80006040ull);
  if(!step_one()) return 8;
  u32 evictionBefore = backing_word(A);
  if(!step_one()) return 9;
  u32 evictionAfter = backing_word(A);
  auto& evictionLine = cpu.dcache.line(VB);
  if(evictionBefore != Original || evictionAfter != Mutated || !evictionLine.hit(B) || evictionLine.dirty != 0) return 10;

  // Phase 3: same-index replacement of a clean line must not create a backing write.
  // A and B intentionally begin with identical payloads to defeat value matching.
  prepare_phase(3);
  set_lineage_observers(traced);
  cpu.pipeline.setPc(0xffffffff80006080ull);
  if(!step_one() || !step_one()) return 11;
  u32 cleanA = backing_word(A), cleanB = backing_word(B);
  if(cleanA != Original || cleanB != Original || !cpu.dcache.line(VB).hit(B) || cpu.dcache.line(VB).dirty) return 12;

  // Phase 4: CACHE 0x11 invalidates the dirty A line without writeback. The later
  // B miss therefore fills over it. The cached mutation is real but never becomes
  // an RDRAM mutation.
  prepare_phase(4);
  set_lineage_observers(traced);
  cpu.pipeline.setPc(0xffffffff800060c0ull);
  if(!step_one()) return 13;
  if(!step_one()) return 14;
  bool validAfterInvalidate = cpu.dcache.line(VA).valid();
  u16 dirtyAfterInvalidate = cpu.dcache.line(VA).dirty;
  u32 invalidateBackingBeforeReplacement = backing_word(A);
  if(!step_one()) return 15;
  u32 invalidateBackingAfterReplacement = backing_word(A);
  if(validAfterInvalidate || dirtyAfterInvalidate != 15 ||
     invalidateBackingBeforeReplacement != Original || invalidateBackingAfterReplacement != Original ||
     !cpu.dcache.line(VB).hit(B) || cpu.dcache.line(VB).dirty) return 16;
  set_lineage_observers(false);

  auto ramHash = nall::Hash::SHA256(std::span<const u8>{rdram.ram.data, rdram.ram.size}).digest();
  auto hiddenHash = nall::Hash::SHA256(std::span<const u8>{hidden.data(), hidden.size()}).digest();
  std::vector<u8> dcacheBytes;
  for(const auto& line : cpu.dcache.lines) {
    append_be(dcacheBytes, line.tagKey, 4);
    append_be(dcacheBytes, line.dirty, 2);
    append_be(dcacheBytes, line.index, 2);
    append_be(dcacheBytes, line.fillPc, 8);
    append_be(dcacheBytes, line.dirtyPc, 8);
    for(u32 word : line.words) append_be(dcacheBytes, word, 4);
  }
  auto dcacheHash = nall::Hash::SHA256(std::span<const u8>{dcacheBytes.data(), dcacheBytes.size()}).digest();

  std::printf("{");
#if PLAID_DCACHE_LINEAGE_SENSOR
  plaid_print_lineage_events();
#else
  std::printf("\"dcache_events\":[],\"burst_events\":[]");
#endif
  std::printf(",\"facts\":{\"explicit_before\":%u,\"explicit_after\":%u,\"explicit_dirty_before\":%u,\"explicit_dirty_after\":%u,\"eviction_before\":%u,\"eviction_after\":%u,\"clean_a\":%u,\"clean_b\":%u,\"valid_after_invalidate\":%s,\"dirty_after_invalidate\":%u,\"invalidate_backing_before_replacement\":%u,\"invalidate_backing_after_replacement\":%u}",
    explicitBefore, explicitAfter, (u32)explicitDirtyBefore, (u32)explicitDirtyAfter,
    evictionBefore, evictionAfter, cleanA, cleanB, validAfterInvalidate ? "true" : "false",
    (u32)dirtyAfterInvalidate, invalidateBackingBeforeReplacement, invalidateBackingAfterReplacement);
  std::printf(",\"state\":{\"pc\":%llu,\"t0\":%u,\"t1\":%u,\"count\":%llu,\"exception\":%u,\"dcache_hits\":%llu,\"dcache_misses\":%llu,\"dcache_writebacks\":%llu,\"ram_sha256\":\"%s\",\"hidden_sha256\":\"%s\",\"dcache_sha256\":\"%s\"}}\n",
    (unsigned long long)cpu.ipu.pc, cpu.ipu.r[8].u32, cpu.ipu.r[9].u32,
    (unsigned long long)cpu.effectiveCount(), (u32)cpu.scc.cause.exceptionCode,
    (unsigned long long)cpu.profile.dcacheHits, (unsigned long long)cpu.profile.dcacheMisses,
    (unsigned long long)cpu.profile.dcacheWritebacks,
    ramHash.data(), hiddenHash.data(), dcacheHash.data());
  ares::Nintendo64::system.unload();
  return 0;
}
