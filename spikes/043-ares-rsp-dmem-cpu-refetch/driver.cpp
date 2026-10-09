/* SPDX-License-Identifier: ISC
 * Original exact-reference composition fixture: RSP DMEM stores -> CPU SP refetch.
 */
#ifndef PLAID_COMPOSE_SENSOR
#define PLAID_COMPOSE_SENSOR 0
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <array>
#include <cstdlib>
#include <vector>
#include <nall/hash/sha256.hpp>
#if PLAID_COMPOSE_SENSOR
#include "observer.hpp"
#endif

struct MixFrontend : Headless {
  auto log(Node::Debugger::Tracer::Tracer node,string_view) -> void override {
    #if PLAID_COMPOSE_SENSOR
    if(node==cpu.debugger.tracer.instruction) mix_fetch_complete();
    #endif
  }
};

int main(int argc,char** argv) {
  if(argc!=2 || (strcmp(argv[1],"plain") && strcmp(argv[1],"traced"))) return 2;
  bool traced=!strcmp(argv[1],"traced");
  MixFrontend frontend;platform=&frontend;
  frontend.cartPak->setAttribute("title","Plaid RSP DMEM CPU refetch composition");
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

  const u32 initialWord=0x340800aau;
  const u32 producedWord=0x34081111u;
  rsp.dmem.write<Word>(0,initialWord);rsp.dmem.write<Word>(4,producedWord);
  rsp.imem.write<Word>(0,0xac220000);      // replaced per RSP phase below
  rsp.imem.write<Word>(4,0x0000000d);      // BREAK
  rdram.ram.write<Word>(0x6000,0xae090000,RBusDevice::ARES_DEBUGGER); // SW t1,0(s0)
  std::array<u8,8> initialBytes{};std::memcpy(initialBytes.data(),rsp.dmem.data,8);

  #if PLAID_COMPOSE_SENSOR
  mixEnabled=traced;
  plaidSpWordObserver=traced ? mix_sp_word : nullptr;
  plaidRspInstructionObserver=traced ? mix_rsp_instruction : nullptr;
  plaidRspDmemObserver=traced ? mix_rsp_dmem : nullptr;
  plaidCpuFetchObserver=traced ? mix_fetch_boundary : nullptr;
  #endif
  cpu.debugger.tracer.instruction->setDepth(0);cpu.debugger.tracer.instruction->setMask(false);cpu.debugger.tracer.instruction->setEnabled(traced);

  auto phase=[](u32 n) {
    #if PLAID_COMPOSE_SENSOR
    mixPhase=n;
    #else
    (void)n;
    #endif
  };
  auto cpuFetch=[&](u32 n,u32 offset,u32 expected) {
    phase(n);cpu.pipeline.setPc(0xffffffffa4000000ull+offset);
    if(cpu.instruction()) cpu.synchronize();
    if(cpu.scc.cause.exceptionCode || cpu.ipu.r[8].u32!=expected) {
      std::fprintf(stderr,"cpuFetch phase=%u exception=%u t0=%08x expected=%08x\n",n,(u32)cpu.scc.cause.exceptionCode,(u32)cpu.ipu.r[8].u32,expected);std::abort();
    }
  };
  auto rspInstruction=[&](u32 n,u32 instruction,u32 base,u32 scalarValue,u8 vectorByte,u32 checkOffset,u32 expectedWord) {
    phase(n);rsp.ipu.r[1].u32=base;rsp.ipu.r[2].u32=scalarValue;rsp.vpu.r[2].byte(0)=vectorByte;
    rsp.imem.write<Word>(0,instruction);
    rsp.pipeline={};rsp.branch.setPc(0);rsp.ipu.pc=0;rsp.status.halted=0;rsp.status.broken=0;
    for(u32 guard=0;guard<8 && !rsp.status.halted;guard++) rsp.instruction();
    if(!rsp.status.halted || rsp.dmem.read<Word>(checkOffset)!=expectedWord) {
      std::fprintf(stderr,"rspInstruction phase=%u instruction=%08x base=%x expected=%08x got=%08x\n",n,instruction,base,expectedWord,(u32)rsp.dmem.read<Word>(checkOffset));std::abort();
    }
  };
  auto cpuStore=[&](u32 n,u32 offset,u32 value) {
    phase(n);cpu.ipu.r[16].u64=0xffffffffa4000000ull+offset;cpu.ipu.r[9].u64=value;
    cpu.pipeline.setPc(0xffffffffa0006000ull);if(cpu.instruction()) cpu.synchronize();
    if(cpu.scc.cause.exceptionCode || rsp.dmem.read<Word>(offset)!=value) {
      std::fprintf(stderr,"cpuStore phase=%u exception=%u offset=%x value=%08x got=%08x\n",n,(u32)cpu.scc.cause.exceptionCode,offset,value,(u32)rsp.dmem.read<Word>(offset));std::abort();
    }
  };

  const u32 rspSw=0xac220000u;
  const u32 rspSb=0xa0220000u;
  const u32 rspSbv=(58u<<26)|(1u<<21)|(2u<<16); // SBV v2[e=0], 0(r1)

  cpuFetch(1,0,0x00aa);
  rspInstruction(2,rspSw,0,producedWord,0,0,producedWord);cpuFetch(3,0,0x1111);
  rspInstruction(4,rspSw,0,producedWord,0,0,producedWord);cpuFetch(5,0,0x1111);
  cpuStore(6,0,producedWord);cpuFetch(7,0,0x1111);
  rspInstruction(8,rspSw,4,producedWord,0,4,producedWord);cpuFetch(9,0,0x1111);

  // Scalar and vector byte stores split one fetched Word across writer generations.
  rspInstruction(10,rspSb,3,0x22,0,0,0x34081122u);cpuFetch(11,0,0x1122);
  rspInstruction(12,rspSbv,2,0,0x77,0,0x34087722u);cpuFetch(13,0,0x7722);

  // Same-value mutation outside an RSP instruction context is deliberately
  // unclassified. It must cut byte 3 lineage even though the payload is unchanged.
  phase(14);rsp.dmem.write<Byte>(3,0x22);cpuFetch(15,0,0x7722);
  // A later measured decoded same-value SB establishes a new known writer.
  rspInstruction(16,rspSb,3,0x22,0,0,0x34087722u);cpuFetch(17,0,0x7722);

  #if PLAID_COMPOSE_SENSOR
  mixEnabled=false;
  string machineHash=mix_machine_digest();
  #else
  string machineHash=nall::Hash::SHA256(std::span<const u8>{rsp.dmem.data,rsp.dmem.size}).digest();
  #endif
  std::printf("{\"initial_bytes\":[");
  for(size_t i=0;i<initialBytes.size();i++) std::printf("%s%u",i?",":"",initialBytes[i]);
  std::printf("],\"word0\":%u,\"word4\":%u,\"t0\":%u,\"machine_sha256\":\"%s\",\"trace\":",
    (u32)rsp.dmem.read<Word>(0),(u32)rsp.dmem.read<Word>(4),(u32)cpu.ipu.r[8].u32,machineHash.data());
  #if PLAID_COMPOSE_SENSOR
  mix_print();
  #else
  std::printf("{\"events\":[]}");
  #endif
  std::printf("}\n");
  ares::Nintendo64::system.unload();return 0;
}
