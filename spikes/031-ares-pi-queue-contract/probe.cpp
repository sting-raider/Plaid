/* SPDX-License-Identifier: ISC
 * Original probe of the separately licensed pinned priority queue container.
 */
#include <nall/nall.hpp>
#include <nall/priority-queue.hpp>
#include <cassert>
#include <cstdio>
#include <vector>

int main() {
  nall::priority_queue<u32[512]> queue;
  std::vector<u32> events;
  auto dispatch=[&](u32 event) { events.push_back(event); };
  queue.reset();
  assert(queue.insert(1,3) && queue.insert(1,5));
  queue.step(3,dispatch); assert(events == std::vector<u32>{1});
  queue.step(2,dispatch); assert(events == (std::vector<u32>{1,1}));

  queue.reset(); events.clear();
  assert(queue.insert(1,3));
  assert(queue.remove(1) == 3);
  assert(queue.insert(0,4));
  queue.step(5,dispatch); assert(events == std::vector<u32>{0});

  queue.reset(); events.clear();
  for(u32 i=0;i<512;i++) assert(queue.insert(1,1));
  assert(queue.remove(1) == 1);
  assert(!queue.insert(0,2)); // Invalidated entries still occupy capacity.
  queue.step(1,dispatch); assert(events.empty());
  assert(queue.insert(0,1)); queue.step(1,dispatch);
  assert(events == std::vector<u32>{0});

  queue.reset(); events.clear();
  queue.step(0xfffffff0,dispatch); assert(queue.insert(1,32));
  queue.step(31,dispatch); assert(events.empty());
  queue.step(1,dispatch); assert(events == std::vector<u32>{1});
  std::printf("{\"duplicate_write_dispatches\":[1,1],\"canceled_write_then_read\":[0],\"capacity\":512,\"canceled_slots_reject_insert_until_drained\":true,\"clock_wrap_dispatch\":[1]}\n");
}
