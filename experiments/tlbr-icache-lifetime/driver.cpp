/* SPDX-License-Identifier: ISC
 * Compose real guest TLBR translation-context changes with cacheable I-cache residency.
 */
#define main capability_fixture_main
#include "../../spikes/003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>
#include <cstdio>
#include <string>
#include <vector>

static constexpr u64 VaSwitch = 0x00004000ull;
static constexpr u64 VaGlobal = 0x00006000ull;
static constexpr u64 VaContext44 = 0x00020000ull;
static constexpr u32 PaA = 0x001000;
static constexpr u32 PaB = 0x003000;
static constexpr u32 PaEqual = 0x005000;
static constexpr u32 PaGlobal = 0x007000;
static constexpr u32 PaContext44 = 0x009000;
static constexpr u32 DirectPa = 0x010000;
static constexpr u64 DirectVa = 0xffff'ffff'a001'0000ull;

static constexpr u32 OriAOld = 0x34091111;   // ori t1,zero,0x1111
static constexpr u32 OriB = 0x34092222;      // ori t1,zero,0x2222
static constexpr u32 OriANew = 0x34094444;   // ori t1,zero,0x4444
static constexpr u32 OriGlobal = 0x340a7777; // ori t2,zero,0x7777
static constexpr u32 TlbrOpcode = 0x42000001;
static constexpr u32 TlbpOpcode = 0x42000008;

static void append_be(std::vector<u8>& out, u64 value, u32 width) {
  for(u32 i = width; i > 0; --i) out.push_back(value >> (8 * (i - 1)));
}

static std::string icache_hash() {
  std::vector<u8> bytes;
  for(const auto& line : cpu.icache.lines) {
    append_be(bytes, line.tagKey, 4);
    append_be(bytes, line.index, 2);
    for(u32 word : line.words) append_be(bytes, word, 4);
  }
  auto digest = nall::Hash::SHA256(std::span<const u8>{bytes.data(), bytes.size()}).digest();
  return digest.data();
}

static void clear_tlb() {
  for(auto& entry : cpu.tlb.entry) entry = {};
  for(auto& slot : cpu.tlb.tlbCache.entry) {
    slot.entry = nullptr;
    slot.frequency = 0;
  }
  cpu.devirtualizeCache = {};
}

static void install_tlb(u32 index, u64 vbase, u32 pbase, u32 asid, bool global) {
  CPU::TLB::Entry entry{};
  entry.pageMask = 0;
  entry.virtualAddress = vbase;
  entry.addressSpaceID = asid;
  entry.region = vbase >> 62;
  entry.global[0] = entry.global[1] = global;
  entry.valid[0] = entry.valid[1] = 1;
  entry.dirty[0] = entry.dirty[1] = 1;
  entry.cacheAlgorithm[0] = entry.cacheAlgorithm[1] = 3;
  entry.physicalAddress[0] = pbase;
  entry.physicalAddress[1] = pbase + 0x1000;
  cpu.scc.index.tlbEntry = index;
  cpu.scc.tlb = entry;
  cpu.TLBWI();
}

static std::string installed_snapshot() {
  std::string out;
  char row[512];
  for(u32 i = 0; i < CPU::TLB::Entries; i++) {
    const auto& e = cpu.tlb.entry[i];
    std::snprintf(row, sizeof(row),
      "%u:%llx:%llx:%u:%u:%u:%u:%u:%u:%u:%u:%u:%u:%u:%llx:%llx:%llx:%llx:%llx;",
      i,
      (unsigned long long)e.pageMask,
      (unsigned long long)e.virtualAddress,
      (u32)e.addressSpaceID,
      (u32)e.region,
      (u32)e.globals,
      (u32)e.global[0], (u32)e.global[1],
      (u32)e.valid[0], (u32)e.valid[1],
      (u32)e.dirty[0], (u32)e.dirty[1],
      (u32)e.cacheAlgorithm[0], (u32)e.cacheAlgorithm[1],
      (unsigned long long)e.physicalAddress[0],
      (unsigned long long)e.physicalAddress[1],
      (unsigned long long)e.addressMaskHi,
      (unsigned long long)e.addressMaskLo,
      (unsigned long long)e.addressSelect);
    out += row;
  }
  return out;
}

static void reset_exception() {
  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.cause.exceptionCode = 0;
  cpu.scc.cause.branchDelay = 0;
  cpu.scc.badVirtualAddress = 0;
  cpu.context.setMode();
}

