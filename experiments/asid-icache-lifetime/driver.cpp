/* SPDX-License-Identifier: ISC
 * Compose EntryHi/ASID translation context with cacheable TLB I-cache residency.
 */
#define main capability_fixture_main
#include "../../spikes/003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>
#include <cstdio>
#include <string>
#include <vector>

static constexpr u64 VaSwitch = 0x00004000ull;
static constexpr u64 VaGlobal = 0x00006000ull;  // different virtual I-cache index
static constexpr u32 PaA = 0x001000;
static constexpr u32 PaB = 0x003000;
static constexpr u32 PaEqual = 0x005000;
static constexpr u32 PaGlobal = 0x007000;
static constexpr u32 DirectPa = 0x010000;
static constexpr u64 DirectVa = 0xffff'ffff'a001'0000ull;

static constexpr u32 OriAOld = 0x34091111;   // ori t1,zero,0x1111
static constexpr u32 OriB = 0x34092222;      // ori t1,zero,0x2222
static constexpr u32 OriANew = 0x34094444;   // ori t1,zero,0x4444
static constexpr u32 OriGlobal = 0x340a7777; // ori t2,zero,0x7777
static constexpr u32 Mtc0T0EntryHi = 0x40885000;

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
  entry.cacheAlgorithm[0] = entry.cacheAlgorithm[1] = 3; // cacheable
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

