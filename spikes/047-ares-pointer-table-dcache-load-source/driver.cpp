/* SPDX-License-Identifier: ISC
 * Controlled cacheable pointer-table load-source fixture for exact pinned ares.
 */
#ifndef PLAID_TABLE_LOAD_SENSOR
#define PLAID_TABLE_LOAD_SENSOR 1
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>
#if PLAID_TABLE_LOAD_SENSOR
#include "observer.hpp"
#endif

static constexpr u32 Table = 0x2000;
static constexpr u32 Conflict = 0x4000;  // same D-cache index as Table
static constexpr u32 Code = 0x6000;
static constexpr u32 TargetA = 0x7000;
static constexpr u32 TargetB = 0x7100;
static constexpr u32 TargetC = 0x7200;
static constexpr u32 PtrA = 0x80007000;
static constexpr u32 PtrB = 0x80007100;
static constexpr u32 PtrC = 0x80007200;

#if PLAID_TABLE_LOAD_SENSOR
struct DReadEvent {
  u64 ordinal, pc, vaddr, value, fillPc, dirtyPc;
  u32 paddr, bytes, tag;
  u16 index, dirty;
  bool hitBefore;
};
struct DWriteEvent : DReadEvent {};
struct ScalarEvent {
  u64 ordinal, pc, value;
  u32 address, bytes, device;
  bool write;
};
struct BurstEvent {
  u64 ordinal, pc;
  u32 address, bytes, device, words[8];
  bool write;
};
static u64 eventOrdinal = 0;
static std::vector<DReadEvent> dreads;
static std::vector<DWriteEvent> dwrites;
static std::vector<ScalarEvent> scalars;
static std::vector<BurstEvent> bursts;

static void observe_dread(u64 pc, u64 vaddr, u32 paddr, u32 bytes, u64 value,
  u32 tag, u16 index, u16 dirty, u64 fillPc, u64 dirtyPc, bool hitBefore) {
  dreads.push_back({++eventOrdinal, pc, vaddr, value, fillPc, dirtyPc,
    paddr, bytes, tag, index, dirty, hitBefore});
}
static void observe_dwrite(u64 pc, u64 vaddr, u32 paddr, u32 bytes, u64 value,
  u32 tag, u16 index, u16 dirty, u64 fillPc, u64 dirtyPc, bool hitBefore) {
  DWriteEvent e;
  static_cast<DReadEvent&>(e) = {++eventOrdinal, pc, vaddr, value, fillPc, dirtyPc,
    paddr, bytes, tag, index, dirty, hitBefore};
  dwrites.push_back(e);
}
static void observe_scalar(bool write, u32 address, u32 bytes, u32 device, u64 value) {
  scalars.push_back({++eventOrdinal, cpu.ipu.pc, value, address, bytes, device, write});
}
static void observe_burst(bool write, u32 address, u32 bytes, u32 device, const u32* words) {
  if((bytes != ICache && bytes != DCache) || (address & (bytes - 1))) std::abort();
  BurstEvent e{++eventOrdinal, cpu.ipu.pc, address, bytes, device, {}, write};
  for(u32 lane = 0; lane < bytes / 4; lane++) e.words[lane] = words[lane];
  bursts.push_back(e);
}

static void enable_observers(bool enabled) {
  plaidDcacheReadObserver = enabled ? observe_dread : nullptr;
  plaidDcacheWriteObserver = enabled ? observe_dwrite : nullptr;
  plaidRdramScalarObserver = enabled ? observe_scalar : nullptr;
  plaidRdramBurstObserver = enabled ? observe_burst : nullptr;
}
#else
static void enable_observers(bool) {}
#endif

static u32 backing_word(u32 address) {
#if PLAID_TABLE_LOAD_SENSOR
  auto saved = plaidRdramScalarObserver;
  plaidRdramScalarObserver = nullptr;
#endif
  u32 value = rdram.ram.read<Word>(address, RBusDevice::ARES_DEBUGGER);
#if PLAID_TABLE_LOAD_SENSOR
  plaidRdramScalarObserver = saved;
#endif
  return value;
}

