/* SPDX-License-Identifier: ISC
 * Original PI/backing/cache chronology component and actual CPU fixture.
 */
#ifndef PLAID_JOINED_SENSOR
#define PLAID_JOINED_SENSOR 1
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <cstdlib>
#include <string>
#include <nall/hash/sha256.hpp>
#if PLAID_JOINED_SENSOR
#include "observer.hpp"
#endif
struct JoinedFrontend : Headless {
  auto log(Node::Debugger::Tracer::Tracer node,string_view) -> void override {
    #if PLAID_JOINED_SENSOR
    if(node == cpu.debugger.tracer.instruction) joined_fetch();
    #endif
  }
};
int main(int argc,char** argv) {
  if(argc != 2 || (strcmp(argv[1],"plain") && strcmp(argv[1],"traced"))) return 2;
  bool traced=!strcmp(argv[1],"traced");
  JoinedFrontend frontend; platform=&frontend;
  std::vector<u8> rom(16384);
  auto put=[&](u32 offset,u32 word) { for(u32 i=0;i<4;i++) rom[offset+i]=word>>(24-i*8); };
  put(0,0x80371240); put(0x80,0xae090000); put(0x84,(0x2fu<<26)|(16u<<21)|(0x10u<<16));
  put(0x1000,0x34081111); put(0x2000,0x34081111); put(0x3000,0x34083333);
  frontend.cartPak->setAttribute("title","Plaid PI fetch history fixture");
  frontend.cartPak->setAttribute("region","NTSC"); frontend.cartPak->setAttribute("cic","CIC-NUS-6102");
  frontend.cartPak->append("program.rom",std::span<const u8>{rom.data(),rom.size()});
  Node::System root;
  if(!load(root,"[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak","true"); option("Deterministic Entropy","true"); option("Recompiler","false");
  cartridgeSlot.port->allocate(); cartridgeSlot.port->connect(); ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled || rdram.ram.size != 8388608) return 4;
  std::vector<u8> hidden(rdram.ram.size/2); rdram.hidden.data=hidden.data();
  rdram.mapIdentity=1; std::memset(rdram.ram.data,0xcc,rdram.ram.size);
  for(auto& reg:cpu.ipu.r) reg.u64=0;
  cpu.scc.status.errorLevel=cpu.scc.status.exceptionLevel=0; cpu.context.setMode();
  cpu.context.endian=CPU::Context::Endian::Big; cpu.icache.power(false); cpu.dcache.power(false);
  #if PLAID_JOINED_SENSOR
  JoinedRom wrapper; pi.detach(cartridge.romDevice); pi.attach(wrapper,0);
  joinedEnabled=traced;
  plaidPiDmaObserver=traced ? joined_pi : nullptr;
  plaidRdramScalarObserver=traced ? joined_scalar : nullptr;
  plaidRdramBurstObserver=traced ? joined_burst : nullptr;
  plaidCacheFillObserver=traced ? joined_fill : nullptr;
  plaidCpuFetchObserver=traced ? joined_boundary : nullptr;
  plaidCacheOperationObserver=traced ? joined_cache : nullptr;
  #endif
  cpu.debugger.tracer.instruction->setDepth(0); cpu.debugger.tracer.instruction->setMask(false);
  cpu.debugger.tracer.instruction->setEnabled(traced);
  auto stage=[](u32 value) {
    #if PLAID_JOINED_SENSOR
    joinedStage=value;
    #else
    (void)value;
    #endif
  };
  struct Checkpoint { u32 stage; u64 pc,count,t0; u32 tag,words[8],ramWord,busy,interrupt; };
  std::vector<Checkpoint> checkpoints;
  auto step=[&](u32 phase,u64 pc,u32 expected) {
    stage(phase); cpu.pipeline.setPc(pc);
    if(cpu.instruction()) cpu.synchronize();
    if(cpu.scc.cause.exceptionCode || cpu.ipu.r[8].u32 != expected) {
      std::fprintf(stderr,"stage=%u pc=%llx exception=%u t0=%x expected=%x\n",phase,
          (unsigned long long)pc,(u32)cpu.scc.cause.exceptionCode,(u32)cpu.ipu.r[8].u32,expected);
      std::abort();
    }
    auto& line=cpu.icache.line(0xffffffff80004000ull);
    // Disable sensors for explicit host checkpoint reads; never use these as origins.
    #if PLAID_JOINED_SENSOR
    joinedEnabled=false;
    #endif
    Checkpoint checkpoint{phase,cpu.ipu.pc,cpu.effectiveCount(),cpu.ipu.r[8].u64,(u32)line.tagKey,{},
        (u32)rdram.ram.read<Word>(0x4000,RBusDevice::ARES_DEBUGGER),(u32)pi.io.dmaBusy,(u32)pi.io.interrupt};
    for(u32 i=0;i<8;i++) checkpoint.words[i]=line.words[i];
    checkpoints.push_back(checkpoint);
    #if PLAID_JOINED_SENSOR
    joinedEnabled=traced;
    #endif
  };
  auto copy=[&](u32 phase,u32 source,u32 length) {
    stage(phase); pi.io.dramAddress=0x4000; pi.io.pbusAddress=0x10000000+source;
    pi.io.writeLength=length-1; pi.io.dmaBusy=1; pi.io.interrupt=0;
    pi.dmaWrite(); pi.dmaFinished();
  };
  copy(1,0x1000,32);
  step(2,0xffffffff80004000ull,0x1111); step(3,0xffffffffa0004000ull,0x1111);
  copy(4,0x2000,32);
  step(5,0xffffffff80004000ull,0x1111); step(6,0xffffffffa0004000ull,0x1111);
  copy(7,0x3000,32);
  step(8,0xffffffff80004000ull,0x1111); step(9,0xffffffffa0004000ull,0x3333);
  cpu.ipu.r[9].u64=0x34084444; cpu.ipu.r[16].u64=0xffffffffa0004000ull;
  step(10,0xffffffffb0000080ull,0x3333); // Actual SW replaces backing, resident line stays.
  step(11,0xffffffff80004000ull,0x1111); step(12,0xffffffffa0004000ull,0x4444);
  cpu.ipu.r[16].u64=0xffffffff80004000ull;
  step(13,0xffffffffb0000084ull,0x4444); // Actual CACHE hit invalidate.
  step(14,0xffffffff80004000ull,0x4444); step(15,0xffffffffa0004004ull,0x4444);
  copy(16,0x1000,3); // Partial word: low byte remains from SW, no contiguous ROM word.
  step(17,0xffffffffb0000084ull,0x4444);
  step(18,0xffffffff80004000ull,0x1144); step(19,0xffffffffa0004000ull,0x1144);
  step(20,0xffffffffa0004004ull,0x1144);
  #if PLAID_JOINED_SENSOR
  joinedEnabled=false;
  #endif
  std::printf("{");
  #if PLAID_JOINED_SENSOR
  joined_print();
  #else
  std::printf("\"events\":[]");
  #endif
  std::printf(",\"checkpoints\":[");
  for(size_t i=0;i<checkpoints.size();i++) {
    auto& c=checkpoints[i];
    std::printf("%s{\"stage\":%u,\"pc\":%llu,\"count\":%llu,\"t0\":%llu,\"tag\":%u,\"ram_word\":%u,\"busy\":%u,\"interrupt\":%u,\"words\":[",
        i ? "," : "",c.stage,(unsigned long long)c.pc,(unsigned long long)c.count,(unsigned long long)c.t0,c.tag,c.ramWord,c.busy,c.interrupt);
    for(u32 j=0;j<8;j++) std::printf("%s%u",j ? "," : "",c.words[j]); std::printf("]}");
  }
  auto ramHash=nall::Hash::SHA256(std::span<const u8>{rdram.ram.data,rdram.ram.size}).digest();
  auto hiddenHash=nall::Hash::SHA256(std::span<const u8>{hidden.data(),hidden.size()}).digest();
  auto romHash=nall::Hash::SHA256(std::span<const u8>{rom.data(),rom.size()}).digest();
  std::vector<u8> cacheBytes;
  for(auto& line:cpu.icache.lines) {
    for(u32 word:line.words) for(u32 i=0;i<4;i++) cacheBytes.push_back(word>>(24-8*i));
    for(u32 i=0;i<4;i++) cacheBytes.push_back((u32)line.tagKey>>(24-8*i));
  }
  auto cacheHash=nall::Hash::SHA256(std::span<const u8>{cacheBytes.data(),cacheBytes.size()}).digest();
  std::printf("],\"state\":{\"pc\":%llu,\"count\":%llu,\"exception\":%u,\"hi\":%llu,\"lo\":%llu,\"rom_sha256\":\"%s\",\"ram_sha256\":\"%s\",\"hidden_sha256\":\"%s\",\"cache_sha256\":\"%s\",\"regs\":[",
      (unsigned long long)cpu.ipu.pc,(unsigned long long)cpu.effectiveCount(),(u32)cpu.scc.cause.exceptionCode,
      (unsigned long long)cpu.ipu.hi.u64,(unsigned long long)cpu.ipu.lo.u64,romHash.data(),ramHash.data(),hiddenHash.data(),cacheHash.data());
  for(u32 i=0;i<32;i++) std::printf("%s%llu",i ? "," : "",(unsigned long long)cpu.ipu.r[i].u64);
  std::printf("]}}\n"); ares::Nintendo64::system.unload(); return 0;
}
