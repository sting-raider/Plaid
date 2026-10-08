/* SPDX-License-Identifier: ISC
 * Exact pinned-ares component fixture for PI DMA-read request -> queue token -> CPU dispatch.
 */
#ifndef PLAID_PI_READ_SENSOR
#define PLAID_PI_READ_SENSOR 1
#endif
#define main plaid_capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>
#if PLAID_PI_READ_SENSOR
#include "observer.hpp"
#endif

struct Fact {
  u32 phase, busyRequest, interruptRequest, busyEnd, interruptEnd, delay, latchRequest, aux;
};

int main(int argc,char** argv) {
  if(argc != 2 || (strcmp(argv[1],"plain") && strcmp(argv[1],"traced"))) return 2;
  bool traced = !strcmp(argv[1],"traced");
  Headless frontend; platform = &frontend;
  std::vector<u8> rom(16384);
  rom[0]=0x80; rom[1]=0x37; rom[2]=0x12; rom[3]=0x40;
  frontend.cartPak->setAttribute("title","Plaid PI DMA read lifecycle fixture");
  frontend.cartPak->setAttribute("region","NTSC");
  frontend.cartPak->setAttribute("cic","CIC-NUS-6102");
  frontend.cartPak->append("program.rom",std::span<const u8>{rom.data(),rom.size()});
  Node::System root;
  if(!load(root,"[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak","true"); option("Deterministic Entropy","true"); option("Recompiler","false");
  cartridgeSlot.port->allocate(); cartridgeSlot.port->connect();
  ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled || rdram.ram.size != 8388608) return 4;
  std::vector<u8> hidden(rdram.ram.size/2); rdram.hidden.data = hidden.data();
  rdram.mapIdentity = 1;
  std::memset(rdram.ram.data,0xcc,rdram.ram.size);

#if PLAID_PI_READ_SENSOR
  plaidQueueOwner=&queue;
  nall::plaidQueueObserver=traced ? plaid_queue_event : nullptr;
  plaidPiDmaObserver=traced ? plaid_pi_event : nullptr;
  plaidRdramScalarObserver=traced ? plaid_rdram_event : nullptr;
#endif

  std::vector<Fact> facts;
  auto phase = [&](u32 id) {
#if PLAID_PI_READ_SENSOR
    if(traced) plaidPhase=id;
#endif
    cpu.clock=0;
    queue.reset();
    pi.io.dmaBusy=0; pi.io.ioBusy=0; pi.io.error=0; pi.io.interrupt=0; pi.io.busLatch=0;
  };
  auto seed = [&](u32 address, std::array<u16,4> values) {
    for(u32 i=0;i<4;i++) rdram.ram.write<Half>(address+i*2,values[i],RBusDevice::ARES_DEBUGGER);
  };
  auto requestRead = [&](u32 id,u32 source,u32 destination,u32 length) -> u64 {
    pi.ioWrite(0x00,source);
    pi.ioWrite(0x04,destination);
    u64 request=0;
#if PLAID_PI_READ_SENSOR
    if(traced) request=plaid_begin_request(id);
#endif
    pi.ioWrite(0x08,length-1);
#if PLAID_PI_READ_SENSOR
    if(traced) plaid_end_request();
#endif
    return request;
  };
  auto dispatchNext = [&]() -> u32 {
    s32 signedDelay=queue.timeToNextEvent();
    assert(signedDelay >= 0 && signedDelay < 100000000);
    u32 delay=(u32)signedDelay;
    cpu.step(delay);
    cpu.synchronize();
    return delay;
  };
  constexpr u32 openPbus=0x07000000;

  // 1: normal actual PI read. dmaRead consumes RDRAM synchronously and updates
  // the PBUS latch before the scheduled completion later reaches dmaFinished.
  phase(1); seed(0x1000,{0x1122,0x3344,0x5566,0x7788});
  u64 normalRequest=requestRead(1,0x1000,openPbus,8);
  u32 normalBusy=(u32)pi.io.dmaBusy, normalInterrupt=(u32)pi.io.interrupt, normalLatch=(u32)pi.io.busLatch;
  u32 normalDelay=dispatchNext();
  facts.push_back({1,normalBusy,normalInterrupt,(u32)pi.io.dmaBusy,(u32)pi.io.interrupt,normalDelay,normalLatch,0});

  // 2: status reset cancels the exact pending PI_DMA_Read token. The immediate
  // RDRAM->PBUS effect remains, but no completion callback is permitted.
  phase(2); seed(0x1100,{0x99aa,0xbbcc,0xddee,0xf012});
  u64 cancelRequest=requestRead(2,0x1100,openPbus,8);
  u32 cancelBusy=(u32)pi.io.dmaBusy, cancelInterrupt=(u32)pi.io.interrupt, cancelLatch=(u32)pi.io.busLatch;
  s32 cancelDelaySigned=queue.timeToNextEvent(); assert(cancelDelaySigned>=0);
  pi.ioWrite(0x10,1);
  cpu.step((u32)cancelDelaySigned); cpu.synchronize();
  facts.push_back({2,cancelBusy,cancelInterrupt,(u32)pi.io.dmaBusy,(u32)pi.io.interrupt,
    (u32)cancelDelaySigned,cancelLatch,0});

  // 3: fill all 512 physical queue slots, then issue a real PI read. The queue
  // insertion must fail while dmaRead still consumes the RDRAM halfwords now.
  phase(3); seed(0x1200,{0x1357,0x2468,0x369c,0x48ad});
  u32 filled=0; for(u32 i=0;i<512;i++) if(queue.insert(Queue::GDB_Poll,100000)) filled++;
  assert(filled==512);
  u64 rejectRequest=requestRead(3,0x1200,openPbus,8);
  facts.push_back({3,(u32)pi.io.dmaBusy,(u32)pi.io.interrupt,(u32)pi.io.dmaBusy,(u32)pi.io.interrupt,
    (u32)queue.timeToNextEvent(),(u32)pi.io.busLatch,filled});

  // 4: queue-only adversary. Two indistinguishable PI_DMA_Read rows at one
  // deadline must keep separate tokens and must not borrow any request identity.
  phase(4);
  assert(queue.insert(Queue::PI_DMA_Read,17));
  assert(queue.insert(Queue::PI_DMA_Read,17));
  pi.io.dmaBusy=1; pi.io.interrupt=0;
  cpu.step(17); cpu.synchronize();
  facts.push_back({4,1,0,(u32)pi.io.dmaBusy,(u32)pi.io.interrupt,17,(u32)pi.io.busLatch,2});

  // 5: save-only serialization must preserve the current integration policy's
  // live token. There is no restore here; the exact request should still join.
  phase(5); seed(0x1300,{0x0a0b,0x0c0d,0x0e0f,0x1a1b});
  u64 saveRequest=requestRead(5,0x1300,openPbus,8);
  u32 saveBusy=(u32)pi.io.dmaBusy, saveInterrupt=(u32)pi.io.interrupt, saveLatch=(u32)pi.io.busLatch;
  nall::serializer saveOnly; saveOnly.setWriting(); queue.serialize(saveOnly);
  u32 saveDelay=dispatchNext();
  facts.push_back({5,saveBusy,saveInterrupt,(u32)pi.io.dmaBusy,(u32)pi.io.interrupt,
    saveDelay,saveLatch,(u32)saveOnly.size()});

  // 6: load is a chronology boundary. The restored reference event remains real,
  // but external request/token identity must be cut and completion left unknown.
  phase(6); seed(0x1400,{0x2a2b,0x2c2d,0x2e2f,0x3a3b});
  u64 restoreRequest=requestRead(6,0x1400,openPbus,8);
  u32 restoreBusy=(u32)pi.io.dmaBusy, restoreInterrupt=(u32)pi.io.interrupt, restoreLatch=(u32)pi.io.busLatch;
  nall::serializer saved; saved.setWriting(); queue.serialize(saved);
  queue.reset(); saved.setReading(); queue.serialize(saved);
  u32 restoreDelay=dispatchNext();
  facts.push_back({6,restoreBusy,restoreInterrupt,(u32)pi.io.dmaBusy,(u32)pi.io.interrupt,
    restoreDelay,restoreLatch,(u32)saved.size()});

  auto ramHash=nall::Hash::SHA256(std::span<const u8>{rdram.ram.data,rdram.ram.size}).digest();
  auto hiddenHash=nall::Hash::SHA256(std::span<const u8>{hidden.data(),hidden.size()}).digest();
  std::printf("{\"facts\":[");
  for(size_t i=0;i<facts.size();i++) {
    const auto& f=facts[i];
    std::printf("%s{\"phase\":%u,\"busy_request\":%u,\"interrupt_request\":%u,\"busy_end\":%u,\"interrupt_end\":%u,\"delay\":%u,\"latch_request\":%u,\"aux\":%u}",
      i ? "," : "",f.phase,f.busyRequest,f.interruptRequest,f.busyEnd,f.interruptEnd,f.delay,f.latchRequest,f.aux);
  }
  std::printf("],\"state\":{\"pc\":%llu,\"count\":%llu,\"exception\":%u,\"ram_sha256\":\"%s\",\"hidden_sha256\":\"%s\"},",
    (unsigned long long)cpu.ipu.pc,(unsigned long long)cpu.effectiveCount(),(u32)cpu.scc.cause.exceptionCode,
    ramHash.data(),hiddenHash.data());
#if PLAID_PI_READ_SENSOR
  if(traced) plaid_print_trace(); else std::printf("\"queue_trace\":[],\"pi_trace\":[],\"rdram_trace\":[]");
  std::printf(",\"requests\":{\"normal\":%llu,\"cancel\":%llu,\"reject\":%llu,\"save\":%llu,\"restore\":%llu}}\n",
    (unsigned long long)normalRequest,(unsigned long long)cancelRequest,(unsigned long long)rejectRequest,
    (unsigned long long)saveRequest,(unsigned long long)restoreRequest);
  nall::plaidQueueObserver=nullptr; plaidPiDmaObserver=nullptr; plaidRdramScalarObserver=nullptr;
#else
  std::printf("\"queue_trace\":[],\"pi_trace\":[],\"rdram_trace\":[],\"requests\":{\"normal\":0,\"cancel\":0,\"reject\":0,\"save\":0,\"restore\":0}}\n");
#endif
  ares::Nintendo64::system.unload();
  return 0;
}
