/* SPDX-License-Identifier: ISC
 * Plaid research fixture: RSP IMEM provenance under pinned ares.
 */
#ifndef PLAID_RSP_OBSERVER
#define PLAID_RSP_OBSERVER 0
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>
#include <vector>

#if PLAID_RSP_OBSERVER
struct RawEvent {
  enum Kind { RdramRead, ImemDmaWrite, ImemDirectWrite, Fetch } kind;
  u64 seq = 0;
  u32 address = 0;
  u32 other = 0;
  u32 size = 0;
  u64 value = 0;
  bool originCpu = false;
};
static std::vector<RawEvent> rawEvents;
static u64 rawSeq = 0;

static auto onRdramRead(u32 address, u32 size, u32 device, u64 value) -> void {
  if(device != (u32)RBusDevice::SP_DMA) return;
  rawEvents.push_back({RawEvent::RdramRead, ++rawSeq, address, 0, size, value, false});
}
static auto onImemDmaWrite(u32 dramAddress, u32 imemAddress, u64 value) -> void {
  rawEvents.push_back({RawEvent::ImemDmaWrite, ++rawSeq, imemAddress & 0xfff, dramAddress, 8, value, false});
}
static auto onImemDirectWrite(u32 imemAddress, u32 value, bool originCpu) -> void {
  rawEvents.push_back({RawEvent::ImemDirectWrite, ++rawSeq, imemAddress & 0xfff, 0, 4, value, originCpu});
}
static auto onRspFetch(u32 pc, u32 instruction) -> void {
  rawEvents.push_back({RawEvent::Fetch, ++rawSeq, pc & 0xfff, 0, 4, instruction, false});
}
#endif

static auto hexDigest(const u8* data, u32 size) -> string {
  return nall::Hash::SHA256(std::span<const u8>{data, size}).digest();
}

