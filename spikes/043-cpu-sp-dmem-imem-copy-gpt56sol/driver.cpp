/* SPDX-License-Identifier: ISC
 * Original bounded VR4300 SP-DMEM -> SP-IMEM copy fixture.
 */
#ifndef PLAID_COPY_SP_SENSOR
#define PLAID_COPY_SP_SENSOR 0
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <cstdlib>
#include <nall/hash/sha256.hpp>
#if PLAID_COPY_SP_SENSOR
#include "observer.hpp"
#endif

struct CopyFrontend : Headless {};

static std::string copy_memory_hash(const u8* data,u32 size) {
  return std::string(nall::Hash::SHA256(std::span<const u8>{data,size}).digest().data());
}

static u32 copy_insn_lw(u32 rt,u32 rs,s16 imm) {
  return (0x23u<<26)|(rs<<21)|(rt<<16)|u16(imm);
}
static u32 copy_insn_sw(u32 rt,u32 rs,s16 imm) {
  return (0x2bu<<26)|(rs<<21)|(rt<<16)|u16(imm);
}

struct CopyStep {
  u32 phase, word;
  u64 pc;
  u64 before8,before9,before10,before16;
  u64 after8,after9,after10,after16;
};

int main(int argc,char** argv) {
  if(argc!=2 || (strcmp(argv[1],"plain") && strcmp(argv[1],"traced"))) return 2;
  bool traced=!strcmp(argv[1],"traced");
  CopyFrontend frontend;platform=&frontend;
  frontend.cartPak->setAttribute("title","Plaid CPU SP DMEM IMEM copy fixture");
  frontend.cartPak->setAttribute("region","NTSC");
  frontend.cartPak->setAttribute("cic","CIC-NUS-6102");
  frontend.cartPak->append("program.rom",8192);
  Node::System root;if(!load(root,"[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak","true");option("Deterministic Entropy","true");option("Recompiler","false");
  cartridgeSlot.port->allocate();cartridgeSlot.port->connect();ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;

  std::vector<u8> hidden(rdram.ram.size/2);rdram.hidden.data=hidden.data();rdram.mapIdentity=1;
  for(auto& r:cpu.ipu.r) r.u64=0;
  cpu.scc.status.exceptionLevel=cpu.scc.status.errorLevel=0;
  cpu.context.setMode();cpu.context.endian=CPU::Context::Endian::Big;
  cpu.icache.power(false);cpu.dcache.power(false);

  constexpr u32 source=0x34081234;
  constexpr u32 clobber=0x00005678;
  rsp.dmem.write<Word>(0x000,source);
  rsp.dmem.write<Word>(0x004,source);  // equal-valued decoy source
  for(u32 off: {0x000u,0x004u,0x008u,0x00cu,0x020u}) rsp.imem.write<Word>(off,0xdeadbeef);

  // Actual interpreted instructions live in uncached RDRAM.
  const u32 words[] = {
    copy_insn_lw(8,16,0x0000),  // 1: load DMEM[0] -> t0
    copy_insn_sw(8,16,0x1000),  // 2: copy t0 -> IMEM[0]
    copy_insn_lw(8,16,0x0000),  // 3: reload source
    copy_insn_lw(9,16,0x0004),  // 4: equal-valued decoy into t1
    copy_insn_sw(8,16,0x1004),  // 5: must still trace to phase 3, not phase 4
    copy_insn_lw(8,16,0x0000),  // 6
    0x34085678,                 // 7: ORI t0,zero,0x5678: clobber
    copy_insn_sw(8,16,0x1008),  // 8: must not certify a copy
    copy_insn_lw(8,16,0x0000),  // 9
    0x01404021,                 // 10: ADDU t0,t2,zero: same-value clobber
    copy_insn_sw(8,16,0x100c),  // 11: must not certify despite equal payload
    copy_insn_sw(8,16,0x0020),  // 13: actual store, but DMEM sink not executable IMEM
    copy_insn_lw(8,16,0x0000),  // 14
    copy_insn_sw(8,16,0x1000),  // 15: same-value rewrite, distinct copy generation
  };
  for(u32 i=0;i<sizeof(words)/sizeof(words[0]);i++)
    rdram.ram.write<Word>(0x6000+i*4,words[i],RBusDevice::ARES_DEBUGGER);

  cpu.ipu.r[16].u64=0xffffffffa4000000ull;  // s0, uncached SP aperture
  cpu.ipu.r[10].u64=source;                 // t2, used for same-value clobber

  #if PLAID_COPY_SP_SENSOR
  copySpEnabled=traced;
  plaidCopySpWordObserver=traced ? copy_sp_word : nullptr;
  #endif

  std::vector<CopyStep> steps;
  auto set_phase=[](u32 n) {
    #if PLAID_COPY_SP_SENSOR
    copyPhase=n;
    #else
    (void)n;
    #endif
  };
  auto step=[&](u32 phase,u32 index,u32 expectedWord) {
    set_phase(phase);
    u64 pc=0xffffffffa0006000ull+index*4;
    CopyStep s{phase,expectedWord,pc,cpu.ipu.r[8].u64,cpu.ipu.r[9].u64,cpu.ipu.r[10].u64,cpu.ipu.r[16].u64,0,0,0,0};
    cpu.pipeline.setPc(pc);
    if(cpu.instruction()) cpu.synchronize();
    if(cpu.scc.cause.exceptionCode || cpu.scc.sysadFrozen) {
      std::fprintf(stderr,"phase=%u exception=%u frozen=%u\n",phase,(u32)cpu.scc.cause.exceptionCode,(u32)cpu.scc.sysadFrozen);
      std::abort();
    }
    s.after8=cpu.ipu.r[8].u64;s.after9=cpu.ipu.r[9].u64;s.after10=cpu.ipu.r[10].u64;s.after16=cpu.ipu.r[16].u64;
    steps.push_back(s);
  };

  step(1,0,words[0]);
  step(2,1,words[1]);
  step(3,2,words[2]);
  step(4,3,words[3]);
  step(5,4,words[4]);
  step(6,5,words[5]);
  step(7,6,words[6]);
  step(8,7,words[7]);
  step(9,8,words[8]);
  step(10,9,words[9]);
  step(11,10,words[10]);

  // Out-of-instruction CPU-thread sink. Thread identity alone must not make it a producer certificate.
  set_phase(12);
  rsp.writeWord(0x04001020,source,cpu);

  step(13,11,words[11]);
  step(14,12,words[12]);
  step(15,13,words[13]);

  if((u32)rsp.imem.read<Word>(0x000)!=source ||
     (u32)rsp.imem.read<Word>(0x004)!=source ||
     (u32)rsp.imem.read<Word>(0x008)!=clobber ||
     (u32)rsp.imem.read<Word>(0x00c)!=source ||
     (u32)rsp.imem.read<Word>(0x020)!=source ||
     (u32)rsp.dmem.read<Word>(0x020)!=source) std::abort();

  #if PLAID_COPY_SP_SENSOR
  copySpEnabled=false;
  #endif

  std::printf("{");
  #if PLAID_COPY_SP_SENSOR
  copy_sp_print();
  #else
  std::printf("\"events\":[]");
  #endif
  std::printf(",\"steps\":[");
  for(size_t n=0;n<steps.size();n++) {
    const auto& s=steps[n];
    std::printf("%s{\"phase\":%u,\"pc\":%llu,\"word\":%u,"
      "\"before\":[%llu,%llu,%llu,%llu],\"after\":[%llu,%llu,%llu,%llu]}",
      n ? "," : "",s.phase,(unsigned long long)s.pc,s.word,
      (unsigned long long)s.before8,(unsigned long long)s.before9,
      (unsigned long long)s.before10,(unsigned long long)s.before16,
      (unsigned long long)s.after8,(unsigned long long)s.after9,
      (unsigned long long)s.after10,(unsigned long long)s.after16);
  }
  std::printf("],\"state\":{\"pc\":%llu,\"count\":%llu,\"exception\":%u,"
    "\"hi\":%llu,\"lo\":%llu,\"epc\":%llu,\"frozen\":%s,"
    "\"rdram_sha256\":\"%s\",\"hidden_sha256\":\"%s\",\"dmem_sha256\":\"%s\",\"imem_sha256\":\"%s\","
    "\"dmem0\":%u,\"dmem4\":%u,\"dmem20\":%u,\"imem0\":%u,\"imem4\":%u,\"imem8\":%u,\"imem12\":%u,\"imem32\":%u,"
    "\"regs\":[",
    (unsigned long long)cpu.ipu.pc,(unsigned long long)cpu.effectiveCount(),(u32)cpu.scc.cause.exceptionCode,
    (unsigned long long)cpu.ipu.hi.u64,(unsigned long long)cpu.ipu.lo.u64,(unsigned long long)cpu.scc.epc,
    cpu.scc.sysadFrozen ? "true" : "false",
    copy_memory_hash(rdram.ram.data,rdram.ram.size).c_str(),copy_memory_hash(hidden.data(),hidden.size()).c_str(),
    copy_memory_hash(rsp.dmem.data,rsp.dmem.size).c_str(),copy_memory_hash(rsp.imem.data,rsp.imem.size).c_str(),
    (u32)rsp.dmem.read<Word>(0),(u32)rsp.dmem.read<Word>(4),(u32)rsp.dmem.read<Word>(0x20),
    (u32)rsp.imem.read<Word>(0),(u32)rsp.imem.read<Word>(4),(u32)rsp.imem.read<Word>(8),
    (u32)rsp.imem.read<Word>(0xc),(u32)rsp.imem.read<Word>(0x20));
  for(u32 n=0;n<32;n++) std::printf("%s%llu",n ? "," : "",(unsigned long long)cpu.ipu.r[n].u64);
  std::printf("]}}\n");
  ares::Nintendo64::system.unload();
  return 0;
}
