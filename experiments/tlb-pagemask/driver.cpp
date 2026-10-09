/* SPDX-License-Identifier: ISC
 * Large-PageMask TLB uncached-fetch provenance fixture for pinned ares.
 */
#ifndef PLAID_RDRAM_FETCH_SENSOR
#define PLAID_RDRAM_FETCH_SENSOR 1
#endif
#define main capability_fixture_main
#include "../../spikes/003-ares-oracle/driver.cpp"
#undef main
#include <cstdlib>
#include <nall/hash/sha256.hpp>
#if PLAID_RDRAM_FETCH_SENSOR
#include "observer.hpp"
#endif

static constexpr u32 Mask4K  = 0;
static constexpr u32 Mask16K = 0b11u << 13;
static constexpr u32 Mask64K = 0b1111u << 13;

static constexpr u64 Va4K       = 0x00004000ull;
static constexpr u64 Va16Even   = 0x00021000ull;
static constexpr u64 Va16Odd    = 0x0002c000ull;
static constexpr u64 Va64Even   = 0x00045000ull;
static constexpr u64 Va64Odd    = 0x00070000ull;
static constexpr u64 VaGlobal   = 0x00084000ull;
static constexpr u64 VaAsidFail = 0x00089000ull;
static constexpr u64 VaInvalid  = 0x00091000ull;

static constexpr u32 Ori4K     = 0x34091111;
static constexpr u32 Ori16Even = 0x340a2222;
static constexpr u32 Ori16Odd  = 0x340b3333;
static constexpr u32 Ori64Even = 0x340c4444;
static constexpr u32 Ori64Odd  = 0x340d5555;
static constexpr u32 OriGlobal = 0x340e6666;
static constexpr u32 OriFail   = 0x340f7777;

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

