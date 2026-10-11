/* SPDX-License-Identifier: ISC
 * Original controlled RSP mutation -> CPU refetch composition.
 */
#ifndef PLAID_COMPOSED_SENSOR
#define PLAID_COMPOSED_SENSOR 0
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <cstdlib>
#include <nall/hash/sha256.hpp>
#include <vector>
#include "../042-ares-rsp-dmem-history/observer.hpp"

struct CombinedEvent {
  u32 kind,ordinal,phase,context,rspContext,rspPc,rspWord,address,bank,offset,bytes;
  u64 pc,value;
  bool write;
};
static std::vector<CombinedEvent> combined;
static u32 phase=0,cpuContext=0,activeRsp=0,activePc=0,activeWord=0;
static bool observing=false;
static void add(u32 kind,u32 address=0,u32 bank=0,u32 offset=0,u32 bytes=0,u64 value=0,bool write=false) {
  if(!observing) return;
  combined.push_back({kind,u32(combined.size()+1),phase,cpuContext,activeRsp,activePc,activeWord,address,bank,offset,bytes,cpu.ipu.pc,value,write});
}
#if PLAID_COMPOSED_SENSOR
static void boundary(bool begin,u64,u32,u32 bus,bool,u32 word) {
  if(begin) { if(cpuContext) std::abort();cpuContext=combined.size()+1;add(0,bus); }
  else { if(!cpuContext) std::abort();add(2,bus,0,0,4,word);cpuContext=0; }
}
static void bankWord(bool write,u32 address,u32 bank,u32 offset,u32 value,bool isCpu) {
  if(!isCpu) std::abort();
  add(1,address,bank,offset,4,value,write);
}
static void rspBoundary(bool begin,u32 pc,u32 word,u32 next,bool halted) {
  if(begin) { if(activeRsp) std::abort();activeRsp=combined.size()+1;activePc=pc;activeWord=word;add(3); }
  else { if(!activeRsp || pc!=activePc || word!=activeWord) std::abort();add(5,next,0,0,0,halted);activeRsp=activePc=activeWord=0; }
}
static void dmemSink(u32 offset,u32 bytes,u64 value) {
  if(!activeRsp) return;add(4,0,0,offset,bytes,value,true);
}
#endif
int main(int argc,char** argv) {
  if(argc!=2) return 2;
  Headless frontend;platform=&frontend;
  frontend.cartPak->setAttribute("title","Plaid RSP CPU refetch fixture");
  frontend.cartPak->setAttribute("region","NTSC");frontend.cartPak->setAttribute("cic","CIC-NUS-6102");
  frontend.cartPak->append("program.rom",8192);
  Node::System root;if(!load(root,"[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak","true");option("Deterministic Entropy","true");option("Recompiler","false");
  cartridgeSlot.port->allocate();cartridgeSlot.port->connect();ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;
  for(auto& r:cpu.ipu.r) r.u64=0;
  cpu.scc.status.exceptionLevel=cpu.scc.status.errorLevel=0;cpu.context.setMode();cpu.context.endian=CPU::Context::Endian::Big;
  cpu.icache.power(false);cpu.dcache.power(false);rdram.mapIdentity=1;
  std::vector<u8> hidden(rdram.ram.size/2);rdram.hidden.data=hidden.data();
  rsp.dmem.fill();rsp.imem.fill();
  rsp.dmem.write<Word>(0,0x34081111);
  rsp.imem.write<Word>(0,0xac220000);rsp.imem.write<Word>(4,13);
  rdram.ram.write<Word>(0x6000,0xae090000,RBusDevice::ARES_DEBUGGER);
  bool traced=!strcmp(argv[1],"traced");observing=traced;
  #if PLAID_COMPOSED_SENSOR
  if(traced) {
    plaidSpWordObserver=bankWord;plaidCpuFetchObserver=boundary;
    plaidRspInstructionObserver=rspBoundary;plaidRspDmemObserver=dmemSink;
  }
  #endif
  std::vector<string> checkpoints;
  auto checkpoint=[&] {
    return string{rsp_machine_digest(),":",cpu.effectiveCount(),":",cpu.Thread::clock,
      ":",cpu.scc.cause.exceptionCode,":",cpu.scc.cause.branchDelay,":",cpu.scc.epc};
  };
  auto cpuStep=[&](u32 p,u64 pc,u32 expected) {
    phase=p;cpu.pipeline.setPc(pc);if(cpu.instruction()) cpu.synchronize();
    if(cpu.scc.cause.exceptionCode || cpu.ipu.r[8].u32!=expected) std::abort();
    checkpoints.push_back(checkpoint());
  };
  auto rspStep=[&](u32 p) {
    phase=p;rsp.ipu.r[1].u32=0x1000;rsp.ipu.r[2].u32=0x34082222;
    rsp.pipeline={};rsp.branch.setPc(0);rsp.ipu.pc=0;rsp.status.halted=0;
    for(u32 guard=0;guard<8 && !rsp.status.halted;guard++) rsp.instruction();
    if(!rsp.status.halted) std::abort();checkpoints.push_back(checkpoint());
  };
  cpuStep(1,0xffffffffa4000000ull,0x1111);
  rspStep(2);cpuStep(3,0xffffffffa4000000ull,0x2222);
  rspStep(4);cpuStep(5,0xffffffffa4020000ull,0x2222);
  cpu.ipu.r[16].u64=0xffffffffa4000000ull;cpu.ipu.r[9].u64=0x34083333;
  cpuStep(6,0xffffffffa0006000ull,0x2222);cpuStep(7,0xffffffffa4000000ull,0x3333);
  observing=false;
  if(cpuContext || activeRsp) std::abort();
  std::printf("{\"checkpoints\":[");
  for(size_t i=0;i<checkpoints.size();i++) std::printf("%s\"%s\"",i?",":"",checkpoints[i].data());
  std::printf("],\"events\":[");
  for(size_t i=0;i<combined.size();i++) {
    const auto& e=combined[i];
    std::printf("%s{\"kind\":%u,\"ordinal\":%u,\"phase\":%u,\"context\":%u,\"rsp_context\":%u,\"rsp_pc\":%u,\"rsp_word\":%u,\"address\":%u,\"bank\":%u,\"offset\":%u,\"bytes\":%u,\"pc\":%llu,\"value\":%llu,\"write\":%s}",
      i?",":"",e.kind,e.ordinal,e.phase,e.context,e.rspContext,e.rspPc,e.rspWord,e.address,e.bank,e.offset,e.bytes,
      (unsigned long long)e.pc,(unsigned long long)e.value,e.write?"true":"false");
  }
  std::printf("]}\n");ares::Nintendo64::system.unload();return 0;
}
