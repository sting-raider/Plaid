/* SPDX-License-Identifier: ISC
 * Bounded composition probe. It executes the exact pinned nall queue container.
 * PI/CPU sequencing below is a synthetic harness guarded against pinned ares source
 * by run.py; it is not a full ares device execution or hardware timing oracle.
 */
#include <nall/nall.hpp>
#include <nall/priority-queue.hpp>
#include <cassert>
#include <cstdio>
#include <map>
#include <vector>
#if PLAID_QUEUE_SENSOR
#include "observer.hpp"
#endif

static constexpr u32 PI_DMA_Read = 0;
static constexpr u32 PI_DMA_Write = 1;
static constexpr u32 Other = 99;

struct Lifecycle {
  u64 request;
  u32 event;
  u64 token;
  bool inserted;
  bool dispatched;
  bool status_finished;
};

int main(int argc, char** argv) {
  if(argc != 2) return 2;
  bool traced = !strcmp(argv[1], "traced");
  nall::priority_queue<u32[512]> queue{};
  std::map<u64,Lifecycle> life;
  std::vector<u64> dispatch_requests;
  u64 next_request = 0;
  u64 copy_effects = 0;
  bool dma_busy = false;
  bool interrupt = false;
  u64 unknown_dispatches = 0;

#if PLAID_QUEUE_SENSOR
  queueIdentityOwner = &queue;
  nall::plaidQueueObserver = traced ? queue_identity : nullptr;
#else
  (void)traced;
#endif

  auto start = [&](u32 event, u32 clocks) -> u64 {
    u64 request = ++next_request;
    dma_busy = true;
#if PLAID_QUEUE_SENSOR
    activePiRequest = request;
#endif
    bool inserted = queue.insert(event, clocks);
#if PLAID_QUEUE_SENSOR
    activePiRequest = 0;
    u64 token = 0;
    for(auto& [candidate, owner] : tokenToRequest) if(owner == request) token = candidate;
#else
    u64 token = 0;
#endif
    // Pinned PI ioWrite calls dmaRead()/dmaWrite() after queueInsert regardless of
    // whether the queue accepted the event. Model only the existence of byte effects.
    copy_effects++;
    life[request] = {request,event,token,inserted,false,false};
    return request;
  };

  auto dispatch = [&](u32 event) {
#if PLAID_QUEUE_SENSOR
    u64 token = pendingDispatchToken;
    pendingDispatchToken = 0;
    u64 request = token && tokenToRequest.count(token) ? tokenToRequest[token] : 0;
#else
    u64 request = 0;
#endif
    if(request) {
      assert(life.count(request));
      assert(life[request].event == event);
      life[request].dispatched = true;
      dispatch_requests.push_back(request);
    } else {
      unknown_dispatches++;
      dispatch_requests.push_back(0);
    }
    // Pinned CPU switch sends both PI DMA event classes to dmaFinished().
    dma_busy = false;
    interrupt = true;
    if(request) life[request].status_finished = true;
  };

  auto reset_status = [&] {
    dma_busy = false;
    queue.remove(PI_DMA_Read);
    queue.remove(PI_DMA_Write);
  };

  // Case 1: identical event and deadline. Event/deadline matching is ambiguous;
  // actual queue token identity must keep both requests distinct.
  auto a = start(PI_DMA_Write, 3);
  auto b = start(PI_DMA_Write, 3);
  assert(a != b);
  queue.step(3, dispatch);
  assert(dispatch_requests.size() == 2);
#if PLAID_QUEUE_SENSOR
  if(traced) {
    assert(life[a].token && life[b].token && life[a].token != life[b].token);
    assert(dispatch_requests[0] != dispatch_requests[1]);
  }
#endif

  // Case 2: canceled PI event. Invalid queue roots are drained without CPU callback.
  queue.reset();
  auto canceled = start(PI_DMA_Read, 2);
  reset_status();
  auto before = dispatch_requests.size();
  queue.step(2, dispatch);
  assert(dispatch_requests.size() == before);
  assert(!life[canceled].dispatched);

  // Case 3: fill capacity, invalidate without draining, then start a PI request.
  // Its byte effects occur even though no lifecycle event can be inserted.
  queue.reset();
  for(u32 i=0;i<512;i++) assert(queue.insert(Other, 1));
  queue.remove(Other);
  auto rejected = start(PI_DMA_Write, 4);
  assert(!life[rejected].inserted);
  assert(dma_busy);
  auto copies_after_reject = copy_effects;
  queue.step(1, dispatch); // drains canceled roots; no callback
  assert(copy_effects == copies_after_reject);
  assert(!life[rejected].dispatched);
  reset_status();
  assert(!dma_busy);

  // Case 4: serialization boundary deliberately destroys identity evidence. The
  // reference event still dispatches and changes status, but request join is unknown.
  queue.reset();
  auto restored = start(PI_DMA_Read, 5);
  nall::serializer saved; saved.setWriting(); queue.serialize(saved);
  saved.setReading(); queue.serialize(saved);
  before = dispatch_requests.size();
  queue.step(5, dispatch);
  assert(dispatch_requests.size() == before + 1);
#if PLAID_QUEUE_SENSOR
  if(traced) {
    assert(dispatch_requests.back() == 0);
    assert(!life[restored].dispatched);
  }
#endif

#if PLAID_QUEUE_SENSOR
  nall::plaidQueueObserver = nullptr;
#endif
  std::printf("{\"copy_effects\":%llu,\"requests\":%llu,\"dispatches\":[",
    (unsigned long long)copy_effects,(unsigned long long)next_request);
  for(size_t i=0;i<dispatch_requests.size();i++)
    std::printf("%s%llu",i ? "," : "",(unsigned long long)dispatch_requests[i]);
  std::printf("],\"unknown_dispatches\":%llu,\"rejected_inserted\":%s,\"rejected_dispatched\":%s,\"serialized_request_joined\":%s,\"busy\":%s,\"interrupt\":%s",
    (unsigned long long)unknown_dispatches,
    life[rejected].inserted ? "true" : "false",
    life[rejected].dispatched ? "true" : "false",
    life[restored].dispatched ? "true" : "false",
    dma_busy ? "true" : "false", interrupt ? "true" : "false");
#if PLAID_QUEUE_SENSOR
  std::printf(",\"token_a\":%llu,\"token_b\":%llu,\"records\":%zu",
    (unsigned long long)life[a].token,(unsigned long long)life[b].token,joinRecords.size());
#else
  std::printf(",\"token_a\":0,\"token_b\":0,\"records\":0");
#endif
  std::printf("}\n");
}
