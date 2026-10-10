/* SPDX-License-Identifier: ISC
 * Plaid research fixture: RSP IMEM lifetime across NMI and system reset on
 * exact pinned ares. The reference implementation is not modified.
 */
#define main capability_fixture_main
#include "../../spikes/003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>
#include <vector>

using namespace ares;
using namespace ares::Nintendo64;

static auto digest(const u8* data, u32 size) -> string {
  return nall::Hash::SHA256(std::span<const u8>{data, size}).digest();
}

static auto put64(u32 address, u64 value) -> void {
  rdram.ram.write<Dual>(address, value, RBusDevice::ARES_DEBUGGER);
}

static auto queueRead(u32 dram, u32 imem, u32 lengthReg = 0) -> void {
  rsp.writeWord(0x04040000, 0x1000 | (imem & 0xff8), cpu);
  rsp.writeWord(0x04040004, dram & 0xfffff8, cpu);
  rsp.writeWord(0x04040008, lengthReg, cpu);
}

static auto seedRspState() -> void {
  for(u32 offset = 0; offset < 0x1000; offset += 8) {
    rsp.imem.write<Dual>(offset, 0x2401000124020002ull ^ (u64(offset) << 32));
  }
  put64(0x1000, 0x2403000324040004ull);
  put64(0x2000, 0x2405000524060006ull);
  rsp.pipeline = {};
  rsp.ipu.pc = 0x234;
  rsp.branch.setPc(0x234);
  rsp.status.halted = 0;
  queueRead(0x1000, 0x100);
  queueRead(0x2000, 0x180);
}

int main() {
  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid RSP reset IMEM lifetime fixture");
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

  std::vector<u8> zeros(4096, 0);
  string zeroHash = digest(zeros.data(), zeros.size());

  // NMI: preserve every RSP byte and the in-flight DMA/execution state.
  seedRspState();
  string nmiBefore = digest(rsp.imem.data, rsp.imem.size);
  u32 nmiPc = rsp.ipu.pc;
  u32 nmiBusy = rsp.dma.busy.any();
  u32 nmiFull = rsp.dma.full.any();
  u32 nmiCurDram = rsp.dma.current.dramAddress;
  u32 nmiCurPbus = rsp.dma.current.pbusAddress;
  u32 nmiPendingDram = rsp.dma.pending.dramAddress;
  u32 nmiPendingPbus = rsp.dma.pending.pbusAddress;
  cpu.scc.status.errorLevel = 0;
  cpu.pipeline.setPc(0xffffffff80001234ull);
  cpu.exception.nmi();
  string nmiAfter = digest(rsp.imem.data, rsp.imem.size);
  bool nmiPreserved = nmiBefore == nmiAfter
    && rsp.ipu.pc == nmiPc
    && (u32)rsp.dma.busy.any() == nmiBusy
    && (u32)rsp.dma.full.any() == nmiFull
    && (u32)rsp.dma.current.dramAddress == nmiCurDram
    && (u32)rsp.dma.current.pbusAddress == nmiCurPbus
    && (u32)rsp.dma.pending.dramAddress == nmiPendingDram
    && (u32)rsp.dma.pending.pbusAddress == nmiPendingPbus;
  if(!nmiPreserved || !nmiBusy || !nmiFull) return 10;

  // ares System::power(true): explicit RSP reset clears IMEM and all DMA/CPU state.
  seedRspState();
  string resetBefore = digest(rsp.imem.data, rsp.imem.size);
  u32 resetBusyBefore = rsp.dma.busy.any();
  u32 resetFullBefore = rsp.dma.full.any();
  ares::Nintendo64::system.power(true);
  string resetAfter = digest(rsp.imem.data, rsp.imem.size);
  bool resetCleared = resetAfter == zeroHash
    && rsp.ipu.pc == 0
    && rsp.status.halted
    && !rsp.dma.busy.any()
    && !rsp.dma.full.any();
  if(!resetCleared || !resetBusyBefore || !resetFullBefore || resetBefore == resetAfter) return 20;

  // Equality adversary: reset an already-zero IMEM while non-memory RSP state is live.
  string equalBefore = digest(rsp.imem.data, rsp.imem.size);
  rsp.ipu.pc = 0x2a0;
  rsp.branch.setPc(0x2a0);
  rsp.status.halted = 0;
  queueRead(0x1000, 0x300);
  bool equalHadState = rsp.ipu.pc == 0x2a0 && rsp.dma.busy.any();
  ares::Nintendo64::system.power(true);
  string equalAfter = digest(rsp.imem.data, rsp.imem.size);
  bool equalPayloadReset = equalBefore == equalAfter
    && equalAfter == zeroHash
    && equalHadState
    && rsp.ipu.pc == 0
    && rsp.status.halted
    && !rsp.dma.busy.any();
  if(!equalPayloadReset) return 30;

  // Cold power also clears an installed nonzero image.
  rsp.imem.write<Dual>(0x200, 0x2407000724080008ull);
  string coldBefore = digest(rsp.imem.data, rsp.imem.size);
  ares::Nintendo64::system.power(false);
  string coldAfter = digest(rsp.imem.data, rsp.imem.size);
  bool coldCleared = coldAfter == zeroHash && coldBefore != coldAfter;
  if(!coldCleared) return 40;

  std::printf(
    "{\"nmi\":{\"before\":\"%s\",\"after\":\"%s\",\"preserved\":%s,\"busy\":%u,\"full\":%u},"
    "\"soft_reset\":{\"before\":\"%s\",\"after\":\"%s\",\"cleared\":%s},"
    "\"equal_payload_reset\":{\"before\":\"%s\",\"after\":\"%s\",\"state_reset\":%s},"
    "\"cold_power\":{\"before\":\"%s\",\"after\":\"%s\",\"cleared\":%s}}\n",
    nmiBefore.data(), nmiAfter.data(), nmiPreserved ? "true" : "false", nmiBusy, nmiFull,
    resetBefore.data(), resetAfter.data(), resetCleared ? "true" : "false",
    equalBefore.data(), equalAfter.data(), equalPayloadReset ? "true" : "false",
    coldBefore.data(), coldAfter.data(), coldCleared ? "true" : "false");

  ares::Nintendo64::system.unload();
  return 0;
}
