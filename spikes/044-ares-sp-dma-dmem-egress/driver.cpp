/* SPDX-License-Identifier: ISC
 * Plaid research fixture: exact SP DMEM -> RDRAM DMA egress provenance under pinned ares.
 */
#ifndef PLAID_DMEM_EGRESS_OBSERVER
#define PLAID_DMEM_EGRESS_OBSERVER 0
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>
#include <vector>

#if PLAID_DMEM_EGRESS_OBSERVER
struct EgressEvent {
  enum Kind { DmemDirectWrite, DmemForeignWrite, DmemDmaRead, RdramWrite } kind;
  u64 seq = 0;
  u32 address = 0;
  u32 other = 0;
  u32 size = 0;
  u64 value = 0;
  bool originCpu = false;
};
static std::vector<EgressEvent> egressEvents;
static u64 egressSeq = 0;

static auto onDmemDirectWrite(u32 dmemAddress, u32 value, bool originCpu) -> void {
  egressEvents.push_back({EgressEvent::DmemDirectWrite, ++egressSeq, dmemAddress & 0xfff, 0, 4, value, originCpu});
}
static auto onDmemForeignWrite(u32 dmemAddress, u32 value) -> void {
  egressEvents.push_back({EgressEvent::DmemForeignWrite, ++egressSeq, dmemAddress & 0xfff, 0, 4, value, false});
}
static auto onDmemDmaRead(u32 dmemAddress, u32 dramAddress, u32 value) -> void {
  egressEvents.push_back({EgressEvent::DmemDmaRead, ++egressSeq, dmemAddress & 0xfff, dramAddress, 4, value, false});
}
static auto onRdramWrite(u32 address, u32 size, u32 device, u64 value) -> void {
  if(device != (u32)RBusDevice::SP_DMA) return;
  egressEvents.push_back({EgressEvent::RdramWrite, ++egressSeq, address, 0, size, value, false});
}
#endif

static auto digest(const u8* data, u32 size) -> string {
  return nall::Hash::SHA256(std::span<const u8>{data, size}).digest();
}

