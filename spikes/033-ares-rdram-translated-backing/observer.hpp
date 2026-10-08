#pragma once

struct PlaidTranslatedReadEvent {
  u32 request;
  u32 mapped;
  u32 bytes;
  u32 device;
  u32 chip;
  u64 raw;
  u64 delivered;
  u32 cci;
  u32 ccLow;
  u32 ccHigh;
};

inline std::vector<PlaidTranslatedReadEvent> plaidTranslatedReads;

inline auto plaid_translated_read_observer(
  u32 request, u32 mapped, u32 bytes, u32 device, u32 chip,
  u64 raw, u64 delivered, u32 cci, u32 ccLow, u32 ccHigh
) -> void {
  plaidTranslatedReads.push_back({request, mapped, bytes, device, chip, raw, delivered, cci, ccLow, ccHigh});
}

inline auto print_plaid_translated_reads() -> void {
  std::printf(",\"translated_reads\":[");
  for(size_t i = 0; i < plaidTranslatedReads.size(); i++) {
    const auto& e = plaidTranslatedReads[i];
    std::printf(
      "%s{\"request\":%u,\"mapped\":%u,\"bytes\":%u,\"device\":%u,\"chip\":%u,"
      "\"raw\":%llu,\"delivered\":%llu,\"cci\":%u,\"cc_low\":%u,\"cc_high\":%u}",
      i ? "," : "", e.request, e.mapped, e.bytes, e.device, e.chip,
      (unsigned long long)e.raw, (unsigned long long)e.delivered, e.cci, e.ccLow, e.ccHigh
    );
  }
  std::printf("]");
}
