/* SPDX-License-Identifier: ISC
 * Plaid research fixture: grouping exact RSP IMEM provenance fragments into
 * completed SP-DMA installation lifetimes on pinned ares.
 */
#ifndef PLAID_RSP_LIFETIME_OBSERVER
#define PLAID_RSP_LIFETIME_OBSERVER 0
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>
#include <vector>

using namespace ares;
using namespace ares::Nintendo64;

#if PLAID_RSP_LIFETIME_OBSERVER
struct RawEvent {
  enum Kind { Promote, RdramRead, ImemWrite, Complete, DirectWrite, Fetch } kind;
  u64 seq = 0;
  u64 transfer = 0;
  u32 a = 0, b = 0, c = 0, d = 0, e = 0, f = 0;
  u64 value = 0;
  bool flag0 = false, flag1 = false;
};
static std::vector<RawEvent> rawEvents;
static u64 rawSeq = 0;

static auto onPromote(u64 transfer, u32 region, u32 pbus, u32 dram, u32 length, u32 count, u32 skip, bool read, bool write) -> void {
  RawEvent e{RawEvent::Promote, ++rawSeq, transfer};
  e.a=region; e.b=pbus; e.c=dram; e.d=length; e.e=count; e.f=skip; e.flag0=read; e.flag1=write;
  rawEvents.push_back(e);
}
static auto onRdramRead(u64 transfer, u32 address, u32 size, u32 device, u64 value) -> void {
  if(device != (u32)RBusDevice::SP_DMA) return;
  RawEvent e{RawEvent::RdramRead, ++rawSeq, transfer}; e.a=address; e.b=size; e.c=device; e.value=value; rawEvents.push_back(e);
}
static auto onImemWrite(u64 transfer, u32 dram, u32 imem, u64 value) -> void {
  RawEvent e{RawEvent::ImemWrite, ++rawSeq, transfer}; e.a=dram; e.b=imem & 0xfff; e.value=value; rawEvents.push_back(e);
}
static auto onComplete(u64 transfer) -> void {
  rawEvents.push_back({RawEvent::Complete, ++rawSeq, transfer});
}
static auto onDirectWrite(u32 imem, u32 value, bool originCpu) -> void {
  RawEvent e{RawEvent::DirectWrite, ++rawSeq}; e.a=imem & 0xfff; e.value=value; e.flag0=originCpu; rawEvents.push_back(e);
}
static auto onFetch(u32 pc, u32 instruction) -> void {
  RawEvent e{RawEvent::Fetch, ++rawSeq}; e.a=pc & 0xfff; e.value=instruction; rawEvents.push_back(e);
}
#endif

static auto digest(const u8* data, u32 size) -> string {
  return nall::Hash::SHA256(std::span<const u8>{data, size}).digest();
}

