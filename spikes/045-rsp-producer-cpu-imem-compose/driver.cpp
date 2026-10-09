/* SPDX-License-Identifier: ISC
 * Exact-reference fixture: RSP DMEM producer -> CPU LW/SW -> executable SP IMEM.
 */
#ifndef PLAID_RSP_CPU_IMEM_SENSOR
#define PLAID_RSP_CPU_IMEM_SENSOR 0
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <array>
#include <cstdlib>
#include <nall/hash/sha256.hpp>
#if PLAID_RSP_CPU_IMEM_SENSOR
#include "observer.hpp"
#endif

struct ComposeFrontend : Headless {};
static std::string memhash(const u8* data,u32 size) { return std::string(nall::Hash::SHA256(std::span<const u8>{data,size}).digest().data()); }
static u32 insn_lw(u32 rt,u32 rs,s16 imm){return (0x23u<<26)|(rs<<21)|(rt<<16)|u16(imm);}
static u32 insn_sw(u32 rt,u32 rs,s16 imm){return (0x2bu<<26)|(rs<<21)|(rt<<16)|u16(imm);}
struct CpuStep { u32 phase,index,word; u64 pc; std::array<u64,32> before,after; };

int main(int argc,char** argv) {
  if(argc!=2 || (strcmp(argv[1],"plain") && strcmp(argv[1],"traced"))) return 2;
  bool traced=!strcmp(argv[1],"traced");
  ComposeFrontend frontend;platform=&frontend;
  frontend.cartPak->setAttribute("title","Plaid RSP producer CPU IMEM composition");
  frontend.cartPak->setAttribute("region","NTSC");frontend.cartPak->setAttribute("cic","CIC-NUS-6102");frontend.cartPak->append("program.rom",8192);
  Node::System root;if(!load(root,"[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak","true");option("Deterministic Entropy","true");option("Recompiler","false");
  cartridgeSlot.port->allocate();cartridgeSlot.port->connect();ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;
  std::vector<u8> hidden(rdram.ram.size/2);rdram.hidden.data=hidden.data();rdram.mapIdentity=1;
  for(auto& r:cpu.ipu.r) r.u64=0;
  cpu.scc.status.exceptionLevel=cpu.scc.status.errorLevel=0;cpu.context.setMode();cpu.context.endian=CPU::Context::Endian::Big;cpu.icache.power(false);cpu.dcache.power(false);

  constexpr u32 pure=0x11223344u, cpuBase=0xaabbccddu, mixed=0xaaee7722u;
  rsp.dmem.write<Word>(0,0x340800aau);rsp.dmem.write<Word>(4,mixed);
  for(u32 off: {0u,4u,8u,12u,16u}) rsp.imem.write<Word>(off,0xdeadbeefu);
  const u32 words[]={insn_lw(8,16,0),insn_sw(8,16,0x1000),insn_lw(8,16,0),insn_sw(8,16,0x1004),insn_sw(9,16,0),insn_lw(8,16,0),insn_lw(9,16,4),insn_sw(8,16,0x1008),0x01404021u,insn_sw(8,16,0x100c)};
  for(u32 i=0;i<sizeof(words)/sizeof(words[0]);i++) rdram.ram.write<Word>(0x6000+i*4,words[i],RBusDevice::ARES_DEBUGGER);
  cpu.ipu.r[16].u64=0xffffffffa4000000ull;cpu.ipu.r[9].u64=cpuBase;cpu.ipu.r[10].u64=mixed;

  #if PLAID_RSP_CPU_IMEM_SENSOR
  composeEnabled=traced;plaidSpWordObserver=traced?compose_sp_word:nullptr;plaidRspInstructionObserver=traced?compose_rsp_instruction:nullptr;plaidRspDmemObserver=traced?compose_rsp_dmem:nullptr;
  #endif
  auto phase=[](u32 n){
    #if PLAID_RSP_CPU_IMEM_SENSOR
    composePhase=n;
    #else
    (void)n;
    #endif
  };
  std::vector<CpuStep> steps;
  auto cpuStep=[&](u32 p,u32 index){
    phase(p);CpuStep s{};s.phase=p;s.index=index;s.word=words[index];s.pc=0xffffffffa0006000ull+index*4;
    for(u32 n=0;n<32;n++)s.before[n]=cpu.ipu.r[n].u64;
    cpu.pipeline.setPc(s.pc);if(cpu.instruction())cpu.synchronize();
    if(cpu.scc.cause.exceptionCode||cpu.scc.sysadFrozen){std::fprintf(stderr,"cpu phase=%u exception=%u frozen=%u\n",p,(u32)cpu.scc.cause.exceptionCode,(u32)cpu.scc.sysadFrozen);std::abort();}
    for(u32 n=0;n<32;n++)s.after[n]=cpu.ipu.r[n].u64;steps.push_back(s);
  };
  auto rspInstruction=[&](u32 p,u32 instruction,u32 base,u32 scalar,u8 vectorByte,u32 expected){
    phase(p);rsp.ipu.r[1].u32=base;rsp.ipu.r[2].u32=scalar;rsp.vpu.r[2].byte(0)=vectorByte;
    rsp.imem.write<Word>(0,instruction);rsp.pipeline={};rsp.branch.setPc(0);rsp.ipu.pc=0;rsp.status.halted=0;rsp.status.broken=0;
    for(u32 guard=0;guard<8&&!rsp.status.halted;guard++)rsp.instruction();
    if(!rsp.status.halted||(u32)rsp.dmem.read<Word>(0)!=expected){std::fprintf(stderr,"rsp phase=%u expected=%08x got=%08x\n",p,expected,(u32)rsp.dmem.read<Word>(0));std::abort();}
  };
  const u32 rspSw=0xac220000u,rspSb=0xa0220000u,rspSbv=(58u<<26)|(1u<<21)|(2u<<16);
  rspInstruction(1,rspSw,0,pure,0,pure);cpuStep(2,0);cpuStep(3,1);
  rspInstruction(4,rspSw,0,pure,0,pure);cpuStep(5,2);cpuStep(6,3);
  cpu.ipu.r[9].u64=cpuBase;cpuStep(7,4);
  phase(8);rsp.dmem.write<Byte>(1,0xee);
  rspInstruction(9,rspSbv,2,0,0x77,0xaaee77ddu);rspInstruction(10,rspSb,3,0x22,0,0xaaee7722u);
  cpuStep(11,5);cpuStep(12,6);cpuStep(13,7);cpuStep(14,8);cpuStep(15,9);
  phase(16);rsp.writeWord(0x04001010,mixed,cpu);
  if((u32)rsp.dmem.read<Word>(0)!=mixed || (u32)rsp.dmem.read<Word>(4)!=mixed || (u32)rsp.imem.read<Word>(0)!=pure || (u32)rsp.imem.read<Word>(4)!=pure || (u32)rsp.imem.read<Word>(8)!=mixed || (u32)rsp.imem.read<Word>(12)!=mixed || (u32)rsp.imem.read<Word>(16)!=mixed) std::abort();
  #if PLAID_RSP_CPU_IMEM_SENSOR
  composeEnabled=false;
  #endif
  std::printf("{\"events\":");
  #if PLAID_RSP_CPU_IMEM_SENSOR
  compose_print();
  #else
  std::printf("[]");
  #endif
  std::printf(",\"steps\":[");
  for(size_t i=0;i<steps.size();i++){auto&s=steps[i];std::printf("%s{\"phase\":%u,\"index\":%u,\"pc\":%llu,\"word\":%u,\"before\":[",i?",":"",s.phase,s.index,(unsigned long long)s.pc,s.word);for(u32 n=0;n<32;n++)std::printf("%s%llu",n?",":"",(unsigned long long)s.before[n]);std::printf("],\"after\":[");for(u32 n=0;n<32;n++)std::printf("%s%llu",n?",":"",(unsigned long long)s.after[n]);std::printf("]}");}
  std::printf("],\"state\":{\"pc\":%llu,\"count\":%llu,\"exception\":%u,\"frozen\":%s,\"rdram\":\"%s\",\"dmem\":\"%s\",\"imem\":\"%s\",\"dmem0\":%u,\"dmem4\":%u,\"imem0\":%u,\"imem4\":%u,\"imem8\":%u,\"imem12\":%u,\"imem16\":%u,\"regs\":[",(unsigned long long)cpu.ipu.pc,(unsigned long long)cpu.effectiveCount(),(u32)cpu.scc.cause.exceptionCode,cpu.scc.sysadFrozen?"true":"false",memhash(rdram.ram.data,rdram.ram.size).c_str(),memhash(rsp.dmem.data,rsp.dmem.size).c_str(),memhash(rsp.imem.data,rsp.imem.size).c_str(),(u32)rsp.dmem.read<Word>(0),(u32)rsp.dmem.read<Word>(4),(u32)rsp.imem.read<Word>(0),(u32)rsp.imem.read<Word>(4),(u32)rsp.imem.read<Word>(8),(u32)rsp.imem.read<Word>(12),(u32)rsp.imem.read<Word>(16));
  for(u32 n=0;n<32;n++)std::printf("%s%llu",n?",":"",(unsigned long long)cpu.ipu.r[n].u64);std::printf("]}}\n");ares::Nintendo64::system.unload();return 0;
}
