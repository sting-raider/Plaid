/* SPDX-License-Identifier: ISC
 * Exact pinned-ares composed RSP IMEM installation-lifetime fixture.
 */
#define main plaid_capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>
#include <vector>
#include <cstring>

using namespace ares;
using namespace ares::Nintendo64;

struct Event {
  u32 seq, caseId, kind, request, pbus, dram, length, count, skip;
  u64 value;
};

static std::vector<Event> events;
static u32 currentCase = 0;
static u32 nextRequest = 0;
static u32 activeRequest = 0;

#ifndef PLAID_BASELINE
static auto observeInstall(u32 kind, u32 pbus, u32 dram, u32 length, u32 count, u32 skip, u64 value) -> void {
  u32 request = activeRequest;
  if(kind == 1) {
    if(activeRequest) std::abort();
    request = activeRequest = ++nextRequest;
  } else if(kind == 2 || kind == 3) {
    if(!activeRequest) std::abort();
    request = activeRequest;
  } else if(kind == 4) {
    request = 0;
  }
  events.push_back({(u32)events.size()+1,currentCase,kind,request,pbus,dram,length,count,skip,value});
  if(kind == 3) activeRequest = 0;
}
#endif

static auto resetRspDma() -> void {
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

static auto checksumImem() -> string {
  return nall::Hash::SHA256(std::span<const u8>{rsp.imem.data, rsp.imem.size}).digest();
}

int main(int argc, char** argv) {
  bool traced = argc > 1 && std::string(argv[1]) == "traced";
  Headless frontend; platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid RSP IMEM install lifetime fixture");
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
#ifndef PLAID_BASELINE
  plaidRspImemInstallObserver = traced ? observeInstall : nullptr;
#endif

  currentCase = 1; resetRspDma();
  put64(0x1000, 0x1111111111111111ull);
  put64(0x1008, 0xdeadbeefdeadbeefull);
  put64(0x1010, 0x2222222222222222ull);
  queueRead(0x1000, 0x200, (1u << 12) | (1u << 23));
  rsp.dmaTransferStep();
  if(rsp.imem.read<Dual>(0x200) != 0x1111111111111111ull) return 10;
  rsp.writeWord(0x04001204, 0x11111111u, cpu);
  if(rsp.imem.read<Dual>(0x200) != 0x1111111111111111ull) return 11;
  rsp.dmaTransferStep();
  if(rsp.imem.read<Dual>(0x208) != 0x2222222222222222ull) return 12;
  auto case1 = checksumImem();

  currentCase = 2; resetRspDma();
  put64(0x2000, 0x3333333333333333ull);
  put64(0x2008, 0x4444444444444444ull);
  put64(0x3000, 0x3333333333333333ull);
  put64(0x3008, 0x4444444444444444ull);
  queueRead(0x2000, 0x300, 0x008); rsp.dmaTransferStep();
  auto firstReloadHash = checksumImem();
  queueRead(0x3000, 0x300, 0x008); rsp.dmaTransferStep();
  auto secondReloadHash = checksumImem();
  if(firstReloadHash != secondReloadHash) return 20;

  currentCase = 3; resetRspDma();
  put64(0x4000, 0x5555555555555555ull);
  put64(0x4008, 0x6666666666666666ull);
  queueRead(0x4000, 0xff8, 0x008); rsp.dmaTransferStep();
  if(rsp.imem.read<Dual>(0xff8) != 0x5555555555555555ull) return 30;
  if(rsp.imem.read<Dual>(0x000) != 0x6666666666666666ull) return 31;
  auto case3 = checksumImem();

  currentCase = 4; resetRspDma();
  put64(0x5000, 0x7777777777777777ull);
  put64(0x6000, 0x8888888888888888ull);
  queueRead(0x5000, 0x380, 0x000);
  queueRead(0x6000, 0x388, 0x000);
  if(!rsp.dma.busy.any() || !rsp.dma.full.any()) return 40;
  rsp.dmaTransferStep();
  if(!rsp.dma.busy.any() || rsp.dma.full.any()) return 41;
  rsp.dmaTransferStep();
  if(rsp.dma.busy.any() || rsp.dma.full.any()) return 42;
  if(rsp.imem.read<Dual>(0x380) != 0x7777777777777777ull || rsp.imem.read<Dual>(0x388) != 0x8888888888888888ull) return 43;
  auto case4 = checksumImem();

#ifndef PLAID_BASELINE
  plaidRspImemInstallObserver = nullptr;
#endif
  std::printf("{\"state\":{\"case1\":\"%s\",\"reload1\":\"%s\",\"reload2\":\"%s\",\"case3\":\"%s\",\"case4\":\"%s\",\"busy\":%u,\"full\":%u},\"events\":[",
    case1.data(), firstReloadHash.data(), secondReloadHash.data(), case3.data(), case4.data(), (u32)rsp.dma.busy.any(), (u32)rsp.dma.full.any());
  for(size_t i=0;i<events.size();i++) {
    const auto& e=events[i];
    const char* kind = e.kind==1?"promote":e.kind==2?"dma_sink":e.kind==3?"complete":"cpu_sink";
    std::printf("%s{\"seq\":%u,\"case\":%u,\"kind\":\"%s\",\"request\":%u,\"pbus\":%u,\"dram\":%u,\"length\":%u,\"count\":%u,\"skip\":%u,\"value\":%llu}",
      i?",":"",e.seq,e.caseId,kind,e.request,e.pbus,e.dram,e.length,e.count,e.skip,(unsigned long long)e.value);
  }
  std::printf("]}\n");
  ares::Nintendo64::system.unload();
  return 0;
}
