/* SPDX-License-Identifier: ISC
 * Original component fixture for buffered PI ROM-to-RAM byte provenance.
 */
#ifndef PLAID_PI_COPY_SENSOR
#define PLAID_PI_COPY_SENSOR 1
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <cstdlib>
#include <nall/hash/sha256.hpp>
#if PLAID_PI_COPY_SENSOR
#include "observer.hpp"
#endif

int main(int argc,char** argv) {
  if(argc != 2 || (strcmp(argv[1],"plain") && strcmp(argv[1],"traced"))) return 2;
  bool traced = !strcmp(argv[1],"traced");
  Headless frontend; platform = &frontend;
  std::vector<u8> rom(16384);
  rom[0]=0x80; rom[1]=0x37; rom[2]=0x12; rom[3]=0x40;
  for(u32 i=0;i<256;i++) {
    rom[0x1000+i] = rom[0x2000+i] = (i*7+3)&255;
    rom[0x3000+i] = (i*3+128)&255;
  }
  frontend.cartPak->setAttribute("title","Plaid buffered PI copy fixture");
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
  #if PLAID_PI_COPY_SENSOR
  PiCopyRom wrapper;
  pi.detach(cartridge.romDevice); pi.attach(wrapper,0);
  #endif
  struct Case { u32 source,destination,length; };
  const Case cases[] = {
    {0x10001000,0x1000,16},{0x10002000,0x1000,16},{0x10003000,0x1000,16},
    {0x10001000,0x1102,16},{0x10001000,0x1200,15},{0x10001000,0x17fe,20},
    {0x10001000,8388608,8},{0x1ff00000,0x1300,8},
  };
  struct Checkpoint { u32 dram,pbus,length,busyBefore,busyAfter,interrupt; std::vector<u32> bytes; };
  std::vector<Checkpoint> checkpoints;
  for(u32 index=0;index<8;index++) {
    const auto& c = cases[index];
    pi.io.dramAddress = c.destination; pi.io.pbusAddress = c.source;
    pi.io.writeLength = c.length-1; pi.io.dmaBusy=1; pi.io.interrupt=0;
    #if PLAID_PI_COPY_SENSOR
    piCopyPhase = index+1; piCopyEnabled = traced;
    plaidPiDmaObserver = traced ? pi_copy_event : nullptr;
    plaidRdramScalarObserver = traced ? pi_copy_scalar : nullptr;
    #endif
    pi.dmaWrite();
    Checkpoint checkpoint{(u32)pi.io.dramAddress,(u32)pi.io.pbusAddress,(u32)pi.io.writeLength,(u32)pi.io.dmaBusy,0,0,{}};
    // Fixture invokes the real completion component directly; no scheduler/
    // hardware DMA duration or guest MMIO setup is claimed by this experiment.
    pi.dmaFinished();
    checkpoint.busyAfter = pi.io.dmaBusy; checkpoint.interrupt = pi.io.interrupt;
    #if PLAID_PI_COPY_SENSOR
    piCopyEnabled = false; plaidPiDmaObserver = nullptr; plaidRdramScalarObserver = nullptr;
    #endif
    if(c.destination < rdram.ram.size)
      for(u32 i=0;i<32;i++) checkpoint.bytes.push_back(rdram.ram.read<Byte>((c.destination&~7)+i,RBusDevice::ARES_DEBUGGER));
    checkpoints.push_back(checkpoint);
  }
  std::printf("{");
  #if PLAID_PI_COPY_SENSOR
  print_pi_copy_events();
  #else
  std::printf("\"events\":[]");
  #endif
  std::printf(",\"checkpoints\":[");
  for(size_t i=0;i<checkpoints.size();i++) {
    const auto& c = checkpoints[i];
    std::printf("%s{\"phase\":%u,\"dram\":%u,\"pbus\":%u,\"length_register\":%u,\"busy_before_finish\":%u,\"busy_after_finish\":%u,\"interrupt\":%u,\"bytes\":[",
      i ? "," : "",(u32)i+1,c.dram,c.pbus,c.length,c.busyBefore,c.busyAfter,c.interrupt);
    for(size_t j=0;j<c.bytes.size();j++) std::printf("%s%u",j ? "," : "",c.bytes[j]);
    std::printf("]}");
  }
  auto ramHash = nall::Hash::SHA256(std::span<const u8>{rdram.ram.data,rdram.ram.size}).digest();
  auto hiddenHash = nall::Hash::SHA256(std::span<const u8>{hidden.data(),hidden.size()}).digest();
  auto romHash = nall::Hash::SHA256(std::span<const u8>{rom.data(),rom.size()}).digest();
  std::printf("],\"state\":{\"pc\":%llu,\"count\":%llu,\"exception\":%u,\"rom_sha256\":\"%s\",\"ram_sha256\":\"%s\",\"hidden_sha256\":\"%s\",\"regs\":[",
    (unsigned long long)cpu.ipu.pc,(unsigned long long)cpu.effectiveCount(),(u32)cpu.scc.cause.exceptionCode,romHash.data(),ramHash.data(),hiddenHash.data());
  for(u32 i=0;i<32;i++) std::printf("%s%llu",i ? "," : "",(unsigned long long)cpu.ipu.r[i].u64);
  std::printf("]}}\n");
  ares::Nintendo64::system.unload();
  return 0;
}
