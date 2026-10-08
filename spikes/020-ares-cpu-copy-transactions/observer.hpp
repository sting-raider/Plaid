/* SPDX-License-Identifier: ISC
 * Original Plaid research sensor for completed identity-mapped RDRAM accesses.
 */
struct PlaidCopyScalarEvent {
  u64 ordinal, pc;
  u32 phase, address, bytes, device;
  bool write;
  u64 value;
};

struct PlaidCopyBurstEvent {
  u64 ordinal, pc;
  u32 phase, address, bytes, device, words[8];
  bool write;
};

static u64 plaidCopyOrdinal = 0;
static u32 plaidCopyPhase = 0;
static std::vector<PlaidCopyScalarEvent> plaidCopyScalarEvents;
static std::vector<PlaidCopyBurstEvent> plaidCopyBurstEvents;

static void plaid_copy_scalar_observer(bool write, u32 address, u32 bytes, u32 device, u64 value) {
  if(bytes != Byte && bytes != Half && bytes != Word && bytes != Dual) std::abort();
  plaidCopyScalarEvents.push_back({++plaidCopyOrdinal, cpu.ipu.pc, plaidCopyPhase,
    address, bytes, device, write, value});
}

static void plaid_copy_burst_observer(bool write, u32 address, u32 bytes, u32 device, const u32* words) {
  if((bytes != ICache && bytes != DCache) || (address & (bytes - 1))) std::abort();
  PlaidCopyBurstEvent event{++plaidCopyOrdinal, cpu.ipu.pc, plaidCopyPhase,
    address, bytes, device, {}, write};
  for(u32 lane = 0; lane < bytes / 4; lane++) event.words[lane] = words[lane];
  plaidCopyBurstEvents.push_back(event);
}

static void plaid_print_copy_events() {
  std::printf("\"scalar_events\":[");
  for(size_t i = 0; i < plaidCopyScalarEvents.size(); i++) {
    const auto& e = plaidCopyScalarEvents[i];
    std::printf("%s{\"ordinal\":%llu,\"phase\":%u,\"pc\":%llu,\"write\":%s,\"address\":%u,\"bytes\":%u,\"uncached_cpu\":%s,\"value\":%llu}",
      i ? "," : "", (unsigned long long)e.ordinal, e.phase, (unsigned long long)e.pc,
      e.write ? "true" : "false", e.address, e.bytes,
      e.device == (u32)RBusDevice::VR4300_UNCACHED ? "true" : "false",
      (unsigned long long)e.value);
  }
  std::printf("],\"burst_events\":[");
  for(size_t i = 0; i < plaidCopyBurstEvents.size(); i++) {
    const auto& e = plaidCopyBurstEvents[i];
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