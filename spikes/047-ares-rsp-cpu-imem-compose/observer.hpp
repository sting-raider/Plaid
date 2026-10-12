/* SPDX-License-Identifier: ISC
 * Original unified chronology of actual decoder and completed SP effects.
 */
struct ComposeEvent {
  const char* kind;
  u64 ordinal,context,pc,value;
  u32 phase,word,address,bank,offset,bytes,next,vectorByte;
  bool cpu,halted;
  std::vector<u64> gpr;
  std::vector<u32> rgpr;
  bool dmaValid=false,fetchValid=false,fetchCached=false;
  u32 dmaPbus=0,dmaDram=0,dmaLength=0,dmaCount=0,dmaSkip=0,fetchPhysical=0;
};
static std::vector<ComposeEvent> composeEvents;
static u32 composePhase=0,composeRspContext=0,composeRspPc=0,composeRspWord=0;
static u32 composeCpuContext=0,composeCpuWord=0;
static u64 composeCpuPc=0;
static bool composeEnabled=false;
static u64 composeFetchContext=0,composeFetchPc=0;
static u64 composeDmaContext=0;

static void compose_push(const char* kind,u64 context,u64 pc,u32 word,
    u32 address=0,u32 bank=0,u32 offset=0,u32 bytes=0,u64 value=0,bool cpuOrigin=false,
    u32 next=0,bool halted=false) {
  if(!composeEnabled) return;
  ComposeEvent e{kind,composeEvents.size()+1,context,pc,value,composePhase,word,
    address,bank,offset,bytes,next,0,cpuOrigin,halted,{},{}};
  if(!strcmp(kind,"cpu_begin") || !strcmp(kind,"cpu_end"))
    for(auto& r:cpu.ipu.r) e.gpr.push_back(r.u64);
  if(!strcmp(kind,"rsp_begin") || !strcmp(kind,"rsp_end")) {
    for(auto& r:rsp.ipu.r) e.rgpr.push_back(r.u32);
    e.vectorByte=rsp.vpu.r[2].byte(0);
  }
  composeEvents.push_back(e);
}

