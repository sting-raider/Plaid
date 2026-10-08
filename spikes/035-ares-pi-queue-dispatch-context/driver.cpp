/* SPDX-License-Identifier: ISC
 * Original PI I/O / CPU synchronize component fixture. No guest MMIO execution.
 */
#ifndef PLAID_QUEUE_COMPONENT_SENSOR
#define PLAID_QUEUE_COMPONENT_SENSOR 1
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <cassert>
#include <nall/hash/sha256.hpp>
#if PLAID_QUEUE_COMPONENT_SENSOR
#include "observer.hpp"
#endif
int main(int argc,char** argv) {
  if(argc!=2) return 2;
  bool traced=!strcmp(argv[1],"traced");
  Headless frontend; platform=&frontend;
  std::vector<u8> rom(16384);
  rom[0]=0x80; rom[1]=0x37; rom[2]=0x12; rom[3]=0x40;
  for(u32 i=0;i<32;i++) rom[0x1000+i]=(i*7+3)&255;
  frontend.cartPak->setAttribute("title","Plaid ares::Nintendo64::queue dispatch component fixture");
  frontend.cartPak->setAttribute("region","NTSC"); frontend.cartPak->setAttribute("cic","CIC-NUS-6102");
  frontend.cartPak->append("program.rom",std::span<const u8>{rom.data(),rom.size()});
  Node::System root; if(!load(root,"[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak","true"); option("Deterministic Entropy","true"); option("Recompiler","false");
  cartridgeSlot.port->allocate(); cartridgeSlot.port->connect(); ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled || rdram.ram.size!=8388608) return 4;
  std::vector<u8> hidden(rdram.ram.size/2); rdram.hidden.data=hidden.data(); rdram.mapIdentity=1;
  std::memset(rdram.ram.data,0xcc,rdram.ram.size);
  #if PLAID_QUEUE_COMPONENT_SENSOR
  queueIdentityOwner=&ares::Nintendo64::queue;
  nall::plaidQueueObserver=traced ? pi_queue_container : nullptr;
  plaidPiIoDmaObserver=traced ? pi_queue_io : nullptr;
  plaidCpuQueueDispatchObserver=traced ? pi_queue_dispatch : nullptr;
  plaidPiDmaObserver=traced ? pi_queue_dma : nullptr;
  plaidRdramScalarObserver=traced ? pi_queue_scalar : nullptr;
  #else
  (void)traced;
  #endif
  struct Checkpoint { u32 phase,busy,interrupt,error,dram,pbus,length,word; u64 count,pc; };
  std::vector<Checkpoint> checkpoints;
  auto record=[&](u32 phase) {
    checkpoints.push_back({phase,(u32)pi.io.dmaBusy,(u32)pi.io.interrupt,(u32)pi.io.error,
      (u32)pi.io.dramAddress,(u32)pi.io.pbusAddress,(u32)pi.io.writeLength,
      (u32)rdram.ram.read<Word>(0x1000,RBusDevice::ARES_DEBUGGER),cpu.effectiveCount(),cpu.ipu.pc});
  };
  auto phase=[&](u32 value) {
    #if PLAID_QUEUE_COMPONENT_SENSOR
    queueIdentityPhase=value;
    #endif
    ares::Nintendo64::queue.reset(); pi.ioWrite(16,3);
  };
  auto write=[&] { pi.ioWrite(0,0x1000); pi.ioWrite(4,0x10001000); pi.ioWrite(12,7); };
  auto synchronize=[&](u32 clocks) {
    // Exercise the real CPU dispatch path. No CPU instructions execute here.
    cpu.Thread::clock=clocks; cpu.synchronize();
  };
  phase(1); write(); record(1);
  auto duration=(u32)ares::Nintendo64::queue.timeToNextEvent(); assert(duration>0 && duration<10000);
  synchronize(duration); record(1);
  phase(2); write(); pi.ioWrite(16,1); record(2);
  pi.ioWrite(0,0x1000); pi.ioWrite(4,0x10001000); pi.ioWrite(8,7);
  duration=(u32)ares::Nintendo64::queue.timeToNextEvent(); assert(duration>0 && duration<10000);
  // A larger finite step drains both canceled/write and new/read deadlines.
  synchronize(1000); record(2);
  phase(3); cpu.queueInsert(Queue::PI_DMA_Write,3); cpu.queueInsert(Queue::PI_DMA_Write,5);
  synchronize(5); record(3);
  phase(4);
  for(u32 i=0;i<512;i++) cpu.queueInsert(Queue::PI_DMA_Write,1);
  pi.ioWrite(16,1); write(); record(4);
  synchronize(1); record(4); assert(pi.io.dmaBusy);
  phase(5); write();
  // Direct invocation has no active CPU dispatch, so completion identity is unknown.
  pi.dmaFinished(); record(5);
  #if PLAID_QUEUE_COMPONENT_SENSOR
  nall::plaidQueueObserver=nullptr; plaidPiIoDmaObserver=nullptr;
  plaidCpuQueueDispatchObserver=nullptr; plaidPiDmaObserver=nullptr; plaidRdramScalarObserver=nullptr;
  #endif
  std::printf("{");
  #if PLAID_QUEUE_COMPONENT_SENSOR
  print_pi_queue();
  #else
  std::printf("\"events\":[]");
  #endif
  std::printf(",\"checkpoints\":[");
  for(size_t i=0;i<checkpoints.size();i++) {
    const auto& c=checkpoints[i];
    std::printf("%s{\"phase\":%u,\"busy\":%u,\"interrupt\":%u,\"error\":%u,\"dram\":%u,\"pbus\":%u,\"length\":%u,\"word\":%u,\"count\":%llu,\"pc\":%llu}",
      i ? "," : "",c.phase,c.busy,c.interrupt,c.error,c.dram,c.pbus,c.length,c.word,
      (unsigned long long)c.count,(unsigned long long)c.pc);
  }
  auto ramHash=nall::Hash::SHA256(std::span<const u8>{rdram.ram.data,rdram.ram.size}).digest();
  auto hiddenHash=nall::Hash::SHA256(std::span<const u8>{hidden.data(),hidden.size()}).digest();
  std::printf("],\"ram_sha256\":\"%s\",\"hidden_sha256\":\"%s\",\"queue_object_bytes\":%zu,\"regs\":[",ramHash.data(),hiddenHash.data(),sizeof(ares::Nintendo64::queue));
  for(u32 i=0;i<32;i++) std::printf("%s%llu",i ? "," : "",(unsigned long long)cpu.ipu.r[i].u64);
  std::printf("],\"hi\":%llu,\"lo\":%llu,\"exception\":%u}\n",
    (unsigned long long)cpu.ipu.hi.u64,(unsigned long long)cpu.ipu.lo.u64,(u32)cpu.scc.cause.exceptionCode);
  ares::Nintendo64::system.unload();
}
