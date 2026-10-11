/* SPDX-License-Identifier: ISC
 * Plaid research fixture: exact RDRAM -> SP DMEM ingress provenance under pinned ares.
 */
#ifndef PLAID_DMEM_INGRESS_OBSERVER
#define PLAID_DMEM_INGRESS_OBSERVER 0
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>
#include <vector>

#if PLAID_DMEM_INGRESS_OBSERVER
struct IngressEvent {
  enum Kind { RdramRead, DmemDmaWrite, DmemDirectWrite } kind;
  u64 seq = 0;
  u32 address = 0;
  u32 other = 0;
  u32 size = 0;
  u64 value = 0;
  bool originCpu = false;
};
static std::vector<IngressEvent> ingressEvents;
static u64 ingressSeq = 0;

static auto onRdramRead(u32 address, u32 size, u32 device, u64 value) -> void {
  if(device != (u32)RBusDevice::SP_DMA) return;
  ingressEvents.push_back({IngressEvent::RdramRead, ++ingressSeq, address, 0, size, value, false});
}
static auto onDmemDmaWrite(u32 dramAddress, u32 dmemAddress, u32 value) -> void {
  ingressEvents.push_back({IngressEvent::DmemDmaWrite, ++ingressSeq, dmemAddress & 0xfff, dramAddress, 4, value, false});
}
static auto onDmemDirectWrite(u32 dmemAddress, u32 value, bool originCpu) -> void {
  ingressEvents.push_back({IngressEvent::DmemDirectWrite, ++ingressSeq, dmemAddress & 0xfff, 0, 4, value, originCpu});
}
#endif

static auto digest(const u8* data, u32 size) -> string {
  return nall::Hash::SHA256(std::span<const u8>{data, size}).digest();
}

