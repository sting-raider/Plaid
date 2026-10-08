/* SPDX-License-Identifier: ISC
 * Actual pinned-ares RSP DMA lifecycle fixture. No reference instrumentation.
 */
#define main plaid_capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>
#include <vector>

using namespace ares;
using namespace ares::Nintendo64;

struct Snapshot {
  const char* name;
  u32 busy, full;
  u32 curRegion, curPbus, curDram, curLength, curCount, curSkip;
  u32 pendRegion, pendPbus, pendDram, pendLength, pendCount, pendSkip;
};

static auto snap(const char* name) -> Snapshot {
  return {
    name, (u32)rsp.dma.busy.any(), (u32)rsp.dma.full.any(),
    (u32)rsp.dma.current.pbusRegion, (u32)rsp.dma.current.pbusAddress,
    (u32)rsp.dma.current.dramAddress, (u32)rsp.dma.current.length,
    (u32)rsp.dma.current.count, (u32)rsp.dma.current.skip,
    (u32)rsp.dma.pending.pbusRegion, (u32)rsp.dma.pending.pbusAddress,
    (u32)rsp.dma.pending.dramAddress, (u32)rsp.dma.pending.length,
    (u32)rsp.dma.pending.count, (u32)rsp.dma.pending.skip,
  };
}

static auto clearDma() -> void {
  rsp.dma.pending = {};
  rsp.dma.current = {};
  rsp.dma.busy = {};
  rsp.dma.full = {};
  rsp.dma.clock = 0;
  rsp.clock = 0;
  cpu.clock = 0;
  std::memset(rsp.imem.data, 0, rsp.imem.size);
  std::memset(rsp.dmem.data, 0, rsp.dmem.size);
}

static auto put64(u32 address, u64 value) -> void {
  rdram.ram.write<Dual>(address, value, RBusDevice::ARES_DEBUGGER);
}

static auto queueRead(u32 dram, u32 imem, u32 lengthReg) -> void {
  rsp.writeWord(0x04040000, 0x1000 | (imem & 0xff8), cpu);
  rsp.writeWord(0x04040004, dram & 0xfffff8, cpu);
  rsp.writeWord(0x04040008, lengthReg, cpu);
}

static auto setPendingAddress(u32 dram, u32 imem) -> void {
  rsp.writeWord(0x04040000, 0x1000 | (imem & 0xff8), cpu);
  rsp.writeWord(0x04040004, dram & 0xfffff8, cpu);
}

