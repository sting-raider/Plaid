/* SPDX-License-Identifier: ISC
 * Exact-reference fixture: RSP DMEM producer -> CPU LW/SW -> executable SP IMEM.
 */
#ifndef PLAID_RSP_CPU_IMEM_SENSOR
#define PLAID_RSP_CPU_IMEM_SENSOR 1
#endif
#ifndef PLAID_RSP_DEFINITIONS_FIXTURE
#define PLAID_RSP_DEFINITIONS_FIXTURE 0
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <array>
#include <cstdlib>
#include <nall/hash/sha256.hpp>
#include "../042-ares-rsp-dmem-history/observer.hpp"
#include "observer.hpp"

struct ComposeFrontend : Headless {};
static std::string memhash(const u8* data,u32 size) { return std::string(nall::Hash::SHA256(std::span<const u8>{data,size}).digest().data()); }
static string compose_cache_digest() {
  std::vector<u8> bytes;
  auto append=[&](u32 value,u32 count){for(u32 n=count;n;n--)bytes.push_back(value>>(8*(n-1)));};
  for(const auto& line:cpu.icache.lines) {
    append(line.tagKey,4);append(line.index,2);for(u32 word:line.words)append(word,4);
  }
  return nall::Hash::SHA256(std::span<const u8>{bytes.data(),bytes.size()}).digest();
}
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
  for(auto& r:rsp.ipu.r) r.u32=0;
  cpu.scc.status.exceptionLevel=cpu.scc.status.errorLevel=0;cpu.context.setMode();cpu.context.endian=CPU::Context::Endian::Big;cpu.icache.power(false);cpu.dcache.power(false);

  constexpr u32 pure=PLAID_RSP_DEFINITIONS_FIXTURE>=3?0u:PLAID_RSP_DEFINITIONS_FIXTURE?0x3344u:0x11223344u, cpuBase=0xaabbccddu, mixed=0xaaee7722u;
  rsp.dmem.write<Word>(0,0x340800aau);rsp.dmem.write<Word>(4,mixed);
  for(u32 off: {0u,4u,8u,12u,16u}) rsp.imem.write<Word>(off,0xdeadbeefu);
  const u32 words[]={insn_lw(8,16,0),insn_sw(8,16,0x1000),insn_lw(8,16,0),insn_sw(8,16,0x1004),insn_sw(9,16,0),insn_lw(8,16,0),insn_lw(9,16,4),insn_sw(8,16,0x1008),0x01404021u,insn_sw(8,16,0x100c)};
  for(u32 i=0;i<sizeof(words)/sizeof(words[0]);i++) rdram.ram.write<Word>(0x6000+i*4,words[i],RBusDevice::ARES_DEBUGGER);
  if(PLAID_RSP_DEFINITIONS_FIXTURE>=4) {
    rdram.ram.write<Word>(0x6028,0,RBusDevice::ARES_DEBUGGER);
    rdram.ram.write<Word>(0x602c,0,RBusDevice::ARES_DEBUGGER);
  }
  cpu.ipu.r[16].u64=0xffffffffa4000000ull;cpu.ipu.r[9].u64=cpuBase;cpu.ipu.r[10].u64=mixed;
  if(PLAID_RSP_DEFINITIONS_FIXTURE>=9) cpu.ipu.r[17].u64=0xffffffffa4040000ull;

  #if PLAID_RSP_CPU_IMEM_SENSOR
  composeEnabled=traced;plaidCpuInstructionObserver=traced?compose_cpu_instruction:nullptr;plaidSpWordObserver=traced?compose_sp_word:nullptr;plaidRspInstructionObserver=traced?compose_rsp_instruction:nullptr;plaidRspDmemObserver=traced?compose_rsp_dmem:nullptr;
  #if PLAID_RSP_DEFINITIONS_FIXTURE >= 2
  plaidRspWordReadObserver=traced?compose_rsp_word_read:nullptr;
  #endif
  #if PLAID_RSP_DEFINITIONS_FIXTURE >= 4
  plaidRdramScalarObserver=traced?compose_ram_scalar:nullptr;
  plaidCpuFetchObserver=traced?compose_ram_fetch:nullptr;
  #if PLAID_RSP_DEFINITIONS_FIXTURE >= 10
  plaidRdramBurstObserver=traced?compose_cache_burst:nullptr;
  plaidCacheFillObserver=traced?compose_cache_fill:nullptr;
  #endif
  #endif
  #if PLAID_RSP_DEFINITIONS_FIXTURE >= 5
  plaidRspDmaLifecycleObserver=traced?compose_dma_lifecycle:nullptr;
  #if PLAID_RSP_DEFINITIONS_FIXTURE >= 8
  plaidRspDmaPendingObserver=traced?compose_dma_pending:nullptr;
  #endif
  #endif
  #if PLAID_RSP_DEFINITIONS_FIXTURE >= 6
  plaidSpDmaStoreObserver=traced?compose_imem_dma_store:nullptr;
  #endif
  #endif
  auto phase=[](u32 n){
    #if PLAID_RSP_CPU_IMEM_SENSOR
    composePhase=n;
    #else
    (void)n;
    #endif
  };
  std::vector<CpuStep> steps;
  std::vector<string> checkpoints;
  auto checkpoint=[&] { string digest{rsp_machine_digest(),":",cpu.effectiveCount(),
    ":",cpu.Thread::clock,":",cpu.scc.cause.exceptionCode,":",cpu.scc.cause.branchDelay,":",cpu.scc.epc};
    if(PLAID_RSP_DEFINITIONS_FIXTURE>=10)digest.append(":",compose_cache_digest());
    checkpoints.push_back(digest); };
  auto printBytes=[](bool imem,u32 length) {
    std::printf("[");
    for(u32 i=0;i<length;i++) std::printf("%s%u",i?",":"",u32(imem?rsp.imem.read<Byte>(i):rsp.dmem.read<Byte>(i)));
    std::printf("]");
  };
  auto printRam=[] {
    std::printf("[");
    for(u32 address=0x6000;address<(PLAID_RSP_DEFINITIONS_FIXTURE>=10?0x6040:0x6030);address++) std::printf("%s%u",address==0x6000?"":",",u32(rdram.ram.read<Byte>(address,RBusDevice::ARES_DEBUGGER)));
    std::printf("]");
  };
  std::printf("{\"initial_dmem\":");printBytes(false,PLAID_RSP_DEFINITIONS_FIXTURE>=4?4096:8);
  if(PLAID_RSP_DEFINITIONS_FIXTURE>=8) {
    auto& p=rsp.dma.pending;
    if(rsp.dma.full.any() || rsp.dma.busy.any()) std::abort();
    std::printf(",\"initial_pending\":{\"bank\":%u,\"descriptor\":{\"pbus\":%u,\"dram\":%u,\"length\":%u,\"count\":%u,\"skip\":%u}}",(u32)p.pbusRegion,(u32)p.pbusAddress,(u32)p.dramAddress,(u32)p.length,(u32)p.count,(u32)p.skip);
  }
  std::printf(",\"initial_imem\":");printBytes(true,PLAID_RSP_DEFINITIONS_FIXTURE>=3?4096:20);
  if(PLAID_RSP_DEFINITIONS_FIXTURE>=4) { std::printf(",\"initial_ram\":");printRam(); }
  auto cpuStep=[&](u32 p,u32 index,bool synchronize=true){
    phase(p);CpuStep s{};s.phase=p;s.index=index;s.word=index>=12?0:index==11?insn_sw(0,17,8):index==10?0:words[index];s.pc=index>=12?0xffffffff80000000ull+(index==12?0x6030:0x6028):0xffffffffa0006000ull+index*4;
    for(u32 n=0;n<32;n++)s.before[n]=cpu.ipu.r[n].u64;
    cpu.pipeline.setPc(s.pc);if(cpu.instruction() && synchronize)cpu.synchronize();
    if(cpu.scc.cause.exceptionCode||cpu.scc.sysadFrozen){std::fprintf(stderr,"cpu phase=%u exception=%u frozen=%u\n",p,(u32)cpu.scc.cause.exceptionCode,(u32)cpu.scc.sysadFrozen);std::abort();}
    for(u32 n=0;n<32;n++)s.after[n]=cpu.ipu.r[n].u64;steps.push_back(s);checkpoint();
  };
  auto rspInstruction=[&](u32 p,u32 instruction,u32 base,u32 scalar,u8 vectorByte,u32 expected){
    phase(p);rsp.ipu.r[1].u32=base;rsp.ipu.r[2].u32=scalar;rsp.vpu.r[2].byte(0)=vectorByte;
    u32 code=0x100;
    auto install=[&](u32 address,u32 word){
      rsp.imem.write<Word>(address,word);
      #if PLAID_RSP_CPU_IMEM_SENSOR && PLAID_RSP_DEFINITIONS_FIXTURE >= 3
      compose_imem_seed(address,word);
      #endif
    };
    if(PLAID_RSP_DEFINITIONS_FIXTURE && p==1) {
      rsp.ipu.r[2].u32=0x13579bdfu;
      for(u32 word:{0x3400ffffu,PLAID_RSP_DEFINITIONS_FIXTURE>=3?0x34020000u:0x34023344u,PLAID_RSP_DEFINITIONS_FIXTURE>=3?0x34020000u:0x34023344u,0x00401821u,0x00601021u}) {
        install(code,word);code+=4;
      }
      if(PLAID_RSP_DEFINITIONS_FIXTURE >= 2) {
        for(u32 word:{0xac220000u,0x8c240000u,0x00801021u}) {
          install(code,word);code+=4;
        }
      }
    }
    install(code,instruction);install(code+4,0x0000000du);
    rsp.pipeline={};rsp.branch.setPc(0x100);rsp.ipu.pc=0x100;rsp.status.halted=0;rsp.status.broken=0;
    for(u32 guard=0;guard<(PLAID_RSP_DEFINITIONS_FIXTURE>=2?16u:8u)&&!rsp.status.halted;guard++)rsp.instruction();
    if(!rsp.status.halted||(u32)rsp.dmem.read<Word>(0)!=expected){std::fprintf(stderr,"rsp phase=%u halted=%u expected=%08x got=%08x\n",p,(u32)rsp.status.halted,expected,(u32)rsp.dmem.read<Word>(0));std::abort();}
    checkpoint();
  };
  const u32 rspSw=0xac220000u,rspSb=0xa0220000u,rspSbv=(58u<<26)|(1u<<21)|(2u<<16);
  rspInstruction(1,rspSw,0,pure,0,pure);cpuStep(2,0);cpuStep(3,1);
  if(PLAID_RSP_DEFINITIONS_FIXTURE>=3) {
    phase(3);rsp.pipeline={};rsp.pipeline.singleIssue=1;rsp.branch.setPc(0);rsp.ipu.pc=0;
    rsp.status.halted=0;rsp.status.broken=0;rsp.instruction();rsp.status.halted=1;
    checkpoint();
  }
  if(PLAID_RSP_DEFINITIONS_FIXTURE>=4) {
    rsp.writeWord(0x04040000,0,cpu);rsp.writeWord(0x04040004,0x6028,cpu);
    rsp.writeWord(0x0404000c,0,cpu);
    if(!rsp.dma.busy.write || rsp.dma.current.pbusRegion) std::abort();
    rsp.dmaTransferStep();checkpoint();
  }
  rspInstruction(4,rspSw,0,pure,0,pure);cpuStep(5,2);cpuStep(6,3);
  cpu.ipu.r[9].u64=cpuBase;cpuStep(7,4);
  phase(8);rsp.dmem.write<Byte>(1,0xee);checkpoint();
  rspInstruction(9,rspSbv,2,0,0x77,0xaaee77ddu);rspInstruction(10,rspSb,3,0x22,0,0xaaee7722u);
  cpuStep(11,5);cpuStep(12,6);cpuStep(13,7);cpuStep(14,8);cpuStep(15,9);
  phase(16);rsp.writeWord(0x04001010,mixed,cpu);checkpoint();
  if(PLAID_RSP_DEFINITIONS_FIXTURE>=4) cpuStep(17,10);
  if(PLAID_RSP_DEFINITIONS_FIXTURE>=6) {
    phase(18);rsp.writeWord(0x04040000,0x1300,cpu);rsp.writeWord(0x04040004,0x6028,cpu);
    rsp.writeWord(0x04040008,0,cpu);
    if(!rsp.dma.busy.read || !rsp.dma.current.pbusRegion) std::abort();
    rsp.dmaTransferStep();checkpoint();
    phase(19);rsp.pipeline={};rsp.pipeline.singleIssue=1;rsp.branch.setPc(0x300);rsp.ipu.pc=0x300;
    rsp.status.halted=0;rsp.status.broken=0;rsp.instruction();rsp.status.halted=1;checkpoint();
  }
  if(PLAID_RSP_DEFINITIONS_FIXTURE>=7) {
    phase(20);rsp.writeWord(0x04040000,0,cpu);rsp.writeWord(0x04040004,0x6028,cpu);rsp.writeWord(0x04040008,0,cpu);
    if(!rsp.dma.busy.read || rsp.dma.current.pbusRegion) std::abort();
    rsp.dmaTransferStep();checkpoint();
    phase(21);rsp.imem.write<Word>(0x320,0x8c040000);
    #if PLAID_RSP_CPU_IMEM_SENSOR
    compose_imem_seed(0x320,0x8c040000);
    #endif
    rsp.pipeline={};rsp.pipeline.singleIssue=1;rsp.branch.setPc(0x320);rsp.ipu.pc=0x320;
    rsp.status.halted=0;rsp.status.broken=0;rsp.instruction();rsp.status.halted=1;checkpoint();
  }
  if((u32)rsp.dmem.read<Word>(0)!=(PLAID_RSP_DEFINITIONS_FIXTURE>=7?pure:mixed) || (u32)rsp.dmem.read<Word>(4)!=mixed || (u32)rsp.imem.read<Word>(0)!=pure || (u32)rsp.imem.read<Word>(4)!=pure || (u32)rsp.imem.read<Word>(8)!=mixed || (u32)rsp.imem.read<Word>(12)!=mixed || (u32)rsp.imem.read<Word>(16)!=mixed) std::abort();
  if(PLAID_RSP_DEFINITIONS_FIXTURE>=8) {
    phase(22);rsp.writeWord(0x04040000,0x1340,cpu);rsp.writeWord(0x04040004,0x6028,cpu);rsp.writeWord(0x04040008,0,cpu);
    rsp.writeWord(0x04040000,0x1380,cpu);rsp.writeWord(0x04040004,0x6028,cpu);rsp.writeWord(0x04040008,0,cpu);
    rsp.writeWord(0x04040008,0,cpu); // Equal recommit supersedes the pending occurrence.
    rsp.writeWord(0x04040000,0x13c0,cpu);rsp.writeWord(0x04040004,0x6028,cpu);
    if(!rsp.dma.busy.read || !rsp.dma.full.read) std::abort();
    rsp.dmaTransferStep();checkpoint();
    if(!rsp.dma.busy.read || rsp.dma.full.any() || (u32)rsp.dma.current.pbusAddress!=0x3c0) std::abort();
    rsp.dmaTransferStep();checkpoint();
    phase(23);rsp.pipeline={};rsp.pipeline.singleIssue=1;rsp.branch.setPc(0x3c0);rsp.ipu.pc=0x3c0;
    rsp.status.halted=0;rsp.status.broken=0;rsp.instruction();rsp.status.halted=1;checkpoint();
  }
  if(PLAID_RSP_DEFINITIONS_FIXTURE>=9) {
    phase(24);rsp.writeWord(0x04040000,0x13e0,cpu);rsp.writeWord(0x04040004,0x6028,cpu);
    rdram.ram.write<Word>(0x602c,insn_sw(0,17,8),RBusDevice::ARES_DEBUGGER);
    cpuStep(24,11,false); // Controlled scheduler: drain separately after decoder completion.
    if(!rsp.dma.busy.read || rsp.dma.full.any()) std::abort();
    phase(25);rsp.dmaTransferStep();checkpoint();
    phase(26);rsp.pipeline={};rsp.pipeline.singleIssue=1;rsp.branch.setPc(0x3e0);rsp.ipu.pc=0x3e0;
    rsp.status.halted=0;rsp.status.broken=0;rsp.instruction();rsp.status.halted=1;checkpoint();
  }
  if(PLAID_RSP_DEFINITIONS_FIXTURE>=10) {
    phase(27);
    #if PLAID_RSP_CPU_IMEM_SENSOR
    compose_push("cpu_reentry",composeEvents.size()+1,0xffffffff80006030ull,0,0,0,0,0,0,true);
    #endif
    cpuStep(27,12,false);
    phase(28);rdram.ram.write<Word>(0x6028,13,RBusDevice::ARES_DEBUGGER);
    #if PLAID_RSP_CPU_IMEM_SENSOR
    compose_push("cpu_reentry",composeEvents.size()+1,0xffffffff80006028ull,0,0,0,0,0,0,true);
    #endif
    cpuStep(28,13,false);
  }
  #if PLAID_RSP_CPU_IMEM_SENSOR
  composeEnabled=false;
  #endif
  std::printf(",\"events\":");
  #if PLAID_RSP_CPU_IMEM_SENSOR
  compose_print();
  #else
  std::printf("[]");
  #endif
  std::printf(",\"steps\":[");
  for(size_t i=0;i<steps.size();i++){auto&s=steps[i];std::printf("%s{\"phase\":%u,\"index\":%u,\"pc\":%llu,\"word\":%u,\"before\":[",i?",":"",s.phase,s.index,(unsigned long long)s.pc,s.word);for(u32 n=0;n<32;n++)std::printf("%s%llu",n?",":"",(unsigned long long)s.before[n]);std::printf("],\"after\":[");for(u32 n=0;n<32;n++)std::printf("%s%llu",n?",":"",(unsigned long long)s.after[n]);std::printf("]}");}
  std::printf("],\"state\":{\"pc\":%llu,\"count\":%llu,\"exception\":%u,\"frozen\":%s,\"rdram\":\"%s\",\"dmem\":\"%s\",\"imem\":\"%s\",\"dmem0\":%u,\"dmem4\":%u,\"imem0\":%u,\"imem4\":%u,\"imem8\":%u,\"imem12\":%u,\"imem16\":%u,\"regs\":[",(unsigned long long)cpu.ipu.pc,(unsigned long long)cpu.effectiveCount(),(u32)cpu.scc.cause.exceptionCode,cpu.scc.sysadFrozen?"true":"false",memhash(rdram.ram.data,rdram.ram.size).c_str(),memhash(rsp.dmem.data,rsp.dmem.size).c_str(),memhash(rsp.imem.data,rsp.imem.size).c_str(),(u32)rsp.dmem.read<Word>(0),(u32)rsp.dmem.read<Word>(4),(u32)rsp.imem.read<Word>(0),(u32)rsp.imem.read<Word>(4),(u32)rsp.imem.read<Word>(8),(u32)rsp.imem.read<Word>(12),(u32)rsp.imem.read<Word>(16));
  for(u32 n=0;n<32;n++)std::printf("%s%llu",n?",":"",(unsigned long long)cpu.ipu.r[n].u64);std::printf("]},\"checkpoints\":[");
  for(size_t i=0;i<checkpoints.size();i++) std::printf("%s\"%s\"",i?",":"",checkpoints[i].data());
  std::printf("],\"final_dmem\":");printBytes(false,PLAID_RSP_DEFINITIONS_FIXTURE>=4?4096:8);
  std::printf(",\"final_imem\":");printBytes(true,PLAID_RSP_DEFINITIONS_FIXTURE>=3?4096:20);
  if(PLAID_RSP_DEFINITIONS_FIXTURE>=4) { std::printf(",\"final_ram\":");printRam(); }
  std::printf("}\n");ares::Nintendo64::system.unload();return 0;
}
