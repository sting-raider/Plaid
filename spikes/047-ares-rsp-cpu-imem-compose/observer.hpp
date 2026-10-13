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
  const char* dmaDirection=nullptr;
  bool pendingValid=false,pendingFull=false;
  bool cacheValid=false;
  u32 cacheSlot=0,cacheTag=0,cacheIndex=0;
  std::vector<u32> cacheWords;
  bool operationValid=false;
  u64 operationAddress=0;
  u32 operation=0,tagBefore=0,tagAfter=0;
  std::vector<u32> wordsBefore,wordsAfter;
};
static std::vector<ComposeEvent> composeEvents;
static u32 composePhase=0,composeRspContext=0,composeRspPc=0,composeRspWord=0;
static u32 composeCpuContext=0,composeCpuWord=0;
static u64 composeCpuPc=0;
static bool composeEnabled=false;
static u64 composeFetchContext=0,composeFetchPc=0;
static u64 composeDmaContext=0;
static u32 composeDmaBank=0;
static bool composeDmaWrite=false;

static void compose_push(const char* kind,u64 context,u64 pc,u32 word,
    u32 address=0,u32 bank=0,u32 offset=0,u32 bytes=0,u64 value=0,bool cpuOrigin=false,
    u32 next=0,bool halted=false) {
  if(!composeEnabled) return;
  ComposeEvent e{kind,composeEvents.size()+1,context,pc,value,composePhase,word,
    address,bank,offset,bytes,next,0,cpuOrigin,halted,{},{}};
  if(!strcmp(kind,"cpu_begin") || !strcmp(kind,"cpu_end") || !strcmp(kind,"cpu_reentry"))
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
  #if PLAID_RSP_DEFINITIONS_FIXTURE >= 7
  else if(composeDmaContext && composeDmaBank==0 && !composeDmaWrite) {
    if(bytes!=4 || composeCpuContext || composeFetchContext) std::abort();
    auto& current=rsp.dma.current;
    u32 lane=(offset-(u32)current.pbusAddress)&4095;
    if(lane!=0 && lane!=4) std::abort();
    compose_push("dmem_dma_write",composeDmaContext,cpu.ipu.pc,0,(u32)current.dramAddress+lane,0,offset,bytes,value);
    auto& event=composeEvents.back();event.dmaValid=true;
    event.dmaPbus=current.pbusAddress;event.dmaDram=current.dramAddress;
    event.dmaLength=current.length;event.dmaCount=current.count;event.dmaSkip=current.skip;
  }
  #endif
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
#if PLAID_RSP_DEFINITIONS_FIXTURE >= 10
static void compose_cache_snapshot(ComposeEvent& event,u32 slot,u32 tag,u32 index,const u32* words) {
  event.cacheValid=true;event.cacheSlot=slot;event.cacheTag=tag;event.cacheIndex=index;
  for(u32 n=0;n<8;n++) event.cacheWords.push_back(words[n]);
}
static void compose_cache_burst(bool write,u32 address,u32 bytes,u32 device,const u32* words) {
  if(!composeEnabled) return;
  if(write || bytes!=32 || device!=(u32)RBusDevice::VR4300_ICACHE || !composeFetchContext
      || composeCpuContext || composeRspContext) std::abort();
  compose_push("cache_burst_read",composeFetchContext,composeFetchPc,0,address,0,0,32,0,true);
  compose_cache_snapshot(composeEvents.back(),(composeFetchPc>>5)&511,(address&~4095)|1,address&0xfe0,words);
}
static void compose_cache_fill(u32 slot,u32 physical,u32 index,const u32* words) {
  if(!composeEnabled) return;
  if(!composeFetchContext || composeCpuContext || composeRspContext) std::abort();
  compose_push("cache_fill",composeFetchContext,composeFetchPc,0,(physical&~4095)|index,0,0,32,0,true);
  compose_cache_snapshot(composeEvents.back(),slot,(physical&~4095)|1,index,words);
}
#if PLAID_RSP_DEFINITIONS_FIXTURE >= 11
static void compose_cache_operation(u64 pc,u32 op,u64 virtualAddress,u32 physical,
    u32 before,u32 after,const u32* wordsBefore,const u32* wordsAfter) {
  if(!composeEnabled) return;
  if(!composeCpuContext || composeRspContext || composeFetchContext || pc!=composeCpuPc || op!=16) std::abort();
  compose_push("cache_operation",composeCpuContext,pc,composeCpuWord,physical,0,0,0,0,true);
  auto& e=composeEvents.back();e.operationValid=true;e.operationAddress=virtualAddress;e.operation=op;
  e.cacheSlot=(virtualAddress>>5)&511;e.cacheIndex=virtualAddress&0xfe0;e.tagBefore=before;e.tagAfter=after;
  for(u32 n=0;n<8;n++){e.wordsBefore.push_back(wordsBefore[n]);e.wordsAfter.push_back(wordsAfter[n]);}
}
#endif
#endif
#if PLAID_RSP_DEFINITIONS_FIXTURE >= 8
static void compose_dma_pending(u32 address,u32 value,bool originCpu) {
  if(!composeEnabled) return;
  if(composeRspContext || composeFetchContext || !originCpu) std::abort();
  #if PLAID_RSP_DEFINITIONS_FIXTURE < 9
  if(composeCpuContext) std::abort();
  #endif
  auto& pending=rsp.dma.pending;
  compose_push("dma_pending_write",composeCpuContext?composeCpuContext:composeEvents.size()+1,
    composeCpuContext?composeCpuPc:cpu.ipu.pc,composeCpuContext?composeCpuWord:0,
    address,pending.pbusRegion,pending.pbusAddress,4,value,originCpu);
  auto& event=composeEvents.back();event.dmaValid=true;event.pendingValid=true;event.pendingFull=rsp.dma.full.any();
  event.dmaPbus=pending.pbusAddress;event.dmaDram=pending.dramAddress;
  event.dmaLength=pending.length;event.dmaCount=pending.count;event.dmaSkip=pending.skip;
  if(event.pendingFull) event.dmaDirection=rsp.dma.full.write?"dmem_egress":pending.pbusRegion?"imem_ingress":"dmem_ingress";
}
#endif
#if PLAID_RSP_DEFINITIONS_FIXTURE >= 5
static void compose_dma_lifecycle(bool begin,u32 bank,bool write,u32 pbus,u32 dram,u32 length,u32 count,u32 skip) {
  #if PLAID_RSP_DEFINITIONS_FIXTURE >= 7
  if(bank>1 || (bank==1 && write) || (bool)rsp.dma.busy.read==write) std::abort();
  #elif PLAID_RSP_DEFINITIONS_FIXTURE >= 6
  if(!((bank==0 && write)||(bank==1 && !write))) std::abort();
  #else
  if(bank || !write) std::abort();
  #endif
  if(composeRspContext || composeFetchContext) std::abort();
  #if PLAID_RSP_DEFINITIONS_FIXTURE >= 9
  if(composeCpuContext && (!begin || composeCpuWord>>26!=0x2b)) std::abort();
  #else
  if(composeCpuContext) std::abort();
  #endif
  if(begin) {
    if(composeDmaContext) std::abort();
    composeDmaContext=composeEvents.size()+1;composeDmaBank=bank;composeDmaWrite=write;
  } else if(!composeDmaContext || bank!=composeDmaBank || write!=composeDmaWrite) std::abort();
  compose_push(begin?"dma_promote":"dma_complete",composeDmaContext,cpu.ipu.pc,0,dram,bank,pbus);
  #if PLAID_RSP_DEFINITIONS_FIXTURE >= 7
  composeEvents.back().dmaDirection=write?"dmem_egress":bank?"imem_ingress":"dmem_ingress";
  #endif
  if(begin) {
    auto& event=composeEvents.back();event.dmaValid=true;
    event.dmaPbus=pbus;event.dmaDram=dram;event.dmaLength=length;event.dmaCount=count;event.dmaSkip=skip;
  } else composeDmaContext=0;
}
#endif
#if PLAID_RSP_DEFINITIONS_FIXTURE >= 6
static void compose_imem_dma_store(u32 address,u32 bank,u32 offset,u32 bytes,u64 value) {
  #if PLAID_RSP_DEFINITIONS_FIXTURE >= 7
  if(bank==0 && composeDmaContext && composeDmaBank==0 && !composeDmaWrite) return; // Lower primitive DMEM sink is already captured.
  #endif
  if(!composeDmaContext || composeDmaBank!=1 || composeDmaWrite || bank!=1 || bytes!=8) std::abort();
  compose_push("imem_dma_write",composeDmaContext,cpu.ipu.pc,0,address,bank,offset,bytes,value);
  auto& event=composeEvents.back();auto& current=rsp.dma.current;
  event.dmaValid=true;event.dmaPbus=current.pbusAddress;event.dmaDram=current.dramAddress;
  event.dmaLength=current.length;event.dmaCount=current.count;event.dmaSkip=current.skip;
}
#endif
static void compose_ram_fetch(bool begin,u64 pc,u32 physical,u32 busAddress,bool cached,u32 value) {
  if(composeCpuContext || composeRspContext || physical!=busAddress) std::abort();
  #if PLAID_RSP_DEFINITIONS_FIXTURE < 10
  if(cached) std::abort();
  #endif
  if(begin) {
    if(composeFetchContext) std::abort();
    composeFetchContext=composeEvents.size()+1;composeFetchPc=pc;
  } else if(!composeFetchContext || composeFetchPc!=pc) std::abort();
  compose_push(begin?"ram_fetch_begin":"ram_fetch_end",composeFetchContext,pc,0,busAddress,0,0,0,value,true);
  auto& event=composeEvents.back();event.fetchValid=true;event.fetchPhysical=physical;event.fetchCached=cached;
  #if PLAID_RSP_DEFINITIONS_FIXTURE >= 10
  if(!begin && cached) { auto& line=cpu.icache.line(pc);
    compose_cache_snapshot(event,(pc>>5)&511,line.tagKey,line.index,line.words); }
  #endif
  if(!begin) composeFetchContext=composeFetchPc=0;
}
static void compose_ram_scalar(bool write,u32 address,u32 bytes,u32 device,u64 value) {
  if(address<0x6000 || address>=(PLAID_RSP_DEFINITIONS_FIXTURE>=10?0x6040:0x6030)) return; // Explicit declared RAM snapshot.
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
  }
  #if PLAID_RSP_DEFINITIONS_FIXTURE >= 6
  else if(composeDmaContext && composeDmaBank==1 && !composeDmaWrite && device==(u32)RBusDevice::SP_DMA) {
    if(bytes!=8 || composeCpuContext || composeRspContext || composeFetchContext) std::abort();
    auto& current=rsp.dma.current;
    compose_push("imem_dma_read",composeDmaContext,cpu.ipu.pc,0,address,1,current.pbusAddress,bytes,value);
    auto& event=composeEvents.back();event.dmaValid=true;
    event.dmaPbus=current.pbusAddress;event.dmaDram=current.dramAddress;
    event.dmaLength=current.length;event.dmaCount=current.count;event.dmaSkip=current.skip;
  }
  #endif
  #if PLAID_RSP_DEFINITIONS_FIXTURE >= 7
  else if(composeDmaContext && composeDmaBank==0 && !composeDmaWrite && device==(u32)RBusDevice::SP_DMA) {
    if(bytes!=4 || composeCpuContext || composeRspContext || composeFetchContext) std::abort();
    auto& current=rsp.dma.current;
    compose_push("dmem_dma_read",composeDmaContext,cpu.ipu.pc,0,address,0,((u32)current.pbusAddress+(address-(u32)current.dramAddress))&4095,bytes,value);
    auto& event=composeEvents.back();event.dmaValid=true;
    event.dmaPbus=current.pbusAddress;event.dmaDram=current.dramAddress;
    event.dmaLength=current.length;event.dmaCount=current.count;event.dmaSkip=current.skip;
  }
  #endif
  else if(composeFetchContext) {
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
    if(e.dmaDirection) std::printf(",\"dma_direction\":\"%s\"",e.dmaDirection);
    if(e.pendingValid) std::printf(",\"pending_full\":%s",e.pendingFull?"true":"false");
    if(e.cacheValid) {
      std::printf(",\"cache_line\":{\"slot\":%u,\"tag_key\":%u,\"index\":%u,\"words\":[",e.cacheSlot,e.cacheTag,e.cacheIndex);
      for(size_t i=0;i<e.cacheWords.size();i++) std::printf("%s%u",i?",":"",e.cacheWords[i]);
      std::printf("]}");
    }
    if(e.operationValid) {
      std::printf(",\"cache_operation\":{\"virtual_address\":%llu,\"operation\":%u",(unsigned long long)e.operationAddress,e.operation);
      for(u32 n=0;n<2;n++) {
        std::printf(",\"%s\":{\"slot\":%u,\"tag_key\":%u,\"index\":%u,\"words\":[",n?"after":"before",e.cacheSlot,n?e.tagAfter:e.tagBefore,e.cacheIndex);
        auto& words=n?e.wordsAfter:e.wordsBefore;
        for(size_t i=0;i<words.size();i++) std::printf("%s%u",i?",":"",words[i]);
        std::printf("]}");
      }
      std::printf("}");
    }
    std::printf("}");
  }
  std::printf("]");
}
