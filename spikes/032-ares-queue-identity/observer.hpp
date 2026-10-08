/* SPDX-License-Identifier: ISC
 * Original finite queue identity metadata. No reference object layout changes.
 */
#include <array>
#include <cassert>
#include <vector>
struct QueueIdentityRecord {
  u32 ordinal, phase, kind, slot, other, event, clock;
  bool valid;
  u64 token;
};
inline u32 queueIdentityPhase = 0;
inline const void* queueIdentityOwner = nullptr;
inline u64 queueIdentityNext = 0;
inline std::array<u64,512> queueIdentitySlots{};
inline std::vector<QueueIdentityRecord> queueIdentityRecords;
inline void queue_identity(u32 kind, const void* owner, u32 slot, u32 other,
                           u32 event, u32 clock, bool valid) {
  // Exactly one declared queue is supported per capture. Other owners fail.
  assert(owner == queueIdentityOwner);
  u64 token = 0;
  if(kind == 1 || kind == 9) queueIdentitySlots.fill(0);
  else if(kind == 3 || kind == 6 || kind == 7) {
    assert(slot < 512 && other < 512);
    queueIdentitySlots[slot] = token = queueIdentitySlots[other];
  } else if(kind == 4) {
    assert(slot < 512);
    queueIdentitySlots[slot] = token = ++queueIdentityNext;
  } else if(kind == 5 || kind == 8) {
    assert(slot < 512);
    token = queueIdentitySlots[slot];
  } else assert(kind == 2);
  queueIdentityRecords.push_back({(u32)queueIdentityRecords.size()+1,
    queueIdentityPhase, kind, slot, other, event, clock, valid, token});
}
inline void print_queue_identity() {
  std::printf("\"events\":[");
  for(size_t i=0;i<queueIdentityRecords.size();i++) {
    const auto& e=queueIdentityRecords[i];
    std::printf("%s{\"ordinal\":%u,\"phase\":%u,\"kind\":%u,\"slot\":%u,\"other\":%u,\"event\":%u,\"clock\":%u,\"valid\":%s,\"token\":%llu}",
      i ? "," : "",e.ordinal,e.phase,e.kind,e.slot,e.other,e.event,e.clock,
      e.valid ? "true" : "false",(unsigned long long)e.token);
  }
  std::printf("]");
}