static bool execute_at(u32 offset) {
  reset_exception();
  cpu.pipeline.setPc(DirectVa + offset);
  if(cpu.instruction()) cpu.synchronize();
  return cpu.scc.cause.exceptionCode == 0;
}

static bool execute_tlbr(u32 slot) {
  cpu.scc.index.tlbEntry = slot;
  cpu.scc.index.probeFailure = 0;
  return execute_at(0);
}

static bool execute_tlbp() {
  return execute_at(4);
}

struct FetchResult {
  u32 value;
  u32 paddr;
  u32 exception;
  u64 badvaddr;
};

static FetchResult fetch_switch() {
  cpu.ipu.r[9].u64 = 0;
  cpu.pipeline.setPc(VaSwitch);
  if(cpu.instruction()) cpu.synchronize();
  return {(u32)cpu.ipu.r[9].u32, (u32)cpu.tlb.physicalAddress,
          (u32)cpu.scc.cause.exceptionCode, (u64)cpu.scc.badVirtualAddress};
}

static FetchResult fetch_global() {
  cpu.ipu.r[10].u64 = 0;
  cpu.pipeline.setPc(VaGlobal);
  if(cpu.instruction()) cpu.synchronize();
  return {(u32)cpu.ipu.r[10].u32, (u32)cpu.tlb.physicalAddress,
          (u32)cpu.scc.cause.exceptionCode, (u64)cpu.scc.badVirtualAddress};
}

