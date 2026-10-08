/* SPDX-License-Identifier: ISC
 * Original actual-container probe; no CPU/device/hardware execution claim.
 */
#include <nall/nall.hpp>
#include <nall/priority-queue.hpp>
#include <cassert>
#include <cstdio>
#include <vector>
#if PLAID_QUEUE_SENSOR
#include "observer.hpp"
#endif
int main(int argc,char** argv) {
  if(argc != 2) return 2;
  bool traced = !strcmp(argv[1],"traced");
  nall::priority_queue<u32[512]> queue{};
  std::vector<u32> dispatches;
  std::vector<u32> boundaries;
  std::vector<u8> checkpoints;
  auto dispatch = [&](u32 event) { dispatches.push_back(event); };
  auto phase = [&](u32 value) {
    #if PLAID_QUEUE_SENSOR
    queueIdentityPhase=value;
    #endif
    queue.reset();
  };
  auto checkpoint = [&] {
    // Unused reference slots are uninitialized. Compare only the serialized
    // clock/size and currently occupied entries, including invalid entries.
    nall::serializer s; s.setWriting(); queue.serialize(s);
    u32 size=0; for(u32 i=0;i<4;i++) size |= u32(s.data()[4+i]) << (i*8);
    assert(s.size()==8+512*9 && size<=512);
    checkpoints.insert(checkpoints.end(),s.data(),s.data()+8+size*9);
    boundaries.push_back(dispatches.size());
  };
  #if PLAID_QUEUE_SENSOR
  queueIdentityOwner=&queue;
  nall::plaidQueueObserver=traced ? queue_identity : nullptr;
  #else
  (void)traced;
  #endif
  phase(1);
  assert(queue.insert(1,9) && queue.insert(1,3) && queue.insert(0,6));
  queue.step(3,dispatch); queue.step(3,dispatch); queue.step(3,dispatch);
  assert(dispatches==(std::vector<u32>{1,0,1})); checkpoint();
  phase(2);
  assert(queue.insert(1,3) && queue.insert(1,5));
  assert(queue.remove(1)==5); assert(queue.remove(1)==5);
  assert(queue.insert(0,4)); queue.step(5,dispatch); checkpoint();
  phase(3);
  for(u32 i=0;i<512;i++) assert(queue.insert(1,1));
  assert(queue.remove(1)==1 && !queue.insert(0,2));
  // Saving while occupied must preserve live identities; loading cuts them.
  checkpoint(); queue.step(1,dispatch);
  assert(queue.insert(0,1)); queue.step(1,dispatch); checkpoint();
  phase(4);
  queue.step(0xfffffff0,dispatch); assert(queue.insert(1,32));
  queue.step(31,dispatch); queue.step(1,dispatch); checkpoint();
  phase(5);
  assert(queue.insert(1,3));
  nall::serializer saved; saved.setWriting(); queue.serialize(saved);
  queue.step(3,dispatch); saved.setReading(); queue.serialize(saved);
  queue.step(3,dispatch); checkpoint();
  phase(6);
  assert(queue.insert(1,3) && queue.insert(1,3));
  queue.step(3,dispatch); checkpoint();
  #if PLAID_QUEUE_SENSOR
  nall::plaidQueueObserver=nullptr;
  #endif
  std::printf("{");
  #if PLAID_QUEUE_SENSOR
  print_queue_identity();
  #else
  std::printf("\"events\":[]");
  #endif
  std::printf(",\"queue_object_bytes\":%zu,\"dispatches\":[",sizeof(queue));
  for(size_t i=0;i<dispatches.size();i++) std::printf("%s%u",i ? "," : "",dispatches[i]);
  std::printf("],\"boundaries\":[");
  for(size_t i=0;i<boundaries.size();i++) std::printf("%s%u",i ? "," : "",boundaries[i]);
  std::printf("],\"occupied_checkpoints_hex\":\"");
  for(auto b:checkpoints) std::printf("%02x",b);
  std::printf("\"}\n");
}
