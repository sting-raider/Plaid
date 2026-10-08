/*
Behavioral extraction/adaptation from ares nall priority queue and N64 PI semantics.
ares is ISC-licensed:
Copyright (c) 2004-2025 ares team, Near et al
Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.
THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
*/

#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <optional>
#include <random>
#include <sstream>
#include <string>
#include <tuple>
#include <vector>

using u32 = uint32_t;
using s32 = int32_t;
using u64 = uint64_t;

// Behavioral extraction of nall::priority_queue<T[512]> at
// ares-emulator/ares@9408cb43d4948fc3ea6e152a307a34348df3fe04.
template <typename EntryMeta>
class AresQueue {
public:
  struct Entry {
    u32 clock = 0;
    u32 event = 0;
    bool valid = false;
    EntryMeta meta{};
  };

  static constexpr u32 Capacity = 512;

  bool insert(u32 event, u32 delta, EntryMeta meta = {}) {
    if(size_ >= Capacity) return false;
    u32 child = size_++;
    u32 absolute = delta + clock_;
    while(child) {
      u32 parent = (child - 1) >> 1;
      if(ge(absolute, heap_[parent].clock)) break;
      heap_[child] = heap_[parent];
      child = parent;
    }
    heap_[child] = Entry{absolute, event, true, meta};
    return true;
  }

  std::optional<Entry> removeFirstRaw() {
    if(!size_) return std::nullopt;
    Entry result = heap_[0];
    u32 parent = 0;
    u32 lastClock = heap_[--size_].clock;
    while(true) {
      u32 child = (parent << 1) + 1;
      if(child >= size_) break;
      if(child + 1 < size_ && ge(heap_[child].clock, heap_[child+1].clock)) child++;
      if(ge(heap_[child].clock, lastClock)) break;
      heap_[parent] = heap_[child];
      parent = child;
    }
    heap_[parent] = heap_[size_];
    heap_[parent].clock = lastClock;
    return result;
  }

  u32 removeEvent(u32 event) {
    u32 cycles = 0;
    for(u32 i=0;i<size_;++i) {
      if(heap_[i].event == event) {
        heap_[i].valid = false;
        cycles = std::max(cycles, heap_[i].clock - clock_);
      }
    }
    return cycles;
  }

  template<class F>
  void step(u32 clocks, F callback) {
    clock_ += clocks;
    while(size_ && ge(clock_, heap_[0].clock)) {
      auto e = removeFirstRaw();
      if(e && e->valid) callback(*e);
    }
  }

  u32 size() const { return size_; }
  u32 clock() const { return clock_; }
  s32 timeToNextEvent() const {
    if(!size_) return 0x7fffffff;
    return static_cast<s32>(heap_[0].clock - clock_);
  }

private:
  static bool ge(u32 x, u32 y) { return x - y < 0x7fffffffU; }
  u32 clock_ = 0;
  u32 size_ = 0;
  std::array<Entry, Capacity> heap_{};
};

struct EmptyMeta {};
struct TokenMeta { u64 token = 0; };

static constexpr u32 PI_DMA_Read = 0;
static constexpr u32 PI_DMA_Write = 1;

struct Observable {
  bool dmaBusy = false;
  bool error = false;
  bool interrupt = false;
  u64 immediateDmas = 0;
  u64 completions = 0;
  std::vector<std::pair<u32,u32>> completionLog;
  auto operator==(const Observable&) const -> bool = default;
};

// Baseline captures pinned ares ordering relevant to the experiment:
// length write: busy=true; queueInsert(...); DMA executes immediately.
// status bit0: busy=false,error=false; queue.remove(read/write).
class BaselinePI {
public:
  Observable o;
  AresQueue<EmptyMeta> q;

  bool request(u32 event, u32 duration) {
    if(o.dmaBusy) { o.error = true; return false; }
    o.dmaBusy = true;
    bool inserted = q.insert(event, duration);
    o.immediateDmas++; // pinned ares does this regardless of insert success
    return inserted;
  }
  void reset() {
    o.dmaBusy = false; o.error = false;
    q.removeEvent(PI_DMA_Read); q.removeEvent(PI_DMA_Write);
  }
  void clearInterrupt() { o.interrupt = false; }
  void step(u32 clocks) {
    q.step(clocks,[&](const auto& e){
      o.dmaBusy = false; o.interrupt = true; o.completions++;
      o.completionLog.emplace_back(e.event,e.clock);
    });
  }
};

