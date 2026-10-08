/* SPDX-License-Identifier: ISC
 * Original guest CACHE tag/invalidation counterexample for fill-only lineage.
 */
#ifndef PLAID_CACHE_FILL_SENSOR
#define PLAID_CACHE_FILL_SENSOR 1
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <cstdlib>
#include <nall/hash/sha256.hpp>
#if PLAID_CACHE_FILL_SENSOR
#include "../012-ares-cache-fill/observer.hpp"
#endif

struct Sample {
  u64 pc, lastFill;
  u32 word, physical, tag;
  bool cached, fillMatchesTag;
};
struct TagObserver : Headless {
  std::vector<Sample> samples;
  auto log(Node::Debugger::Tracer::Tracer node,string_view) -> void override {
    if(node != cpu.debugger.tracer.instruction) return;
    Sample sample{};
    sample.pc = cpu.ipu.pc; sample.word = cpu.disassembler.fetchedWord();
    sample.physical = plaidFetchAccess.physical; sample.cached = plaidFetchAccess.cached;
    if(sample.cached) {
      const auto& line = cpu.icache.line(sample.pc);
      if(!line.hit(sample.physical) || line.words[sample.physical >> 2 & 7] != sample.word) std::abort();
      sample.tag = line.tagKey;
      #if PLAID_CACHE_FILL_SENSOR
      sample.lastFill = lastCacheFill[sample.pc >> 5 & 0x1ff];
      if(!sample.lastFill) std::abort();
      sample.fillMatchesTag = (cacheFills[sample.lastFill-1].physical & ~0xfff) == (line.tagKey & ~0xfff);
      #endif
    }
    samples.push_back(sample);
  }
};

