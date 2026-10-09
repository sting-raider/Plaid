/* SPDX-License-Identifier: ISC
 * Exact pinned-ares TLBP/TLBR translation-state fixture.
 */
#define main capability_fixture_main
#include "../../spikes/003-ares-oracle/driver.cpp"
#undef main

static constexpr u32 CodePa = 0x00002000;
static constexpr u64 CodePc = 0xffffffffa0002000ull;
static constexpr u32 TlbrOpcode = 0x42000001;
static constexpr u32 TlbpOpcode = 0x42000008;
static constexpr u64 ProbeVa = 0x0000000000004000ull;

static CPU::TLB::Entry make_entry(u64 vbase, u32 pbase, u32 asid, u32 cca, bool global = false) {
  CPU::TLB::Entry e{};
  e.pageMask = 0;
  e.virtualAddress = vbase;
  e.addressSpaceID = asid;
  e.region = vbase >> 62;
  for(u32 half = 0; half < 2; half++) {
    e.global[half] = global;
    e.valid[half] = 1;
    e.dirty[half] = 1;
    e.cacheAlgorithm[half] = cca;
    e.physicalAddress[half] = pbase + half * 0x1000;
  }
  e.synchronize();
  return e;
}

static bool same_entry(const CPU::TLB::Entry& a, const CPU::TLB::Entry& b) {
  for(u32 half = 0; half < 2; half++) {
    if((u64)a.global[half] != (u64)b.global[half]) return false;
    if((u64)a.valid[half] != (u64)b.valid[half]) return false;
    if((u64)a.dirty[half] != (u64)b.dirty[half]) return false;
    if((u64)a.cacheAlgorithm[half] != (u64)b.cacheAlgorithm[half]) return false;
    if((u64)a.physicalAddress[half] != (u64)b.physicalAddress[half]) return false;
  }
  return (u64)a.pageMask == (u64)b.pageMask
      && (u64)a.virtualAddress == (u64)b.virtualAddress
      && (u64)a.addressSpaceID == (u64)b.addressSpaceID
      && (u64)a.region == (u64)b.region
      && (u64)a.globals == (u64)b.globals
      && (u64)a.addressMaskHi == (u64)b.addressMaskHi
      && (u64)a.addressMaskLo == (u64)b.addressMaskLo
      && (u64)a.addressSelect == (u64)b.addressSelect;
}

static std::array<CPU::TLB::Entry, CPU::TLB::Entries> snapshot_entries() {
  std::array<CPU::TLB::Entry, CPU::TLB::Entries> out{};
  for(u32 i = 0; i < CPU::TLB::Entries; i++) out[i] = cpu.tlb.entry[i];
  return out;
}

static u32 changed_slots(const std::array<CPU::TLB::Entry, CPU::TLB::Entries>& before) {
  u32 changed = 0;
  for(u32 i = 0; i < CPU::TLB::Entries; i++) if(!same_entry(before[i], cpu.tlb.entry[i])) changed++;
  return changed;
}

struct CacheSig {
  std::array<int, CPU::TLB::TlbCache::entries> slot{};
  std::array<int, CPU::TLB::TlbCache::entries> frequency{};
};

static CacheSig cache_sig() {
  CacheSig out{};
  for(u32 i = 0; i < CPU::TLB::TlbCache::entries; i++) {
    auto& c = cpu.tlb.tlbCache.entry[i];
    out.slot[i] = c.entry ? (int)(c.entry - &cpu.tlb.entry[0]) : -1;
    out.frequency[i] = c.frequency;
  }
  return out;
}

static bool same_cache(const CacheSig& a, const CacheSig& b) {
  return a.slot == b.slot && a.frequency == b.frequency;
}

struct Translation { bool found; bool cache; u32 paddr; };

static Translation translate(u64 vaddr) {
  auto a = cpu.tlb.load(vaddr, true);
  return {(bool)a, a.cache, a.paddr};
}

static bool same_translation(const Translation& a, const Translation& b) {
  return a.found == b.found && a.cache == b.cache && a.paddr == b.paddr;
}

static bool execute_at(u32 offset) {
  cpu.scc.cause.exceptionCode = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.status.errorLevel = 0;
  cpu.pipeline.setPc(CodePc + offset);
  if(cpu.instruction()) cpu.synchronize();
  return cpu.scc.cause.exceptionCode == 0;
}