static bool execute_mtc0_entryhi(u32 asid) {
  rdram.ram.write<Word>(DirectPa + 0, Mtc0T0EntryHi, RBusDevice::ARES_DEBUGGER);
  rdram.ram.write<Word>(DirectPa + 4, 0, RBusDevice::ARES_DEBUGGER);
  rdram.ram.write<Word>(DirectPa + 8, 0, RBusDevice::ARES_DEBUGGER);
  rdram.ram.write<Word>(DirectPa + 12, 0, RBusDevice::ARES_DEBUGGER);
  cpu.ipu.r[8].u64 = (VaSwitch & ~0x1fffull) | (asid & 0xff);
  cpu.pipeline.setPc(DirectVa);
  for(u32 i = 0; i < 4; i++) {
    if(cpu.instruction()) cpu.synchronize();
  }
  return cpu.scc.cause.exceptionCode == 0 && (u32)cpu.scc.tlb.addressSpaceID == (asid & 0xff);
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

static void append_be(std::vector<u8>& out, u64 value, u32 width) {
  for(u32 i = width; i > 0; --i) out.push_back(value >> (8 * (i - 1)));
}

int main() {
  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid ASID I-cache lifetime fixture");
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
  put(PaA, OriAOld);
  put(PaB, OriB);
  put(PaEqual, OriAOld);  // equal payload, distinct backing
  put(PaGlobal, OriGlobal);

  install_tlb(0, VaSwitch, PaA, 0x11, false);
  install_tlb(1, VaSwitch, PaB, 0x22, false);
  install_tlb(2, VaSwitch, PaEqual, 0x33, false);
  install_tlb(3, VaGlobal, PaGlobal, 0x77, true);
  const std::string installed = installed_snapshot();

  const u32 idxSwitch = (u32)(VaSwitch >> 5 & 0x1ff);
  const u32 idxGlobal = (u32)(VaGlobal >> 5 & 0x1ff);
  if(idxSwitch == idxGlobal) return 4;

  reset_exception();
  if(!execute_mtc0_entryhi(0x11) || installed_snapshot() != installed) return 5;
  u64 misses0 = cpu.profile.icacheMisses;
  auto firstA = fetch_switch();
  u64 misses1 = cpu.profile.icacheMisses;
  if(firstA.exception || firstA.value != 0x1111 || firstA.paddr != PaA || misses1 != misses0 + 1) return 6;
  auto& line = cpu.icache.line(VaSwitch);
  u32 initialTag = line.tagKey;
  u32 initialWord = line.words[0];
  if(!line.valid() || initialWord != OriAOld) return 7;

  // Switch away by context only. No installed TLB entry or I-cache line changes.
  reset_exception();
  if(!execute_mtc0_entryhi(0x22) || installed_snapshot() != installed) return 8;
  if(line.tagKey != initialTag || line.words[0] != initialWord || !line.valid()) return 9;

  // Mutate A backing while ASID B is active. Then execute unrelated global code
  // at another virtual cache index so the A resident line remains untouched.
  put(PaA, OriANew);
  auto globalB = fetch_global();
  if(globalB.exception || globalB.value != 0x7777 || globalB.paddr != PaGlobal) return 10;
  if(line.tagKey != initialTag || line.words[0] != initialWord || !line.valid()) return 11;

  // Same-value context write is a new writer event even though CP0 snapshot is equal.
  const u64 entryhiBeforeSame = cpu.getControlRegister(10);
  reset_exception();
  if(!execute_mtc0_entryhi(0x22)) return 12;
  const u64 entryhiAfterSame = cpu.getControlRegister(10);
  if(entryhiBeforeSame != entryhiAfterSame || installed_snapshot() != installed) return 13;
  if(line.tagKey != initialTag || line.words[0] != initialWord || !line.valid()) return 14;

  // Unmatched ASID faults before an instruction-cache fill and must not destroy A.
  reset_exception();
  if(!execute_mtc0_entryhi(0x44)) return 15;
  u64 missesBeforeFault = cpu.profile.icacheMisses;
  auto fault = fetch_switch();
  u64 missesAfterFault = cpu.profile.icacheMisses;
  if(fault.exception != 2 || fault.badvaddr != VaSwitch || missesAfterFault != missesBeforeFault) return 16;
  if(line.tagKey != initialTag || line.words[0] != initialWord || !line.valid()) return 17;

  // Reactivate A. Its old resident tag still matches translated PA-A, so exact ares
  // must hit stale bytes even though current PA-A backing has changed to 0x4444.
  reset_exception();
  if(!execute_mtc0_entryhi(0x11)) return 18;
  u64 missesBeforeReactivate = cpu.profile.icacheMisses;
  auto staleA = fetch_switch();
  u64 missesAfterReactivate = cpu.profile.icacheMisses;
  if(staleA.exception || staleA.value != 0x1111 || staleA.paddr != PaA) return 19;
  if(missesAfterReactivate != missesBeforeReactivate) return 20;
  if(rdram.ram.read<Word>(PaA, RBusDevice::ARES_DEBUGGER) != OriANew) return 21;

  // Equal bytes at a different physical backing are not the same resident generation.
  // ASID C selects PA-Equal, forcing a physical-tag miss/refill despite payload equality.
  reset_exception();
  if(!execute_mtc0_entryhi(0x33)) return 22;
  u32 tagBeforeEqual = line.tagKey;
  u64 missesBeforeEqual = cpu.profile.icacheMisses;
  auto equalC = fetch_switch();
  u64 missesAfterEqual = cpu.profile.icacheMisses;
  u32 tagAfterEqual = line.tagKey;
  if(equalC.exception || equalC.value != 0x1111 || equalC.paddr != PaEqual) return 23;
  if(missesAfterEqual != missesBeforeEqual + 1) return 24;
  if((tagBeforeEqual & ~1u) == (tagAfterEqual & ~1u)) return 25;

  // C's fill replaced A. Returning to A now misses and finally observes current A backing.
  reset_exception();
  if(!execute_mtc0_entryhi(0x11)) return 26;
  u64 missesBeforeFreshA = cpu.profile.icacheMisses;
  auto freshA = fetch_switch();
  u64 missesAfterFreshA = cpu.profile.icacheMisses;
  if(freshA.exception || freshA.value != 0x4444 || freshA.paddr != PaA) return 27;
  if(missesAfterFreshA != missesBeforeFreshA + 1) return 28;

  auto globalA = fetch_global();
  if(globalA.exception || globalA.value != 0x7777 || globalA.paddr != PaGlobal) return 29;
  if(installed_snapshot() != installed) return 30;

  std::vector<u8> cacheBytes;
  for(const auto& cacheLine : cpu.icache.lines) {
    append_be(cacheBytes, cacheLine.tagKey, 4);
    append_be(cacheBytes, cacheLine.index, 2);
    for(u32 word : cacheLine.words) append_be(cacheBytes, word, 4);
  }
  auto cacheHash = nall::Hash::SHA256(std::span<const u8>{cacheBytes.data(), cacheBytes.size()}).digest();

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
  std::printf("\"same_value_entryhi_unchanged\":true,\"installed_entries_unchanged\":true,\"inactive_backing_word\":%u,", OriANew);
  std::printf("\"icache_sha256\":\"%s\"}\n", cacheHash.data());
  return 0;
}
