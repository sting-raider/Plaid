/* SPDX-License-Identifier: ISC
 * Original research observer, no extra guest accesses or reference state writes.
 */
struct RspDmemEvent {
  u32 kind,ordinal,context,phase,pc,word,offset,bytes,next;
  u64 value;
  bool halted;
};
static std::vector<RspDmemEvent> rspEvents;
static u32 rspPhase=0,rspContext=0,rspPc=0,rspWord=0,rspForeignWrites=0;
static void rsp_instruction_event(bool begin,u32 pc,u32 word,u32 next,bool halted) {
  u32 ordinal=rspEvents.size()+1;
  if(begin) {
    if(rspContext) std::abort();
    rspContext=ordinal;rspPc=pc;rspWord=word;
  } else if(!rspContext || pc!=rspPc || word!=rspWord) std::abort();
  rspEvents.push_back({begin?0u:2u,ordinal,rspContext,rspPhase,pc,word,0,0,next,0,halted});
  if(!begin) rspContext=0;
}
static void rsp_dmem_event(u32 offset,u32 bytes,u64 value) {
  if(!rspContext) { ++rspForeignWrites;return; }
  rspEvents.push_back({1,u32(rspEvents.size()+1),rspContext,rspPhase,rspPc,rspWord,offset,bytes,0,value,false});
}
static void rsp_print_events() {
  std::printf("{\"format\":\"plaid-rsp-dmem-component-v0\",\"foreign_writes\":%u,\"events\":[",rspForeignWrites);
  for(size_t i=0;i<rspEvents.size();i++) {
    const auto& e=rspEvents[i];
    std::printf("%s{\"kind\":%u,\"ordinal\":%u,\"context\":%u,\"phase\":%u,\"pc\":%u,\"word\":%u,\"offset\":%u,\"bytes\":%u,\"next\":%u,\"value\":%llu,\"halted\":%s}",
      i?",":"",e.kind,e.ordinal,e.context,e.phase,e.pc,e.word,e.offset,e.bytes,e.next,(unsigned long long)e.value,e.halted?"true":"false");
  }
  std::printf("]}\n");
}
static string rsp_machine_digest() {
  std::vector<u64> words;
  auto add=[&](auto value) { words.push_back(u64(value)); };
  for(auto& r:cpu.ipu.r) add(r.u64);
  add(cpu.ipu.hi.u64);add(cpu.ipu.lo.u64);add(cpu.ipu.pc);
  for(auto& r:rsp.ipu.r) add(r.u32);
  add(rsp.ipu.pc);add(rsp.Thread::clock);
  add(rsp.branch.pc);add(rsp.branch.nextpc);add(rsp.branch.state);add(rsp.branch.nstate);
  for(auto& r:rsp.vpu.r) { add(r.u128.lo);add(r.u128.hi); }
  for(auto* r:{&rsp.vpu.acch,&rsp.vpu.accm,&rsp.vpu.accl,&rsp.vpu.vcoh,&rsp.vpu.vcol,&rsp.vpu.vcch,&rsp.vpu.vccl,&rsp.vpu.vce}) { add(r->u128.lo);add(r->u128.hi); }
  add(rsp.vpu.divin);add(rsp.vpu.divout);add(rsp.vpu.divdp);
  for(auto* r:{&rsp.dma.pending,&rsp.dma.current}) {
    add(r->pbusRegion);add(r->pbusAddress);add(r->dramAddress);add(r->length);
    add(r->skip);add(r->count);add(r->originPc);add(r->originCpu);
  }
  add(rsp.dma.busy.read);add(rsp.dma.busy.write);add(rsp.dma.full.read);add(rsp.dma.full.write);add(rsp.dma.clock);
  add(rsp.status.semaphore);add(rsp.status.halted);add(rsp.status.broken);add(rsp.status.full);
  add(rsp.status.singleStep);add(rsp.status.interruptOnBreak);
  for(auto signal:rsp.status.signal) add(signal);
  auto& p=rsp.pipeline;
  add(p.address);add(p.instruction);add(p.clocks);add(p.clocksTotal);add(p.singleIssue);add(p.stallCount);add(p.dblIssueCount);
  for(auto& q:p.previous) { add(q.load);add(q.rWrite);add(q.vWrite); }
  add(p.current.load);add(p.current.rWrite);add(p.current.vWrite);add(p.current.store);add(p.current.branch);add(p.current.rRead);add(p.current.vRead);
  add(rsp.profile.cycles);add(rsp.profile.haltedCycles);
  nall::Hash::SHA256 hash;
  hash.input(std::span<const u8>{reinterpret_cast<const u8*>(words.data()),words.size()*sizeof(u64)});
  hash.input(std::span<const u8>{rdram.ram.data,rdram.ram.size});
  hash.input(std::span<const u8>{rsp.dmem.data,rsp.dmem.size});
  hash.input(std::span<const u8>{rsp.imem.data,rsp.imem.size});
  return hash.digest();
}