int main() {
  Headless frontend; platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid SP DMA lifecycle fixture");
  frontend.cartPak->setAttribute("region", "NTSC");
  frontend.cartPak->setAttribute("cic", "CIC-NUS-6102");
  frontend.cartPak->append("program.rom", 8192);
  Node::System root;
  if(!load(root, "[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak", "true");
  option("Deterministic Entropy", "true");
  option("Recompiler", "false");
  cartridgeSlot.port->allocate(); cartridgeSlot.port->connect();
  ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;
  std::vector<u8> hidden(rdram.ram.size / 2); rdram.hidden.data = hidden.data();
  rdram.mapIdentity = 1;

  // Distinct payloads let destination memory prove which descriptor actually ran.
  put64(0x1000, 0x1111111111111111ull);
  put64(0x2000, 0x2222222222222222ull);
  put64(0x3000, 0x3333333333333333ull);
  put64(0x3008, 0x3434343434343434ull);
  put64(0x4000, 0x4444444444444444ull);
  put64(0x4008, 0xdeadbeefdeadbeefull); // skipped poison
  put64(0x4010, 0x4545454545454545ull);
  put64(0x5000, 0x5555555555555555ull);
  put64(0x6000, 0x6666666666666666ull);
  put64(0x6008, 0x6767676767676767ull);

  std::vector<Snapshot> states;

  // Case 1: a pending descriptor is mutable after its length-register commit.
  clearDma();
  queueRead(0x1000, 0x000, 0x000); // current A
  queueRead(0x2000, 0x080, 0x000); // pending B
  states.push_back(snap("pending_committed_B"));
  setPendingAddress(0x3000, 0x100); // no new length write
  states.push_back(snap("pending_mutated_to_C"));
  rsp.dmaTransferStep();             // A completes, mutated pending is promoted
  states.push_back(snap("after_A_handoff"));
  if(rsp.imem.read<Dual>(0x000) != 0x1111111111111111ull) return 10;
  if(rsp.imem.read<Dual>(0x080) != 0) return 11;
  rsp.dmaTransferStep();
  if(rsp.imem.read<Dual>(0x100) != 0x3333333333333333ull) return 12;
  states.push_back(snap("after_mutated_C_complete"));

  // Case 2: a third length write while BUSY+FULL does not reject. It rewrites
  // the same pending slot's length/count/skip. Address writes before it already
  // mutate the same slot, so the originally queued B descriptor is gone.
  clearDma();
  queueRead(0x1000, 0x000, 0x000); // current A
  queueRead(0x2000, 0x080, 0x000); // pending B, 8 bytes
  states.push_back(snap("third_before"));
  setPendingAddress(0x3000, 0x100);
  rsp.writeWord(0x04040008, 0x008, cpu); // third commit: C, 16 bytes
  states.push_back(snap("third_overwrote_pending"));
  rsp.dmaTransferStep();
  states.push_back(snap("third_promoted"));
  if((u32)rsp.dma.current.length != 8 || (u32)rsp.dma.current.dramAddress != 0x3000 || (u32)rsp.dma.current.pbusAddress != 0x100) return 20;
  rsp.dmaTransferStep();
  if(rsp.imem.read<Dual>(0x080) != 0) return 21;
  if(rsp.imem.read<Dual>(0x100) != 0x3333333333333333ull) return 22;
  if(rsp.imem.read<Dual>(0x108) != 0x3434343434343434ull) return 23;
  states.push_back(snap("third_complete"));

  // Case 3: count/skip sub-blocks are one current request. When it completes
  // with a pending request, dmaTransferStep clears BUSY and immediately starts
  // the pending request inside the same call, so external BUSY never falls.
  clearDma();
  // length=0 => 8 bytes/block; count=1 => two blocks; skip=8 => 0x4000,0x4010.
  queueRead(0x4000, 0x200, (1u << 12) | (1u << 23));
  queueRead(0x5000, 0x300, 0x000);
  states.push_back(snap("multiblock_start"));
  rsp.dmaTransferStep();
  states.push_back(snap("multiblock_after_first"));
  if(!(rsp.dma.busy.any() && rsp.dma.full.any()) || (u32)rsp.dma.current.count != 0 || (u32)rsp.dma.current.dramAddress != 0x4010) return 30;
  rsp.dmaTransferStep();
  states.push_back(snap("multiblock_handoff_no_busy_edge"));
  if(!(rsp.dma.busy.any()) || rsp.dma.full.any()) return 31;
  if((u32)rsp.dma.current.dramAddress != 0x5000 || (u32)rsp.dma.current.pbusAddress != 0x300) return 32;
  if(rsp.imem.read<Dual>(0x200) != 0x4444444444444444ull) return 33;
  if(rsp.imem.read<Dual>(0x208) != 0x4545454545454545ull) return 34;
  rsp.dmaTransferStep();
  states.push_back(snap("multiblock_pending_complete"));
  if(rsp.dma.busy.any() || rsp.dma.full.any()) return 35;
  if(rsp.imem.read<Dual>(0x300) != 0x5555555555555555ull) return 36;

  // Case 4: n12 PBUS address wraps inside one 16-byte current transfer.
  clearDma();
  queueRead(0x6000, 0xff8, 0x008);
  states.push_back(snap("wrap_start"));
  rsp.dmaTransferStep();
  states.push_back(snap("wrap_complete"));
  if(rsp.imem.read<Dual>(0xff8) != 0x6666666666666666ull) return 40;
  if(rsp.imem.read<Dual>(0x000) != 0x6767676767676767ull) return 41;
  if((u32)rsp.dma.current.pbusAddress != 0x008) return 42;

  auto imemHash = nall::Hash::SHA256(std::span<const u8>{rsp.imem.data, rsp.imem.size}).digest();
  std::printf("{\"states\":[");
  for(size_t i=0;i<states.size();i++) {
    const auto& s=states[i];
    std::printf("%s{\"name\":\"%s\",\"busy\":%u,\"full\":%u,\"current\":{\"region\":%u,\"pbus\":%u,\"dram\":%u,\"length\":%u,\"count\":%u,\"skip\":%u},\"pending\":{\"region\":%u,\"pbus\":%u,\"dram\":%u,\"length\":%u,\"count\":%u,\"skip\":%u}}",
      i ? "," : "", s.name,s.busy,s.full,
      s.curRegion,s.curPbus,s.curDram,s.curLength,s.curCount,s.curSkip,
      s.pendRegion,s.pendPbus,s.pendDram,s.pendLength,s.pendCount,s.pendSkip);
  }
  std::printf("],\"final\":{\"imem_sha256\":\"%s\",\"busy\":%u,\"full\":%u}}\n",
    imemHash.data(),(u32)rsp.dma.busy.any(),(u32)rsp.dma.full.any());
  ares::Nintendo64::system.unload();
  return 0;
}
