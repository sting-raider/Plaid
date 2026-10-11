/* SPDX-License-Identifier: ISC
 * Original ordered CPU instruction + completed RDRAM observer.
 */
struct FlowInstructionEvent {
  bool begin;
  u64 ordinal, context, pc;
  u32 phase, word;
  u64 gpr[32];
};
struct FlowScalarEvent {
  u64 ordinal, context, pc, value;
  u32 phase, address, bytes, device;
  bool write;
};
static u64 flowOrdinal=0, flowContext=0, flowPc=0;
static u32 flowPhase=0, flowWord=0;
static bool flowEnabled=false;
static std::vector<FlowInstructionEvent> flowInstructions;
static std::vector<FlowScalarEvent> flowScalars;
static void flow_instruction(bool begin,u64 pc,u32 word) {
  if(!flowEnabled) return;
  if(begin) {
    if(flowContext) std::abort();
    flowContext=++flowOrdinal; flowPc=pc; flowWord=word;
  } else {
    if(!flowContext || word!=flowWord) std::abort();
    ++flowOrdinal;
  }
  FlowInstructionEvent e{begin,flowOrdinal,flowContext,flowPc,flowPhase,flowWord,{}};
  for(u32 i=0;i<32;i++) e.gpr[i]=cpu.ipu.r[i].u64;
  flowInstructions.push_back(e);
  if(!begin) flowContext=flowPc=flowWord=0;
}
static void flow_scalar(bool write,u32 address,u32 bytes,u32 device,u64 value) {
  if(!flowEnabled) return;
  flowScalars.push_back({++flowOrdinal,flowContext,flowPc,value,flowPhase,address,bytes,device,write});
}
static void flow_print() {
  std::printf("\"instruction_events\":[");
  for(size_t n=0;n<flowInstructions.size();n++) {
    auto& e=flowInstructions[n];
    std::printf("%s{\"begin\":%s,\"ordinal\":%llu,\"context\":%llu,\"phase\":%u,\"pc\":%llu,\"word\":%u,\"gpr\":[",
      n?",":"",e.begin?"true":"false",(unsigned long long)e.ordinal,(unsigned long long)e.context,e.phase,(unsigned long long)e.pc,e.word);
    for(u32 i=0;i<32;i++) std::printf("%s%llu",i?",":"",(unsigned long long)e.gpr[i]);
    std::printf("]}");
  }
  std::printf("],\"scalar_events\":[");
  for(size_t n=0;n<flowScalars.size();n++) {
    auto& e=flowScalars[n];
    std::printf("%s{\"ordinal\":%llu,\"context\":%llu,\"phase\":%u,\"pc\":%llu,\"write\":%s,\"address\":%u,\"bytes\":%u,\"uncached_cpu\":%s,\"value\":%llu}",
      n?",":"",(unsigned long long)e.ordinal,(unsigned long long)e.context,e.phase,(unsigned long long)e.pc,e.write?"true":"false",e.address,e.bytes,e.device==(u32)RBusDevice::VR4300_UNCACHED?"true":"false",(unsigned long long)e.value);
  }
  std::printf("]");
}
