/* SPDX-License-Identifier: ISC
 * Shared chronology for completed CPU SP word effects and scoped RSP DMEM sinks.
 * No guest reads, clock steps, serialization, or reference object fields.
 */
struct MixEvent {
  const char* kind;
  u64 ordinal, context, pc, value;
  u32 phase, word, address, bank, offset, bytes;
  bool cpu, cached;
};
static std::vector<MixEvent> mixEvents;
static u32 mixPhase=0, mixRspContext=0, mixRspPc=0, mixRspWord=0;
static u64 mixFetchActive=0, mixFetchPending=0;
static bool mixEnabled=false;

static void mix_push(const char* kind,u64 context,u64 pc,u32 word,u32 address,u32 bank,u32 offset,u32 bytes,u64 value,bool originCpu,bool cached=false) {
  if(!mixEnabled) return;
  mixEvents.push_back({kind,mixEvents.size()+1,context,pc,value,mixPhase,word,address,bank,offset,bytes,originCpu,cached});
}

static void mix_rsp_instruction(bool begin,u32 pc,u32 word,u32 next,bool halted) {
  (void)next;(void)halted;
  if(!mixEnabled) return;
  u32 ordinal=mixEvents.size()+1;
  if(begin) {
    if(mixRspContext) std::abort();
    mixRspContext=ordinal;mixRspPc=pc;mixRspWord=word;
  } else if(!mixRspContext || pc!=mixRspPc || word!=mixRspWord) std::abort();
  mix_push(begin?"rsp_begin":"rsp_end",mixRspContext,pc,word,0,0,0,0,0,false);
  if(!begin) mixRspContext=0;
}

static void mix_rsp_dmem(u32 offset,u32 bytes,u64 value) {
  if(!mixEnabled) return;
  if(!mixRspContext) {
    mix_push("foreign_sink",0,cpu.ipu.pc,0,offset,0,offset,bytes,value,false);
    return;
  }
  mix_push("rsp_sink",mixRspContext,mixRspPc,mixRspWord,offset,0,offset,bytes,value,false);
}

static void mix_sp_word(bool write,u32 address,u32 bank,u32 offset,u32 value,bool originCpu) {
  if(!mixEnabled) return;
  mix_push(write?"sp_write":"sp_read",mixFetchActive,cpu.ipu.pc,0,address,bank,offset,4,value,originCpu);
}

static void mix_fetch_boundary(bool begin,u64 vaddr,u32 translated,u32 bus,bool cached,u32 value) {
  (void)translated;
  if(!mixEnabled) return;
  if(vaddr!=cpu.ipu.pc) std::abort();
  if(begin) {
    if(mixFetchActive || mixFetchPending) std::abort();
    mixFetchActive=mixEvents.size()+1;
  }
  if(!mixFetchActive) std::abort();
  mix_push(begin?"cpu_fetch_begin":"cpu_fetch_end",mixFetchActive,cpu.ipu.pc,0,bus,0,0,4,value,true,cached);
  if(!begin) { mixFetchPending=mixFetchActive;mixFetchActive=0; }
}

static void mix_fetch_complete() {
  if(!mixEnabled) return;
  if(mixFetchActive || !mixFetchPending) std::abort();
  mix_push("cpu_fetch",mixFetchPending,cpu.ipu.pc,0,plaidFetchAccess.physical,0,0,4,cpu.disassembler.fetchedWord(),true,plaidFetchAccess.cached);
  mixFetchPending=0;
}

static string mix_machine_digest() {
  nall::Hash::SHA256 hash;
  std::vector<u64> words;
  auto add=[&](auto value){ words.push_back(u64(value)); };
  for(auto& r:cpu.ipu.r) add(r.u64);
  add(cpu.ipu.hi.u64);add(cpu.ipu.lo.u64);add(cpu.ipu.pc);add(cpu.effectiveCount());
  for(auto& r:rsp.ipu.r) add(r.u32);
  add(rsp.ipu.pc);add(rsp.Thread::clock);add(rsp.branch.pc);add(rsp.branch.nextpc);add(rsp.branch.state);add(rsp.branch.nstate);
  for(auto& r:rsp.vpu.r){ add(r.u128.lo);add(r.u128.hi); }
  for(auto* r:{&rsp.vpu.acch,&rsp.vpu.accm,&rsp.vpu.accl,&rsp.vpu.vcoh,&rsp.vpu.vcol,&rsp.vpu.vcch,&rsp.vpu.vccl,&rsp.vpu.vce}) { add(r->u128.lo);add(r->u128.hi); }
  add(rsp.status.halted);add(rsp.status.broken);add(rsp.status.singleStep);add(rsp.status.interruptOnBreak);
  hash.input(std::span<const u8>{reinterpret_cast<const u8*>(words.data()),words.size()*sizeof(u64)});
  hash.input(std::span<const u8>{rdram.ram.data,rdram.ram.size});
  hash.input(std::span<const u8>{rsp.dmem.data,rsp.dmem.size});
  hash.input(std::span<const u8>{rsp.imem.data,rsp.imem.size});
  return hash.digest();
}

static void mix_print() {
  std::printf("{\"events\":[");
  for(size_t n=0;n<mixEvents.size();n++) {
    const auto& e=mixEvents[n];
    std::printf("%s{\"kind\":\"%s\",\"ordinal\":%llu,\"context\":%llu,\"pc\":%llu,\"phase\":%u,\"word\":%u,\"address\":%u,\"bank\":%u,\"offset\":%u,\"bytes\":%u,\"value\":%llu,\"cpu\":%s,\"cached\":%s}",
      n?",":"",e.kind,(unsigned long long)e.ordinal,(unsigned long long)e.context,(unsigned long long)e.pc,e.phase,e.word,e.address,e.bank,e.offset,e.bytes,(unsigned long long)e.value,e.cpu?"true":"false",e.cached?"true":"false");
  }
  std::printf("]}");
}