int main(int argc, char** argv) {
  if(argc != 2 || (strcmp(argv[1], "plain") && strcmp(argv[1], "traced"))) return 2;
  bool traced = !strcmp(argv[1], "traced");
#if !PLAID_RSP_OBSERVER
  if(traced) return 90;
#endif

  Headless frontend; platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid RSP IMEM provenance fixture");
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
  // A and A' are byte-identical at different backing addresses.
  put(0x1000, 0x24010001); put(0x1004, 0x24020002); put(0x1008, 0); put(0x100c, 0);
  put(0x2000, 0x24010001); put(0x2004, 0x24020002); put(0x2008, 0); put(0x200c, 0);
  // B changes the first instruction at the same IMEM destination.
  put(0x3000, 0x24010009); put(0x3004, 0x24020002); put(0x3008, 0); put(0x300c, 0);
  // Count/skip source: 0x4008 is poison and must be skipped.
  put(0x4000, 0x24030004); put(0x4004, 0);
  put(0x4008, 0x24030066); put(0x400c, 0x24040066);
  put(0x4010, 0x24040005); put(0x4014, 0);
  // DMEM-only transfer source.
  put(0x5000, 0x24050006); put(0x5004, 0x24060006);

#if PLAID_RSP_OBSERVER
  plaidRdramReadObserver = traced ? onRdramRead : nullptr;
  plaidRspImemDmaWriteObserver = traced ? onImemDmaWrite : nullptr;
  plaidRspImemDirectWriteObserver = traced ? onImemDirectWrite : nullptr;
  plaidRspFetchObserver = traced ? onRspFetch : nullptr;
#endif

  auto dmaRead = [&](u32 dram, u32 pbus, bool imem, u32 lengthReg) {
    rsp.writeWord(0x04040000, (imem ? 0x1000u : 0u) | (pbus & 0xff8), cpu);
    rsp.writeWord(0x04040004, dram & 0xfffff8, cpu);
    rsp.writeWord(0x04040008, lengthReg, cpu);
    u32 guard = 0;
    while(rsp.dma.busy.any()) {
      rsp.dmaTransferStep();
      if(++guard > 260) std::abort();
    }
  };
  auto executeOne = [&](u32 pc) {
    rsp.pipeline = {};
    rsp.branch.setPc(pc);
    rsp.ipu.pc = pc;
    rsp.status.halted = 0;
    rsp.instruction();
  };

  std::vector<u32> checkpoints;
  dmaRead(0x1000, 0x000, true, 0x008); // 16 bytes
  rsp.ipu.r[1].u32 = rsp.ipu.r[2].u32 = 0;
  executeOne(0x000); checkpoints.push_back(rsp.ipu.r[1].u32);
  executeOne(0x004); checkpoints.push_back(rsp.ipu.r[2].u32);

  dmaRead(0x2000, 0x000, true, 0x008); // byte-identical reload, distinct origin
  rsp.ipu.r[1].u32 = 0; executeOne(0x000); checkpoints.push_back(rsp.ipu.r[1].u32);

  dmaRead(0x3000, 0x000, true, 0x008); // changed reload
  rsp.ipu.r[1].u32 = 0; executeOne(0x000); checkpoints.push_back(rsp.ipu.r[1].u32);

  // length=0 => 8 bytes per block, count=1 => two blocks, skip=8 bytes.
  dmaRead(0x4000, 0x020, true, (1u << 12) | (1u << 23));
  rsp.ipu.r[3].u32 = rsp.ipu.r[4].u32 = 0;
  executeOne(0x020); checkpoints.push_back(rsp.ipu.r[3].u32);
  executeOne(0x028); checkpoints.push_back(rsp.ipu.r[4].u32);

  u64 imem40Before = rsp.imem.read<Dual>(0x040);
  dmaRead(0x5000, 0x040, false, 0x000); // DMEM, never IMEM
  if(rsp.imem.read<Dual>(0x040) != imem40Before) return 30;
  if(rsp.dmem.read<Dual>(0x040) != 0x2405000624060006ull) return 31;

  // CPU direct IMEM write supersedes prior DMA lineage for these four bytes.
  rsp.writeWord(0x04001000, 0x24010007, cpu);
  rsp.ipu.r[1].u32 = 0; executeOne(0x000); checkpoints.push_back(rsp.ipu.r[1].u32);

  // Out-of-bounds backing read returns zero but is not a successful RDRAM read.
  dmaRead(rdram.ram.size, 0x060, true, 0x000);
  executeOne(0x060); checkpoints.push_back(rsp.pipeline.instruction);

  const std::vector<u32> expected{1,2,1,9,4,5,7,0};
  if(checkpoints != expected) return 32;

  string imemHash = hexDigest(rsp.imem.data, rsp.imem.size);
  string dmemHash = hexDigest(rsp.dmem.data, rsp.dmem.size);
  string ramHash = hexDigest(rdram.ram.data, rdram.ram.size);
  std::printf("{\"events\":[");
#if PLAID_RSP_OBSERVER
  if(traced) for(size_t i=0;i<rawEvents.size();i++) {
    const auto& e = rawEvents[i];
    std::printf("%s{\"seq\":%llu,", i ? "," : "", (unsigned long long)e.seq);
    if(e.kind == RawEvent::RdramRead) {
      std::printf("\"kind\":\"rdram_read\",\"dram\":%u,\"bytes\":%u,\"value\":%llu",
        e.address,e.size,(unsigned long long)e.value);
    } else if(e.kind == RawEvent::ImemDmaWrite) {
      std::printf("\"kind\":\"imem_dma_write\",\"imem\":%u,\"dram\":%u,\"bytes\":8,\"value\":%llu",
        e.address,e.other,(unsigned long long)e.value);
    } else if(e.kind == RawEvent::ImemDirectWrite) {
      std::printf("\"kind\":\"imem_direct_write\",\"imem\":%u,\"bytes\":4,\"value\":%llu,\"origin_cpu\":%s",
        e.address,(unsigned long long)e.value,e.originCpu ? "true" : "false");
    } else {
      std::printf("\"kind\":\"fetch\",\"pc\":%u,\"word\":%u",e.address,(u32)e.value);
    }
    std::printf("}");
  }
#endif
  std::printf("],\"state\":{\"checkpoints\":[");
  for(size_t i=0;i<checkpoints.size();i++) std::printf("%s%u",i ? "," : "",checkpoints[i]);
  std::printf("],\"imem_sha256\":\"%s\",\"dmem_sha256\":\"%s\",\"rdram_sha256\":\"%s\",\"pc\":%u,\"dma_busy\":%u,\"dma_full\":%u}}\n",
    imemHash.data(),dmemHash.data(),ramHash.data(),rsp.ipu.pc,(u32)rsp.dma.busy.any(),(u32)rsp.dma.full.any());
  ares::Nintendo64::system.unload();
  return 0;
}
