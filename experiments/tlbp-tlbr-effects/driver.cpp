/* SPDX-License-Identifier: ISC
 * Exact pinned-ares TLBP/TLBR translation-context fixture.
 */
#define main capability_fixture_main
#include "../../spikes/003-ares-oracle/driver.cpp"
#undef main

static constexpr u32 CodePa = 0x00002000;
static constexpr u64 CodePc = 0xffffffffa0002000ull;
static constexpr u32 TlbrOpcode = 0x42000001;
static constexpr u32 TlbpOpcode = 0x42000008;
static constexpr u64 ProbeVa = 0x0000000000004000ull;
static constexpr u32 ProbePa = 0x00060000u;
static constexpr u8 ProbeAsid = 0x55;

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

  const u32 code[] = {TlbpOpcode, TlbpOpcode, TlbrOpcode, TlbrOpcode, TlbrOpcode, TlbrOpcode};
  for(u32 i = 0; i < sizeof(code) / sizeof(code[0]); i++)
    rdram.ram.write<Word>(CodePa + i * 4, code[i], RBusDevice::ARES_DEBUGGER);

  for(u32 i = 0; i < CPU::TLB::Entries; i++)
    cpu.tlb.entry[i] = make_entry(0x00100000ull + (u64)i * 0x2000, 0x00010000u + i * 0x2000, i, 2);
  const auto target = make_entry(ProbeVa, ProbePa, ProbeAsid, 2);
  cpu.tlb.entry[9] = target;
  cpu.tlb.entry[17] = target;  // equal-mapping decoy; probe must return first match
  cpu.tlb.tlbCache = {};
  cpu.devirtualizeCache = {};

  // TLBP hit: Index changes, active ASID and translation do not.
  cpu.scc.tlb = target;
  cpu.scc.index.tlbEntry = 23;
  cpu.scc.index.probeFailure = 1;
  cpu.tlb.tlbCache = {};
  auto probeBefore = translate(ProbeVa);
  auto probeCacheBefore = cache_sig();
  auto probeEntriesBefore = snapshot_entries();
  cpu.devirtualizeCache = {0x1111222233334444ull, 0x5555666677778888ull};
  if(!execute_at(0)) return 4;
  auto probeCacheAfter = cache_sig();
  auto probeAfter = translate(ProbeVa);
  bool probeOkay = (u32)cpu.scc.index.tlbEntry == 9
                && !(bool)cpu.scc.index.probeFailure
                && (u32)cpu.scc.tlb.addressSpaceID == ProbeAsid
                && changed_slots(probeEntriesBefore) == 0
                && same_cache(probeCacheBefore, probeCacheAfter)
                && cpu.devirtualizeCache.vbase == 0x1111222233334444ull
                && cpu.devirtualizeCache.pbase == 0x5555666677778888ull
                && same_translation(probeBefore, probeAfter);
  if(!probeOkay) return 5;

  // TLBP miss: exact ares sets Index.tlbEntry=0 plus probeFailure=1, but does
  // not change the staged EntryHi ASID or the translation result.
  cpu.scc.tlb = make_entry(0x003f0000ull, 0x00300000u, 0xe1, 2);
  cpu.scc.index.tlbEntry = 31;
  cpu.scc.index.probeFailure = 0;
  cpu.tlb.tlbCache = {};
  auto missBefore = translate(ProbeVa);
  auto missCacheBefore = cache_sig();
  auto missEntriesBefore = snapshot_entries();
  cpu.devirtualizeCache = {0x0102030405060708ull, 0x8877665544332211ull};
  if(!execute_at(4)) return 6;
  auto missCacheAfter = cache_sig();
  auto missAfter = translate(ProbeVa);
  bool missOkay = (u32)cpu.scc.index.tlbEntry == 0
               && (bool)cpu.scc.index.probeFailure
               && (u32)cpu.scc.tlb.addressSpaceID == 0xe1
               && changed_slots(missEntriesBefore) == 0
               && same_cache(missCacheBefore, missCacheAfter)
               && cpu.devirtualizeCache.vbase == 0x0102030405060708ull
               && cpu.devirtualizeCache.pbase == 0x8877665544332211ull
               && same_translation(missBefore, missAfter);
  if(!missOkay) return 7;

  // Decisive counterexample: TLBR does not mutate the TLB mapping array or
  // caches, but loading EntryHi from slot 9 changes active ASID 0x22 -> 0x55.
  // The exact same non-global VA therefore flips from no translation to ProbePa.
  cpu.scc.index.tlbEntry = 9;
  cpu.scc.tlb = make_entry(0x00008000ull, 0x00180000u, 0x22, 3);
  cpu.tlb.tlbCache = {};
  auto enableBefore = translate(ProbeVa);
  auto enableCacheBefore = cache_sig();
  auto enableEntriesBefore = snapshot_entries();
  cpu.devirtualizeCache = {0x1234123412341234ull, 0x5678567856785678ull};
  if(!execute_at(8)) return 8;
  auto enableCacheAfterInstruction = cache_sig();
  u32 enableAsidAfter = cpu.scc.tlb.addressSpaceID;
  auto enableAfter = translate(ProbeVa);
  bool enableCounterexample = !enableBefore.found
                           && enableAfter.found
                           && enableAfter.paddr == ProbePa
                           && enableAsidAfter == ProbeAsid
                           && same_entry(cpu.scc.tlb, target)
                           && changed_slots(enableEntriesBefore) == 0
                           && same_cache(enableCacheBefore, enableCacheAfterInstruction)
                           && cpu.devirtualizeCache.vbase == 0x1234123412341234ull
                           && cpu.devirtualizeCache.pbase == 0x5678567856785678ull;
  if(!enableCounterexample) return 9;

  // Reverse counterexample: start with ASID 0x55 (ProbeVa resolves), then TLBR
  // slot 10 whose ASID is 10. The same mapping entries remain installed, but
  // ProbeVa becomes unavailable for the new active address space.
  cpu.scc.tlb = target;
  cpu.scc.index.tlbEntry = 10;
  cpu.tlb.tlbCache = {};
  auto disableBefore = translate(ProbeVa);
  auto disableCacheBefore = cache_sig();
  auto disableEntriesBefore = snapshot_entries();
  cpu.devirtualizeCache = {0x9999888877776666ull, 0x5555444433332222ull};
  if(!execute_at(12)) return 10;
  auto disableCacheAfterInstruction = cache_sig();
  u32 disableAsidAfter = cpu.scc.tlb.addressSpaceID;
  auto disableAfter = translate(ProbeVa);
  bool disableCounterexample = disableBefore.found
                            && disableBefore.paddr == ProbePa
                            && !disableAfter.found
                            && disableAsidAfter == 10
                            && same_entry(cpu.scc.tlb, cpu.tlb.entry[10])
                            && changed_slots(disableEntriesBefore) == 0
                            && same_cache(disableCacheBefore, disableCacheAfterInstruction)
                            && cpu.devirtualizeCache.vbase == 0x9999888877776666ull
                            && cpu.devirtualizeCache.pbase == 0x5555444433332222ull;
  if(!disableCounterexample) return 11;

  // Same-value TLBR: if staged EntryHi/EntryLo/PageMask already equal slot 9,
  // translation remains stable and there is still no mapping-entry generation.
  cpu.scc.index.tlbEntry = 9;
  cpu.scc.tlb = target;
  cpu.tlb.tlbCache = {};
  auto sameBefore = translate(ProbeVa);
  auto sameCacheBefore = cache_sig();
  auto sameEntriesBefore = snapshot_entries();
  cpu.devirtualizeCache = {0xaaaaaaaa55555555ull, 0x0f0e0d0c0b0a0908ull};
  if(!execute_at(16)) return 12;
  auto sameCacheAfterInstruction = cache_sig();
  auto sameAfter = translate(ProbeVa);
  bool sameOkay = same_translation(sameBefore, sameAfter)
               && same_entry(cpu.scc.tlb, target)
               && changed_slots(sameEntriesBefore) == 0
               && same_cache(sameCacheBefore, sameCacheAfterInstruction)
               && cpu.devirtualizeCache.vbase == 0xaaaaaaaa55555555ull
               && cpu.devirtualizeCache.pbase == 0x0f0e0d0c0b0a0908ull;
  if(!sameOkay) return 13;

  // Out-of-range TLBR Index=63 is an exact-pin no-op.
  cpu.scc.index.tlbEntry = 63;
  cpu.scc.tlb = make_entry(0x0000c000ull, 0x001c0000u, 0x22, 2);
  auto rangeStagedBefore = cpu.scc.tlb;
  cpu.tlb.tlbCache = {};
  auto rangeBefore = translate(ProbeVa);
  auto rangeCacheBefore = cache_sig();
  auto rangeEntriesBefore = snapshot_entries();
  cpu.devirtualizeCache = {0xfeedfacecafebeefull, 0x0123456789abcdefull};
  if(!execute_at(20)) return 14;
  auto rangeCacheAfter = cache_sig();
  auto rangeAfter = translate(ProbeVa);
  bool rangeOkay = same_entry(rangeStagedBefore, cpu.scc.tlb)
                && same_translation(rangeBefore, rangeAfter)
                && changed_slots(rangeEntriesBefore) == 0
                && same_cache(rangeCacheBefore, rangeCacheAfter)
                && cpu.devirtualizeCache.vbase == 0xfeedfacecafebeefull
                && cpu.devirtualizeCache.pbase == 0x0123456789abcdefull;
  if(!rangeOkay) return 15;

  std::printf(
    "{\"tlbp_hit_slot\":9,\"tlbp_hit_translation_same\":true,\"tlbp_miss_index\":0,\"tlbp_miss_translation_same\":true,"
    "\"tlbr_enable_before_found\":%s,\"tlbr_enable_after_found\":%s,\"tlbr_enable_after_paddr\":%u,\"tlbr_enable_asid_after\":%u,"
    "\"tlbr_disable_before_found\":%s,\"tlbr_disable_after_found\":%s,\"tlbr_disable_asid_after\":%u,"
    "\"all_mapping_entry_changes\":0,\"all_instruction_cache_snapshots_unchanged\":true,\"all_devirtualize_sentinels_unchanged\":true,"
    "\"same_value_tlbr_translation_same\":true,\"out_of_range_tlbr_translation_same\":true}\n",
    enableBefore.found ? "true" : "false", enableAfter.found ? "true" : "false", enableAfter.paddr, enableAsidAfter,
    disableBefore.found ? "true" : "false", disableAfter.found ? "true" : "false", disableAsidAfter);
  return 0;
}
