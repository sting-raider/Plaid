/* SPDX-License-Identifier: ISC
 * TLB-mapped uncached instruction-fetch provenance fixture for pinned ares.
 */
#ifndef PLAID_RDRAM_FETCH_SENSOR
#define PLAID_RDRAM_FETCH_SENSOR 1
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <cstdlib>
#include <nall/hash/sha256.hpp>
#if PLAID_RDRAM_FETCH_SENSOR
#include "observer.hpp"
#endif

static constexpr u64 VaPrimary = 0x00004000ull;
static constexpr u64 VaAlias   = 0x00008000ull;
static constexpr u64 VaCached  = 0x0000c000ull;
static constexpr u64 VaLittle  = 0x00010000ull;
static constexpr u64 VaDecoyCode = 0x00014000ull;
static constexpr u64 VaDecoyData = 0x00018000ull;
static constexpr u64 VaGlobal  = 0x0001c000ull;
static constexpr u64 VaAsidMiss = 0x00020000ull;
static constexpr u64 VaInvalid = 0x00024000ull;
static constexpr u64 VaMissing = 0x00028000ull;

static constexpr u32 PaPrimary = 0x001000;
static constexpr u32 PaRemap   = 0x003000;
static constexpr u32 PaCached  = 0x005000;
static constexpr u32 PaLittle  = 0x007000;
static constexpr u32 PaDecoyCode = 0x009000;
static constexpr u32 PaDecoyData = 0x00b000;
static constexpr u32 PaGlobal  = 0x00d000;
static constexpr u32 PaAsidMiss = 0x00f000;
static constexpr u32 PaInvalid = 0x011000;

static constexpr u32 OriT1 = 0x34091234;
static constexpr u32 OriT2 = 0x340a5678;
static constexpr u32 OriT3 = 0x340b9abc;
static constexpr u32 OriT4 = 0x340c2468;
static constexpr u32 LwT0S0 = 0x8e080000;

static void set_fetch_observers(bool enabled) {
#if PLAID_RDRAM_FETCH_SENSOR
  plaidRdramScalarObserver = enabled ? plaid_rdram_fetch_scalar_observer : nullptr;
  plaidCpuFetchObserver = enabled ? plaid_cpu_fetch_boundary_observer : nullptr;
#else
  (void)enabled;
#endif
}

static void set_phase(u32 phase, bool traced) {
  set_fetch_observers(false);
#if PLAID_RDRAM_FETCH_SENSOR
  plaidRdramFetchPhase = phase;
#endif
  set_fetch_observers(traced);
}

static void clear_tlb_cache() {
  for(auto& slot : cpu.tlb.tlbCache.entry) {
    slot.entry = nullptr;
    slot.frequency = 0;
  }
  cpu.devirtualizeCache = {};
}

static void clear_tlb_entries() {
  for(auto& entry : cpu.tlb.entry) entry = {};
  clear_tlb_cache();
}

static void write_tlb(u32 index, u64 vbase, u32 pbase0, u32 pbase1,
                      u32 cca, u32 entryAsid, bool global,
                      bool valid0 = true, bool valid1 = true) {
  CPU::TLB::Entry entry{};
  entry.pageMask = 0;
  entry.virtualAddress = vbase;
  entry.addressSpaceID = entryAsid;
  entry.region = vbase >> 62;
  entry.global[0] = global;
  entry.global[1] = global;
  entry.valid[0] = valid0;
  entry.valid[1] = valid1;
  entry.dirty[0] = 1;
  entry.dirty[1] = 1;
  entry.cacheAlgorithm[0] = cca;
  entry.cacheAlgorithm[1] = cca;
  entry.physicalAddress[0] = pbase0;
  entry.physicalAddress[1] = pbase1;
  cpu.scc.index.tlbEntry = index;
  cpu.scc.tlb = entry;
  cpu.TLBWI();
}

static void set_current_asid(u32 asid) {
  cpu.scc.tlb.addressSpaceID = asid;
}

static void reset_exception() {
  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.cause.exceptionCode = 0;
  cpu.scc.cause.branchDelay = 0;
  cpu.scc.badVirtualAddress = 0;
  cpu.context.setMode();
}

static void execute_one(u32 phase, u64 pc, bool traced) {
  set_phase(phase, traced);
  cpu.pipeline.setPc(pc);
  if(cpu.instruction()) cpu.synchronize();
  set_fetch_observers(false);
}

static void append_be(std::vector<u8>& bytes, u64 value, u32 width) {
  for(u32 i = width; i > 0; i--) bytes.push_back(value >> (8 * (i - 1)));
}

