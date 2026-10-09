/* SPDX-License-Identifier: ISC
 * Exact pinned-ares TLBWR mapping-generation fixture.
 */
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main

static constexpr u32 CodePa = 0x00002000;
static constexpr u64 CodePc = 0xffffffffa0002000ull;
static constexpr u32 TlbwrOpcode = 0x42000006;

static CPU::TLB::Entry make_entry(u64 vbase, u32 pbase, u32 asid, u32 cca) {
  CPU::TLB::Entry e{};
  e.pageMask = 0;
  e.virtualAddress = vbase;
  e.addressSpaceID = asid;
  e.region = vbase >> 62;
  for(u32 half = 0; half < 2; half++) {
    e.global[half] = 0;
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

static std::array<CPU::TLB::Entry, CPU::TLB::Entries> snapshot() {
  std::array<CPU::TLB::Entry, CPU::TLB::Entries> out{};
  for(u32 i = 0; i < CPU::TLB::Entries; i++) out[i] = cpu.tlb.entry[i];
  return out;
}

static std::vector<u32> changed_slots(const std::array<CPU::TLB::Entry, CPU::TLB::Entries>& before) {
  std::vector<u32> out;
  for(u32 i = 0; i < CPU::TLB::Entries; i++) if(!same_entry(before[i], cpu.tlb.entry[i])) out.push_back(i);
  return out;
}

static bool execute_tlbwr(u32 codeOffset) {
  cpu.scc.cause.exceptionCode = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.pipeline.setPc(CodePc + codeOffset);
  if(cpu.instruction()) cpu.synchronize();
  return cpu.scc.cause.exceptionCode == 0;
}

int main() {
  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid TLBWR mapping generation fixture");
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

  for(u32 off = 0; off < 0x100; off += 4)
    rdram.ram.write<Word>(CodePa + off, TlbwrOpcode, RBusDevice::ARES_DEBUGGER);

  // Make every initial slot distinguishable. Slot 7 will then be replaced with
  // an equal-payload decoy for the first real TLBWR.
  for(u32 i = 0; i < CPU::TLB::Entries; i++)
    cpu.tlb.entry[i] = make_entry(0x00100000ull + (u64)i * 0x2000, 0x00010000u + i * 0x2000, i, 2);
  cpu.tlb.tlbCache = {};
  cpu.devirtualizeCache = {};

  const auto target = make_entry(0x00004000ull, 0x00060000u, 0x55, 2);
  cpu.tlb.entry[7] = target; // equal mapping decoy at the misleading CP0 Index.
  cpu.scc.tlb = target;
  cpu.scc.index.tlbEntry = 7;
  cpu.scc.wired.index = 31; // getControlRandom() must select slot 31.
  cpu.devirtualizeCache.vbase = 0x1111222233334444ull;
  cpu.devirtualizeCache.pbase = 0x5555666677778888ull;

  auto beforeChange = snapshot();
  if(!execute_tlbwr(0)) return 4;
  auto firstChanged = changed_slots(beforeChange);
  if(firstChanged.size() != 1 || firstChanged[0] != 31) return 5;
  if(!same_entry(cpu.tlb.entry[31], target) || !same_entry(cpu.tlb.entry[7], target)) return 6;
  if((u32)cpu.scc.index.tlbEntry != 7) return 7;
  bool firstCacheCleared = cpu.devirtualizeCache.vbase == 0 && cpu.devirtualizeCache.pbase == 0;
  if(!firstCacheCleared) return 8;

  // Same-value rewrite: the real TLBWR still executes, Wired=31 still selects
  // slot 31, and the devirtualization cache is still cleared, but a pre/post
  // TLB snapshot contains no changed slot. A snapshot diff therefore cannot
  // mint a complete mapping-generation history.
  cpu.scc.tlb = cpu.tlb.entry[31];
  cpu.scc.index.tlbEntry = 7;
  cpu.devirtualizeCache.vbase = 0xaaaaaaaa55555555ull;
  cpu.devirtualizeCache.pbase = 0x123456789abcdef0ull;
  auto beforeSame = snapshot();
  if(!execute_tlbwr(4)) return 9;
  auto sameChanged = changed_slots(beforeSame);
  if(!sameChanged.empty()) return 10;
  if((u32)cpu.scc.index.tlbEntry != 7) return 11;
  bool sameCacheCleared = cpu.devirtualizeCache.vbase == 0 && cpu.devirtualizeCache.pbase == 0;
  if(!sameCacheCleared) return 12;

  // Wider replacement range. Every staged entry is unique, so snapshot diff is
  // allowed here only as an observation of which concrete slot changed. The
  // source contract says getControlRandom() must keep every selection >= Wired.
  std::vector<u32> selected;
  cpu.scc.wired.index = 30;
  cpu.scc.index.tlbEntry = 5;
  for(u32 i = 0; i < 32; i++) {
    cpu.scc.tlb = make_entry(0x00200000ull + (u64)i * 0x2000, 0x00100000u + i * 0x2000, 0x80 + i, 2);
    auto before = snapshot();
    if(!execute_tlbwr(8 + (i % 30) * 4)) return 13;
    auto changed = changed_slots(before);
    if(changed.size() != 1) return 14;
    if(changed[0] < 30 || changed[0] > 31) return 15;
    if((u32)cpu.scc.index.tlbEntry != 5) return 16;
    selected.push_back(changed[0]);
  }

  std::printf("{\"first_changed_slot\":%u,\"same_value_changed_count\":%zu,\"index_after_first\":%u,\"index_after_range\":%u,\"slot7_equals_slot31\":%s,\"first_cache_cleared\":%s,\"same_cache_cleared\":%s,\"range\":[",
    firstChanged[0], sameChanged.size(), (u32)7, (u32)cpu.scc.index.tlbEntry,
    same_entry(cpu.tlb.entry[7], target) ? "true" : "false",
    firstCacheCleared ? "true" : "false", sameCacheCleared ? "true" : "false");
  for(size_t i = 0; i < selected.size(); i++) {
    if(i) std::printf(",");
    std::printf("%u", selected[i]);
  }
  std::printf("]}\n");
  return 0;
}
