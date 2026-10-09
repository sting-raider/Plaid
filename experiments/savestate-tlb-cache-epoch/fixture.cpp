/* SPDX-License-Identifier: ISC
 * Composed savestate restore epoch fixture for exact pinned ares.
 */
#define main capability_fixture_main
#include "../../spikes/003-ares-oracle/driver.cpp"
#undef main
#include <cstdlib>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#if defined(PLAID_CACHE_FILL_CONTEXT)
#include "../../spikes/012-ares-cache-fill/observer.hpp"
#endif

static constexpr u64 Va = 0x00004000ull;
static constexpr u32 PaA = 0x001000;
static constexpr u32 PaB = 0x003000;
static constexpr u32 DirectPa = 0x010000;
static constexpr u64 DirectVa = 0xffff'ffff'a001'0000ull;
static constexpr u32 InstA = 0x34091111; // ori t1,zero,0x1111
static constexpr u32 InstB = 0x34092222; // ori t1,zero,0x2222
static constexpr u32 Mtc0T0EntryHi = 0x40885000;

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

static void install_tlb(u32 index, u32 pbase, u32 asid) {
  CPU::TLB::Entry entry{};
  entry.pageMask = 0;
  entry.virtualAddress = Va;
  entry.addressSpaceID = asid;
  entry.region = Va >> 62;
  entry.global[0] = entry.global[1] = 0;
  entry.valid[0] = entry.valid[1] = 1;
  entry.dirty[0] = entry.dirty[1] = 1;
  entry.cacheAlgorithm[0] = entry.cacheAlgorithm[1] = 3;
  entry.physicalAddress[0] = pbase;
  entry.physicalAddress[1] = pbase + 0x1000;
  cpu.scc.index.tlbEntry = index;
  cpu.scc.tlb = entry;
  cpu.TLBWI();
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
  cpu.ipu.r[8].u64 = (Va & ~0x1fffull) | (asid & 0xff);
  cpu.pipeline.setPc(DirectVa);
  for(u32 i = 0; i < 4; i++) {
    if(cpu.instruction()) cpu.synchronize();
  }
  return cpu.scc.cause.exceptionCode == 0 && (u32)cpu.scc.tlb.addressSpaceID == (asid & 0xff);
}

static u32 execute_one(u64 pc) {
  reset_exception();
  cpu.ipu.r[9].u64 = 0;
  cpu.pipeline.setPc(pc);
  if(cpu.instruction()) cpu.synchronize();
  if(cpu.scc.cause.exceptionCode != 0) std::abort();
  return cpu.ipu.r[9].u32;
}

static std::string mapping_signature() {
  const auto& e = cpu.tlb.entry[0];
  char out[256];
  std::snprintf(out, sizeof(out), "%llx:%u:%u:%u:%u:%llx:%llx:%llx",
    (unsigned long long)e.virtualAddress,
    (u32)e.addressSpaceID,
    (u32)e.valid[0], (u32)e.valid[1],
    (u32)e.cacheAlgorithm[0],
    (unsigned long long)e.physicalAddress[0],
    (unsigned long long)e.physicalAddress[1],
    (unsigned long long)e.pageMask);
  return out;
}

static std::string cache_signature() {
  const auto& line = cpu.icache.line(Va);
  char part[64];
  std::string out;
  std::snprintf(part, sizeof(part), "%u:%u", line.tagKey, line.index);
  out += part;
  for(u32 word : line.words) {
    std::snprintf(part, sizeof(part), ":%u", word);
    out += part;
  }
  return out;
}