int main(int argc, char** argv) {
  if(argc != 2 || (strcmp(argv[1], "plain") && strcmp(argv[1], "traced"))) return 2;
  bool traced = !strcmp(argv[1], "traced");
#if !PLAID_DMEM_INGRESS_OBSERVER
  if(traced) return 90;
#endif

  Headless frontend; platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid SP DMA DMEM ingress fixture");
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

  auto put = [](u32 address, u32 word) {
    rdram.ram.write<Word>(address, word, RBusDevice::ARES_DEBUGGER);
  };
  // Equal-valued halves are deliberate: payload equality cannot identify which read produced which sink.
  put(0x1000, 0x11223344); put(0x1004, 0x11223344);
  put(0x2000, 0x11223344); put(0x2004, 0x11223344); // byte-identical reload, distinct source/generation

  // Two-row count/skip case. 0x3008/0x300c are poison and must not be transferred.
  put(0x3000, 0xa0a1a2a3); put(0x3004, 0xa4a5a6a7);
  put(0x3008, 0xdead0001); put(0x300c, 0xdead0002);
  put(0x3010, 0xb0b1b2b3); put(0x3014, 0xb4b5b6b7);

  // Wrap case: 16 bytes from DMEM 0xff8 must continue at 0x000.
  put(0x4000, 0xc0c1c2c3); put(0x4004, 0xc4c5c6c7);
  put(0x4008, 0xd0d1d2d3); put(0x400c, 0xd4d5d6d7);

#if PLAID_DMEM_INGRESS_OBSERVER
  plaidRdramReadObserver = traced ? onRdramRead : nullptr;
  plaidRspDmemDmaWriteObserver = traced ? onDmemDmaWrite : nullptr;
  plaidRspDmemDirectWriteObserver = traced ? onDmemDirectWrite : nullptr;
#endif

  auto dmaRead = [&](u32 dram, u32 dmem, u32 lengthReg) {
    rsp.writeWord(0x04040000, dmem & 0xff8, cpu); // DMEM region
    rsp.writeWord(0x04040004, dram & 0xfffff8, cpu);
    rsp.writeWord(0x04040008, lengthReg, cpu);
    u32 guard = 0;
    while(rsp.dma.busy.any()) {
      rsp.dmaTransferStep();
      if(++guard > 260) std::abort();
    }
  };

  std::vector<u32> checkpoints;
  dmaRead(0x1000, 0x000, 0x000); // one 8-byte fragment = two Word reads then two Word writes
  checkpoints.push_back(rsp.dmem.read<Word>(0x000));
  checkpoints.push_back(rsp.dmem.read<Word>(0x004));

  dmaRead(0x2000, 0x000, 0x000); // same bytes, new producer generation
  checkpoints.push_back(rsp.dmem.read<Word>(0x000));

  // length=0 => 8 bytes/row, count=1 => two rows, skip=8 source bytes.
  dmaRead(0x3000, 0x020, (1u << 12) | (1u << 23));
  checkpoints.push_back(rsp.dmem.read<Word>(0x020));
  checkpoints.push_back(rsp.dmem.read<Word>(0x024));
  checkpoints.push_back(rsp.dmem.read<Word>(0x028));
  checkpoints.push_back(rsp.dmem.read<Word>(0x02c));

  // 16 bytes starting at 0xff8: pbusAddress is n12 and wraps into 0x000.
  dmaRead(0x4000, 0xff8, 0x008);
  checkpoints.push_back(rsp.dmem.read<Word>(0xff8));
  checkpoints.push_back(rsp.dmem.read<Word>(0xffc));
  checkpoints.push_back(rsp.dmem.read<Word>(0x000));
  checkpoints.push_back(rsp.dmem.read<Word>(0x004));

  // OOB source returns zero but does not cross the successful RDRAM-read callback.
  dmaRead(rdram.ram.size, 0x060, 0x000);
  checkpoints.push_back(rsp.dmem.read<Word>(0x060));
  checkpoints.push_back(rsp.dmem.read<Word>(0x064));

  // Same-value direct CPU overwrite must cut DMA lineage despite unchanged bytes.
  u32 same = rsp.dmem.read<Word>(0x020);
  rsp.writeWord(0x04000020, same, cpu);
  checkpoints.push_back(rsp.dmem.read<Word>(0x020));

  const std::vector<u32> expected{
    0x11223344,0x11223344,0x11223344,
    0xa0a1a2a3,0xa4a5a6a7,0xb0b1b2b3,0xb4b5b6b7,
    0xc0c1c2c3,0xc4c5c6c7,0xd0d1d2d3,0xd4d5d6d7,
    0,0,0xa0a1a2a3
  };
  if(checkpoints != expected) return 31;

  string dmemHash = digest(rsp.dmem.data, rsp.dmem.size);
  string imemHash = digest(rsp.imem.data, rsp.imem.size);
  string ramHash = digest(rdram.ram.data, rdram.ram.size);
  std::printf("{\"events\":[");
#if PLAID_DMEM_INGRESS_OBSERVER
  if(traced) for(size_t i=0;i<ingressEvents.size();i++) {
    const auto& e = ingressEvents[i];
    std::printf("%s{\"seq\":%llu,", i ? "," : "", (unsigned long long)e.seq);
    if(e.kind == IngressEvent::RdramRead) {
      std::printf("\"kind\":\"rdram_read\",\"dram\":%u,\"bytes\":%u,\"value\":%llu",
        e.address,e.size,(unsigned long long)e.value);
    } else if(e.kind == IngressEvent::DmemDmaWrite) {
      std::printf("\"kind\":\"dmem_dma_write\",\"dmem\":%u,\"dram\":%u,\"bytes\":4,\"value\":%llu",
        e.address,e.other,(unsigned long long)e.value);
    } else {
      std::printf("\"kind\":\"dmem_direct_write\",\"dmem\":%u,\"bytes\":4,\"value\":%llu,\"origin_cpu\":%s",
        e.address,(unsigned long long)e.value,e.originCpu ? "true" : "false");
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