struct TokenRecord {
  enum State { Requested, Queued, Completed, Cancelled, QueueRejected } state = Requested;
  u64 token = 0;
  u32 event = 0;
  u32 due = 0;
};

// Instrumented model deliberately keeps token metadata observationally inert.
// Crucial design: request identity exists BEFORE queue insertion, because insertion may fail.
class TaggedPI {
public:
  Observable o;
  AresQueue<TokenMeta> q;
  std::vector<TokenRecord> records;
  std::optional<u64> active;
  u64 nextToken = 1;

  bool request(u32 event, u32 duration) {
    if(o.dmaBusy) { o.error = true; return false; }
    o.dmaBusy = true;
    u64 tok = nextToken++;
    records.push_back({TokenRecord::Requested,tok,event,q.clock()+duration});
    active = tok;
    bool inserted = q.insert(event,duration,TokenMeta{tok});
    records.back().state = inserted ? TokenRecord::Queued : TokenRecord::QueueRejected;
    o.immediateDmas++;
    return inserted;
  }
  void reset() {
    o.dmaBusy = false; o.error = false;
    if(active) mark(*active, TokenRecord::Cancelled);
    active.reset();
    q.removeEvent(PI_DMA_Read); q.removeEvent(PI_DMA_Write);
  }
  void clearInterrupt() { o.interrupt = false; }
  void step(u32 clocks) {
    q.step(clocks,[&](const auto& e){
      o.dmaBusy = false; o.interrupt = true; o.completions++;
      o.completionLog.emplace_back(e.event,e.clock);
      mark(e.meta.token,TokenRecord::Completed);
      if(active && *active == e.meta.token) active.reset();
    });
  }

  const TokenRecord* find(u64 token) const {
    for(auto const& r:records) if(r.token==token) return &r;
    return nullptr;
  }
private:
  void mark(u64 token, TokenRecord::State state) {
    for(auto& r:records) if(r.token==token) { r.state=state; return; }
    assert(false && "token must exist");
  }
};

static void assertNeutral(const BaselinePI& b, const TaggedPI& t) {
  if(!(b.o == t.o) || b.q.size()!=t.q.size() || b.q.clock()!=t.q.clock() || b.q.timeToNextEvent()!=t.q.timeToNextEvent()) {
    std::cerr << "neutrality mismatch\n";
    std::abort();
  }
}