int main() {
  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid TLBR I-cache lifetime fixture");
  frontend.cartPak->setAttribute("region", "NTSC");
  frontend.cartPak->setAttribute("cic", "CIC-NUS-6102");
  frontend.cartPak->append("program.rom", 8192);
  Node::System root;
  if(!load(root, "[Nintendo] Nintendo 64 (NTSC)")) return 2;
  option("Expansion Pak", "true");
  option("Deterministic Entropy", "true");
  option("Recompiler", "false");
  cartridgeSlot.port->allocate();
  cartridgeSlot.port->connect();
  ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 3;

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
  clear_tlb();

  auto put = [](u32 address, u32 word) {
    rdram.ram.write<Word>(address, word, RBusDevice::ARES_DEBUGGER);
  };
  put(DirectPa + 0, TlbrOpcode);
  put(DirectPa + 4, TlbpOpcode);
  put(DirectPa + 8, 0);
  put(PaA, OriAOld);
  put(PaB, OriB);
  put(PaEqual, OriAOld);
  put(PaGlobal, OriGlobal);

  install_tlb(0, VaSwitch, PaA, 0x11, false);
  install_tlb(1, VaSwitch, PaB, 0x22, false);
  install_tlb(2, VaSwitch, PaEqual, 0x33, false);
  install_tlb(3, VaGlobal, PaGlobal, 0x77, true);
  install_tlb(4, VaContext44, PaContext44, 0x44, false);
  const std::string installed = installed_snapshot();

  const u32 idxSwitch = (u32)(VaSwitch >> 5 & 0x1ff);
  const u32 idxGlobal = (u32)(VaGlobal >> 5 & 0x1ff);
  if(idxSwitch == idxGlobal) return 4;

  // Activate A by a real guest TLBR, not by directly writing EntryHi.
  auto cacheBeforeFirstTlbr = icache_hash();
  u64 missesBeforeFirstTlbr = cpu.profile.icacheMisses;
  if(!execute_tlbr(0) || (u32)cpu.scc.tlb.addressSpaceID != 0x11) return 5;
  if(installed_snapshot() != installed || icache_hash() != cacheBeforeFirstTlbr || cpu.profile.icacheMisses != missesBeforeFirstTlbr) return 6;

  u64 misses0 = cpu.profile.icacheMisses;
  auto firstA = fetch_switch();
  u64 misses1 = cpu.profile.icacheMisses;
  if(firstA.exception || firstA.value != 0x1111 || firstA.paddr != PaA || misses1 != misses0 + 1) return 7;
  auto& line = cpu.icache.line(VaSwitch);
  u32 initialTag = line.tagKey;
  u32 initialWord = line.words[0];
  if(!line.valid() || initialWord != OriAOld) return 8;

  // TLBP may alter Index, but must not alter EntryHi context or I-cache residency.
  const u64 entryhiBeforeProbe = cpu.getControlRegister(10);
  const auto cacheBeforeProbe = icache_hash();
  const u64 missesBeforeProbe = cpu.profile.icacheMisses;
  if(!execute_tlbp()) return 9;
  const u64 entryhiAfterProbe = cpu.getControlRegister(10);
  if(entryhiBeforeProbe != entryhiAfterProbe || (u32)cpu.scc.index.tlbEntry != 0 || (bool)cpu.scc.index.probeFailure) return 10;
  if(installed_snapshot() != installed || icache_hash() != cacheBeforeProbe || cpu.profile.icacheMisses != missesBeforeProbe) return 11;

  // TLBR B changes translation context only. The resident A line survives.
  const auto cacheBeforeB = icache_hash();
  const u64 missesBeforeB = cpu.profile.icacheMisses;
  if(!execute_tlbr(1) || (u32)cpu.scc.tlb.addressSpaceID != 0x22) return 12;
  if(installed_snapshot() != installed || icache_hash() != cacheBeforeB || cpu.profile.icacheMisses != missesBeforeB) return 13;
  if(line.tagKey != initialTag || line.words[0] != initialWord || !line.valid()) return 14;

  // Mutate A backing while A is inactive, then touch unrelated global code at a
  // different ares I-cache index so A's old resident generation is preserved.
  put(PaA, OriANew);
  reset_exception();
  auto globalB = fetch_global();
  if(globalB.exception || globalB.value != 0x7777 || globalB.paddr != PaGlobal) return 15;
  if(line.tagKey != initialTag || line.words[0] != initialWord || !line.valid()) return 16;

  // Same-value TLBR is still an executed context writer even though EntryHi is equal.
  const u64 entryhiBeforeSame = cpu.getControlRegister(10);
  const auto cacheBeforeSame = icache_hash();
  const u64 missesBeforeSame = cpu.profile.icacheMisses;
  if(!execute_tlbr(1)) return 17;
  const u64 entryhiAfterSame = cpu.getControlRegister(10);
  if(entryhiBeforeSame != entryhiAfterSame || (u32)cpu.scc.tlb.addressSpaceID != 0x22) return 18;
  if(installed_snapshot() != installed || icache_hash() != cacheBeforeSame || cpu.profile.icacheMisses != missesBeforeSame) return 19;

  // Out-of-range TLBR executes as an exact-pinned no-op and must not be confused
  // with a successful context write merely because the instruction occurred.
  const u64 entryhiBeforeBad = cpu.getControlRegister(10);
  const auto cacheBeforeBad = icache_hash();
  const u64 missesBeforeBad = cpu.profile.icacheMisses;
  if(!execute_tlbr(63)) return 20;
  const u64 entryhiAfterBad = cpu.getControlRegister(10);
  if(entryhiBeforeBad != entryhiAfterBad) return 21;
  if(installed_snapshot() != installed || icache_hash() != cacheBeforeBad || cpu.profile.icacheMisses != missesBeforeBad) return 22;

  // TLBR an unrelated entry solely to load ASID 0x44. VaSwitch must now fault,
  // and the fault must not destroy the old resident A line.
  const auto cacheBefore44 = icache_hash();
  if(!execute_tlbr(4) || (u32)cpu.scc.tlb.addressSpaceID != 0x44) return 23;
  if(installed_snapshot() != installed || icache_hash() != cacheBefore44) return 24;
  u64 missesBeforeFault = cpu.profile.icacheMisses;
  reset_exception();
  auto fault = fetch_switch();
  u64 missesAfterFault = cpu.profile.icacheMisses;
  if(fault.exception != 2 || fault.badvaddr != VaSwitch || missesAfterFault != missesBeforeFault) return 25;
  if(line.tagKey != initialTag || line.words[0] != initialWord || !line.valid()) return 26;

  // Decisive composition: TLBR A makes the old A mapping reachable again without
  // changing entries or I-cache. The subsequent fetch must hit stale resident
  // 0x1111 although current PA-A backing is already 0x4444.
  const auto cacheBeforeReactivateTlbr = icache_hash();
  const u64 missesBeforeReactivateTlbr = cpu.profile.icacheMisses;
  if(!execute_tlbr(0) || (u32)cpu.scc.tlb.addressSpaceID != 0x11) return 27;
  if(installed_snapshot() != installed || icache_hash() != cacheBeforeReactivateTlbr || cpu.profile.icacheMisses != missesBeforeReactivateTlbr) return 28;
  u64 missesBeforeReactivate = cpu.profile.icacheMisses;
  reset_exception();
  auto staleA = fetch_switch();
  u64 missesAfterReactivate = cpu.profile.icacheMisses;
  if(staleA.exception || staleA.value != 0x1111 || staleA.paddr != PaA) return 29;
  if(missesAfterReactivate != missesBeforeReactivate) return 30;
  if(rdram.ram.read<Word>(PaA, RBusDevice::ARES_DEBUGGER) != OriANew) return 31;

  // Equal bytes at a different physical address are a distinct resident generation.
  const auto cacheBeforeC = icache_hash();
  if(!execute_tlbr(2) || (u32)cpu.scc.tlb.addressSpaceID != 0x33) return 32;
  if(installed_snapshot() != installed || icache_hash() != cacheBeforeC) return 33;
  u32 tagBeforeEqual = line.tagKey;
  u64 missesBeforeEqual = cpu.profile.icacheMisses;
  reset_exception();
  auto equalC = fetch_switch();
  u64 missesAfterEqual = cpu.profile.icacheMisses;
  u32 tagAfterEqual = line.tagKey;
  if(equalC.exception || equalC.value != 0x1111 || equalC.paddr != PaEqual) return 34;
  if(missesAfterEqual != missesBeforeEqual + 1) return 35;
  if((tagBeforeEqual & ~1u) == (tagAfterEqual & ~1u)) return 36;

  // C's fill replaced A. TLBR A followed by fetch now misses and sees fresh backing.
  const auto cacheBeforeFreshTlbr = icache_hash();
  if(!execute_tlbr(0) || (u32)cpu.scc.tlb.addressSpaceID != 0x11) return 37;
  if(installed_snapshot() != installed || icache_hash() != cacheBeforeFreshTlbr) return 38;
  u64 missesBeforeFreshA = cpu.profile.icacheMisses;
  reset_exception();
  auto freshA = fetch_switch();
  u64 missesAfterFreshA = cpu.profile.icacheMisses;
  if(freshA.exception || freshA.value != 0x4444 || freshA.paddr != PaA) return 39;
  if(missesAfterFreshA != missesBeforeFreshA + 1) return 40;

  reset_exception();
  auto globalA = fetch_global();
  if(globalA.exception || globalA.value != 0x7777 || globalA.paddr != PaGlobal) return 41;
  if(installed_snapshot() != installed) return 42;

  auto finalCacheHash = icache_hash();
  std::printf("{\"idx_switch\":%u,\"idx_global\":%u,", idxSwitch, idxGlobal);
  std::printf("\"first_a\":{\"value\":%u,\"paddr\":%u},", firstA.value, firstA.paddr);
  std::printf("\"global_b\":{\"value\":%u,\"paddr\":%u},", globalB.value, globalB.paddr);
  std::printf("\"fault\":{\"exception\":%u,\"badvaddr\":%llu},", fault.exception, (unsigned long long)fault.badvaddr);
  std::printf("\"stale_reactivated_a\":{\"value\":%u,\"paddr\":%u},", staleA.value, staleA.paddr);
  std::printf("\"equal_c\":{\"value\":%u,\"paddr\":%u},", equalC.value, equalC.paddr);
  std::printf("\"fresh_a\":{\"value\":%u,\"paddr\":%u},", freshA.value, freshA.paddr);
  std::printf("\"global_a\":{\"value\":%u,\"paddr\":%u},", globalA.value, globalA.paddr);
  std::printf("\"misses\":{\"start\":%llu,\"first_a\":%llu,\"fault_before\":%llu,\"fault_after\":%llu,\"reactivate_before\":%llu,\"reactivate_after\":%llu,\"equal_before\":%llu,\"equal_after\":%llu,\"fresh_before\":%llu,\"fresh_after\":%llu},",
    (unsigned long long)misses0, (unsigned long long)misses1,
    (unsigned long long)missesBeforeFault, (unsigned long long)missesAfterFault,
    (unsigned long long)missesBeforeReactivate, (unsigned long long)missesAfterReactivate,
    (unsigned long long)missesBeforeEqual, (unsigned long long)missesAfterEqual,
    (unsigned long long)missesBeforeFreshA, (unsigned long long)missesAfterFreshA);
  std::printf("\"initial_tag\":%u,\"equal_tag\":%u,", initialTag, tagAfterEqual);
  std::printf("\"tlbp_context_unchanged\":true,\"same_value_tlbr_unchanged\":true,\"out_of_range_tlbr_unchanged\":true,");
  std::printf("\"installed_entries_unchanged\":true,\"inactive_backing_word\":%u,", OriANew);
  std::printf("\"icache_sha256\":\"%s\"}\n", finalCacheHash.c_str());
  return 0;
}