static void append_be(std::vector<u8>& bytes, u64 value, u32 width) {
  for(u32 i = width; i > 0; i--) bytes.push_back(value >> (8 * (i - 1)));
}

#if PLAID_TABLE_LOAD_SENSOR
static void print_events() {
  std::printf("\"dreads\":[");
  for(size_t i = 0; i < dreads.size(); i++) {
    const auto& e = dreads[i];
    std::printf("%s{\"ordinal\":%llu,\"pc\":%llu,\"vaddr\":%llu,\"paddr\":%u,\"bytes\":%u,\"value\":%llu,\"tag\":%u,\"index\":%u,\"dirty\":%u,\"fill_pc\":%llu,\"dirty_pc\":%llu,\"hit_before\":%s}",
      i ? "," : "", (unsigned long long)e.ordinal, (unsigned long long)e.pc,
      (unsigned long long)e.vaddr, e.paddr, e.bytes, (unsigned long long)e.value,
      e.tag, (u32)e.index, (u32)e.dirty, (unsigned long long)e.fillPc,
      (unsigned long long)e.dirtyPc, e.hitBefore ? "true" : "false");
  }
  std::printf("],\"dwrites\":[");
  for(size_t i = 0; i < dwrites.size(); i++) {
    const auto& e = dwrites[i];
    std::printf("%s{\"ordinal\":%llu,\"pc\":%llu,\"vaddr\":%llu,\"paddr\":%u,\"bytes\":%u,\"value\":%llu,\"tag\":%u,\"index\":%u,\"dirty\":%u,\"fill_pc\":%llu,\"dirty_pc\":%llu,\"hit_before\":%s}",
      i ? "," : "", (unsigned long long)e.ordinal, (unsigned long long)e.pc,
      (unsigned long long)e.vaddr, e.paddr, e.bytes, (unsigned long long)e.value,
      e.tag, (u32)e.index, (u32)e.dirty, (unsigned long long)e.fillPc,
      (unsigned long long)e.dirtyPc, e.hitBefore ? "true" : "false");
  }
  std::printf("],\"scalars\":[");
  for(size_t i = 0; i < scalars.size(); i++) {
    const auto& e = scalars[i];
    std::printf("%s{\"ordinal\":%llu,\"pc\":%llu,\"write\":%s,\"address\":%u,\"bytes\":%u,\"device\":%u,\"uncached_cpu\":%s,\"value\":%llu}",
      i ? "," : "", (unsigned long long)e.ordinal, (unsigned long long)e.pc,
      e.write ? "true" : "false", e.address, e.bytes, e.device,
      e.device == (u32)RBusDevice::VR4300_UNCACHED ? "true" : "false",
      (unsigned long long)e.value);
  }
  std::printf("],\"bursts\":[");
  for(size_t i = 0; i < bursts.size(); i++) {
    const auto& e = bursts[i];
    std::printf("%s{\"ordinal\":%llu,\"pc\":%llu,\"write\":%s,\"address\":%u,\"bytes\":%u,\"device\":%u,\"dcache\":%s,\"icache\":%s,\"words\":[",
      i ? "," : "", (unsigned long long)e.ordinal, (unsigned long long)e.pc,
      e.write ? "true" : "false", e.address, e.bytes, e.device,
      e.device == (u32)RBusDevice::VR4300_DCACHE ? "true" : "false",
      e.device == (u32)RBusDevice::VR4300_ICACHE ? "true" : "false");
    for(u32 lane = 0; lane < e.bytes / 4; lane++) std::printf("%s%u", lane ? "," : "", e.words[lane]);
    std::printf("]}");
  }
  std::printf("]");
}
#else
static void print_events() {
  std::printf("\"dreads\":[],\"dwrites\":[],\"scalars\":[],\"bursts\":[]");
}
#endif

