/* SPDX-License-Identifier: ISC
 * Exact-pinned ares MTC0 EntryHi/ASID translation-context fixture.
 */
#define main capability_fixture_main
#include "../../spikes/003-ares-oracle/driver.cpp"
#undef main

#include <cstdio>
#include <string>
#include <vector>

static constexpr u64 VaSwitch = 0x00004000ull;
static constexpr u64 VaGlobal = 0x00008000ull;
static constexpr u32 PaA = 0x001000;
static constexpr u32 PaB = 0x003000;
static constexpr u32 PaEqual = 0x005000;
static constexpr u32 PaGlobal = 0x007000;
static constexpr u32 DirectPa = 0x010000;
static constexpr u64 DirectVa = 0xffff'ffff'a001'0000ull;

static constexpr u32 OriT1A = 0x34091111;
static constexpr u32 OriT1B = 0x34092222;
static constexpr u32 OriT2G = 0x340a7777;
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
  entry.global[0] = global;
  entry.global[1] = global;
  entry.valid[0] = entry.valid[1] = 1;
  entry.dirty[0] = entry.dirty[1] = 1;
  entry.cacheAlgorithm[0] = entry.cacheAlgorithm[1] = 2;
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
      "%u:%llx:%llx:%u:%u:%u:%u:%u:%u:%u:%u:%u:%u:%u:%u:%llx:%llx:%llx:%llx:%llx;",
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
      (u32)e.addressSelect,
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

int main() {
  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid MTC0 EntryHi ASID fixture");
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
  put(PaA, OriT1A);
  put(PaB, OriT1B);
  put(PaEqual, OriT1A);
  put(PaGlobal, OriT2G);

  install_tlb(0, VaSwitch, PaA, 0x11, false);
  install_tlb(1, VaSwitch, PaB, 0x22, false);
  install_tlb(2, VaSwitch, PaEqual, 0x33, false);
  install_tlb(3, VaGlobal, PaGlobal, 0x77, true);
  const std::string installed = installed_snapshot();

  reset_exception();
  if(!execute_mtc0_entryhi(0x11)) return 4;
  if(installed_snapshot() != installed) return 5;
  auto a = fetch_switch();
  if(a.exception || a.value != 0x1111 || a.paddr != PaA) return 6;

  reset_exception();
  if(!execute_mtc0_entryhi(0x22)) return 7;
  if(installed_snapshot() != installed) return 8;
  auto b = fetch_switch();
  if(b.exception || b.value != 0x2222 || b.paddr != PaB) return 9;

  reset_exception();
  if(!execute_mtc0_entryhi(0x33)) return 10;
  if(installed_snapshot() != installed) return 11;
  auto equal1 = fetch_switch();
  if(equal1.exception || equal1.value != 0x1111 || equal1.paddr != PaEqual) return 12;

  const u64 staged_before_same = cpu.getControlRegister(10);
  reset_exception();
  if(!execute_mtc0_entryhi(0x33)) return 13;
  const u64 staged_after_same = cpu.getControlRegister(10);
  if(staged_after_same != staged_before_same) return 14;
  if(installed_snapshot() != installed) return 15;
  auto equal2 = fetch_switch();
  if(equal2.exception || equal2.value != 0x1111 || equal2.paddr != PaEqual) return 16;

  reset_exception();
  if(!execute_mtc0_entryhi(0x22)) return 17;
  auto global_b = fetch_global();
  if(global_b.exception || global_b.value != 0x7777 || global_b.paddr != PaGlobal) return 18;
  reset_exception();
  if(!execute_mtc0_entryhi(0x11)) return 19;
  auto global_a = fetch_global();
  if(global_a.exception || global_a.value != 0x7777 || global_a.paddr != PaGlobal) return 20;
  if(installed_snapshot() != installed) return 21;

  reset_exception();
  if(!execute_mtc0_entryhi(0x44)) return 22;
  auto miss = fetch_switch();
  if(miss.exception != 2 || miss.badvaddr != VaSwitch) return 23;
  if(installed_snapshot() != installed) return 24;

  std::printf(
    "{\"a\":{\"value\":%u,\"paddr\":%u},"
    "\"b\":{\"value\":%u,\"paddr\":%u},"
    "\"equal1\":{\"value\":%u,\"paddr\":%u},"
    "\"equal2\":{\"value\":%u,\"paddr\":%u},"
    "\"global_b\":{\"value\":%u,\"paddr\":%u},"
    "\"global_a\":{\"value\":%u,\"paddr\":%u},"
    "\"miss\":{\"exception\":%u,\"badvaddr\":%llu},"
    "\"same_value_entryhi_unchanged\":true,"
    "\"installed_entries_unchanged\":true,"
    "\"mtc0_writes\":7}\n",
    a.value, a.paddr, b.value, b.paddr,
    equal1.value, equal1.paddr, equal2.value, equal2.paddr,
    global_b.value, global_b.paddr, global_a.value, global_a.paddr,
    miss.exception, (unsigned long long)miss.badvaddr);
  return 0;
}
