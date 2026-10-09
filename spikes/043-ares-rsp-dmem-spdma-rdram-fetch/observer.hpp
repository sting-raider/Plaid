/* SPDX-License-Identifier: ISC
 * Project-owned observation callbacks. They record already-computed values only.
 */
struct PlaidRspInstructionEvent {
  u64 ordinal;
  u32 phase, context, pc, word, next;
  bool begin, halted;
};
struct PlaidRspSinkEvent {
  u64 ordinal;
  u32 phase, context, pc, word, offset, bytes;
  u64 value;
};
struct PlaidRdramEvent {
  u64 ordinal;
  u32 phase, address, bytes, device;
  bool write, spDma, uncachedCpu;
  u64 value;
};
struct PlaidFetchEvent {
  u64 ordinal, vaddr;
  u32 phase, translatedPaddr, busPaddr, value;
  bool begin, cache;
};

static u64 plaidOrdinal = 0;
static u32 plaidPhase = 0;
static u32 plaidRspContext = 0, plaidRspPc = 0, plaidRspWord = 0;
static std::vector<PlaidRspInstructionEvent> plaidRspInstructions;
static std::vector<PlaidRspSinkEvent> plaidRspSinks;
static std::vector<PlaidRdramEvent> plaidRdramEvents;
static std::vector<PlaidFetchEvent> plaidFetchEvents;

static void plaid_rsp_instruction(bool begin, u32 pc, u32 word, u32 next, bool halted) {
  u64 ordinal = ++plaidOrdinal;
  if(begin) {
    if(plaidRspContext) std::abort();
    plaidRspContext = (u32)ordinal;
    plaidRspPc = pc;
    plaidRspWord = word;
  } else if(!plaidRspContext || pc != plaidRspPc || word != plaidRspWord) {
    std::abort();
  }
  plaidRspInstructions.push_back({ordinal, plaidPhase, plaidRspContext, pc, word, next, begin, halted});
  if(!begin) plaidRspContext = 0;
}

static void plaid_rsp_sink(u32 offset, u32 bytes, u64 value) {
  if(!plaidRspContext) std::abort();
  plaidRspSinks.push_back({++plaidOrdinal, plaidPhase, plaidRspContext, plaidRspPc, plaidRspWord,
                           offset, bytes, value});
}

static void plaid_rdram(bool write, u32 address, u32 bytes, u32 device, u64 value) {
  plaidRdramEvents.push_back({++plaidOrdinal, plaidPhase, address, bytes, device, write,
    device == (u32)RBusDevice::SP_DMA,
    device == (u32)RBusDevice::VR4300_UNCACHED,
    value});
}

static void plaid_fetch(bool begin, u64 vaddr, u32 translatedPaddr, u32 busPaddr,
                        bool cache, u32 value) {
  plaidFetchEvents.push_back({++plaidOrdinal, vaddr, plaidPhase, translatedPaddr, busPaddr,
                              value, begin, cache});
}

static void plaid_print_history() {
  std::printf("{\"format\":\"plaid-rsp-dmem-spdma-rdram-fetch-v0\",\"rsp_instructions\":[");
  for(size_t i=0;i<plaidRspInstructions.size();i++) {
    auto& e=plaidRspInstructions[i];
    std::printf("%s{\"ordinal\":%llu,\"phase\":%u,\"context\":%u,\"pc\":%u,\"word\":%u,\"next\":%u,\"begin\":%s,\"halted\":%s}",
      i?",":"",(unsigned long long)e.ordinal,e.phase,e.context,e.pc,e.word,e.next,
      e.begin?"true":"false",e.halted?"true":"false");
  }
  std::printf("],\"rsp_sinks\":[");
  for(size_t i=0;i<plaidRspSinks.size();i++) {
    auto& e=plaidRspSinks[i];
    std::printf("%s{\"ordinal\":%llu,\"phase\":%u,\"context\":%u,\"pc\":%u,\"word\":%u,\"offset\":%u,\"bytes\":%u,\"value\":%llu}",
      i?",":"",(unsigned long long)e.ordinal,e.phase,e.context,e.pc,e.word,e.offset,e.bytes,
      (unsigned long long)e.value);
  }
  std::printf("],\"rdram\":[");
  for(size_t i=0;i<plaidRdramEvents.size();i++) {
    auto& e=plaidRdramEvents[i];
    std::printf("%s{\"ordinal\":%llu,\"phase\":%u,\"write\":%s,\"address\":%u,\"bytes\":%u,\"device\":%u,\"sp_dma\":%s,\"uncached_cpu\":%s,\"value\":%llu}",
      i?",":"",(unsigned long long)e.ordinal,e.phase,e.write?"true":"false",e.address,e.bytes,e.device,
      e.spDma?"true":"false",e.uncachedCpu?"true":"false",(unsigned long long)e.value);
  }
  std::printf("],\"fetch\":[");
  for(size_t i=0;i<plaidFetchEvents.size();i++) {
    auto& e=plaidFetchEvents[i];
    std::printf("%s{\"ordinal\":%llu,\"phase\":%u,\"begin\":%s,\"cache\":%s,\"vaddr\":%llu,\"translated_paddr\":%u,\"bus_paddr\":%u,\"value\":%u}",
      i?",":"",(unsigned long long)e.ordinal,e.phase,e.begin?"true":"false",e.cache?"true":"false",
      (unsigned long long)e.vaddr,e.translatedPaddr,e.busPaddr,e.value);
  }
  std::printf("]}\n");
}