int main(int argc, char** argv) {
  if(argc != 2 || (strcmp(argv[1], "plain") && strcmp(argv[1], "traced"))) return 2;
  bool traced = !strcmp(argv[1], "traced");
  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid TLB uncached fetch fixture");
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
  cpu.scc.status.privilegeMode = 0;
  cpu.scc.status.kernelExtendedAddressing = 0;
  cpu.context.setMode();
  cpu.context.endian = CPU::Context::Endian::Big;
  cpu.dcache.power(false);
  cpu.icache.power(false);
  clear_tlb_entries();

  auto put = [](u32 address, u32 word) {
    rdram.ram.write<Word>(address, word, RBusDevice::ARES_DEBUGGER);
  };

  // 1: valid non-global CCA=2 mapping. This is the positive mapped-uncached root.
  put(PaPrimary, OriT1);
  write_tlb(0, VaPrimary, PaPrimary, PaPrimary + 0x1000, 2, 7, false);
  set_current_asid(7);
  cpu.ipu.r[9].u64 = 0;
  execute_one(1, VaPrimary, traced);
  if(cpu.scc.cause.exceptionCode != 0 || cpu.ipu.r[9].u32 != 0x1234) return 5;
  u32 primaryValue = cpu.ipu.r[9].u32;

  // 2: a distinct virtual alias maps to the exact same physical word/value.
  // Any provenance key that drops vaddr/mapping context merges these histories.
  write_tlb(1, VaAlias, PaPrimary, PaPrimary + 0x1000, 2, 7, false);
  set_current_asid(7);
  cpu.ipu.r[9].u64 = 0;
  execute_one(2, VaAlias, traced);
  if(cpu.scc.cause.exceptionCode != 0 || cpu.ipu.r[9].u32 != 0x1234) return 6;
  u32 aliasValue = cpu.ipu.r[9].u32;

  // 3: rewrite entry 0 with real TLBWI. Same vaddr and same instruction bytes,
  // but a different physical backing page must produce a different witness.
  put(PaRemap, OriT1);
  write_tlb(0, VaPrimary, PaRemap, PaRemap + 0x1000, 2, 7, false);
  set_current_asid(7);
  cpu.ipu.r[9].u64 = 0;
  execute_one(3, VaPrimary, traced);
  if(cpu.scc.cause.exceptionCode != 0 || cpu.ipu.r[9].u32 != 0x1234) return 7;
  u32 remapValue = cpu.ipu.r[9].u32;

  // 4: CCA=3 is cacheable in pinned ares. It may fill I-cache, but must not
  // inherit the ordinary scalar backing witness used for CCA=2.
  put(PaCached, OriT2);
  write_tlb(2, VaCached, PaCached, PaCached + 0x1000, 3, 7, false);
  set_current_asid(7);
  cpu.ipu.r[10].u64 = 0;
  execute_one(4, VaCached, traced);
  if(cpu.scc.cause.exceptionCode != 0 || cpu.ipu.r[10].u32 != 0x5678) return 8;
  u32 cachedValue = cpu.ipu.r[10].u32;

  // 5: forced reverse-endian context. TLB translates to PaLittle, while the
  // actual uncached Word bus transaction must occur at PaLittle^4.
  put(PaLittle + 0x00, 0x00000000);
  put(PaLittle + 0x04, OriT3);
  write_tlb(3, VaLittle, PaLittle, PaLittle + 0x1000, 2, 7, false);
  set_current_asid(7);
  cpu.ipu.r[11].u64 = 0;
  cpu.context.endian = CPU::Context::Endian::Little;
  execute_one(5, VaLittle, traced);
  if(cpu.scc.cause.exceptionCode != 0 || cpu.ipu.r[11].u32 != 0x9abc) return 9;
  u32 littleValue = cpu.ipu.r[11].u32;
  cpu.context.endian = CPU::Context::Endian::Big;

  // 6: TLB-mapped instruction fetches around an equal-valued TLB-mapped data
  // read. The data zero lies between the two fetch contexts, not inside either.
  put(PaDecoyCode + 0x00, LwT0S0);
  put(PaDecoyCode + 0x04, 0x00000000);
  put(PaDecoyData, 0x00000000);
  write_tlb(4, VaDecoyCode, PaDecoyCode, PaDecoyCode + 0x1000, 2, 7, false);
  write_tlb(5, VaDecoyData, PaDecoyData, PaDecoyData + 0x1000, 2, 7, false);
  set_current_asid(7);
  cpu.ipu.r[16].u64 = VaDecoyData;
  cpu.ipu.r[8].u64 = ~0ull;
  set_phase(6, traced);
  cpu.pipeline.setPc(VaDecoyCode);
  for(u32 i = 0; i < 2; i++) if(cpu.instruction()) cpu.synchronize();
  set_fetch_observers(false);
  if(cpu.scc.cause.exceptionCode != 0 || cpu.ipu.r[8].u32 != 0) return 10;
  u32 decoyValue = cpu.ipu.r[8].u32;

  // 7: global mapping remains eligible across an ASID mismatch; global is part
  // of TLB matching semantics and cannot be approximated as `entry ASID == current`.
  put(PaGlobal, OriT4);
  write_tlb(6, VaGlobal, PaGlobal, PaGlobal + 0x1000, 2, 1, true);
  set_current_asid(99);
  cpu.ipu.r[12].u64 = 0;
  execute_one(7, VaGlobal, traced);
  if(cpu.scc.cause.exceptionCode != 0 || cpu.ipu.r[12].u32 != 0x2468) return 11;
  u32 globalValue = cpu.ipu.r[12].u32;

  // 8: same shape without global bits and with wrong ASID must fail before fetch.
  reset_exception();
  put(PaAsidMiss, OriT4);
  write_tlb(7, VaAsidMiss, PaAsidMiss, PaAsidMiss + 0x1000, 2, 1, false);
  set_current_asid(99);
  execute_one(8, VaAsidMiss, traced);
  u32 asidException = cpu.scc.cause.exceptionCode;
  u64 asidBadVaddr = cpu.scc.badVirtualAddress;
  if(asidException == 0 || asidBadVaddr != VaAsidMiss) return 12;

  // 9: matching entry but invalid selected half must also fail before fetch.
  reset_exception();
  write_tlb(8, VaInvalid, PaInvalid, PaInvalid + 0x1000, 2, 7, false, false, true);
  set_current_asid(7);
  execute_one(9, VaInvalid, traced);
  u32 invalidException = cpu.scc.cause.exceptionCode;
  u64 invalidBadVaddr = cpu.scc.badVirtualAddress;
  if(invalidException == 0 || invalidBadVaddr != VaInvalid) return 13;

  // 10: no matching entry. Clear all TLB rows so this is a true miss.
  reset_exception();
  clear_tlb_entries();
  set_current_asid(7);
  execute_one(10, VaMissing, traced);
  u32 missingException = cpu.scc.cause.exceptionCode;
  u64 missingBadVaddr = cpu.scc.badVirtualAddress;
  if(missingException == 0 || missingBadVaddr != VaMissing) return 14;
  set_fetch_observers(false);

  auto ramHash = nall::Hash::SHA256(std::span<const u8>{rdram.ram.data, rdram.ram.size}).digest();
  std::vector<u8> icacheBytes;
  for(const auto& line : cpu.icache.lines) {
    append_be(icacheBytes, line.tagKey, 4);
    append_be(icacheBytes, line.index, 2);
    for(u32 word : line.words) append_be(icacheBytes, word, 4);
  }
  auto icacheHash = nall::Hash::SHA256(std::span<const u8>{icacheBytes.data(), icacheBytes.size()}).digest();

  std::printf("{");
#if PLAID_RDRAM_FETCH_SENSOR
  plaid_print_rdram_fetch_events();
#else
  std::printf("\"scalar_events\":[],\"fetch_events\":[]");
#endif
  std::printf(",\"facts\":{\"primary\":%u,\"alias\":%u,\"remap\":%u,\"cached\":%u,\"little\":%u,\"decoy\":%u,\"global\":%u,\"asid_exception\":%u,\"asid_badvaddr\":%llu,\"invalid_exception\":%u,\"invalid_badvaddr\":%llu,\"missing_exception\":%u,\"missing_badvaddr\":%llu}",
    primaryValue, aliasValue, remapValue, cachedValue, littleValue, decoyValue, globalValue,
    asidException, (unsigned long long)asidBadVaddr,
    invalidException, (unsigned long long)invalidBadVaddr,
    missingException, (unsigned long long)missingBadVaddr);
  std::printf(",\"state\":{\"pc\":%llu,\"count\":%llu,\"exception\":%u,\"icache_hits\":%llu,\"icache_misses\":%llu,\"ram_sha256\":\"%s\",\"icache_sha256\":\"%s\"}}\n",
    (unsigned long long)cpu.ipu.pc, (unsigned long long)cpu.effectiveCount(),
    (u32)cpu.scc.cause.exceptionCode, (unsigned long long)cpu.profile.icacheHits,
    (unsigned long long)cpu.profile.icacheMisses, ramHash.data(), icacheHash.data());
  ares::Nintendo64::system.unload();
  return 0;
}
