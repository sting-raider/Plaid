/* SPDX-License-Identifier: ISC
 * Original actual-decoder context / CPU SP Word fixture reconciliation.
 */
#ifndef PLAID_SP_PRODUCER_SENSOR
#define PLAID_SP_PRODUCER_SENSOR 1
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>
#include "../042-ares-rsp-dmem-history/observer.hpp"

struct ProducerEvent {
  u32 kind,ordinal,context,phase,word,address,bank,offset,value,exception,copError;
  u64 pc;
  bool fr,cu1,originCpu;
  std::vector<u64> gpr,fpr;
};
static std::vector<ProducerEvent> events;
static u32 phase=0,context=0,activeWord=0;
static u64 activePc=0;
static bool observing=false;
static void add(u32 kind,u32 address=0,u32 bank=0,u32 offset=0,u32 value=0,bool originCpu=true) {
  if(!observing) return;
  ProducerEvent event{kind,u32(events.size()+1),context,phase,activeWord,address,bank,offset,value,0,0,
    context?activePc:cpu.ipu.pc,false,false,originCpu,{},{}};
  if(kind!=1) {
    for(auto& r:cpu.ipu.r) event.gpr.push_back(r.u64);
    for(auto& r:cpu.fpu.r) event.fpr.push_back(r.u64);
    event.fr=cpu.scc.status.floatingPointMode;event.cu1=cpu.scc.status.enable.coprocessor1;
    event.exception=cpu.scc.cause.exceptionCode;event.copError=cpu.scc.cause.coprocessorError;
  }
  events.push_back(event);
}
#if PLAID_SP_PRODUCER_SENSOR
static void instruction(bool begin,u64 pc,u32 word) {
  if(begin) {
    if(context) std::abort();context=events.size()+1;activePc=pc;activeWord=word;add(0);
  } else {
    if(!context || word!=activeWord) std::abort();add(2);context=activeWord=activePc=0;
  }
}
static void spWord(bool write,u32 address,u32 bank,u32 offset,u32 value,bool originCpu) {
  if(write) add(1,address,bank,offset,value,originCpu);
}
#endif
static u32 encode(u32 opcode,u32 base,u32 source,s16 immediate) {
  return opcode<<26 | base<<21 | source<<16 | u16(immediate);
}
int main(int argc,char** argv) {
  if(argc!=2 || (strcmp(argv[1],"plain") && strcmp(argv[1],"traced"))) return 2;
  Headless frontend;platform=&frontend;
  frontend.cartPak->setAttribute("title","Plaid actual CPU SP producer fixture");
  frontend.cartPak->setAttribute("region","NTSC");frontend.cartPak->setAttribute("cic","CIC-NUS-6102");
  frontend.cartPak->append("program.rom",8192);
  Node::System root;if(!load(root,"[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak","true");option("Deterministic Entropy","true");option("Recompiler","false");
  cartridgeSlot.port->allocate();cartridgeSlot.port->connect();ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;
  std::vector<u8> hidden(rdram.ram.size/2);rdram.hidden.data=hidden.data();rdram.mapIdentity=1;
  for(auto& r:cpu.ipu.r) r.u64=0;
  for(auto& r:cpu.fpu.r) r.u64=0;
  cpu.context.endian=CPU::Context::Endian::Big;cpu.icache.power(false);cpu.dcache.power(false);
  cpu.scc.status.floatingPointMode=0;cpu.scc.status.enable.coprocessor1=0;
  for(u32 i=0;i<16;i++) rsp.imem.write<Byte>(i,0xa0+i);
  // Generic IMEM storage is host ordered; normalize through the same guest
  // accessor used for the final snapshot and SP Word view.
  std::vector<u8> initial;
  for(u32 i=0;i<16;i++) initial.push_back(rsp.imem.read<Byte>(i));
  bool traced=!strcmp(argv[1],"traced");observing=traced;
  #if PLAID_SP_PRODUCER_SENSOR
  if(traced) { plaidCpuInstructionObserver=instruction;plaidSpWordObserver=spWord; }
  #endif
  std::vector<string> checkpoints;
  auto checkpoint=[&] {
    nall::Hash::SHA256 hash;
    auto digest=rsp_machine_digest();hash.input(std::span<const u8>{reinterpret_cast<const u8*>(digest.data()),digest.size()});
    for(auto& r:cpu.fpu.r) {
      u64 value=r.u64;hash.input(std::span<const u8>{reinterpret_cast<const u8*>(&value),sizeof(value)});
    }
    return string{hash.digest(),":",cpu.effectiveCount(),":",cpu.Thread::clock,":",cpu.scc.cause.exceptionCode,
      ":",cpu.scc.cause.coprocessorError,":",cpu.scc.cause.branchDelay,":",cpu.scc.epc,
      ":",cpu.scc.status.floatingPointMode,":",cpu.scc.status.enable.coprocessor1};
  };
  auto clearException=[&] {
    cpu.scc.status.errorLevel=cpu.scc.status.exceptionLevel=0;
    cpu.scc.cause.exceptionCode=cpu.scc.cause.coprocessorError=cpu.scc.cause.branchDelay=0;
    cpu.scc.badVirtualAddress=0;cpu.scc.sysadFrozen=false;cpu.context.setMode();
  };
  auto execute=[&](u32 p,u32 word) {
    phase=p;clearException();rdram.ram.write<Word>(0x6000,word,RBusDevice::ARES_DEBUGGER);
    cpu.pipeline.setPc(0xffffffffa0006000ull);
    if(cpu.instruction()) cpu.synchronize();
    if(context) std::abort();checkpoints.push_back(checkpoint());
  };
  cpu.ipu.r[1].u64=0xffffffffa4001000ull;cpu.ipu.r[2].u64=0x1122334455667788ull;
  execute(1,encode(0x2b,1,2,0));execute(2,encode(0x2b,1,2,0));
  phase=0;clearException();
  if(!cpu.write<Word>(0xffffffffa4001000ull,0x55667788u)) return 5;
  checkpoints.push_back(checkpoint());
  execute(3,encode(0x28,1,2,1));
  cpu.scc.status.enable.coprocessor1=1;
  cpu.fpu.r[0].u64=0x1122334455667788ull;cpu.fpu.r[1].u64=0x99aabbccddeeff00ull;
  cpu.ipu.r[1].u64=0xffffffffa4001004ull;cpu.scc.status.floatingPointMode=0;
  execute(4,encode(0x39,1,0,0));
  cpu.ipu.r[1].u64=0xffffffffa4001008ull;execute(5,encode(0x39,1,1,0));
  cpu.ipu.r[1].u64=0xffffffffa400100cull;cpu.scc.status.floatingPointMode=1;
  execute(6,encode(0x39,1,1,0));
  cpu.ipu.r[1].u64=0xffffffffa4001000ull;cpu.scc.status.enable.coprocessor1=0;
  execute(7,encode(0x39,1,1,0));
  observing=false;
  std::printf("{\"initial_imem\":[");
  for(size_t i=0;i<initial.size();i++) std::printf("%s%u",i?",":"",initial[i]);
  std::printf("],\"checkpoints\":[");
  for(size_t i=0;i<checkpoints.size();i++) std::printf("%s\"%s\"",i?",":"",checkpoints[i].data());
  std::printf("],\"events\":[");
  for(size_t i=0;i<events.size();i++) {
    const auto& e=events[i];
    std::printf("%s{\"kind\":%u,\"ordinal\":%u,\"context\":%u,\"phase\":%u,\"pc\":%llu,\"word\":%u,\"address\":%u,\"bank\":%u,\"offset\":%u,\"value\":%u,\"exception\":%u,\"cop_error\":%u,\"fr\":%s,\"cu1\":%s,\"cpu\":%s,\"gpr\":[",
      i?",":"",e.kind,e.ordinal,e.context,e.phase,(unsigned long long)e.pc,e.word,e.address,e.bank,e.offset,e.value,
      e.exception,e.copError,e.fr?"true":"false",e.cu1?"true":"false",e.originCpu?"true":"false");
    for(size_t j=0;j<e.gpr.size();j++) std::printf("%s%llu",j?",":"",(unsigned long long)e.gpr[j]);
    std::printf("],\"fpr\":[");
    for(size_t j=0;j<e.fpr.size();j++) std::printf("%s%llu",j?",":"",(unsigned long long)e.fpr[j]);
    std::printf("]}");
  }
  std::printf("],\"final_imem\":[");
  for(u32 i=0;i<16;i++) std::printf("%s%u",i?",":"",u32(rsp.imem.read<Byte>(i)));
  std::printf("]}\n");ares::Nintendo64::system.unload();return 0;
}