int main() {
  // 1. Straight request -> exact tagged completion.
  {
    BaselinePI b; TaggedPI t;
    assert(b.request(PI_DMA_Write,17));
    assert(t.request(PI_DMA_Write,17));
    assertNeutral(b,t);
    t.step(17); b.step(17); // order intentionally differs to catch hidden coupling; independent objects
    assertNeutral(b,t);
    assert(t.records.size()==1 && t.records[0].state==TokenRecord::Completed);
    std::cout << "PASS straight_completion token=" << t.records[0].token << "\n";
  }

  // 2. Busy request rejected by PI before queue insertion, so it MUST NOT mint a token.
  {
    BaselinePI b; TaggedPI t;
    assert(b.request(PI_DMA_Read,50)); assert(t.request(PI_DMA_Read,50));
    assert(!b.request(PI_DMA_Write,10)); assert(!t.request(PI_DMA_Write,10));
    assert(t.records.size()==1);
    assertNeutral(b,t);
    std::cout << "PASS busy_reject_no_token records=" << t.records.size() << "\n";
  }

  // 3. Cancel then identical restart at same absolute deadline. The old tombstone and new valid
  // entry can have the same event+deadline tuple. Token is the only causal discriminator.
  {
    BaselinePI b; TaggedPI t;
    assert(b.request(PI_DMA_Write,100)); assert(t.request(PI_DMA_Write,100));
    const u64 oldTok=t.records.back().token;
    b.reset(); t.reset();
    assert(b.request(PI_DMA_Write,100)); assert(t.request(PI_DMA_Write,100));
    const u64 newTok=t.records.back().token;
    assert(oldTok!=newTok);
    assert(t.records[0].due==t.records[1].due);
    assert(t.records[0].event==t.records[1].event);
    assert(t.records[0].state==TokenRecord::Cancelled);
    b.step(100); t.step(100);
    assertNeutral(b,t);
    assert(t.find(newTok)->state==TokenRecord::Completed);
    assert(t.find(oldTok)->state==TokenRecord::Cancelled);
    assert(t.o.completions==1);
    std::cout << "PASS equal_tuple_cancel_restart old="<<oldTok<<" new="<<newTok<<" completions="<<t.o.completions<<"\n";
  }

  // 4. Clearing the PI interrupt is not cancellation and must not retire the active request.
  {
    BaselinePI b; TaggedPI t;
    assert(b.request(PI_DMA_Read,23)); assert(t.request(PI_DMA_Read,23));
    const u64 tok=t.records.back().token;
    b.o.interrupt=true; t.o.interrupt=true;
    b.clearInterrupt(); t.clearInterrupt();
    assert(t.active && *t.active==tok);
    assert(t.find(tok)->state==TokenRecord::Queued);
    b.step(23); t.step(23);
    assertNeutral(b,t);
    assert(t.find(tok)->state==TokenRecord::Completed);
    std::cout << "PASS interrupt_clear_preserves_request token="<<tok<<"\n";
  }

  // 5. Queue-capacity counterexample: remove(event) leaves tombstones occupying capacity.
  // 512 legal request/reset pairs without advancing queue time fill it. Request 513 is accepted by PI,
  // its DMA executes immediately, but queue insertion fails, hence there is no completion entry identity.
  {
    BaselinePI b; TaggedPI t;
    for(u32 i=0;i<512;i++) {
      bool bi=b.request(PI_DMA_Write,1000000);
      bool ti=t.request(PI_DMA_Write,1000000);
      assert(bi && ti);
      b.reset(); t.reset();
      assertNeutral(b,t);
    }
    assert(b.q.size()==512 && t.q.size()==512);
    auto beforeDmas=b.o.immediateDmas;
    bool bi=b.request(PI_DMA_Write,1000000);
    bool ti=t.request(PI_DMA_Write,1000000);
    assert(!bi && !ti);
    assert(b.o.immediateDmas==beforeDmas+1 && t.o.immediateDmas==beforeDmas+1);
    assert(t.records.back().state==TokenRecord::QueueRejected);
    assert(t.o.dmaBusy);
    assertNeutral(b,t);
    std::cout << "PASS queue_full_dma_without_event queue_size="<<b.q.size()
              <<" immediate_dmas="<<b.o.immediateDmas
              <<" rejected_token="<<t.records.back().token<<"\n";
  }

  // 6. Differential fuzz. Random legal/illegal PI requests, reset/interrupt-clear, and time steps.
  // Instrumentation metadata must never perturb externally observable behavior or queue timing.
  {
    for(u64 seed=1; seed<=64; ++seed) {
      std::mt19937_64 rng(seed);
      BaselinePI b; TaggedPI t;
      for(u32 i=0;i<20000;i++) {
        u32 op=rng()%6;
        if(op<=1) {
          u32 ev=(rng()&1)?PI_DMA_Read:PI_DMA_Write;
          u32 dur=1+(rng()%2000);
          bool x=b.request(ev,dur), y=t.request(ev,dur);
          assert(x==y);
        } else if(op==2) {
          b.reset(); t.reset();
        } else if(op==3) {
          b.clearInterrupt(); t.clearInterrupt();
        } else {
          u32 clocks=rng()%128;
          b.step(clocks); t.step(clocks);
        }
        assertNeutral(b,t);
      }
    }
    std::cout << "PASS differential_fuzz seeds=64 ops_per_seed=20000 total_ops=1280000\n";
  }

  std::cout << "RESULT PARTIAL: queue-entry token is sufficient for successful insertions but not universal; request identity must predate queue insertion and record insertion failure.\n";
}
