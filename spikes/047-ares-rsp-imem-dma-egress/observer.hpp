/* SPDX-License-Identifier: ISC
 * Plaid research-only IMEM reverse-DMA chronology observer.
 * Uses existing generated completed SP-word and identity-RDRAM callbacks only.
 */
#include <vector>

struct ImemEgressEvent {
  u32 kind = 0;
  u32 seq = 0;
  u32 phase = 0;
  u32 offset = 0;
  u32 bytes = 0;
  u32 dram = 0;
  u32 source = 0xffff'ffff;
  u32 region = 0xffff'ffff;
  u32 device = 0xffff'ffff;
  u32 dmaPbus = 0;
  u32 dmaRegion = 0;
  u32 dmaDram = 0;
  u32 dmaLength = 0;
  u32 dmaCount = 0;
  u32 dmaSkip = 0;
  u64 value = 0;
  bool cpu = false;
};

static std::vector<ImemEgressEvent> imemEgressEvents;
static u32 imemEgressSeq = 0;
static u32 imemEgressPhase = 0;

static auto imem_egress_push(ImemEgressEvent event) -> void {
  event.seq = ++imemEgressSeq;
  event.phase = imemEgressPhase;
  imemEgressEvents.push_back(event);
}

static auto imem_egress_spword(bool write, u32 address, u32 region, u32 offset, u32 value, bool cpu) -> void {
  if(!write || region != 1) return;
  ImemEgressEvent event{};
  event.kind = 1;
  event.offset = offset & 0xffc;
  event.region = region;
  event.bytes = 4;
  event.value = value;
  event.cpu = cpu;
  imem_egress_push(event);
}

static auto imem_egress_target_window(u32 address, u32 bytes) -> bool {
  u64 end = u64(address) + bytes;
  return (address >= 0x1000 && end <= 0x1018) || (address >= 0x2000 && end <= 0x2010);
}

static auto imem_egress_rdram(bool write, u32 address, u32 bytes, u32 device, u64 value) -> void {
  using namespace ares::Nintendo64;
  if(!write) return;
  if(device != (u32)RBusDevice::SP_DMA) {
    if(!imem_egress_target_window(address, bytes)) return;
    ImemEgressEvent event{};
    event.kind = 3;
    event.dram = address;
    event.bytes = bytes;
    event.device = device;
    event.value = value;
    imem_egress_push(event);
    return;
  }

  ImemEgressEvent event{};
  event.kind = 2;
  event.dram = address;
  event.bytes = bytes;
  event.device = device;
  event.value = value;
  event.dmaPbus = (u32)rsp.dma.current.pbusAddress;
  event.dmaRegion = (u32)rsp.dma.current.pbusRegion;
  event.dmaDram = (u32)rsp.dma.current.dramAddress;
  event.dmaLength = (u32)rsp.dma.current.length;
  event.dmaCount = (u32)rsp.dma.current.count;
  event.dmaSkip = (u32)rsp.dma.current.skip;

  // The exact guarded ares path performs imem.read<Dual>(current.pbusAddress)
  // immediately before this completed Dual RDRAM write, without changing the
  // descriptor in between. Keep bank identity separate from the wrapped offset.
  if(rsp.dma.busy.write && event.dmaRegion == 1 && bytes == 8 && address == event.dmaDram) {
    event.source = event.dmaPbus & 0xff8;
    event.region = 1;
  }
  imem_egress_push(event);
}

static auto imem_egress_print_events() -> void {
  std::printf("[");
  for(size_t index = 0; index < imemEgressEvents.size(); index++) {
    const auto& e = imemEgressEvents[index];
    std::printf(
      "%s{\"kind\":%u,\"seq\":%u,\"phase\":%u,\"offset\":%u,\"bytes\":%u,\"dram\":%u,\"source\":%u,\"region\":%u,\"device\":%u,\"dma_pbus\":%u,\"dma_region\":%u,\"dma_dram\":%u,\"dma_length\":%u,\"dma_count\":%u,\"dma_skip\":%u,\"value\":%llu,\"cpu\":%s}",
      index ? "," : "", e.kind, e.seq, e.phase, e.offset, e.bytes, e.dram,
      e.source, e.region, e.device, e.dmaPbus, e.dmaRegion, e.dmaDram,
      e.dmaLength, e.dmaCount, e.dmaSkip, (unsigned long long)e.value,
      e.cpu ? "true" : "false");
  }
  std::printf("]");
}
