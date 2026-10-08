/* SPDX-License-Identifier: ISC
 * Plaid research observer for ordinary RDRAM reads and CPU fetch boundaries.
 */
struct PlaidRdramFetchScalarEvent {
  u64 ordinal, pc;
  u32 phase, address, bytes, device;
  bool write;
  u64 value;
};

struct PlaidRdramFetchBoundaryEvent {
  u64 ordinal, pc, vaddr;
  u32 phase, translatedPaddr, busPaddr, value;
  bool begin, cache;
};

static u64 plaidRdramFetchOrdinal = 0;
static u32 plaidRdramFetchPhase = 0;
static std::vector<PlaidRdramFetchScalarEvent> plaidRdramFetchScalarEvents;
static std::vector<PlaidRdramFetchBoundaryEvent> plaidRdramFetchBoundaryEvents;

static void plaid_rdram_fetch_scalar_observer(bool write, u32 address, u32 bytes, u32 device, u64 value) {
  if(bytes != Byte && bytes != Half && bytes != Word && bytes != Dual) std::abort();
  plaidRdramFetchScalarEvents.push_back({++plaidRdramFetchOrdinal, cpu.ipu.pc, plaidRdramFetchPhase,
    address, bytes, device, write, value});
}

static void plaid_cpu_fetch_boundary_observer(bool begin, u64 vaddr, u32 translatedPaddr,
                                               u32 busPaddr, bool cache, u32 value) {
  plaidRdramFetchBoundaryEvents.push_back({++plaidRdramFetchOrdinal, cpu.ipu.pc, vaddr,
    plaidRdramFetchPhase, translatedPaddr, busPaddr, value, begin, cache});
}

static void plaid_print_rdram_fetch_events() {
  std::printf("\"scalar_events\":[");
  for(size_t i = 0; i < plaidRdramFetchScalarEvents.size(); i++) {
    const auto& e = plaidRdramFetchScalarEvents[i];
    std::printf("%s{\"ordinal\":%llu,\"phase\":%u,\"pc\":%llu,\"write\":%s,\"address\":%u,\"bytes\":%u,\"device\":%u,\"uncached_cpu\":%s,\"value\":%llu}",
      i ? "," : "", (unsigned long long)e.ordinal, e.phase, (unsigned long long)e.pc,
      e.write ? "true" : "false", e.address, e.bytes, e.device,
      e.device == (u32)RBusDevice::VR4300_UNCACHED ? "true" : "false",
      (unsigned long long)e.value);
  }
  std::printf("],\"fetch_events\":[");
  for(size_t i = 0; i < plaidRdramFetchBoundaryEvents.size(); i++) {
    const auto& e = plaidRdramFetchBoundaryEvents[i];
    std::printf("%s{\"ordinal\":%llu,\"phase\":%u,\"pc\":%llu,\"begin\":%s,\"cache\":%s,\"vaddr\":%llu,\"translated_paddr\":%u,\"bus_paddr\":%u,\"value\":%u}",
      i ? "," : "", (unsigned long long)e.ordinal, e.phase, (unsigned long long)e.pc,
      e.begin ? "true" : "false", e.cache ? "true" : "false",
      (unsigned long long)e.vaddr, e.translatedPaddr, e.busPaddr, e.value);
  }
  std::printf("]");
}
