/* SPDX-License-Identifier: ISC
 * Actual pinned-ares component fixture for PI request -> queue token -> CPU dispatch.
 */
#ifndef PLAID_PI_QUEUE_SENSOR
#define PLAID_PI_QUEUE_SENSOR 1
#endif
#define main plaid_capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>
#if PLAID_PI_QUEUE_SENSOR
#include "observer.hpp"
#endif

struct Fact {
  u32 phase, busyRequest, interruptRequest, busyEnd, interruptEnd, delay, byte0, aux;
};

int main(int argc,char** argv) {
  if(argc != 2 || (strcmp(argv[1],"plain") && strcmp(argv[1],"traced"))) return 2;
  bool traced = !strcmp(argv[1],"traced");
  Headless frontend; platform = &frontend;
  std::vector<u8> rom(16384);
  rom[0]=0x80; rom[1]=0x37; rom[2]=0x12; rom[3]=0x40;
  for(u32 i=0;i<256;i++) rom[0x1000+i]=(0xa0+i)&255;
  frontend.cartPak->setAttribute("title","Plaid PI queue dispatch fixture");
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

#if PLAID_PI_QUEUE_SENSOR
  plaidQueueOwner=&queue;
  nall::plaidQueueObserver=traced ? plaid_queue_event : nullptr;
  plaidPiDmaObserver=traced ? plaid_pi_event : nullptr;
#endif

  std::vector<Fact> facts;
  auto phase = [&](u32 id) {
#if PLAID_PI_QUEUE_SENSOR
    if(traced) plaidPhase=id;
#endif
    cpu.clock=0;
    queue.reset();
    pi.io.dmaBusy=0; pi.io.ioBusy=0; pi.io.error=0; pi.io.interrupt=0;
  };
  auto clearBytes = [&](u32 address) {
    for(u32 i=0;i<32;i++) rdram.ram.write<Byte>(address+i,0xcc,RBusDevice::ARES_DEBUGGER);
  };
  auto requestWrite = [&](u32 id,u32 destination,u32 source,u32 length) -> u64 {
    pi.ioWrite(0x00,destination);
    pi.ioWrite(0x04,source);
    u64 request=0;
#if PLAID_PI_QUEUE_SENSOR
    if(traced) request=plaid_begin_request(id);
#endif
    pi.ioWrite(0x0c,length-1);
#if PLAID_PI_QUEUE_SENSOR
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

  // 1: normal actual PI write request. The copy occurs inside ioWrite/dmaWrite;
  // the queued event later enters CPU::synchronize and invokes dmaFinished.
  phase(1); clearBytes(0x1000);
  u64 normalRequest=requestWrite(1,0x1000,0x10001000,8);
  u32 normalBusy=(u32)pi.io.dmaBusy, normalInterrupt=(u32)pi.io.interrupt;
  u32 normalByte=rdram.ram.read<Byte>(0x1000,RBusDevice::ARES_DEBUGGER);
  u32 normalDelay=dispatchNext();
  facts.push_back({1,normalBusy,normalInterrupt,(u32)pi.io.dmaBusy,(u32)pi.io.interrupt,normalDelay,normalByte,0});

  // 2: PI_STATUS reset cancels the scheduled token. Draining the invalid heap
  // entry must not dispatch dmaFinished.
  phase(2); clearBytes(0x1100);
  u64 cancelRequest=requestWrite(2,0x1100,0x10001020,8);
  u32 cancelBusy=(u32)pi.io.dmaBusy, cancelInterrupt=(u32)pi.io.interrupt;
  s32 cancelDelaySigned=queue.timeToNextEvent(); assert(cancelDelaySigned>=0);
  pi.ioWrite(0x10,1);
  cpu.step((u32)cancelDelaySigned); cpu.synchronize();
  facts.push_back({2,cancelBusy,cancelInterrupt,(u32)pi.io.dmaBusy,(u32)pi.io.interrupt,
    (u32)cancelDelaySigned,rdram.ram.read<Byte>(0x1100,RBusDevice::ARES_DEBUGGER),0});

  // 3: fill all physical queue slots, then issue an actual PI write request.
  // CPU::queueInsert silently rejects, while PI still performs dmaWrite now.
  phase(3); clearBytes(0x1200);
  u32 filled=0; for(u32 i=0;i<512;i++) if(queue.insert(Queue::GDB_Poll,100000)) filled++;
  assert(filled==512);
  u64 rejectRequest=requestWrite(3,0x1200,0x10001040,8);
  facts.push_back({3,(u32)pi.io.dmaBusy,(u32)pi.io.interrupt,(u32)pi.io.dmaBusy,(u32)pi.io.interrupt,
    (u32)queue.timeToNextEvent(),rdram.ram.read<Byte>(0x1200,RBusDevice::ARES_DEBUGGER),filled});

  // 4: queue-only adversary. Two indistinguishable PI write event values share
  // one deadline and both traverse the real CPU dispatcher. They are not real
  // requests, so a causal joiner must leave both request identities unbound.
  phase(4);
#if PLAID_PI_QUEUE_SENSOR
  if(traced) plaidPhase=4;
#endif
  assert(queue.insert(Queue::PI_DMA_Write,17));
  assert(queue.insert(Queue::PI_DMA_Write,17));
  pi.io.dmaBusy=1; pi.io.interrupt=0;
  cpu.step(17); cpu.synchronize();
  facts.push_back({4,1,0,(u32)pi.io.dmaBusy,(u32)pi.io.interrupt,17,0,2});

  // 5: a real request is serialized and restored before its due time. The
  // reference queue completes it, but external finite metadata deliberately
  // forgets identity at serialization, so completion must be fail-closed.
  phase(5); clearBytes(0x1300);
  u64 restoreRequest=requestWrite(5,0x1300,0x10001060,8);
  u32 restoreBusy=(u32)pi.io.dmaBusy, restoreInterrupt=(u32)pi.io.interrupt;
  nall::serializer saved; saved.setWriting(); queue.serialize(saved);
  queue.reset(); saved.setReading(); queue.serialize(saved);
  u32 restoreDelay=dispatchNext();
  facts.push_back({5,restoreBusy,restoreInterrupt,(u32)pi.io.dmaBusy,(u32)pi.io.interrupt,
    restoreDelay,rdram.ram.read<Byte>(0x1300,RBusDevice::ARES_DEBUGGER),(u32)saved.size()});

  auto ramHash=nall::Hash::SHA256(std::span<const u8>{rdram.ram.data,rdram.ram.size}).digest();
  auto hiddenHash=nall::Hash::SHA256(std::span<const u8>{hidden.data(),hidden.size()}).digest();
  std::printf("{\"facts\":[");
  for(size_t i=0;i<facts.size();i++) {
    const auto& f=facts[i];
    std::printf("%s{\"phase\":%u,\"busy_request\":%u,\"interrupt_request\":%u,\"busy_end\":%u,\"interrupt_end\":%u,\"delay\":%u,\"byte0\":%u,\"aux\":%u}",
      i ? "," : "",f.phase,f.busyRequest,f.interruptRequest,f.busyEnd,f.interruptEnd,f.delay,f.byte0,f.aux);
  }
  std::printf("],\"state\":{\"pc\":%llu,\"count\":%llu,\"exception\":%u,\"ram_sha256\":\"%s\",\"hidden_sha256\":\"%s\"},",
    (unsigned long long)cpu.ipu.pc,(unsigned long long)cpu.effectiveCount(),(u32)cpu.scc.cause.exceptionCode,
    ramHash.data(),hiddenHash.data());
#if PLAID_PI_QUEUE_SENSOR
  if(traced) plaid_print_trace(); else std::printf("\"queue_trace\":[],\"pi_trace\":[]");
  std::printf(",\"requests\":{\"normal\":%llu,\"cancel\":%llu,\"reject\":%llu,\"restore\":%llu}}\n",
    (unsigned long long)normalRequest,(unsigned long long)cancelRequest,(unsigned long long)rejectRequest,(unsigned long long)restoreRequest);
  nall::plaidQueueObserver=nullptr; plaidPiDmaObserver=nullptr;
#else
  std::printf("\"queue_trace\":[],\"pi_trace\":[],\"requests\":{\"normal\":0,\"cancel\":0,\"reject\":0,\"restore\":0}}\n");
#endif
  ares::Nintendo64::system.unload();
  return 0;
}
