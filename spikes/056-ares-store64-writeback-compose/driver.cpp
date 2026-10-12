/* SPDX-License-Identifier: ISC
 * Actual decoded cached SD/SDL/SDR -> primitive subwrites -> backing export.
 */
#ifndef PLAID_DCACHE_LINEAGE_SENSOR
#define PLAID_DCACHE_LINEAGE_SENSOR 1
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <cstdlib>
#include <nall/hash/sha256.hpp>
#if PLAID_DCACHE_LINEAGE_SENSOR
#include "observer.hpp"
#endif

static void observers(bool enabled) {
#if PLAID_DCACHE_LINEAGE_SENSOR
  plaidDcacheObserver = enabled ? plaid_dcache_observer : nullptr;
  plaidRdramBurstObserver = enabled ? plaid_lineage_burst_observer : nullptr;
#else
  (void)enabled;
#endif
}
static void phase(u32 value) {
#if PLAID_DCACHE_LINEAGE_SENSOR
  plaidLineagePhase = value;
#else
  (void)value;
#endif
}
static void append_be(std::vector<u8>& result, u64 value, u32 width) {
  for(u32 i=0;i<width;i++) result.push_back(value >> ((width-1-i)*8));
}
static std::vector<u8> resident() {
  std::vector<u8> result;
  for(auto word : cpu.dcache.line(0xffffffff80002000ull).words) append_be(result,word,4);
  return result;
}
static std::vector<u8> backing() {
  std::vector<u8> result;
  for(u32 i=0;i<16;i++) result.push_back(rdram.ram.read<Byte>(0x2000+i,RBusDevice::ARES_DEBUGGER));
  return result;
}
static void bytes(const char* name,const std::vector<u8>& data) {
  std::printf("\"%s\":[",name);
  for(size_t i=0;i<data.size();i++) std::printf("%s%u",i?",":"",data[i]);
  std::printf("]");
}
struct Step {
  u32 phase,word,exception;
  u64 pc,next;
  bool little;
  u64 before[32],after[32];
};
static Step execute(u32 number,u32 word,u64 pc) {
  phase(number);
  // Duplicate instruction words account for the observed reversed Word address
  // under little-endian context without changing the data-store instruction.
  u32 pa=(u32)pc&0x1fffffff;
  rdram.ram.write<Word>(pa,word,RBusDevice::ARES_DEBUGGER);
  rdram.ram.write<Word>(pa+4,word,RBusDevice::ARES_DEBUGGER);
  cpu.pipeline.setPc(pc);
  Step result{number,word,0,pc,0,cpu.context.littleEndian(),{}, {}};
  for(u32 i=0;i<32;i++) result.before[i]=cpu.ipu.r[i].u64;
  if(cpu.instruction()) cpu.synchronize();
  result.next=cpu.ipu.pc;result.exception=cpu.scc.cause.exceptionCode;
  for(u32 i=0;i<32;i++) result.after[i]=cpu.ipu.r[i].u64;
  return result;
}
static void print_steps(const std::vector<Step>& steps) {
  std::printf("\"steps\":[");
  for(size_t n=0;n<steps.size();n++) {
    const auto& s=steps[n];
    std::printf("%s{\"phase\":%u,\"word\":%u,\"pc\":%llu,\"next\":%llu,\"little\":%s,\"exception\":%u,\"before\":[",
      n?",":"",s.phase,s.word,(unsigned long long)s.pc,(unsigned long long)s.next,s.little?"true":"false",s.exception);
    for(u32 i=0;i<32;i++) std::printf("%s%llu",i?",":"",(unsigned long long)s.before[i]);
    std::printf("],\"after\":[");
    for(u32 i=0;i<32;i++) std::printf("%s%llu",i?",":"",(unsigned long long)s.after[i]);
    std::printf("]}");
  }
  std::printf("]");
}
int main(int argc,char** argv) {
  if(argc!=5) return 2;
  bool traced=!std::strcmp(argv[1],"traced");
  const char* name=argv[2];bool little=!std::strcmp(argv[3],"little");
  u32 offset=std::strtoul(argv[4],nullptr,10);
  u32 opcode=!std::strcmp(name,"SD")?0x3f:!std::strcmp(name,"SDL")?0x2c:!std::strcmp(name,"SDR")?0x2d:0;
  if(!opcode||offset>7) return 3;
  Headless frontend;platform=&frontend;
  frontend.cartPak->setAttribute("title","Plaid cached store64 composition fixture");
  frontend.cartPak->setAttribute("region","NTSC");frontend.cartPak->setAttribute("cic","CIC-NUS-6102");
  frontend.cartPak->append("program.rom",8192);
  Node::System root;if(!load(root,"[Nintendo] Nintendo 64 (NTSC)")) return 4;
  option("Expansion Pak","true");option("Deterministic Entropy","true");option("Recompiler","false");
  cartridgeSlot.port->allocate();cartridgeSlot.port->connect();ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled||rsp.recompiler.enabled) return 5;
  std::vector<u8> hidden(rdram.ram.size/2);rdram.hidden.data=hidden.data();rdram.mapIdentity=1;
  for(auto& r:cpu.ipu.r) r.u64=0;
  cpu.scc.status.errorLevel=cpu.scc.status.exceptionLevel=0;cpu.scc.cause.exceptionCode=0;
  cpu.context.setMode();cpu.context.endian=little?CPU::Context::Little:CPU::Context::Big;
  cpu.dcache.power(false);
  for(u32 i=0;i<16;i++) rdram.ram.write<Byte>(0x2000+i,0xa0+i,RBusDevice::ARES_DEBUGGER);
  cpu.ipu.r[1].u64=0xffffffff80002000ull;cpu.ipu.r[2].u64=0x1122334455667788ull;
  auto initial=backing();observers(traced);phase(0);
  if(!cpu.read<Word>(cpu.ipu.r[1].u64)) return 6;
  std::vector<Step> steps;
  u32 word=(opcode<<26)|(1<<21)|(2<<16)|offset;
  steps.push_back(execute(1,word,0xffffffffa0001000ull));
  auto first=resident(),stale=backing();
  for(u32 i=0;i<32;i++) if(steps.back().before[i]!=steps.back().after[i]) return 7;
  if(!steps.back().exception) {
    steps.push_back(execute(2,word,0xffffffffa0001000ull));
    for(u32 i=0;i<32;i++) if(steps.back().before[i]!=steps.back().after[i]) return 8;
    if(steps.back().exception||resident()!=first||backing()!=stale) return 9;
    steps.push_back(execute(3,(0x2fu<<26)|(1<<21)|(0x19u<<16),0xffffffffa0001040ull));
    if(steps.back().exception||backing()!=first||cpu.dcache.line(cpu.ipu.r[1].u64).dirty) return 10;
  } else if(steps.back().exception!=5||first!=initial||stale!=initial) return 11;
  observers(false);
  auto final=backing();
  std::vector<u8> cache;
  for(const auto& line:cpu.dcache.lines) {
    append_be(cache,line.tagKey,4);append_be(cache,line.dirty,2);append_be(cache,line.index,2);
    append_be(cache,line.fillPc,8);append_be(cache,line.dirtyPc,8);
    for(u32 value:line.words) append_be(cache,value,4);
  }
  auto ram=nall::Hash::SHA256(std::span<const u8>{rdram.ram.data,rdram.ram.size}).digest();
  auto auxiliary=nall::Hash::SHA256(std::span<const u8>{hidden.data(),hidden.size()}).digest();
  auto cacheHash=nall::Hash::SHA256(std::span<const u8>{cache.data(),cache.size()}).digest();
  std::printf("{");print_steps(steps);std::printf(",");bytes("initial",initial);std::printf(",");
  bytes("resident_after_first",first);std::printf(",");bytes("backing_before_export",stale);std::printf(",");bytes("final_backing",final);
  std::printf(",\"state\":{\"pc\":%llu,\"count\":%llu,\"exception\":%u,\"hi\":%llu,\"lo\":%llu,\"ram_sha256\":\"%s\",\"hidden_sha256\":\"%s\",\"dcache_sha256\":\"%s\"},",
    (unsigned long long)cpu.ipu.pc,(unsigned long long)cpu.effectiveCount(),(u32)cpu.scc.cause.exceptionCode,
    (unsigned long long)cpu.ipu.hi.u64,(unsigned long long)cpu.ipu.lo.u64,ram.data(),auxiliary.data(),cacheHash.data());
#if PLAID_DCACHE_LINEAGE_SENSOR
  plaid_print_lineage_events();
#else
  std::printf("\"dcache_events\":[],\"burst_events\":[]");
#endif
  std::printf("}\n");ares::Nintendo64::system.unload();return 0;
}
