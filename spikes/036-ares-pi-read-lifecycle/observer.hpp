/* SPDX-License-Identifier: ISC
 * External causal metadata for the pinned ares PI-read lifecycle experiment.
 * No reference object-layout changes.
 */
#pragma once
#include <array>
#include <cassert>
#include <cstdio>
#include <vector>

struct PlaidQueueTrace {
  u64 ordinal, token, request;
  u32 phase, kind, slot, other, event, clock;
  bool valid;
};
struct PlaidPiTrace {
  u64 ordinal, request, token;
  u32 phase, kind, a, b, c, d, e;
};
struct PlaidRdramTrace {
  u64 ordinal, request, value;
  u32 phase, address, size, device;
  bool write;
};

inline u64 plaidOrdinal = 0;
inline u64 plaidNextToken = 0;
inline u64 plaidNextRequest = 0;
inline u64 plaidCurrentRequest = 0;
inline u64 plaidPendingDispatchToken = 0;
inline u64 plaidPendingDispatchRequest = 0;
inline u32 plaidPhase = 0;
inline bool plaidRequestOpen = false;
inline const void* plaidQueueOwner = nullptr;
inline std::array<u64,512> plaidQueueSlots{};
inline std::vector<std::pair<u64,u64>> plaidTokenRequests;
inline std::vector<PlaidQueueTrace> plaidQueueTrace;
inline std::vector<PlaidPiTrace> plaidPiTrace;
inline std::vector<PlaidRdramTrace> plaidRdramTrace;

inline auto plaid_request_for_token(u64 token) -> u64 {
  for(auto [candidate, request] : plaidTokenRequests) if(candidate == token) return request;
  return 0;
}
inline auto plaid_begin_request(u32 phase) -> u64 {
  assert(!plaidRequestOpen);
  plaidPhase = phase;
  plaidCurrentRequest = ++plaidNextRequest;
  plaidRequestOpen = true;
  return plaidCurrentRequest;
}
inline auto plaid_end_request() -> void {
  assert(plaidRequestOpen);
  plaidRequestOpen = false;
  plaidCurrentRequest = 0;
}

inline void plaid_queue_event(u32 kind, const void* owner, u32 slot, u32 other,
                              u32 event, u32 clock, bool valid) {
  assert(owner == plaidQueueOwner);
  u64 token = 0;
  if(kind == 1 || (kind == 9 && valid)) {
    // Reset and load cut external identity. Saving (kind 9, valid=false) does not.
    plaidQueueSlots.fill(0);
    plaidPendingDispatchToken = 0;
    plaidPendingDispatchRequest = 0;
  } else if(kind == 9) {
    // Save-only boundary: preserve live sidecar identities.
  } else if(kind == 3 || kind == 6 || kind == 7) {
    assert(slot < plaidQueueSlots.size() && other < plaidQueueSlots.size());
    plaidQueueSlots[slot] = token = plaidQueueSlots[other];
  } else if(kind == 4) {
    assert(slot < plaidQueueSlots.size());
    plaidQueueSlots[slot] = token = ++plaidNextToken;
    if(plaidRequestOpen && (event == Queue::PI_DMA_Read || event == Queue::PI_DMA_Write))
      plaidTokenRequests.push_back({token, plaidCurrentRequest});
  } else if(kind == 5 || kind == 8) {
    assert(slot < plaidQueueSlots.size());
    token = plaidQueueSlots[slot];
    if(kind == 5) {
      plaidPendingDispatchToken = valid ? token : 0;
      plaidPendingDispatchRequest = valid ? plaid_request_for_token(token) : 0;
    }
  } else {
    assert(kind == 2);
  }
  plaidQueueTrace.push_back({++plaidOrdinal, token, plaid_request_for_token(token),
    plaidPhase, kind, slot, other, event, clock, valid});
}

inline void plaid_pi_event(u32 kind, u32 a, u32 b, u32 c, u32 d, u32 e) {
  u64 request = plaidRequestOpen ? plaidCurrentRequest : 0;
  u64 token = 0;
  if(kind == 8) {
    token = plaidPendingDispatchToken;
    request = plaidPendingDispatchRequest;
    plaidPendingDispatchToken = 0;
    plaidPendingDispatchRequest = 0;
  }
  plaidPiTrace.push_back({++plaidOrdinal, request, token, plaidPhase, kind, a, b, c, d, e});
}

inline void plaid_rdram_event(bool write, u32 address, u32 size, u32 device, u64 value) {
  plaidRdramTrace.push_back({++plaidOrdinal, plaidRequestOpen ? plaidCurrentRequest : 0,
    value, plaidPhase, address, size, device, write});
}

inline void plaid_print_trace() {
  std::printf("\"queue_trace\":[");
  for(size_t i=0;i<plaidQueueTrace.size();i++) {
    const auto& x=plaidQueueTrace[i];
    std::printf("%s{\"o\":%llu,\"phase\":%u,\"kind\":%u,\"slot\":%u,\"other\":%u,\"event\":%u,\"clock\":%u,\"valid\":%s,\"token\":%llu,\"request\":%llu}",
      i ? "," : "",(unsigned long long)x.ordinal,x.phase,x.kind,x.slot,x.other,x.event,x.clock,
      x.valid ? "true" : "false",(unsigned long long)x.token,(unsigned long long)x.request);
  }
  std::printf("],\"pi_trace\":[");
  for(size_t i=0;i<plaidPiTrace.size();i++) {
    const auto& x=plaidPiTrace[i];
    std::printf("%s{\"o\":%llu,\"phase\":%u,\"kind\":%u,\"request\":%llu,\"token\":%llu,\"a\":%u,\"b\":%u,\"c\":%u,\"d\":%u,\"e\":%u}",
      i ? "," : "",(unsigned long long)x.ordinal,x.phase,x.kind,(unsigned long long)x.request,
      (unsigned long long)x.token,x.a,x.b,x.c,x.d,x.e);
  }
  std::printf("],\"rdram_trace\":[");
  for(size_t i=0;i<plaidRdramTrace.size();i++) {
    const auto& x=plaidRdramTrace[i];
    std::printf("%s{\"o\":%llu,\"phase\":%u,\"request\":%llu,\"write\":%s,\"address\":%u,\"size\":%u,\"device\":%u,\"value\":%llu}",
      i ? "," : "",(unsigned long long)x.ordinal,x.phase,(unsigned long long)x.request,
      x.write ? "true" : "false",x.address,x.size,x.device,(unsigned long long)x.value);
  }
  std::printf("]");
}
