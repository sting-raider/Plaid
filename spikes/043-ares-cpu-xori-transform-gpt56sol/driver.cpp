/* SPDX-License-Identifier: ISC
 * Controlled LW/LWU -> XORI -> SW transformed provenance fixture for pinned ares.
 */
#ifndef PLAID_CPU_XORI_TRANSFORM_SENSOR
#define PLAID_CPU_XORI_TRANSFORM_SENSOR 1
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>
#if PLAID_CPU_XORI_TRANSFORM_SENSOR
#include "observer.hpp"
#endif

static constexpr u32 SourceA=0x1000, SourceB=0x1100;
static constexpr u32 DestBase=0x2000, CodeBase=0x6000;
static constexpr u32 HighValue=0x89abcdef, PlainValue=0x12345678, SmallValue=0x00001234;

static void observers(bool enabled) {
#if PLAID_CPU_XORI_TRANSFORM_SENSOR
  flowEnabled=enabled;
  plaidCpuInstructionObserver=enabled?flow_instruction:nullptr;
  plaidRdramScalarObserver=enabled?flow_scalar:nullptr;
#else
  (void)enabled;
#endif
}
static u32 backing(u32 address) {
#if PLAID_CPU_XORI_TRANSFORM_SENSOR
  auto saved=plaidRdramScalarObserver; plaidRdramScalarObserver=nullptr;
#endif
  u32 value=rdram.ram.read<Word>(address,RBusDevice::ARES_DEBUGGER);
#if PLAID_CPU_XORI_TRANSFORM_SENSOR
  plaidRdramScalarObserver=saved;
#endif
  return value;
}
static void put(u32 address,u32 word) { rdram.ram.write<Word>(address,word,RBusDevice::ARES_DEBUGGER); }
static void run_case(u32 phase,u32 offset,u32 count,bool traced) {
#if PLAID_CPU_XORI_TRANSFORM_SENSOR
  flowPhase=phase;
#endif
  observers(traced);
  cpu.pipeline.setPc(0xffffffff80000000ull | (CodeBase+offset));
  for(u32 i=0;i<count;i++) if(cpu.instruction()) cpu.synchronize();
  observers(false);
}
static void setup(u32 source,u32 destination) {
  cpu.ipu.r[16].u64=0xffffffffa0000000ull | source;
  cpu.ipu.r[17].u64=0xffffffffa0000000ull | destination;
  cpu.ipu.r[18].u64=0xffffffffa0001100ull;
  cpu.ipu.r[8].u64=0;
  cpu.ipu.r[9].u64=0;
}
int main(int argc,char** argv) {
  if(argc!=2 || (strcmp(argv[1],"plain") && strcmp(argv[1],"traced"))) return 2;
  bool traced=!strcmp(argv[1],"traced");
  Headless frontend; platform=&frontend;
  frontend.cartPak->setAttribute("title","Plaid CPU XORI transform fixture");
  frontend.cartPak->setAttribute("region","NTSC");
  frontend.cartPak->setAttribute("cic","CIC-NUS-6102");
  frontend.cartPak->append("program.rom",8192);
  Node::System root;
  if(!load(root,"[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak","true"); option("Deterministic Entropy","true"); option("Recompiler","false");
  cartridgeSlot.port->allocate(); cartridgeSlot.port->connect();
  ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;
  std::vector<u8> hidden(rdram.ram.size/2); rdram.hidden.data=hidden.data(); rdram.mapIdentity=1;
  for(auto& reg:cpu.ipu.r) reg.u64=0;
  cpu.scc.status.errorLevel=cpu.scc.status.exceptionLevel=0; cpu.context.setMode(); cpu.dcache.power(false); cpu.icache.power(false);

  // Positive LW transform: t0 = [s0]; t0 ^= 0x00ff; [s1] = t0.
  put(CodeBase+0x000,0x8e080000); put(CodeBase+0x004,0x390800ff); put(CodeBase+0x008,0xae280000);
  // Positive LWU transform.
  put(CodeBase+0x040,0x9e080000); put(CodeBase+0x044,0x3908f00f); put(CodeBase+0x048,0xae280000);
  // Same-value transform generation (XORI imm=0).
  put(CodeBase+0x080,0x8e080000); put(CodeBase+0x084,0x39080000); put(CodeBase+0x088,0xae280000);
  // Equal-value decoy read in t1 before the real t0 chain.
  put(CodeBase+0x0c0,0x8e490000); put(CodeBase+0x0c4,0x8e080000); put(CodeBase+0x0c8,0x390800ff); put(CodeBase+0x0cc,0xae280000);
  // Wrong-source XORI: load t0, but XORI reads t1 with equal bits.
  put(CodeBase+0x100,0x8e080000); put(CodeBase+0x104,0x392800ff); put(CodeBase+0x108,0xae280000);
  // Equal-bit non-XORI clobber from zero.
  put(CodeBase+0x140,0x8e080000); put(CodeBase+0x144,0x34081234); put(CodeBase+0x148,0xae280000);
  // Failed misaligned load, no completed backing read.
  put(CodeBase+0x180,0x8e080001);

  put(SourceA,HighValue); put(DestBase+0x00,0); setup(SourceA,DestBase+0x00);
  run_case(1,0x000,3,traced); u32 d1=backing(DestBase+0x00); u64 p1=cpu.ipu.r[8].u64;

  put(SourceA,HighValue); put(DestBase+0x04,0); setup(SourceA,DestBase+0x04);
  run_case(2,0x040,3,traced); u32 d2=backing(DestBase+0x04); u64 p2=cpu.ipu.r[8].u64;

  put(SourceA,PlainValue); put(DestBase+0x08,0); setup(SourceA,DestBase+0x08);
  run_case(3,0x080,3,traced); u32 d3=backing(DestBase+0x08); u64 p3=cpu.ipu.r[8].u64;

  put(SourceA,HighValue); put(SourceB,HighValue); put(DestBase+0x0c,0); setup(SourceA,DestBase+0x0c);
  run_case(4,0x0c0,4,traced); u32 d4=backing(DestBase+0x0c);

  put(SourceA,HighValue); put(DestBase+0x10,0); setup(SourceA,DestBase+0x10); cpu.ipu.r[9].u64=0xffffffff89abcdefull;
  run_case(5,0x100,3,traced); u32 d5=backing(DestBase+0x10);

  put(SourceA,SmallValue); put(DestBase+0x14,0); setup(SourceA,DestBase+0x14);
  run_case(6,0x140,3,traced); u32 d6=backing(DestBase+0x14);

  put(SourceA,HighValue); setup(SourceA,DestBase+0x18); cpu.ipu.r[8].u64=0xfeedface;
  run_case(7,0x180,1,traced); u32 finalException=cpu.scc.cause.exceptionCode; u64 failedT0=cpu.ipu.r[8].u64;

  std::printf("{");
#if PLAID_CPU_XORI_TRANSFORM_SENSOR
  flow_print();
#else
  std::printf("\"instruction_events\":[],\"scalar_events\":[]");
#endif
  std::printf(",\"facts\":{\"d1\":%u,\"d2\":%u,\"d3\":%u,\"d4\":%u,\"d5\":%u,\"d6\":%u,\"p1\":%llu,\"p2\":%llu,\"p3\":%llu,\"failed_t0\":%llu,\"final_exception\":%u}",
    d1,d2,d3,d4,d5,d6,(unsigned long long)p1,(unsigned long long)p2,(unsigned long long)p3,(unsigned long long)failedT0,finalException);
  auto ramHash=nall::Hash::SHA256(std::span<const u8>{rdram.ram.data,rdram.ram.size}).digest();
  std::printf(",\"state\":{\"pc\":%llu,\"count\":%llu,\"ram_sha256\":\"%s\"}}\n",(unsigned long long)cpu.ipu.pc,(unsigned long long)cpu.effectiveCount(),ramHash.data());
  ares::Nintendo64::system.unload(); return 0;
}
