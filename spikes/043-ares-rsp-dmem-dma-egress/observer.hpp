/* SPDX-License-Identifier: ISC
 * Plaid research-only composed chronology observer.
 * Records existing completed sink callbacks and current SP-DMA descriptor state.
 * It performs no guest memory reads, clock steps, serialization, reset, or
 * reference object-layout changes.
 */
#include <vector>

struct EgressEvent {
  u32 kind = 0;
  u32 seq = 0;
  u32 context = 0;
  u32 phase = 0;
  u32 pc = 0;
  u32 word = 0;
  u32 offset = 0;
  u32 bytes = 0;
  u32 dram = 0;
  u32 source = 0xffff'ffff;
  u32 dmaPbus = 0;
  u32 dmaDram = 0;
  u32 dmaLength = 0;
  u32 dmaCount = 0;
  u32 dmaSkip = 0;
  u64 value = 0;
  bool halted = false;
};

static std::vector<EgressEvent> egressEvents;
static u32 egressSeq = 0;
static u32 egressContext = 0;
static u32 egressPhase = 0;
static u32 egressPc = 0;
static u32 egressWord = 0;
static bool egressCpuScope = false;

static auto egress_push(EgressEvent event) -> void {
  event.seq = ++egressSeq;
  event.phase = egressPhase;
  egressEvents.push_back(event);
}

static auto egress_instruction(bool begin, u32 pc, u32 word, u32 next, bool halted) -> void {
  (void)next;
  if(begin) {
    if(egressContext) std::abort();
    EgressEvent event{};
    event.kind = 0;
    event.pc = pc;
    event.word = word;
    event.halted = halted;
    event.seq = ++egressSeq;
    event.phase = egressPhase;
    event.context = event.seq;
    egressContext = event.context;
    egressPc = pc;
    egressWord = word;
    egressEvents.push_back(event);
    return;
  }
  if(!egressContext || pc != egressPc || word != egressWord) std::abort();
  EgressEvent event{};
  event.kind = 2;
  event.context = egressContext;
  event.pc = pc;
  event.word = word;
  event.halted = halted;
  egress_push(event);
  egressContext = 0;
}

static auto egress_dmem(u32 offset, u32 bytes, u64 value) -> void {
  EgressEvent event{};
  event.kind = egressContext ? 1u : egressCpuScope ? 3u : 4u;
  event.context = egressContext;
  event.pc = egressContext ? egressPc : 0;
  event.word = egressContext ? egressWord : 0;
  event.offset = offset & 0xfff;
  event.bytes = bytes;
  event.value = value;
  egress_push(event);
}

static auto egress_rdram(bool write, u32 address, u32 bytes, u32 device, u64 value) -> void {
  using namespace ares::Nintendo64;
  if(!write || device != (u32)RBusDevice::SP_DMA) return;

  EgressEvent event{};
  event.kind = 5;
  event.dram = address;
  event.bytes = bytes;
  event.value = value;
  event.dmaPbus = (u32)rsp.dma.current.pbusAddress;
  event.dmaDram = (u32)rsp.dma.current.dramAddress;
  event.dmaLength = (u32)rsp.dma.current.length;
  event.dmaCount = (u32)rsp.dma.current.count;
  event.dmaSkip = (u32)rsp.dma.current.skip;

  // Pinned ares write-DMA reads DMEM then performs two Word RDRAM writes while
  // current addresses are still unchanged. Derive source identity from that
  // nested descriptor state, never from matching payload bytes.
  if(rsp.dma.busy.write && !rsp.dma.current.pbusRegion && bytes == 4 &&
      (address == event.dmaDram || address == event.dmaDram + 4)) {
    event.source = (event.dmaPbus + (address - event.dmaDram)) & 0xfff;
  }
  egress_push(event);
}

static auto egress_print_events() -> void {
  std::printf("["");
  for(size_t index = 0; index < egressEvents.size(); index++) {
    const auto& e = egressEvents[index];
    std::printf(
      "%s{\"kind\":%u,\"seq\":%u,\"context\":%u,\"phase\":%u,\"pc\":%u,\"word\":%u,\"offset\":%u,\"bytes\":%u,\"dram\":%u,\"source\":%u,\"dma_pbus\":%u,\"dma_dram\":%u,\"dma_length\":%u,\"dma_count\":%u,\"dma_skip\":%u,\"value\":%llu,\"halted\":%s}",
      index ? "," : "", e.kind, e.seq, e.context, e.phase, e.pc, e.word,
      e.offset, e.bytes, e.dram, e.source, e.dmaPbus, e.dmaDram,
      e.dmaLength, e.dmaCount, e.dmaSkip, (unsigned long long)e.value,
      e.halted ? "true" : "false");
  }
  std::printf("]");
}
