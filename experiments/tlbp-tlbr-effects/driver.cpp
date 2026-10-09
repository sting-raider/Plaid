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

struct Translation {
  bool found = false;
  bool cache = false;
  u32 paddr = 0;
};

static Translation translate(u64 vaddr) {
  auto a = cpu.tlb.load(vaddr, true);
  return {(bool)a, a.cache, a.paddr};
}

static bool same_translation(const Translation& a, const Translation& b) {
  return a.found == b.found && a.cache == b.cache && a.paddr == b.paddr;
}

static bool execute_at(u32 codeOffset) {
  cpu.scc.cause.exceptionCode = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.status.errorLevel = 0;
  cpu.pipeline.setPc(CodePc + codeOffset);
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
  cpu.scc.status.enable.coprocessor0 = 1;
  cpu.context.setMode();
  cpu.context.endian = CPU::Context::Endian::Big;

  const u32 code[] = {TlbpOpcode, TlbpOpcode, TlbrOpcode, TlbrOpcode, TlbrOpcode};
  for(u32 i = 0; i < sizeof(code) / sizeof(code[0]); i++)
    rdram.ram.write<Word>(CodePa + i * 4, code[i], RBusDevice::ARES_DEBUGGER);

  for(u32 i = 0; i < CPU::TLB::Entries; i++)
    cpu.tlb.entry[i] = make_entry(0x00100000ull + (u64)i * 0x2000, 0x00010000u + i * 0x2000, i, 2);

  const auto target = make_entry(ProbeVa, 0x00060000u, 0x55, 2);
  cpu.tlb.entry[9] = target;
  cpu.tlb.entry[17] = target;  // equal-mapping decoy; TLBP must return first matching slot.
  cpu.tlb.tlbCache = {};
  cpu.devirtualizeCache = {};

  // Successful TLBP. Prime the translation cache first, then compare it before
  // and immediately after the instruction. The later translation check happens
  // only after that cache snapshot so its frequency increment cannot mask an
  // instruction-side effect.
  cpu.scc.tlb = make_entry(ProbeVa, 0x00200000u, 0x55, 2);
  cpu.scc.index.tlbEntry = 23;
  cpu.scc.index.probeFailure = 1;
  cpu.tlb.tlbCache = {};
  auto probeBeforeTranslation = translate(ProbeVa);
  auto probeCacheBefore = cache_sig();
  auto probeEntriesBefore = snapshot_entries();
  cpu.devirtualizeCache.vbase = 0x1111222233334444ull;
  cpu.devirtualizeCache.pbase = 0x5555666677778888ull;
  if(!execute_at(0)) return 4;
  auto probeCacheAfter = cache_sig();
  bool probeDevirtSame = cpu.devirtualizeCache.vbase == 0x1111222233334444ull
                      && cpu.devirtualizeCache.pbase == 0x5555666677778888ull;
  if((u32)cpu.scc.index.tlbEntry != 9 || (bool)cpu.scc.index.probeFailure) return 5;
  if(changed_slots(probeEntriesBefore) != 0) return 6;
  if(!same_cache(probeCacheBefore, probeCacheAfter)) return 7;
  auto probeAfterTranslation = translate(ProbeVa);
  if(!same_translation(probeBeforeTranslation, probeAfterTranslation)) return 8;

  // Failed TLBP. The exact ares implementation documents tlbEntry=0 as
  // technically undefined on miss, but probeFailure is authoritative. No TLB
  // entry/cache/devirtualization state may change.
  cpu.scc.tlb = make_entry(0x003f0000ull, 0x00300000u, 0xe1, 2);
  cpu.scc.index.tlbEntry = 31;
  cpu.scc.index.probeFailure = 0;
  cpu.tlb.tlbCache = {};
  auto missBeforeTranslation = translate(ProbeVa);
  auto missCacheBefore = cache_sig();
  auto missEntriesBefore = snapshot_entries();
  cpu.devirtualizeCache.vbase = 0x0102030405060708ull;
  cpu.devirtualizeCache.pbase = 0x8877665544332211ull;
  if(!execute_at(4)) return 9;
  auto missCacheAfter = cache_sig();
  bool missDevirtSame = cpu.devirtualizeCache.vbase == 0x0102030405060708ull
                     && cpu.devirtualizeCache.pbase == 0x8877665544332211ull;
  if(!(bool)cpu.scc.index.probeFailure || (u32)cpu.scc.index.tlbEntry != 0) return 10;
  if(changed_slots(missEntriesBefore) != 0) return 11;
  if(!same_cache(missCacheBefore, missCacheAfter)) return 12;
  auto missAfterTranslation = translate(ProbeVa);
  if(!same_translation(missBeforeTranslation, missAfterTranslation)) return 13;

  // Successful TLBR with deliberately misleading staged CP0 TLB fields.
  cpu.scc.index.tlbEntry = 9;
  cpu.scc.index.probeFailure = 1;
  cpu.scc.tlb = make_entry(0x00008000ull, 0x00180000u, 0x22, 3);
  cpu.tlb.tlbCache = {};
  auto readBeforeTranslation = translate(ProbeVa);
  auto readCacheBefore = cache_sig();
  auto readEntriesBefore = snapshot_entries();
  cpu.devirtualizeCache.vbase = 0x1234123412341234ull;
  cpu.devirtualizeCache.pbase = 0x5678567856785678ull;
  if(!execute_at(8)) return 14;
  auto readCacheAfter = cache_sig();
  bool readDevirtSame = cpu.devirtualizeCache.vbase == 0x1234123412341234ull
                     && cpu.devirtualizeCache.pbase == 0x5678567856785678ull;
  if(!same_entry(cpu.scc.tlb, target)) return 15;
  if(changed_slots(readEntriesBefore) != 0) return 16;
  if(!same_cache(readCacheBefore, readCacheAfter)) return 17;
  auto readAfterTranslation = translate(ProbeVa);
  if(!same_translation(readBeforeTranslation, readAfterTranslation)) return 18;

  // Same-value TLBR must remain a real CP0 operation without becoming a mapping
  // generation merely because the staged fields happen already to match.
  cpu.scc.index.tlbEntry = 9;
  cpu.scc.tlb = target;
  auto sameReadEntriesBefore = snapshot_entries();
  auto stagedBefore = cpu.scc.tlb;
  cpu.devirtualizeCache.vbase = 0xaaaaaaaa55555555ull;
  cpu.devirtualizeCache.pbase = 0x0f0e0d0c0b0a0908ull;
  if(!execute_at(12)) return 19;
  bool sameReadStaged = same_entry(stagedBefore, cpu.scc.tlb);
  bool sameReadDevirtSame = cpu.devirtualizeCache.vbase == 0xaaaaaaaa55555555ull
                         && cpu.devirtualizeCache.pbase == 0x0f0e0d0c0b0a0908ull;
  if(!sameReadStaged || changed_slots(sameReadEntriesBefore) != 0) return 20;

  // Out-of-range Index is a no-op for TLBR at this exact pin.
  cpu.scc.index.tlbEntry = 63;
  cpu.scc.tlb = make_entry(0x0000c000ull, 0x001c0000u, 0x33, 2);
  auto outOfRangeStaged = cpu.scc.tlb;
  auto outOfRangeEntriesBefore = snapshot_entries();
  cpu.tlb.tlbCache = {};
  auto rangeBeforeTranslation = translate(ProbeVa);
  auto rangeCacheBefore = cache_sig();
  cpu.devirtualizeCache.vbase = 0xfeedfacecafebeefull;
  cpu.devirtualizeCache.pbase = 0x0123456789abcdefull;
  if(!execute_at(16)) return 21;
  auto rangeCacheAfter = cache_sig();
  bool rangeDevirtSame = cpu.devirtualizeCache.vbase == 0xfeedfacecafebeefull
                      && cpu.devirtualizeCache.pbase == 0x0123456789abcdefull;
  if(!same_entry(outOfRangeStaged, cpu.scc.tlb)) return 22;
  if(changed_slots(outOfRangeEntriesBefore) != 0) return 23;
  if(!same_cache(rangeCacheBefore, rangeCacheAfter)) return 24;
  auto rangeAfterTranslation = translate(ProbeVa);
  if(!same_translation(rangeBeforeTranslation, rangeAfterTranslation)) return 25;

  std::printf("{\"probe_slot\":%u,\"probe_failure\":%s,\"probe_entries_changed\":0,\"probe_cache_unchanged\":%s,\"probe_devirt_unchanged\":%s,\"probe_translation_same\":%s,\"miss_index\":%u,\"miss_failure\":%s,\"miss_entries_changed\":0,\"miss_cache_unchanged\":%s,\"miss_devirt_unchanged\":%s,\"miss_translation_same\":%s,\"tlbr_staged_matches\":%s,\"tlbr_entries_changed\":0,\"tlbr_cache_unchanged\":%s,\"tlbr_devirt_unchanged\":%s,\"tlbr_translation_same\":%s,\"same_value_tlbr_staged_same\":%s,\"same_value_tlbr_devirt_unchanged\":%s,\"oor_tlbr_staged_same\":%s,\"oor_tlbr_entries_changed\":0,\"oor_tlbr_cache_unchanged\":%s,\"oor_tlbr_devirt_unchanged\":%s,\"oor_tlbr_translation_same\":%s}\n",
    (u32)9,
    (bool)cpu.scc.index.probeFailure ? "true" : "false",
    same_cache(probeCacheBefore, probeCacheAfter) ? "true" : "false",
    probeDevirtSame ? "true" : "false",
    same_translation(probeBeforeTranslation, probeAfterTranslation) ? "true" : "false",
    (u32)0,
    "true",
    same_cache(missCacheBefore, missCacheAfter) ? "true" : "false",
    missDevirtSame ? "true" : "false",
    same_translation(missBeforeTranslation, missAfterTranslation) ? "true" : "false",
    same_entry(cpu.tlb.entry[9], target) ? "true" : "false",
    same_cache(readCacheBefore, readCacheAfter) ? "true" : "false",
    readDevirtSame ? "true" : "false",
    same_translation(readBeforeTranslation, readAfterTranslation) ? "true" : "false",
    sameReadStaged ? "true" : "false",
    sameReadDevirtSame ? "true" : "false",
    same_entry(outOfRangeStaged, cpu.scc.tlb) ? "true" : "false",
    same_cache(rangeCacheBefore, rangeCacheAfter) ? "true" : "false",
    rangeDevirtSame ? "true" : "false",
    same_translation(rangeBeforeTranslation, rangeAfterTranslation) ? "true" : "false");
  return 0;
}