static auto clearDma() -> void {
  rsp.dma.pending = {};
  rsp.dma.current = {};
  rsp.dma.busy = {};
  rsp.dma.full = {};
  rsp.dma.clock = 0;
  rsp.clock = 0;
  cpu.clock = 0;
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

static auto executeOne(u32 pc) -> u32 {
  rsp.pipeline = {};
  rsp.branch.setPc(pc);
  rsp.ipu.pc = pc;
  rsp.status.halted = 0;
  rsp.instruction();
  return rsp.pipeline.instruction;
}

int main(int argc, char** argv) {
  if(argc != 2 || (strcmp(argv[1], "plain") && strcmp(argv[1], "traced"))) return 2;
  bool traced = !strcmp(argv[1], "traced");
#if !PLAID_RSP_LIFETIME_OBSERVER
  if(traced) return 90;
#endif

  Headless frontend; platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid RSP microcode lifetime fixture");
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

  put64(0x1000, 0x2401000124020002ull); put64(0x1008, 0x2403000324040004ull);
  put64(0x2000, 0x2405000500000000ull); put64(0x2008, 0xdeadbeefdeadbeefull); put64(0x2010, 0x2406000600000000ull);
  put64(0x3000, 0x2407000700000000ull); put64(0x3008, 0x2408000800000000ull);
  put64(0x4000, 0x2409000900000000ull); put64(0x5000, 0x2409000900000000ull);
  put64(0x6000, 0x240a000a00000000ull); put64(0x7000, 0x240b000b00000000ull); put64(0x7100, 0x240c000c00000000ull);
  rsp.imem.write<Word>(0x108, 0x24060055);

#if PLAID_RSP_LIFETIME_OBSERVER
  plaidRspDmaTransferId = 0;
  rawSeq = 0;
  rawEvents.clear();
  plaidRspDmaPromoteObserver = traced ? onPromote : nullptr;
  plaidRdramReadObserver = traced ? onRdramRead : nullptr;
  plaidRspImemWriteObserver = traced ? onImemWrite : nullptr;
  plaidRspDmaCompleteObserver = traced ? onComplete : nullptr;
  plaidRspImemDirectWriteObserver = traced ? onDirectWrite : nullptr;
  plaidRspFetchObserver = traced ? onFetch : nullptr;
#endif

  std::vector<u32> checkpoints;
  std::vector<u32> handoff;

  clearDma(); queueRead(0x1000, 0x000, 0x008); rsp.dmaTransferStep();
  checkpoints.push_back(executeOne(0x000)); checkpoints.push_back(executeOne(0x008));

  clearDma(); queueRead(0x2000, 0x100, (1u << 12) | (1u << 23));
  rsp.dmaTransferStep();
  checkpoints.push_back(executeOne(0x100));
  checkpoints.push_back(executeOne(0x108));
  if(!rsp.dma.busy.any()) return 20;
  rsp.dmaTransferStep();
  checkpoints.push_back(executeOne(0x108));

  clearDma(); queueRead(0x3000, 0xff8, 0x008); rsp.dmaTransferStep();
  checkpoints.push_back(executeOne(0xff8)); checkpoints.push_back(executeOne(0x000));

  clearDma(); queueRead(0x4000, 0x200, 0x000); queueRead(0x5000, 0x200, 0x000);
  handoff.push_back((u32)rsp.dma.busy.any()); handoff.push_back((u32)rsp.dma.full.any());
  rsp.dmaTransferStep();
  handoff.push_back((u32)rsp.dma.busy.any()); handoff.push_back((u32)rsp.dma.full.any());
  checkpoints.push_back(executeOne(0x200));
  rsp.dmaTransferStep();
  checkpoints.push_back(executeOne(0x200));

  rsp.writeWord(0x04001300, 0x240d000d, cpu);
  checkpoints.push_back(executeOne(0x200));
  rsp.writeWord(0x04001200, 0x240e000e, cpu);
  checkpoints.push_back(executeOne(0x200));

  u64 untouched380 = rsp.imem.read<Dual>(0x380);
  clearDma(); queueRead(0x6000, 0x300, 0x000); queueRead(0x7000, 0x380, 0x000);
  setPendingAddress(0x7100, 0x3c0);
  rsp.dmaTransferStep();
  if((u32)rsp.dma.current.dramAddress != 0x7100 || (u32)rsp.dma.current.pbusAddress != 0x3c0) return 30;
  rsp.dmaTransferStep();
  checkpoints.push_back(executeOne(0x3c0));
  if(rsp.imem.read<Dual>(0x380) != untouched380) return 31;

  const std::vector<u32> expectedWords{
    0x24010001,0x24030003,0x24050005,0x24060055,0x24060006,
    0x24070007,0x24080008,0x24090009,0x24090009,0x24090009,0x240e000e,0x240c000c
  };
  if(checkpoints != expectedWords) return 40;
  const std::vector<u32> expectedHandoff{1,1,1,0};
  if(handoff != expectedHandoff) return 41;

  string imemHash = digest(rsp.imem.data, rsp.imem.size);
  string ramHash = digest(rdram.ram.data, rdram.ram.size);
  std::printf("{\"events\":[");
#if PLAID_RSP_LIFETIME_OBSERVER
  if(traced) for(size_t i=0;i<rawEvents.size();i++) {
    const auto& e=rawEvents[i];
    std::printf("%s{\"seq\":%llu,",i?",":"",(unsigned long long)e.seq);
    if(e.kind==RawEvent::Promote) std::printf("\"kind\":\"promote\",\"transfer\":%llu,\"region\":%u,\"pbus\":%u,\"dram\":%u,\"length\":%u,\"count\":%u,\"skip\":%u,\"read\":%s,\"write\":%s",
      (unsigned long long)e.transfer,e.a,e.b,e.c,e.d,e.e,e.f,e.flag0?"true":"false",e.flag1?"true":"false");
    else if(e.kind==RawEvent::RdramRead) std::printf("\"kind\":\"rdram_read\",\"transfer\":%llu,\"dram\":%u,\"bytes\":%u,\"value\":%llu",
      (unsigned long long)e.transfer,e.a,e.b,(unsigned long long)e.value);
    else if(e.kind==RawEvent::ImemWrite) std::printf("\"kind\":\"imem_write\",\"transfer\":%llu,\"dram\":%u,\"imem\":%u,\"bytes\":8,\"value\":%llu",
      (unsigned long long)e.transfer,e.a,e.b,(unsigned long long)e.value);
    else if(e.kind==RawEvent::Complete) std::printf("\"kind\":\"complete\",\"transfer\":%llu",(unsigned long long)e.transfer);
    else if(e.kind==RawEvent::DirectWrite) std::printf("\"kind\":\"direct_write\",\"imem\":%u,\"bytes\":4,\"value\":%llu,\"origin_cpu\":%s",e.a,(unsigned long long)e.value,e.flag0?"true":"false");
    else std::printf("\"kind\":\"fetch\",\"pc\":%u,\"word\":%u",e.a,(u32)e.value);
    std::printf("}");
  }
#endif
  std::printf("],\"state\":{\"checkpoints\":[");
  for(size_t i=0;i<checkpoints.size();i++) std::printf("%s%u",i?",":"",checkpoints[i]);
  std::printf("],\"handoff\":[");
  for(size_t i=0;i<handoff.size();i++) std::printf("%s%u",i?",":"",handoff[i]);
  std::printf("],\"imem_sha256\":\"%s\",\"rdram_sha256\":\"%s\",\"busy\":%u,\"full\":%u}}\n",
    imemHash.data(),ramHash.data(),(u32)rsp.dma.busy.any(),(u32)rsp.dma.full.any());
  ares::Nintendo64::system.unload();
  return 0;
}