static void write_tlb(u32 index, u32 pageMask, u64 vbase, u32 pbase0, u32 pbase1,
                      u32 cca, u32 entryAsid, bool global,
                      bool valid0 = true, bool valid1 = true) {
  CPU::TLB::Entry entry{};
  entry.pageMask = pageMask;
  entry.virtualAddress = vbase;
  entry.addressSpaceID = entryAsid;
  entry.region = vbase >> 62;
  entry.global[0] = global;
  entry.global[1] = global;
  entry.valid[0] = valid0;
  entry.valid[1] = valid1;
  entry.dirty[0] = true;
  entry.dirty[1] = true;
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
  frontend.cartPak->setAttribute("title", "Plaid TLB PageMask fixture");
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

  // Phase 1: ordinary 4 KiB control. Fixed-bit-12 and PageMask-aware geometry agree.
  put(0x001000, Ori4K);
  write_tlb(0, Mask4K, 0x00004000, 0x001000, 0x002000, 2, 7, false);
  u32 select4k = cpu.tlb.entry[0].addressSelect;
  cpu.ipu.r[9].u64 = 0;
  set_current_asid(7);
  execute_one(1, Va4K, traced);
  if(cpu.scc.cause.exceptionCode != 0 || cpu.ipu.r[9].u32 != 0x1111) return 5;

  // Phase 2: 16 KiB even page with bit 12 set. Actual selector is bit 14.
  // Put the same instruction at the fixed-4KiB guess so value equality cannot expose the mistake.
  put(0x011000, Ori16Even);
  put(0x020000, Ori16Even);
  write_tlb(1, Mask16K, 0x00020000, 0x010000, 0x020000, 2, 7, false);
  u32 select16k = cpu.tlb.entry[1].addressSelect;
  u32 normalized16k = cpu.tlb.entry[1].pageMask;
  cpu.ipu.r[10].u64 = 0;
  execute_one(2, Va16Even, traced);
  if(cpu.scc.cause.exceptionCode != 0 || cpu.ipu.r[10].u32 != 0x2222) return 6;

  // Phase 3: 16 KiB odd page with bit 12 clear. Fixed-4KiB guessing picks EntryLo0.
  put(0x030000, Ori16Odd);
  put(0x040000, Ori16Odd);
  write_tlb(2, Mask16K, 0x00028000, 0x030000, 0x040000, 2, 7, false);
  cpu.ipu.r[11].u64 = 0;
  execute_one(3, Va16Odd, traced);
  if(cpu.scc.cause.exceptionCode != 0 || cpu.ipu.r[11].u32 != 0x3333) return 7;

  // Phase 4: 64 KiB even page. Actual offset includes 0x5000 and selector is bit 16.
  put(0x055000, Ori64Even);
  put(0x070000, Ori64Even);
  write_tlb(3, Mask64K, 0x00040000, 0x050000, 0x070000, 2, 7, false);
  u32 select64k = cpu.tlb.entry[3].addressSelect;
  u32 normalized64k = cpu.tlb.entry[3].pageMask;
  cpu.ipu.r[12].u64 = 0;
  execute_one(4, Va64Even, traced);
  if(cpu.scc.cause.exceptionCode != 0 || cpu.ipu.r[12].u32 != 0x4444) return 8;

  // Phase 5: 64 KiB odd page with bit 12 clear. Again place an equal-value decoy at the naive PFN.
  put(0x080000, Ori64Odd);
  put(0x0a0000, Ori64Odd);
  write_tlb(4, Mask64K, 0x00060000, 0x080000, 0x0a0000, 2, 7, false);
  cpu.ipu.r[13].u64 = 0;
  execute_one(5, Va64Odd, traced);
  if(cpu.scc.cause.exceptionCode != 0 || cpu.ipu.r[13].u32 != 0x5555) return 9;

  // Phase 6: global 16 KiB odd mapping remains valid across an ASID mismatch.
  put(0x0c0000, OriGlobal);
  put(0x0d0000, OriGlobal);
  write_tlb(5, Mask16K, 0x00080000, 0x0c0000, 0x0d0000, 2, 1, true);
  set_current_asid(99);
  cpu.ipu.r[14].u64 = 0;
  execute_one(6, VaGlobal, traced);
  if(cpu.scc.cause.exceptionCode != 0 || cpu.ipu.r[14].u32 != 0x6666) return 10;

  // Phase 7: the same large-page shape without global bits fails before CPU::fetch.
  reset_exception();
  put(0x0e1000, OriFail);
  put(0x0f0000, OriFail);
  write_tlb(6, Mask16K, 0x00088000, 0x0e0000, 0x0f0000, 2, 1, false);
  set_current_asid(99);
  execute_one(7, VaAsidFail, traced);
  u32 asidException = cpu.scc.cause.exceptionCode;
  u64 asidBadVaddr = cpu.scc.badVirtualAddress;
  if(asidException != 2 || asidBadVaddr != VaAsidFail) return 11;

  // Phase 8: actual large-page even half is invalid while the bit-12-selected odd half is valid.
  // A fixed-4KiB selector would incorrectly fabricate a successful fetch from the decoy EntryLo1.
  reset_exception();
  put(0x101000, OriFail);
  put(0x110000, OriFail);
  write_tlb(7, Mask16K, 0x00090000, 0x100000, 0x110000, 2, 7, false, false, true);
  set_current_asid(7);
  execute_one(8, VaInvalid, traced);
  u32 invalidException = cpu.scc.cause.exceptionCode;
  u64 invalidBadVaddr = cpu.scc.badVirtualAddress;
  if(invalidException != 2 || invalidBadVaddr != VaInvalid) return 12;
  set_fetch_observers(false);

  std::vector<u8> cpuBytes;
  for(const auto& reg : cpu.ipu.r) append_be(cpuBytes, reg.u64, 8);
  append_be(cpuBytes, cpu.ipu.hi.u64, 8);
  append_be(cpuBytes, cpu.ipu.lo.u64, 8);
  append_be(cpuBytes, cpu.ipu.pc, 8);
  append_be(cpuBytes, cpu.effectiveCount(), 8);
  append_be(cpuBytes, cpu.scc.cause.exceptionCode, 4);
  append_be(cpuBytes, cpu.scc.badVirtualAddress, 8);
  auto cpuHash = nall::Hash::SHA256(std::span<const u8>{cpuBytes.data(), cpuBytes.size()}).digest();
  auto ramHash = nall::Hash::SHA256(std::span<const u8>{rdram.ram.data, rdram.ram.size}).digest();

  std::printf("{");
#if PLAID_RDRAM_FETCH_SENSOR
  plaid_print_rdram_fetch_events();
#else
  std::printf("\"scalar_events\":[],\"fetch_events\":[]");
#endif
  std::printf(",\"facts\":{\"v4k\":%u,\"v16_even\":%u,\"v16_odd\":%u,\"v64_even\":%u,\"v64_odd\":%u,\"vglobal\":%u,\"select4k\":%u,\"select16k\":%u,\"select64k\":%u,\"mask16k\":%u,\"mask64k\":%u,\"asid_exception\":%u,\"asid_badvaddr\":%llu,\"invalid_exception\":%u,\"invalid_badvaddr\":%llu}",
    cpu.ipu.r[9].u32, cpu.ipu.r[10].u32, cpu.ipu.r[11].u32, cpu.ipu.r[12].u32,
    cpu.ipu.r[13].u32, cpu.ipu.r[14].u32,
    select4k, select16k, select64k, normalized16k, normalized64k,
    asidException, (unsigned long long)asidBadVaddr,
    invalidException, (unsigned long long)invalidBadVaddr);
  std::printf(",\"state\":{\"cpu_sha256\":\"%s\",\"ram_sha256\":\"%s\",\"count\":%llu}}\n",
    cpuHash.data(), ramHash.data(), (unsigned long long)cpu.effectiveCount());
  return 0;
}
