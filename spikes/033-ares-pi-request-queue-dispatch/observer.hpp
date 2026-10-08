/* SPDX-License-Identifier: ISC
 * External PI-request / queue-token join state for the bounded research probe.
 * No reference queue object layout changes.
 */
#include <array>
#include <cassert>
#include <map>
#include <vector>

struct JoinRecord {
  u32 kind;
  u32 event;
  bool valid;
  u64 token;
  u64 request;
};

inline const void* queueIdentityOwner = nullptr;
inline u64 queueIdentityNext = 0;
inline std::array<u64,512> queueIdentitySlots{};
inline u64 activePiRequest = 0;
inline u64 pendingDispatchToken = 0;
inline std::map<u64,u64> tokenToRequest;
inline std::vector<JoinRecord> joinRecords;

inline void queue_identity(u32 kind, const void* owner, u32 slot, u32 other,
                           u32 event, u32 clock, bool valid) {
  (void)clock;
  assert(owner == queueIdentityOwner);
  u64 token = 0;
  if(kind == 1 || kind == 9) {
    queueIdentitySlots.fill(0);
    pendingDispatchToken = 0;
  } else if(kind == 3 || kind == 6 || kind == 7) {
    assert(slot < 512 && other < 512);
    queueIdentitySlots[slot] = token = queueIdentitySlots[other];
  } else if(kind == 4) {
    assert(slot < 512);
    queueIdentitySlots[slot] = token = ++queueIdentityNext;
    if(activePiRequest) tokenToRequest[token] = activePiRequest;
  } else if(kind == 5) {
    assert(slot < 512);
    token = queueIdentitySlots[slot];
    if(valid) pendingDispatchToken = token;
  } else if(kind == 8) {
    assert(slot < 512);
    token = queueIdentitySlots[slot];
  } else {
    assert(kind == 2);
  }
  if(activePiRequest || kind == 2 || kind == 4 || kind == 5 || kind == 8 || kind == 9) {
    auto request = token && tokenToRequest.count(token) ? tokenToRequest[token] : activePiRequest;
    joinRecords.push_back({kind,event,valid,token,request});
  }
}