int main(int argc, char** argv) {
  if(argc != 3 || (strcmp(argv[1], "plain") && strcmp(argv[1], "traced"))) return 2;
  bool traced = !strcmp(argv[1], "traced");
  const char* scenario = argv[2];
  bool stale = !strcmp(scenario, "stale");
  bool same = !strcmp(scenario, "same");
  bool refill = !strcmp(scenario, "refill");
  bool sameRefill = !strcmp(scenario, "same_refill");
  bool resident = !strcmp(scenario, "resident");
  if(!(stale || same || refill || sameRefill || resident)) return 3;

  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid cacheable table load source fixture");
  frontend.cartPak->setAttribute("region", "NTSC");
  frontend.cartPak->setAttribute("cic", "CIC-NUS-6102");
  frontend.cartPak->append("program.rom", 8192);
  Node::System root;
  if(!load(root, "[Nintendo] Nintendo 64 (NTSC)")) return 4;
  option("Expansion Pak", "true");
  option("Deterministic Entropy", "true");
  option("Recompiler", "false");
  cartridgeSlot.port->allocate();
  cartridgeSlot.port->connect();
  ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 5;

  std::vector<u8> hidden(rdram.ram.size / 2);
  rdram.hidden.data = hidden.data();
  rdram.mapIdentity = 1;
  for(auto& reg : cpu.ipu.r) reg.u64 = 0;
  cpu.scc.status.errorLevel = cpu.scc.status.exceptionLevel = 0;
  cpu.context.setMode();
  cpu.dcache.power(false);
  cpu.icache.power(false);
  enable_observers(false);

  auto put = [](u32 address, u32 word) {
    rdram.ram.write<Word>(address, word, RBusDevice::ARES_DEBUGGER);
  };
  auto put_target = [&](u32 address, u16 marker) {
    put(address, 0x34020000u | marker);  // ORI v0,zero,marker
    put(address + 4, 0x00000000);
  };

  put_target(TargetA, 0x11);
  put_target(TargetB, 0x22);
  put_target(TargetC, 0x33);
  // The conflict line deliberately carries an equal-payload decoy pointer.
  put(Conflict + 0x0, PtrA);
  put(Conflict + 0x4, 0x13579bdf);
  put(Conflict + 0x8, 0x2468ace0);
  put(Conflict + 0xc, 0x0badf00d);

  u32 initialTable = resident ? PtrB : PtrA;
  put(Table, initialTable);
  put(Table + 4, 0x11112222);
  put(Table + 8, 0x33334444);
  put(Table + 0xc, 0x55556666);

  u32 dispatchPc = Code + 8;
  u32 expectedPointer = PtrA;
  u16 expectedMarker = 0x11;
  u32 rewriteValue = 0;
  u32 instructionCount = 6;

  if(resident) {
    // Fill B, mutate only the resident cache word to C, load C, dispatch C.
    put(Code + 0x00, 0x8e080000);  // LW t0,0(s0)
    put(Code + 0x04, 0xae090000);  // SW t1,0(s0) cached
    put(Code + 0x08, 0x8e0a0000);  // LW t2,0(s0) dispatch load
    put(Code + 0x0c, 0x01400008);  // JR t2
    put(Code + 0x10, 0x00000000);  // delay NOP
    rewriteValue = PtrC;
    expectedPointer = PtrC;
    expectedMarker = 0x33;
  } else if(refill || sameRefill) {
    // Fill A, rewrite backing through KSEG1, evict the clean table line using
    // an equal-index decoy, refill the table, then dispatch the refilled value.
    put(Code + 0x00, 0x8e080000);  // LW t0,0(s0)
    put(Code + 0x04, 0xae290000);  // SW t1,0(s1) uncached alias
    put(Code + 0x08, 0x8e6b0000);  // LW t3,0(s3) conflict/slot reuse
    put(Code + 0x0c, 0x8e0a0000);  // LW t2,0(s0) dispatch load
    put(Code + 0x10, 0x01400008);  // JR t2
    put(Code + 0x14, 0x00000000);  // delay NOP
    dispatchPc = Code + 0x0c;
    rewriteValue = sameRefill ? PtrA : PtrB;
    expectedPointer = rewriteValue;
    expectedMarker = sameRefill ? 0x11 : 0x22;
    instructionCount = 7;
  } else {
    // Fill A, rewrite backing through KSEG1, then dispatch from the still-valid
    // cached line.  `same` performs a same-value backing rewrite.
    put(Code + 0x00, 0x8e080000);  // LW t0,0(s0)
    put(Code + 0x04, 0xae290000);  // SW t1,0(s1) uncached alias
    put(Code + 0x08, 0x8e0a0000);  // LW t2,0(s0) dispatch load
    put(Code + 0x0c, 0x01400008);  // JR t2
    put(Code + 0x10, 0x00000000);  // delay NOP
    rewriteValue = same ? PtrA : PtrB;
  }

  cpu.ipu.r[16].u64 = 0xffffffff80002000ull;  // s0 cached Table
  cpu.ipu.r[17].u64 = 0xffffffffa0002000ull;  // s1 uncached Table alias
  cpu.ipu.r[19].u64 = 0xffffffff80004000ull;  // s3 cached Conflict
  cpu.ipu.r[9].u64 = rewriteValue;             // t1 store value
  cpu.pipeline.setPc(0xffffffff80006000ull);
  enable_observers(traced);
  for(u32 i = 0; i < instructionCount; i++) if(cpu.instruction()) cpu.synchronize();
  enable_observers(false);

  if(cpu.scc.cause.exceptionCode != 0) return 6;
  if(cpu.ipu.r[10].u32 != expectedPointer || cpu.ipu.r[2].u32 != expectedMarker) return 7;
  u32 finalBacking = backing_word(Table);
  if(resident) {
    if(finalBacking != PtrB) return 8;
  } else if(finalBacking != rewriteValue) return 9;

  const auto& tableLine = cpu.dcache.line(0xffffffff80002000ull);
  if(!tableLine.hit(Table) || tableLine.words[0] != expectedPointer) return 10;

  auto ramHash = nall::Hash::SHA256(std::span<const u8>{rdram.ram.data, rdram.ram.size}).digest();
  std::vector<u8> dcacheBytes;
  for(const auto& line : cpu.dcache.lines) {
    append_be(dcacheBytes, line.tagKey, 4);
    append_be(dcacheBytes, line.dirty, 2);
    append_be(dcacheBytes, line.index, 2);
    append_be(dcacheBytes, line.fillPc, 8);
    append_be(dcacheBytes, line.dirtyPc, 8);
    for(u32 word : line.words) append_be(dcacheBytes, word, 4);
  }
  auto dcacheHash = nall::Hash::SHA256(std::span<const u8>{dcacheBytes.data(), dcacheBytes.size()}).digest();

  std::printf("{\"scenario\":\"%s\",\"events\":{", scenario);
  print_events();
  std::printf("},\"facts\":{");
  std::printf("\"initial_table\":%u,\"rewrite_value\":%u,\"dispatch_pc\":%u,\"expected_pointer\":%u,\"dispatch_register\":%u,\"marker\":%u,\"final_backing\":%u,",
    initialTable, rewriteValue, dispatchPc, expectedPointer, cpu.ipu.r[10].u32,
    cpu.ipu.r[2].u32, finalBacking);
  std::printf("\"resident_tag\":%u,\"resident_index\":%u,\"resident_dirty\":%u,\"resident_word\":%u,\"resident_fill_pc\":%llu,\"resident_dirty_pc\":%llu},",
    tableLine.tagKey, (u32)tableLine.index, (u32)tableLine.dirty, tableLine.words[0],
    (unsigned long long)tableLine.fillPc, (unsigned long long)tableLine.dirtyPc);
  std::printf("\"state\":{\"pc\":%llu,\"count\":%llu,\"exception\":%u,\"dcache_hits\":%llu,\"dcache_misses\":%llu,\"dcache_writebacks\":%llu,\"ram_sha256\":\"%s\",\"dcache_sha256\":\"%s\"}}\n",
    (unsigned long long)cpu.ipu.pc, (unsigned long long)cpu.effectiveCount(),
    (u32)cpu.scc.cause.exceptionCode, (unsigned long long)cpu.profile.dcacheHits,
    (unsigned long long)cpu.profile.dcacheMisses,
    (unsigned long long)cpu.profile.dcacheWritebacks,
    ramHash.data(), dcacheHash.data());
  ares::Nintendo64::system.unload();
  return 0;
}
