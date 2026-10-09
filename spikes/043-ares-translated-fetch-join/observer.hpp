/* SPDX-License-Identifier: ISC
 * Unified research observer for CPU fetch boundaries and translated RDRAM reads.
 */
#pragma once

struct PlaidTranslatedFetchEvent {
  u32 kind = 0; // 0 fetch boundary, 1 completed translated RDRAM scalar read
  u64 ordinal = 0;
  u32 phase = 0;
  u64 pc = 0;

  bool begin = false;
  u64 vaddr = 0;
  u32 translatedPaddr = 0;
  u32 busPaddr = 0;
  bool cache = false;
  u32 value = 0;

  u32 request = 0;
  u32 mapped = 0;
  u32 bytes = 0;
  u32 device = 0;
  u32 chip = 0;
  u64 raw = 0;
  u64 delivered = 0;
  u32 cci = 0;
  u32 ccLow = 0;
  u32 ccHigh = 0;
};

static u64 plaidTranslatedFetchOrdinal = 0;
static u32 plaidTranslatedFetchPhase = 0;
static std::vector<PlaidTranslatedFetchEvent> plaidTranslatedFetchEvents;

static void plaid_translated_fetch_boundary(
  bool begin, u64 vaddr, u32 translatedPaddr, u32 busPaddr, bool cache, u32 value
) {
  PlaidTranslatedFetchEvent e{};
  e.kind = 0;
  e.ordinal = ++plaidTranslatedFetchOrdinal;
  e.phase = plaidTranslatedFetchPhase;
  e.pc = cpu.ipu.pc;
  e.begin = begin;
  e.vaddr = vaddr;
  e.translatedPaddr = translatedPaddr;
  e.busPaddr = busPaddr;
  e.cache = cache;
  e.value = value;
  plaidTranslatedFetchEvents.push_back(e);
}

static void plaid_translated_rdram_read(
  u32 request, u32 mapped, u32 bytes, u32 device, u32 chip,
  u64 raw, u64 delivered, u32 cci, u32 ccLow, u32 ccHigh
) {
  PlaidTranslatedFetchEvent e{};
  e.kind = 1;
  e.ordinal = ++plaidTranslatedFetchOrdinal;
  e.phase = plaidTranslatedFetchPhase;
  e.pc = cpu.ipu.pc;
  e.request = request;
  e.mapped = mapped;
  e.bytes = bytes;
  e.device = device;
  e.chip = chip;
  e.raw = raw;
  e.delivered = delivered;
  e.cci = cci;
  e.ccLow = ccLow;
  e.ccHigh = ccHigh;
  plaidTranslatedFetchEvents.push_back(e);
}

static void plaid_print_translated_fetch_events() {
  std::printf("\"events\":[");
  for(size_t i = 0; i < plaidTranslatedFetchEvents.size(); i++) {
    const auto& e = plaidTranslatedFetchEvents[i];
    std::printf(
      "%s{\"kind\":%u,\"ordinal\":%llu,\"phase\":%u,\"pc\":%llu,"
      "\"begin\":%s,\"vaddr\":%llu,\"translated_paddr\":%u,\"bus_paddr\":%u,"
      "\"cache\":%s,\"value\":%u,\"request\":%u,\"mapped\":%u,\"bytes\":%u,"
      "\"device\":%u,\"uncached_cpu\":%s,\"chip\":%u,\"raw\":%llu,"
      "\"delivered\":%llu,\"cci\":%u,\"cc_low\":%u,\"cc_high\":%u}",
      i ? "," : "", e.kind, (unsigned long long)e.ordinal, e.phase,
      (unsigned long long)e.pc, e.begin ? "true" : "false",
      (unsigned long long)e.vaddr, e.translatedPaddr, e.busPaddr,
      e.cache ? "true" : "false", e.value, e.request, e.mapped, e.bytes,
      e.device, e.device == (u32)RBusDevice::VR4300_UNCACHED ? "true" : "false",
      e.chip, (unsigned long long)e.raw, (unsigned long long)e.delivered,
      e.cci, e.ccLow, e.ccHigh
    );
  }
  std::printf("]");
}