int main() {
  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid TLBP TLBR effects fixture");
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
  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.status.privilegeMode = 0;
  cpu.scc.status.kernelExtendedAddressing = 0;
  cpu.context.setMode();
  cpu.context.endian = CPU::Context::Endian::Big;

  const u32 code[] = {TlbpOpcode, TlbpOpcode, TlbrOpcode, TlbrOpcode, TlbrOpcode};
  for(u32 i = 0; i < sizeof(code) / sizeof(code[0]); i++)
    rdram.ram.write<Word>(CodePa + i * 4, code[i], RBusDevice::ARES_DEBUGGER);

  for(u32 i = 0; i < CPU::TLB::Entries; i++)
    cpu.tlb.entry[i] = make_entry(0x00100000ull + (u64)i * 0x2000, 0x00010000u + i * 0x2000, i, 2);
  const auto target = make_entry(ProbeVa, 0x00060000u, 0x55, 2);
  cpu.tlb.entry[9] = target;
  cpu.tlb.entry[17] = target;  // equal-mapping decoy
  cpu.tlb.tlbCache = {};
  cpu.devirtualizeCache = {};

  // Successful TLBP with duplicate equal mappings.
  cpu.scc.tlb = make_entry(ProbeVa, 0x00200000u, 0x55, 2);
  cpu.scc.index.tlbEntry = 23;
  cpu.scc.index.probeFailure = 1;
  cpu.tlb.tlbCache = {};
  auto probeBeforeTranslation = translate(ProbeVa);
  auto probeCacheBefore = cache_sig();
  auto probeEntriesBefore = snapshot_entries();
  cpu.devirtualizeCache = {0x1111222233334444ull, 0x5555666677778888ull};
  if(!execute_at(0)) return 4;
  auto probeCacheAfter = cache_sig();
  u32 probeSlot = cpu.scc.index.tlbEntry;
  bool probeFailure = cpu.scc.index.probeFailure;
  bool probeDevirtSame = cpu.devirtualizeCache.vbase == 0x1111222233334444ull && cpu.devirtualizeCache.pbase == 0x5555666677778888ull;
  u32 probeChanged = changed_slots(probeEntriesBefore);
  bool probeCacheSame = same_cache(probeCacheBefore, probeCacheAfter);
  auto probeAfterTranslation = translate(ProbeVa);
  bool probeTranslationSame = same_translation(probeBeforeTranslation, probeAfterTranslation);
  if(probeSlot != 9 || probeFailure || probeChanged || !probeCacheSame || !probeDevirtSame || !probeTranslationSame) return 5;

  // Failed TLBP. tlbEntry=0 is exact-ares behavior but architecturally undefined.
  cpu.scc.tlb = make_entry(0x003f0000ull, 0x00300000u, 0xe1, 2);
  cpu.scc.index.tlbEntry = 31;
  cpu.scc.index.probeFailure = 0;
  cpu.tlb.tlbCache = {};
  auto missBeforeTranslation = translate(ProbeVa);
  auto missCacheBefore = cache_sig();
  auto missEntriesBefore = snapshot_entries();
  cpu.devirtualizeCache = {0x0102030405060708ull, 0x8877665544332211ull};
  if(!execute_at(4)) return 6;
  auto missCacheAfter = cache_sig();
  u32 missIndex = cpu.scc.index.tlbEntry;
  bool missFailure = cpu.scc.index.probeFailure;
  bool missDevirtSame = cpu.devirtualizeCache.vbase == 0x0102030405060708ull && cpu.devirtualizeCache.pbase == 0x8877665544332211ull;
  u32 missChanged = changed_slots(missEntriesBefore);
  bool missCacheSame = same_cache(missCacheBefore, missCacheAfter);
  auto missAfterTranslation = translate(ProbeVa);
  bool missTranslationSame = same_translation(missBeforeTranslation, missAfterTranslation);
  if(missIndex != 0 || !missFailure || missChanged || !missCacheSame || !missDevirtSame || !missTranslationSame) return 7;

  // Successful TLBR replaces staged CP0 TLB fields, not the mapping array.
  cpu.scc.index.tlbEntry = 9;
  cpu.scc.index.probeFailure = 1;
  cpu.scc.tlb = make_entry(0x00008000ull, 0x00180000u, 0x22, 3);
  cpu.tlb.tlbCache = {};
  auto readBeforeTranslation = translate(ProbeVa);
  auto readCacheBefore = cache_sig();
  auto readEntriesBefore = snapshot_entries();
  cpu.devirtualizeCache = {0x1234123412341234ull, 0x5678567856785678ull};
  if(!execute_at(8)) return 8;
  auto readCacheAfter = cache_sig();
  bool readStagedMatches = same_entry(cpu.scc.tlb, target);
  bool readDevirtSame = cpu.devirtualizeCache.vbase == 0x1234123412341234ull && cpu.devirtualizeCache.pbase == 0x5678567856785678ull;
  u32 readChanged = changed_slots(readEntriesBefore);
  bool readCacheSame = same_cache(readCacheBefore, readCacheAfter);
  auto readAfterTranslation = translate(ProbeVa);
  bool readTranslationSame = same_translation(readBeforeTranslation, readAfterTranslation);
  if(!readStagedMatches || readChanged || !readCacheSame || !readDevirtSame || !readTranslationSame) return 9;

  // Same-value TLBR still executes but produces no staged-value delta.
  cpu.scc.index.tlbEntry = 9;
  cpu.scc.tlb = target;
  auto sameReadEntriesBefore = snapshot_entries();
  auto stagedBefore = cpu.scc.tlb;
  cpu.devirtualizeCache = {0xaaaaaaaa55555555ull, 0x0f0e0d0c0b0a0908ull};
  if(!execute_at(12)) return 10;
  bool sameReadStaged = same_entry(stagedBefore, cpu.scc.tlb);
  bool sameReadDevirtSame = cpu.devirtualizeCache.vbase == 0xaaaaaaaa55555555ull && cpu.devirtualizeCache.pbase == 0x0f0e0d0c0b0a0908ull;
  u32 sameReadChanged = changed_slots(sameReadEntriesBefore);
  if(!sameReadStaged || !sameReadDevirtSame || sameReadChanged) return 11;

  // Out-of-range Index is a no-op for TLBR at this exact pin.
  cpu.scc.index.tlbEntry = 63;
  cpu.scc.tlb = make_entry(0x0000c000ull, 0x001c0000u, 0x33, 2);
  auto rangeStagedBefore = cpu.scc.tlb;
  auto rangeEntriesBefore = snapshot_entries();
  cpu.tlb.tlbCache = {};
  auto rangeBeforeTranslation = translate(ProbeVa);
  auto rangeCacheBefore = cache_sig();
  cpu.devirtualizeCache = {0xfeedfacecafebeefull, 0x0123456789abcdefull};
  if(!execute_at(16)) return 12;
  auto rangeCacheAfter = cache_sig();
  bool rangeStagedSame = same_entry(rangeStagedBefore, cpu.scc.tlb);
  bool rangeDevirtSame = cpu.devirtualizeCache.vbase == 0xfeedfacecafebeefull && cpu.devirtualizeCache.pbase == 0x0123456789abcdefull;
  u32 rangeChanged = changed_slots(rangeEntriesBefore);
  bool rangeCacheSame = same_cache(rangeCacheBefore, rangeCacheAfter);
  auto rangeAfterTranslation = translate(ProbeVa);
  bool rangeTranslationSame = same_translation(rangeBeforeTranslation, rangeAfterTranslation);
  if(!rangeStagedSame || rangeChanged || !rangeCacheSame || !rangeDevirtSame || !rangeTranslationSame) return 13;

  std::printf(
    "{\"probe_slot\":%u,\"probe_failure\":%s,\"probe_entries_changed\":%u,\"probe_cache_unchanged\":%s,\"probe_devirt_unchanged\":%s,\"probe_translation_same\":%s,"
    "\"miss_index\":%u,\"miss_failure\":%s,\"miss_entries_changed\":%u,\"miss_cache_unchanged\":%s,\"miss_devirt_unchanged\":%s,\"miss_translation_same\":%s,"
    "\"tlbr_staged_matches\":%s,\"tlbr_entries_changed\":%u,\"tlbr_cache_unchanged\":%s,\"tlbr_devirt_unchanged\":%s,\"tlbr_translation_same\":%s,"
    "\"same_value_tlbr_staged_same\":%s,\"same_value_tlbr_entries_changed\":%u,\"same_value_tlbr_devirt_unchanged\":%s,"
    "\"oor_tlbr_staged_same\":%s,\"oor_tlbr_entries_changed\":%u,\"oor_tlbr_cache_unchanged\":%s,\"oor_tlbr_devirt_unchanged\":%s,\"oor_tlbr_translation_same\":%s}\n",
    probeSlot, probeFailure ? "true" : "false", probeChanged, probeCacheSame ? "true" : "false", probeDevirtSame ? "true" : "false", probeTranslationSame ? "true" : "false",
    missIndex, missFailure ? "true" : "false", missChanged, missCacheSame ? "true" : "false", missDevirtSame ? "true" : "false", missTranslationSame ? "true" : "false",
    readStagedMatches ? "true" : "false", readChanged, readCacheSame ? "true" : "false", readDevirtSame ? "true" : "false", readTranslationSame ? "true" : "false",
    sameReadStaged ? "true" : "false", sameReadChanged, sameReadDevirtSame ? "true" : "false",
    rangeStagedSame ? "true" : "false", rangeChanged, rangeCacheSame ? "true" : "false", rangeDevirtSame ? "true" : "false", rangeTranslationSame ? "true" : "false");
  return 0;
}
