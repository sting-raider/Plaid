/* SPDX-License-Identifier: ISC
 * Exact pinned-ares TLBWI mapping-generation fixture.
 */
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main

static constexpr u32 CodePa = 0x00002000;
static constexpr u64 CodePc = 0xffffffffa0002000ull;
static constexpr u64 UserCodePc = 0x0000000000004000ull;
static constexpr u32 TlbwiOpcode = 0x42000002;

static CPU::TLB::Entry make_entry(u64 vbase, u32 pbase, u32 asid, u32 cca, bool global = false) {
  CPU::TLB::Entry e{};
  e.pageMask = 0;
  e.virtualAddress = vbase;
  e.addressSpaceID = asid;
  e.region = vbase >> 62;
  for(u32 half = 0; half < 2; half++) {
    e.global[half] = global ? 1 : 0;
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

static u32 execute_one(u64 pc) {
  cpu.scc.cause.exceptionCode = 0;
  cpu.pipeline.setPc(pc);
  if(cpu.instruction()) cpu.synchronize();
  return (u32)cpu.scc.cause.exceptionCode;
}

static void kernel_mode() {
  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.status.privilegeMode = 0;
  cpu.scc.status.enable.coprocessor0 = 1;
  cpu.context.setMode();
  cpu.context.endian = CPU::Context::Endian::Big;
}

int main() {
  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid TLBWI mapping generation fixture");
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
  kernel_mode();

  for(u32 off = 0; off < 0x100; off += 4)
    rdram.ram.write<Word>(CodePa + off, TlbwiOpcode, RBusDevice::ARES_DEBUGGER);

  for(u32 i = 0; i < CPU::TLB::Entries; i++)
    cpu.tlb.entry[i] = make_entry(0x00100000ull + (u64)i * 0x2000, 0x00010000u + i * 0x2000, i, 2);
  cpu.tlb.tlbCache = {};
  cpu.devirtualizeCache = {};

  const auto target = make_entry(0x00008000ull, 0x00060000u, 0x55, 2);
  cpu.tlb.entry[7] = target;  // equal-payload decoy in a different slot.
  cpu.scc.tlb = target;
  cpu.scc.index.tlbEntry = 5;
  cpu.devirtualizeCache.vbase = 0x1111222233334444ull;
  cpu.devirtualizeCache.pbase = 0x5555666677778888ull;

  // Changed-value TLBWI: CP0 Index selects slot 5, not the equal payload at 7.
  auto beforeChange = snapshot();
  if(execute_one(CodePc) != 0) return 4;
  auto firstChanged = changed_slots(beforeChange);
  if(firstChanged.size() != 1 || firstChanged[0] != 5) return 5;
  if(!same_entry(cpu.tlb.entry[5], target) || !same_entry(cpu.tlb.entry[7], target)) return 6;
  if((u32)cpu.scc.index.tlbEntry != 5) return 7;
  bool firstCacheCleared = cpu.devirtualizeCache.vbase == 0 && cpu.devirtualizeCache.pbase == 0;
  if(!firstCacheCleared) return 8;

  // Same-value TLBWI: the instruction still traverses the legal write path and
  // clears devirtualization state, but a complete pre/post TLB snapshot is equal.
  // Therefore snapshot inequality cannot be the mapping-generation witness.
  cpu.scc.tlb = cpu.tlb.entry[5];
  cpu.scc.index.tlbEntry = 5;
  cpu.devirtualizeCache.vbase = 0xaaaaaaaa55555555ull;
  cpu.devirtualizeCache.pbase = 0x123456789abcdef0ull;
  auto beforeSame = snapshot();
  if(execute_one(CodePc + 4) != 0) return 9;
  auto sameChanged = changed_slots(beforeSame);
  if(!sameChanged.empty()) return 10;
  bool sameCacheCleared = cpu.devirtualizeCache.vbase == 0 && cpu.devirtualizeCache.pbase == 0;
  if(!sameCacheCleared) return 11;

  // Out-of-range Index returns before the TLB write/cache-clear boundary.
  cpu.scc.tlb = make_entry(0x0000c000ull, 0x00080000u, 0x66, 2);
  cpu.scc.index.tlbEntry = 63;
  cpu.devirtualizeCache.vbase = 0x1111111122222222ull;
  cpu.devirtualizeCache.pbase = 0x3333333344444444ull;
  auto beforeOob = snapshot();
  if(execute_one(CodePc + 8) != 0) return 12;
  auto oobChanged = changed_slots(beforeOob);
  if(!oobChanged.empty()) return 13;
  bool oobCachePreserved = cpu.devirtualizeCache.vbase == 0x1111111122222222ull
                        && cpu.devirtualizeCache.pbase == 0x3333333344444444ull;
  if(!oobCachePreserved) return 14;

  // User-mode CU0-disabled control. Fetch the real opcode through a global,
  // uncached TLB entry so the privilege failure belongs to TLBWI, not the fetch.
  kernel_mode();
  cpu.tlb.entry[31] = make_entry(UserCodePc, CodePa, 0, 2, true);
  cpu.tlb.tlbCache = {};
  cpu.scc.tlb = target;
  cpu.scc.index.tlbEntry = 6;
  auto beforePrivilege = snapshot();
  cpu.scc.status.privilegeMode = 2;
  cpu.scc.status.enable.coprocessor0 = 0;
  cpu.context.setMode();
  cpu.context.endian = CPU::Context::Endian::Big;
  u32 privilegeException = execute_one(UserCodePc);
  auto privilegeChanged = changed_slots(beforePrivilege);
  if(privilegeException != 11) return 15;
  if(!privilegeChanged.empty()) return 16;

  std::printf("{\"first_changed_slot\":%u,\"same_value_changed_count\":%zu,\"slot5_equals_slot7\":%s,", firstChanged[0], sameChanged.size(), same_entry(cpu.tlb.entry[5], target) && same_entry(cpu.tlb.entry[7], target) ? "true" : "false");
  std::printf("\"first_cache_cleared\":%s,\"same_cache_cleared\":%s,\"oob_changed_count\":%zu,\"oob_cache_preserved\":%s,", firstCacheCleared ? "true" : "false", sameCacheCleared ? "true" : "false", oobChanged.size(), oobCachePreserved ? "true" : "false");
  std::printf("\"privilege_exception\":%u,\"privilege_changed_count\":%zu}\n", privilegeException, privilegeChanged.size());
  return 0;
}
