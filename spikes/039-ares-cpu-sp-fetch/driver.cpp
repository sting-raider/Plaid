/* SPDX-License-Identifier: ISC
 * Original actual CPU/SP backing and mutation fixture.
 */
#ifndef PLAID_SP_SENSOR
#define PLAID_SP_SENSOR 0
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <cstdlib>
#include <nall/hash/sha256.hpp>
#if PLAID_SP_SENSOR
#include "observer.hpp"
#endif
struct SpFrontend : Headless {
  auto log(Node::Debugger::Tracer::Tracer node,string_view) -> void override {
    #if PLAID_SP_SENSOR
    if(node==cpu.debugger.tracer.instruction) sp_fetch();
    #endif
  }
};
static std::string memory_hash(const u8* data,u32 size) {
  return std::string(nall::Hash::SHA256(std::span<const u8>{data,size}).digest().data());
}
int main(int argc,char** argv) {
  if(argc!=2 || (strcmp(argv[1],"plain") && strcmp(argv[1],"traced"))) return 2;
  bool traced=!strcmp(argv[1],"traced");
  SpFrontend frontend;platform=&frontend;
  frontend.cartPak->setAttribute("title","Plaid CPU SP fetch fixture");
  frontend.cartPak->setAttribute("region","NTSC");frontend.cartPak->setAttribute("cic","CIC-NUS-6102");
  frontend.cartPak->append("program.rom",8192);
  Node::System root;if(!load(root,"[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak","true");option("Deterministic Entropy","true");option("Recompiler","false");
  cartridgeSlot.port->allocate();cartridgeSlot.port->connect();ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;
  std::vector<u8> hidden(rdram.ram.size/2);rdram.hidden.data=hidden.data();rdram.mapIdentity=1;
  for(auto& r:cpu.ipu.r) r.u64=0;
  cpu.scc.status.exceptionLevel=cpu.scc.status.errorLevel=0;cpu.context.setMode();cpu.context.endian=CPU::Context::Endian::Big;
  cpu.icache.power(false);cpu.dcache.power(false);
  rsp.dmem.write<Word>(0,0x34081111);rsp.imem.write<Word>(0,0x34082222);
  rsp.dmem.write<Word>(0x40,0x8e080000);rsp.dmem.write<Word>(0x44,0);rsp.dmem.write<Word>(0x80,0);
  rdram.ram.write<Word>(0x6000,0xae090000,RBusDevice::ARES_DEBUGGER);
  rdram.ram.write<Word>(0x6004,(0x28u<<26)|(16u<<21)|(9u<<16)|3,RBusDevice::ARES_DEBUGGER);
  rdram.ram.write<Word>(0x6008,0x8e080000,RBusDevice::ARES_DEBUGGER);
  rdram.ram.write<Word>(0x1000,0x34084444,RBusDevice::ARES_DEBUGGER);
  rdram.ram.write<Word>(0x1004,0,RBusDevice::ARES_DEBUGGER);
  rdram.ram.write<Word>(0x2000,0x34085555,RBusDevice::ARES_DEBUGGER);
  rdram.ram.write<Word>(0x2004,0,RBusDevice::ARES_DEBUGGER);
  #if PLAID_SP_SENSOR
  spEnabled=traced;plaidSpWordObserver=traced ? sp_word : nullptr;plaidSpDmaStoreObserver=traced ? sp_dma : nullptr;
  plaidRdramScalarObserver=traced ? sp_rdram : nullptr;plaidCpuFetchObserver=traced ? sp_boundary : nullptr;
  #endif
  cpu.debugger.tracer.instruction->setDepth(0);cpu.debugger.tracer.instruction->setMask(false);
  cpu.debugger.tracer.instruction->setEnabled(traced);
  std::vector<std::string> checkpoints;
  auto phase=[](u32 n) {
    #if PLAID_SP_SENSOR
    spPhase=n;
    #else
    (void)n;
    #endif
  };
  auto step=[&](u32 n,u64 pc,u32 t0,bool frozen=false) {
    phase(n);cpu.pipeline.setPc(pc);if(cpu.instruction()) cpu.synchronize();
    if(cpu.scc.cause.exceptionCode || cpu.ipu.r[8].u32!=t0 || bool(cpu.scc.sysadFrozen)!=frozen) {
      std::fprintf(stderr,"phase=%u exception=%u t0=%x expected=%x frozen=%u\n",n,
        (u32)cpu.scc.cause.exceptionCode,(u32)cpu.ipu.r[8].u32,t0,(u32)cpu.scc.sysadFrozen);std::abort();
    }
    char summary[256];
    std::snprintf(summary,sizeof(summary),"{\"phase\":%u,\"pc\":%llu,\"count\":%llu,\"t0\":%u,\"frozen\":%s,\"dmem\":%u,\"imem\":%u}",
      n,(unsigned long long)cpu.ipu.pc,(unsigned long long)cpu.effectiveCount(),(u32)cpu.ipu.r[8].u32,
      frozen ? "true" : "false",(u32)rsp.dmem.read<Word>(0),(u32)rsp.imem.read<Word>(0));
    checkpoints.emplace_back(summary);
  };
  step(1,0xffffffffa4000000ull,0x1111);step(2,0xffffffffa4001000ull,0x2222);
  step(3,0xffffffffa4020000ull,0x1111);step(4,0xffffffffa4021000ull,0x2222);
  cpu.ipu.r[16].u64=0xffffffffa4000080ull;
  step(5,0xffffffffa4000040ull,0);step(6,0xffffffffa4000044ull,0);
  cpu.ipu.r[16].u64=0xffffffffa4001000ull;cpu.ipu.r[9].u64=0x34083333;
  step(7,0xffffffffa0006000ull,0);step(8,0xffffffffa4001000ull,0x3333);
  // Equal-value successful store remains a separate observed mutation.
  step(9,0xffffffffa0006000ull,0x3333);step(10,0xffffffffa4001000ull,0x3333);
  cpu.ipu.r[16].u64=0xffffffffa4001004ull;cpu.ipu.r[9].u64=0;
  step(11,0xffffffffa0006000ull,0x3333);step(12,0xffffffffa4001000ull,0x3333);
  auto dma=[&](u32 n,u32 dram,bool imem) {
    phase(n);rsp.writeWord(0x04040000,imem ? 0x1000 : 0,cpu);rsp.writeWord(0x04040004,dram,cpu);
    rsp.writeWord(0x04040008,0,cpu);u32 guard=0;
    while(rsp.dma.busy.any()) { rsp.dmaTransferStep();if(++guard>4) std::abort(); }
  };
  dma(13,0x1000,true);step(14,0xffffffffa4001000ull,0x4444);
  dma(15,0x2000,false);step(16,0xffffffffa4000000ull,0x5555);
  // SB +3 retains upper register bits in the actual full-word SP sink.
  cpu.ipu.r[16].u64=0xffffffffa4001000ull;cpu.ipu.r[9].u64=0x34086666;
  step(17,0xffffffffa0006004ull,0x5555);step(18,0xffffffffa4001000ull,0x6666);
  cpu.ipu.r[16].u64=0xffffffffa4040010ull;
  step(19,0xffffffffa0006008ull,1); // CPU LW from status IO is not SP backing.
  step(20,0xffffffff84000000ull,1,true); // Cached SP path freezes; no backing read.
  #if PLAID_SP_SENSOR
  spEnabled=false;
  #endif
  std::printf("{");
  #if PLAID_SP_SENSOR
  sp_print();
  #else
  std::printf("\"events\":[]");
  #endif
  std::printf(",\"checkpoints\":[");for(size_t i=0;i<checkpoints.size();i++) std::printf("%s%s",i ? "," : "",checkpoints[i].c_str());
  std::printf("],\"state\":{\"pc\":%llu,\"count\":%llu,\"exception\":%u,\"hi\":%llu,\"lo\":%llu,\"epc\":%llu,\"frozen\":%s,\"rdram_sha256\":\"%s\",\"hidden_sha256\":\"%s\",\"dmem_sha256\":\"%s\",\"imem_sha256\":\"%s\",\"regs\":[",
    (unsigned long long)cpu.ipu.pc,(unsigned long long)cpu.effectiveCount(),(u32)cpu.scc.cause.exceptionCode,
    (unsigned long long)cpu.ipu.hi.u64,(unsigned long long)cpu.ipu.lo.u64,(unsigned long long)cpu.scc.epc,
    cpu.scc.sysadFrozen ? "true" : "false",memory_hash(rdram.ram.data,rdram.ram.size).c_str(),memory_hash(hidden.data(),hidden.size()).c_str(),
    memory_hash(rsp.dmem.data,rsp.dmem.size).c_str(),memory_hash(rsp.imem.data,rsp.imem.size).c_str());
  for(u32 n=0;n<32;n++) std::printf("%s%llu",n ? "," : "",(unsigned long long)cpu.ipu.r[n].u64);
  std::printf("]}}\n");ares::Nintendo64::system.unload();return 0;
}
