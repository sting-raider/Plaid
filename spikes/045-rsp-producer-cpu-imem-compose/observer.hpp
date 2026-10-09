/* SPDX-License-Identifier: ISC
 * Shared chronology for scoped RSP DMEM sinks and CPU SP Word reads/writes.
 */
struct ComposeEvent {
  const char* kind;
  u64 ordinal, context, pc, value;
  u32 phase, word, address, bank, offset, bytes;
  bool cpu;
};
static std::vector<ComposeEvent> composeEvents;
static u32 composePhase=0, composeRspContext=0, composeRspPc=0, composeRspWord=0;
static bool composeEnabled=false;

static void compose_push(const char* kind,u64 context,u64 pc,u32 word,u32 address,u32 bank,u32 offset,u32 bytes,u64 value,bool cpuOrigin) {
  if(!composeEnabled) return;
  composeEvents.push_back({kind,composeEvents.size()+1,context,pc,value,composePhase,word,address,bank,offset,bytes,cpuOrigin});
}

static void compose_rsp_instruction(bool begin,u32 pc,u32 word,u32 next,bool halted) {
  (void)next;(void)halted;
  if(!composeEnabled) return;
  u32 ordinal=composeEvents.size()+1;
  if(begin) {
    if(composeRspContext) std::abort();
    composeRspContext=ordinal;composeRspPc=pc;composeRspWord=word;
  } else if(!composeRspContext || pc!=composeRspPc || word!=composeRspWord) std::abort();
  compose_push(begin?"rsp_begin":"rsp_end",composeRspContext,pc,word,0,0,0,0,0,false);
  if(!begin) composeRspContext=0;
}

static void compose_rsp_dmem(u32 offset,u32 bytes,u64 value) {
  if(!composeEnabled) return;
  if(!composeRspContext) {
    compose_push("foreign_sink",0,cpu.ipu.pc,0,offset,0,offset,bytes,value,false);
    return;
  }
  compose_push("rsp_sink",composeRspContext,composeRspPc,composeRspWord,offset,0,offset,bytes,value,false);
}

static void compose_sp_word(bool write,u32 address,u32 bank,u32 offset,u32 value,bool originCpu) {
  if(!composeEnabled) return;
  compose_push(write?"sp_write":"sp_read",0,cpu.ipu.pc,0,address,bank,offset,4,value,originCpu);
}

static void compose_print() {
  std::printf("[");
  for(size_t n=0;n<composeEvents.size();n++) {
    const auto& e=composeEvents[n];
    std::printf("%s{\"kind\":\"%s\",\"ordinal\":%llu,\"context\":%llu,\"pc\":%llu,\"phase\":%u,\"word\":%u,\"address\":%u,\"bank\":%u,\"offset\":%u,\"bytes\":%u,\"value\":%llu,\"cpu\":%s}",
      n?",":"",e.kind,(unsigned long long)e.ordinal,(unsigned long long)e.context,(unsigned long long)e.pc,e.phase,e.word,e.address,e.bank,e.offset,e.bytes,(unsigned long long)e.value,e.cpu?"true":"false");
  }
  std::printf("]");
}