int main(int argc,char** argv) {
  if(argc != 2 || (strcmp(argv[1],"plain") && strcmp(argv[1],"traced"))) return 2;
  bool traced = !strcmp(argv[1],"traced");
  TagObserver frontend; platform = &frontend;
  frontend.cartPak->setAttribute("title","Plaid CACHE tag fixture");
  frontend.cartPak->setAttribute("region","NTSC");
  frontend.cartPak->setAttribute("cic","CIC-NUS-6102");
  frontend.cartPak->append("program.rom",8192);
  Node::System root;
  if(!load(root,"[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Deterministic Entropy","true"); option("Recompiler","false");
  cartridgeSlot.port->allocate(); cartridgeSlot.port->connect();
  ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;
  #if PLAID_CACHE_FILL_SENSOR
  plaidCacheFillObserver = traced ? cache_fill_observer : nullptr;
  #endif
  std::vector<u8> hidden(rdram.ram.size/2); rdram.hidden.data = hidden.data();
  rdram.mapIdentity = 1;
  for(auto& reg : cpu.ipu.r) reg.u64 = 0;
  cpu.scc.status.errorLevel = cpu.scc.status.exceptionLevel = 0;
  cpu.context.setMode();
  cpu.debugger.tracer.instruction->setDepth(0);
  cpu.debugger.tracer.instruction->setMask(false);
  cpu.debugger.tracer.instruction->setEnabled(traced);
  auto put = [](u32 pa,u32 word) { rdram.ram.write<Word>(pa,word,RBusDevice::ARES_DEBUGGER); };
  put(0,0x24100001); put(0x4000,0x24100009);
  put(0x2000,0xbd080000); // CACHE index store tag, 0(t0)
  put(0x2004,0xbd000000); // CACHE index invalidate, 0(t0)
  put(0x2008,0xbd080000); // CACHE index store tag, 0(t0)
  std::vector<u32> postTags;
  std::vector<u64> postFillCounts;
  auto step = [&](u64 pc,u64 expected) {
    cpu.pipeline.setPc(pc);
    if(cpu.instruction()) cpu.synchronize();
    postTags.push_back(cpu.icache.line(0).tagKey);
    #if PLAID_CACHE_FILL_SENSOR
    postFillCounts.push_back(cacheFills.size());
    #endif
    return cpu.ipu.r[16].u64 == expected && cpu.scc.cause.exceptionCode == 0;
  };
  if(!step(0xffffffff80000000ull,1)) return 5;
  cpu.ipu.r[8].u64 = 0xffffffff80004000ull;
  cpu.scc.tagLo.setPhysicalAddress(0x4000); cpu.scc.tagLo.setPrimaryCacheState(2);
  if(!step(0xffffffffa0002000ull,1)) return 6;
  // Retagging changes the hit address without reading the new RAM page.
  if(!step(0xffffffff80004000ull,1)) return 7;
  if(!step(0xffffffffa0002004ull,1)) return 8;
  if(!step(0xffffffff80004000ull,9)) return 9;
  cpu.ipu.r[8].u64 = 0xffffffff80000000ull;
  cpu.scc.tagLo.setPhysicalAddress(0); cpu.scc.tagLo.setPrimaryCacheState(2);
  if(!step(0xffffffffa0002008ull,9)) return 10;
  if(!step(0xffffffff80000000ull,9)) return 11;

  std::printf("{\"events\":[");
  for(size_t i=0;i<frontend.samples.size();i++) {
    const auto& s = frontend.samples[i];
    std::printf("%s{\"pc\":%llu,\"word\":%u,\"physical\":%u,\"cached\":%s",
      i ? "," : "",(unsigned long long)s.pc,s.word,s.physical,s.cached ? "true" : "false");
    if(s.cached) std::printf(",\"tag_key\":%u,\"last_fill_event\":%llu,\"fill_matches_tag\":%s",
      s.tag,(unsigned long long)s.lastFill,s.fillMatchesTag ? "true" : "false");
    std::printf("}");
  }
  std::printf("]");
  #if PLAID_CACHE_FILL_SENSOR
  print_cache_fills();
  #else
  std::printf(",\"fills\":[]");
  #endif
  std::printf(",\"post_tags\":[");
  for(size_t i=0;i<postTags.size();i++) std::printf("%s%u",i ? "," : "",postTags[i]);
  std::printf("],\"post_fill_counts\":[");
  for(size_t i=0;i<postFillCounts.size();i++) std::printf("%s%llu",i ? "," : "",(unsigned long long)postFillCounts[i]);
  std::printf("],\"state\":{\"pc\":%llu,\"regs\":[",(unsigned long long)cpu.ipu.pc);
  for(u32 i=0;i<32;i++) std::printf("%s%lld",i ? "," : "",(long long)(int64_t)cpu.ipu.r[i].u64);
  auto ramHash = nall::Hash::SHA256(std::span<const u8>{rdram.ram.data,rdram.ram.size}).digest();
  std::vector<u8> cacheBytes;
  auto append = [&](u32 value,u32 width) {
    for(u32 i=width;i>0;i--) cacheBytes.push_back(value >> (8*(i-1)));
  };
  for(const auto& line : cpu.icache.lines) {
    append(line.tagKey,4); append(line.index,2);
    for(u32 word : line.words) append(word,4);
  }
  auto cacheHash = nall::Hash::SHA256(std::span<const u8>{cacheBytes.data(),cacheBytes.size()}).digest();
  std::printf("],\"hi\":%lld,\"lo\":%lld,\"count\":%llu,\"exception\":%u,\"epc\":%llu,\"status\":%u,\"configuration\":%u,\"cache_hits\":%lld,\"cache_misses\":%lld,\"ram_sha256\":\"%s\",\"icache_sha256\":\"%s\"}}\n",
    (long long)(int64_t)cpu.ipu.hi.u64,(long long)(int64_t)cpu.ipu.lo.u64,
    (unsigned long long)cpu.effectiveCount(),(u32)cpu.scc.cause.exceptionCode,
    (unsigned long long)cpu.scc.epc,(u32)cpu.getControlRegister(12),(u32)cpu.getControlRegister(16),
    (long long)cpu.profile.icacheHits,(long long)cpu.profile.icacheMisses,ramHash.data(),cacheHash.data());
  ares::Nintendo64::system.unload();
  return 0;
}