int main(int argc, char** argv) {
  if(argc != 2 || (std::strcmp(argv[1], "plain") && std::strcmp(argv[1], "traced"))) return 2;
  bool traced = !std::strcmp(argv[1], "traced");
  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid savestate TLB cache epoch fixture");
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
#if defined(PLAID_CACHE_FILL_CONTEXT)
  plaidCacheFillObserver = traced ? cache_fill_observer : nullptr;
#endif

  auto put = [](u32 address, u32 word) {
    rdram.ram.write<Word>(address, word, RBusDevice::ARES_DEBUGGER);
  };
  put(PaA, InstA);
  put(PaB, InstB);

  // External research histories deliberately live outside the serialized CPU.
  u64 mappingGeneration = 0;
  u64 contextGeneration = 0;
  u64 restoreEpoch = 0;

  // S0: one mapping generation, one EntryHi context generation, one cache fill.
  install_tlb(0, PaA, 0x11); mappingGeneration++;
  reset_exception();
  if(!execute_mtc0_entryhi(0x11)) return 5;
  contextGeneration++;
  if(execute_one(Va) != 0x1111) return 6;
#if defined(PLAID_CACHE_FILL_CONTEXT)
  if(traced && cacheFills.size() != 1) return 7;
#endif
  const std::string s0Mapping = mapping_signature();
  const u64 s0EntryHi = cpu.getControlRegister(10);
  const std::string s0Cache = cache_signature();
  const u32 s0Tag = cpu.icache.line(Va).tagKey;
  auto saved = ares::Nintendo64::system.serialize(true);

  // S1-distinct: newer mapping/context/cache generations with visibly different state.
  install_tlb(0, PaB, 0x22); mappingGeneration++;
  reset_exception();
  if(!execute_mtc0_entryhi(0x22)) return 8;
  contextGeneration++;
  if(execute_one(Va) != 0x2222) return 9;
#if defined(PLAID_CACHE_FILL_CONTEXT)
  if(traced && cacheFills.size() != 2) return 10;
#endif
  if(mapping_signature() == s0Mapping || cpu.getControlRegister(10) == s0EntryHi || cache_signature() == s0Cache) return 11;

  // Restore S0. The external generation histories must not silently rewind.
  const u64 mapBeforeRestore1 = mappingGeneration;
  const u64 ctxBeforeRestore1 = contextGeneration;
#if defined(PLAID_CACHE_FILL_CONTEXT)
  const u64 fillsBeforeRestore1 = traced ? cacheFills.size() : 0;
#endif
  serializer replay1(saved.data(), saved.size());
  if(!ares::Nintendo64::system.unserialize(replay1)) return 12;
  restoreEpoch++;
  if(mappingGeneration != mapBeforeRestore1 || contextGeneration != ctxBeforeRestore1) return 13;
#if defined(PLAID_CACHE_FILL_CONTEXT)
  if(traced && cacheFills.size() != fillsBeforeRestore1) return 14;
#endif
  if(mapping_signature() != s0Mapping || cpu.getControlRegister(10) != s0EntryHi || cache_signature() != s0Cache) return 15;
  if((u32)cpu.scc.tlb.addressSpaceID != 0x11 || cpu.tlb.entry[0].physicalAddress[0] != PaA) return 16;
  if(cpu.icache.line(Va).words[0] != InstA || cpu.icache.line(Va).tagKey != s0Tag) return 17;
  if(execute_one(Va) != 0x1111) return 18;
#if defined(PLAID_CACHE_FILL_CONTEXT)
  if(traced && cacheFills.size() != fillsBeforeRestore1) return 19;
#endif

  // Equal-state adversary. Mint newer same-value mapping/context generations and
  // an exact equal-tuple cache-fill generation, then restore S0 again.
  install_tlb(0, PaA, 0x11); mappingGeneration++;
  reset_exception();
  if(!execute_mtc0_entryhi(0x11)) return 20;
  contextGeneration++;
  if(mapping_signature() != s0Mapping || cpu.getControlRegister(10) != s0EntryHi) return 21;
  cpu.icache.line(Va).setValid(false);
  if(execute_one(Va) != 0x1111) return 22;
  if(cache_signature() != s0Cache) return 23;
#if defined(PLAID_CACHE_FILL_CONTEXT)
  if(traced && cacheFills.size() != 3) return 24;
#endif

  const u64 mapBeforeRestore2 = mappingGeneration;
  const u64 ctxBeforeRestore2 = contextGeneration;
#if defined(PLAID_CACHE_FILL_CONTEXT)
  const u64 fillsBeforeRestore2 = traced ? cacheFills.size() : 0;
#endif
  serializer replay2(saved.data(), saved.size());
  if(!ares::Nintendo64::system.unserialize(replay2)) return 25;
  restoreEpoch++;
  if(mappingGeneration != mapBeforeRestore2 || contextGeneration != ctxBeforeRestore2) return 26;
#if defined(PLAID_CACHE_FILL_CONTEXT)
  if(traced && cacheFills.size() != fillsBeforeRestore2) return 27;
#endif
  if(mapping_signature() != s0Mapping || cpu.getControlRegister(10) != s0EntryHi || cache_signature() != s0Cache) return 28;

  u64 naiveFill = 0;
#if defined(PLAID_CACHE_FILL_CONTEXT)
  if(traced) {
    const auto& line = cpu.icache.line(Va);
    naiveFill = cache_fill_for_fetch((u32)(Va >> 5 & 0x1ff), PaA, line.index, line.words);
    if(naiveFill != 3) return 29;
  }
#endif
  if(execute_one(Va) != 0x1111) return 30;
#if defined(PLAID_CACHE_FILL_CONTEXT)
  if(traced && cacheFills.size() != fillsBeforeRestore2) return 31;
#endif

  std::printf("{\"naive_post_restore_fill\":%llu,\"fill_count\":%llu,",
    (unsigned long long)naiveFill,
    (unsigned long long)
#if defined(PLAID_CACHE_FILL_CONTEXT)
      (traced ? cacheFills.size() : 0)
#else
      0
#endif
  );
  std::printf("\"external_generations\":{\"mapping\":%llu,\"context\":%llu,\"restore_epoch\":%llu},",
    (unsigned long long)mappingGeneration,
    (unsigned long long)contextGeneration,
    (unsigned long long)restoreEpoch);
  std::printf("\"state\":{\"entryhi\":%llu,\"asid\":%u,\"tlb_pa0\":%llu,\"cache_tag\":%u,\"cache_word0\":%u,\"t1\":%u,\"exception\":%u,\"distinct_rollback\":true,\"equal_state_restore\":true}}\n",
    (unsigned long long)cpu.getControlRegister(10),
    (u32)cpu.scc.tlb.addressSpaceID,
    (unsigned long long)cpu.tlb.entry[0].physicalAddress[0],
    cpu.icache.line(Va).tagKey,
    cpu.icache.line(Va).words[0],
    cpu.ipu.r[9].u32,
    (u32)cpu.scc.cause.exceptionCode);
  return 0;
}
