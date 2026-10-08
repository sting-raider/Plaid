/* SPDX-License-Identifier: ISC
 * Project-owned D-cache/RDRAM chronology sensor for pinned ares research only.
 */
struct PlaidDcacheEvent {
  u64 ordinal, pc;
  u32 phase, kind, slot, tag, paddr, bytes;
  u16 dirtyBefore, dirtyAfter;
  u32 words[4];
};

struct PlaidDcacheBurstEvent {
  u64 ordinal, pc;
  u32 phase, address, bytes, device, words[8];
  bool write;
};

static u64 plaidLineageOrdinal = 0;
static u32 plaidLineagePhase = 0;
static std::vector<PlaidDcacheEvent> plaidDcacheEvents;
static std::vector<PlaidDcacheBurstEvent> plaidDcacheBurstEvents;

static void plaid_dcache_observer(u32 kind, const void* opaqueLine, u32 paddr, u32 bytes,
                                  u16 dirtyBefore, u16 dirtyAfter, const u32* words) {
  auto* line = static_cast<const CPU::DataCache::Line*>(opaqueLine);
  auto slot = (u32)(line - &cpu.dcache.lines[0]);
  if(slot >= 512) std::abort();
  PlaidDcacheEvent event{++plaidLineageOrdinal, cpu.ipu.pc, plaidLineagePhase, kind, slot,
    line->tagKey & ~1u, paddr, bytes, dirtyBefore, dirtyAfter, {}};
  for(u32 lane = 0; lane < 4; lane++) event.words[lane] = words[lane];
  plaidDcacheEvents.push_back(event);
}

static void plaid_lineage_burst_observer(bool write, u32 address, u32 bytes, u32 device, const u32* words) {
  if((bytes != ICache && bytes != DCache) || (address & (bytes - 1))) std::abort();
  PlaidDcacheBurstEvent event{++plaidLineageOrdinal, cpu.ipu.pc, plaidLineagePhase,
    address, bytes, device, {}, write};
  for(u32 lane = 0; lane < bytes / 4; lane++) event.words[lane] = words[lane];
  plaidDcacheBurstEvents.push_back(event);
}

static const char* plaid_dcache_kind(u32 kind) {
  switch(kind) {
  case 1: return "fill";
  case 2: return "store";
  case 3: return "writeback_begin";
  case 4: return "writeback_end";
  case 5: return "invalidate";
  default: return "unknown";
  }
}

static void plaid_print_lineage_events() {
  std::printf("\"dcache_events\":[");
  for(size_t i = 0; i < plaidDcacheEvents.size(); i++) {
    const auto& e = plaidDcacheEvents[i];
    std::printf("%s{\"ordinal\":%llu,\"phase\":%u,\"pc\":%llu,\"kind\":\"%s\",\"slot\":%u,\"tag\":%u,\"paddr\":%u,\"bytes\":%u,\"dirty_before\":%u,\"dirty_after\":%u,\"words\":[",
      i ? "," : "", (unsigned long long)e.ordinal, e.phase, (unsigned long long)e.pc,
      plaid_dcache_kind(e.kind), e.slot, e.tag, e.paddr, e.bytes,
      (u32)e.dirtyBefore, (u32)e.dirtyAfter);
    for(u32 lane = 0; lane < 4; lane++) std::printf("%s%u", lane ? "," : "", e.words[lane]);
    std::printf("]}");
  }
  std::printf("],\"burst_events\":[");
  for(size_t i = 0; i < plaidDcacheBurstEvents.size(); i++) {
    const auto& e = plaidDcacheBurstEvents[i];
    std::printf("%s{\"ordinal\":%llu,\"phase\":%u,\"pc\":%llu,\"write\":%s,\"address\":%u,\"bytes\":%u,\"icache\":%s,\"dcache\":%s,\"words\":[",
      i ? "," : "", (unsigned long long)e.ordinal, e.phase, (unsigned long long)e.pc,
      e.write ? "true" : "false", e.address, e.bytes,
      e.device == (u32)RBusDevice::VR4300_ICACHE ? "true" : "false",
      e.device == (u32)RBusDevice::VR4300_DCACHE ? "true" : "false");
    for(u32 lane = 0; lane < e.bytes / 4; lane++) std::printf("%s%u", lane ? "," : "", e.words[lane]);
    std::printf("]}");
  }
  std::printf("]");
}