int main(int argc, char** argv) {
  if(argc != 2 || (strcmp(argv[1], "plain") && strcmp(argv[1], "traced"))) return 2;
  bool traced = !strcmp(argv[1], "traced");
#if !PLAID_DMEM_EGRESS_OBSERVER
  if(traced) return 90;
#endif

  Headless frontend; platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid SP DMA DMEM egress fixture");
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

#if PLAID_DMEM_EGRESS_OBSERVER
  plaidRspDmemDirectWriteObserver = traced ? onDmemDirectWrite : nullptr;
  plaidRspDmemDmaReadObserver = traced ? onDmemDmaRead : nullptr;
  plaidRdramWriteObserver = traced ? onRdramWrite : nullptr;
#endif

  auto cpuDmemWrite = [&](u32 address, u32 value) {
    rsp.writeWord(0x04000000 | (address & 0xfff), value, cpu);
  };
  auto putRam = [&](u32 address, u32 value) {
    rdram.ram.write<Word>(address, value, RBusDevice::ARES_DEBUGGER);
  };
  auto dmaWrite = [&](u32 dmem, u32 dram, u32 lengthReg) {
    rsp.writeWord(0x04040000, dmem & 0xff8, cpu);
    rsp.writeWord(0x04040004, dram & 0xfffff8, cpu);
    rsp.writeWord(0x0404000c, lengthReg, cpu);
    u32 guard = 0;
    while(rsp.dma.busy.any()) {
      rsp.dmaTransferStep();
      if(++guard > 260) std::abort();
    }
  };

  // Equal-valued sources are deliberate: the second read occurs before the first sink.
  cpuDmemWrite(0x000, 0x11223344);
  cpuDmemWrite(0x004, 0x11223344);
  dmaWrite(0x000, 0x1000, 0x000);

  // Same bytes, fresh source writer generations.
  cpuDmemWrite(0x000, 0x11223344);
  cpuDmemWrite(0x004, 0x11223344);
  dmaWrite(0x000, 0x2000, 0x000);

  // Two rows with an 8-byte DRAM skip. 0x3008/0x300c are poison destinations.
  cpuDmemWrite(0x020, 0xa0a1a2a3);
  cpuDmemWrite(0x024, 0xa4a5a6a7);
  cpuDmemWrite(0x028, 0xb0b1b2b3);
  cpuDmemWrite(0x02c, 0xb4b5b6b7);
  putRam(0x3008, 0xdead0001); putRam(0x300c, 0xdead0002);
  dmaWrite(0x020, 0x3000, (1u << 12) | (1u << 23));

  // 16 bytes beginning at 0xff8 wrap the n12 DMEM source to 0x000.
  cpuDmemWrite(0xff8, 0xc0c1c2c3);
  cpuDmemWrite(0xffc, 0xc4c5c6c7);
  cpuDmemWrite(0x000, 0xd0d1d2d3);
  cpuDmemWrite(0x004, 0xd4d5d6d7);
  dmaWrite(0xff8, 0x4000, 0x008);

  // Same-value CPU overwrite is a new writer generation before a later DMA.
  u32 same = rsp.dmem.read<Word>(0x020);
  cpuDmemWrite(0x020, same);
  dmaWrite(0x020, 0x5000, 0x000);

  // A measured foreign same-value storage effect must cut known CPU ancestry.
  cpuDmemWrite(0x070, 0xfeedface);
  cpuDmemWrite(0x074, 0x0badf00d);
  rsp.dmem.write<Word>(0x070, 0xfeedface);
#if PLAID_DMEM_EGRESS_OBSERVER
  if(traced) onDmemForeignWrite(0x070, 0xfeedface);
#endif
  dmaWrite(0x070, 0x6000, 0x000);

  // OOB RDRAM destination consumes DMEM reads but produces no successful sink witness.
  cpuDmemWrite(0x060, 0x55667788);
  cpuDmemWrite(0x064, 0x99aabbcc);
  dmaWrite(0x060, rdram.ram.size, 0x000);

  std::vector<u32> checkpoints{
    (u32)rdram.ram.read<Word>(0x1000, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x1004, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x2000, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x2004, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x3000, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x3004, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x3008, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x300c, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x3010, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x3014, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x4000, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x4004, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x4008, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x400c, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x5000, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x5004, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x6000, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x6004, RBusDevice::ARES_DEBUGGER),
  };
  const std::vector<u32> expected{
    0x11223344,0x11223344,0x11223344,0x11223344,
    0xa0a1a2a3,0xa4a5a6a7,0xdead0001,0xdead0002,0xb0b1b2b3,0xb4b5b6b7,
    0xc0c1c2c3,0xc4c5c6c7,0xd0d1d2d3,0xd4d5d6d7,
    0xa0a1a2a3,0xa4a5a6a7,0xfeedface,0x0badf00d,
  };
  if(checkpoints != expected) return 31;

  string dmemHash = digest(rsp.dmem.data, rsp.dmem.size);
  string imemHash = digest(rsp.imem.data, rsp.imem.size);
  string ramHash = digest(rdram.ram.data, rdram.ram.size);
  std::printf("{\"events\":[");
#if PLAID_DMEM_EGRESS_OBSERVER
  if(traced) for(size_t i=0;i<egressEvents.size();i++) {
    const auto& e = egressEvents[i];
    std::printf("%s{\"seq\":%llu,", i ? "," : "", (unsigned long long)e.seq);
    if(e.kind == EgressEvent::DmemDirectWrite) {
      std::printf("\"kind\":\"dmem_direct_write\",\"dmem\":%u,\"bytes\":4,\"value\":%llu,\"origin_cpu\":%s",
        e.address,(unsigned long long)e.value,e.originCpu ? "true" : "false");
    } else if(e.kind == EgressEvent::DmemForeignWrite) {
      std::printf("\"kind\":\"dmem_foreign_write\",\"dmem\":%u,\"bytes\":4,\"value\":%llu",
        e.address,(unsigned long long)e.value);
    } else if(e.kind == EgressEvent::DmemDmaRead) {
      std::printf("\"kind\":\"dmem_dma_read\",\"dmem\":%u,\"dram\":%u,\"bytes\":4,\"value\":%llu",
        e.address,e.other,(unsigned long long)e.value);
    } else {
      std::printf("\"kind\":\"rdram_write\",\"dram\":%u,\"bytes\":%u,\"value\":%llu",
        e.address,e.size,(unsigned long long)e.value);
    }
    std::printf("}");
  }
#endif
  std::printf("],\"state\":{\"checkpoints\":[");
  for(size_t i=0;i<checkpoints.size();i++) std::printf("%s%u",i ? "," : "",checkpoints[i]);
  std::printf("],\"dmem_sha256\":\"%s\",\"imem_sha256\":\"%s\",\"rdram_sha256\":\"%s\",\"dma_busy\":%u,\"dma_full\":%u}}\n",
    dmemHash.data(),imemHash.data(),ramHash.data(),(u32)rsp.dma.busy.any(),(u32)rsp.dma.full.any());
  ares::Nintendo64::system.unload();
  return 0;
}