#if PLAID_RSP_CPU_IMEM_SENSOR
static void compose_cpu_instruction(bool begin,u64 pc,u32 word) {
  if(begin) {
    if(composeCpuContext || composeRspContext) std::abort();
    composeCpuContext=composeEvents.size()+1;composeCpuPc=pc;composeCpuWord=word;
  } else if(!composeCpuContext || word!=composeCpuWord) std::abort();
  compose_push(begin?"cpu_begin":"cpu_end",composeCpuContext,composeCpuPc,word,0,0,0,0,0,true);
  if(!begin) composeCpuContext=composeCpuPc=composeCpuWord=0;
}
static void compose_rsp_instruction(bool begin,u32 pc,u32 word,u32 next,bool halted) {
  if(begin) {
    if(composeRspContext || composeCpuContext) std::abort();
    composeRspContext=composeEvents.size()+1;composeRspPc=pc;composeRspWord=word;
  } else if(!composeRspContext || pc!=composeRspPc || word!=composeRspWord) std::abort();
  compose_push(begin?"rsp_begin":"rsp_end",composeRspContext,pc,word,0,0,0,0,0,false,next,halted);
  if(!begin) composeRspContext=composeRspPc=composeRspWord=0;
}
static void compose_rsp_dmem(u32 offset,u32 bytes,u64 value) {
  if(composeRspContext)
    compose_push("rsp_sink",composeRspContext,composeRspPc,composeRspWord,offset,0,offset,bytes,value);
  else compose_push("foreign_sink",composeCpuContext,composeCpuContext?composeCpuPc:cpu.ipu.pc,
    composeCpuWord,offset,0,offset,bytes,value);
}
#if PLAID_RSP_DEFINITIONS_FIXTURE >= 2
static void compose_rsp_word_read(u32 address,u32 value) {
  if(!composeRspContext) std::abort();
  compose_push("rsp_read",composeRspContext,composeRspPc,composeRspWord,address,0,address&4095,4,value);
}
#endif
#if PLAID_RSP_DEFINITIONS_FIXTURE >= 3
static void compose_imem_seed(u32 address,u32 value) {
  if(composeCpuContext || composeRspContext) std::abort();
  compose_push("opaque_imem_seed",0,cpu.ipu.pc,0,address,1,address,4,value);
}
#endif
static void compose_sp_word(bool write,u32 address,u32 bank,u32 offset,u32 value,bool originCpu) {
  compose_push(write?"sp_write":"sp_read",composeCpuContext,
    composeCpuContext?composeCpuPc:cpu.ipu.pc,composeCpuWord,address,bank,offset,4,value,originCpu);
}
#if PLAID_RSP_DEFINITIONS_FIXTURE >= 4
#if PLAID_RSP_DEFINITIONS_FIXTURE >= 5
static void compose_dma_lifecycle(bool begin,u32 bank,bool write,u32 pbus,u32 dram,u32 length,u32 count,u32 skip) {
  if(bank || !write || composeCpuContext || composeRspContext || composeFetchContext) std::abort();
  if(begin) {
    if(composeDmaContext) std::abort();
    composeDmaContext=composeEvents.size()+1;
  } else if(!composeDmaContext) std::abort();
  compose_push(begin?"dma_promote":"dma_complete",composeDmaContext,cpu.ipu.pc,0,dram,0,pbus);
  if(begin) {
    auto& event=composeEvents.back();event.dmaValid=true;
    event.dmaPbus=pbus;event.dmaDram=dram;event.dmaLength=length;event.dmaCount=count;event.dmaSkip=skip;
  } else composeDmaContext=0;
}
#endif
static void compose_ram_fetch(bool begin,u64 pc,u32 physical,u32 busAddress,bool cached,u32 value) {
  if(composeCpuContext || composeRspContext || cached || physical!=busAddress) std::abort();
  if(begin) {
    if(composeFetchContext) std::abort();
    composeFetchContext=composeEvents.size()+1;composeFetchPc=pc;
  } else if(!composeFetchContext || composeFetchPc!=pc) std::abort();
  compose_push(begin?"ram_fetch_begin":"ram_fetch_end",composeFetchContext,pc,0,busAddress,0,0,0,value,true);
  auto& event=composeEvents.back();event.fetchValid=true;event.fetchPhysical=physical;event.fetchCached=cached;
  if(!begin) composeFetchContext=composeFetchPc=0;
}
static void compose_ram_scalar(bool write,u32 address,u32 bytes,u32 device,u64 value) {
  if(address<0x6000 || address>=0x6030) return; // Explicit declared RAM snapshot.
  if(write) {
    if(composeCpuContext || composeRspContext || composeFetchContext || bytes!=4) std::abort();
    u32 source=0;
    bool dma=device==(u32)RBusDevice::SP_DMA;
    if(dma) {
      if(rsp.dma.current.pbusRegion || !rsp.dma.busy.write) std::abort();
      source=(rsp.dma.current.pbusAddress+(address-(u32)rsp.dma.current.dramAddress))&4095;
    }
    #if PLAID_RSP_DEFINITIONS_FIXTURE >= 5
    if(dma && !composeDmaContext) std::abort();
    #endif
    compose_push("ram_write",dma?composeDmaContext:0,cpu.ipu.pc,0,address,0,source,bytes,value);
    if(dma) {
      auto& event=composeEvents.back();auto& current=rsp.dma.current;
      event.dmaValid=true;event.dmaPbus=current.pbusAddress;event.dmaDram=current.dramAddress;
      event.dmaLength=current.length;event.dmaCount=current.count;event.dmaSkip=current.skip;
    }
  } else if(composeFetchContext) {
    if(device!=(u32)RBusDevice::VR4300_UNCACHED || bytes!=4) std::abort();
    compose_push("ram_read",composeFetchContext,composeFetchPc,0,address,0,0,bytes,value,true);
  }
}
#endif
#endif

static void compose_print() {
  std::printf("[");
  for(size_t n=0;n<composeEvents.size();n++) {
    const auto& e=composeEvents[n];
    std::printf("%s{\"kind\":\"%s\",\"ordinal\":%llu,\"context\":%llu,\"pc\":%llu,\"phase\":%u,\"word\":%u,\"address\":%u,\"bank\":%u,\"offset\":%u,\"bytes\":%u,\"value\":%llu,\"cpu\":%s,\"next\":%u,\"halted\":%s,\"vector_byte\":%u,\"gpr\":[",
      n?",":"",e.kind,(unsigned long long)e.ordinal,(unsigned long long)e.context,
      (unsigned long long)e.pc,e.phase,e.word,e.address,e.bank,e.offset,e.bytes,
      (unsigned long long)e.value,e.cpu?"true":"false",e.next,e.halted?"true":"false",e.vectorByte);
    for(size_t i=0;i<e.gpr.size();i++) std::printf("%s%llu",i?",":"",(unsigned long long)e.gpr[i]);
    std::printf("],\"rgpr\":[");
    for(size_t i=0;i<e.rgpr.size();i++) std::printf("%s%u",i?",":"",e.rgpr[i]);
    std::printf("]");
    if(e.dmaValid) std::printf(",\"dma\":{\"pbus\":%u,\"dram\":%u,\"length\":%u,\"count\":%u,\"skip\":%u}",e.dmaPbus,e.dmaDram,e.dmaLength,e.dmaCount,e.dmaSkip);
    if(e.fetchValid) std::printf(",\"fetch\":{\"physical\":%u,\"cached\":%s}",e.fetchPhysical,e.fetchCached?"true":"false");
    std::printf("}");
  }
  std::printf("]");
}
