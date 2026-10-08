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
#if defined(PLAID_ORDERED_HISTORY_CONTEXT)
#include "../018-ares-ordered-history/history.hpp"
#endif
#if PLAID_CACHE_FILL_SENSOR
#include "../012-ares-cache-fill/observer.hpp"
#endif
#if defined(PLAID_CACHE_OPERATION_CONTEXT)
#include "../014-ares-cache-operations/observer.hpp"
#endif
#if defined(PLAID_RDRAM_BURST_CONTEXT)
#include "../016-ares-rdram-bursts/observer.hpp"
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
    #if defined(PLAID_ORDERED_HISTORY_CONTEXT)
    history_event("fetch",samples.size());
    #endif
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
  #if defined(PLAID_ORDERED_HISTORY_CONTEXT)
  historyEnabled = traced;
  #endif
  #if PLAID_CACHE_FILL_SENSOR
  plaidCacheFillObserver = traced ? cache_fill_observer : nullptr;
  #endif
  #if defined(PLAID_CACHE_OPERATION_CONTEXT)
  plaidCacheOperationObserver = traced ? cache_operation_observer : nullptr;
  #endif
  #if defined(PLAID_RDRAM_BURST_CONTEXT)
  plaidRdramBurstObserver = traced ? rdram_burst_observer : nullptr;
  #endif
  std::vector<u8> hidden(rdram.ram.size/2); rdram.hidden.data = hidden.data();
  rdram.mapIdentity = 1;
  #if defined(PLAID_RDRAM_BURST_CONTEXT)
  if(traced) {
    u32 outOfBounds[8]; for(auto& word : outOfBounds) word = 0xdeadbeef;
    rdram.ram.readBurst<ICache>(rdram.ram.size,outOfBounds,RBusDevice::ARES_DEBUGGER);
    for(u32 word : outOfBounds) if(word != 0) return 22;
    rdram.ram.writeBurst<ICache>(rdram.ram.size,outOfBounds,RBusDevice::ARES_DEBUGGER);
    if(!rdramBursts.empty()) return 23; // Neither attempt supplies a valid backing witness.
  }
  #endif
  for(auto& reg : cpu.ipu.r) reg.u64 = 0;
  cpu.scc.status.errorLevel = cpu.scc.status.exceptionLevel = 0;
  cpu.context.setMode();
  cpu.debugger.tracer.instruction->setDepth(0);
  cpu.debugger.tracer.instruction->setMask(false);
  cpu.debugger.tracer.instruction->setEnabled(traced);
  auto put = [](u32 pa,u32 word) {
    rdram.ram.write<Word>(pa,word,RBusDevice::ARES_DEBUGGER);
    #if defined(PLAID_ORDERED_HISTORY_CONTEXT)
    history_fixture_write(pa,word);
    #endif
  };
  put(0,0x24100001); put(0x4000,0x24100009);
  put(0x2000,0xbd080000); // CACHE index store tag, 0(t0)
  put(0x2004,0xbd000000); // CACHE index invalidate, 0(t0)
  put(0x2008,0xbd080000); // CACHE index store tag, 0(t0)
  #if defined(PLAID_CACHE_EXTRA_CASES)
  put(0x200c,0xbd100000); // CACHE hit invalidate, 0(t0)
  put(0x2010,0xbd140000); // CACHE fill, 0(t0)
  put(0x2014,0xbd180000); // CACHE hit writeback, 0(t0)
  #endif
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
  #if defined(PLAID_CACHE_EXTRA_CASES)
  if(!step(0xffffffffa000200cull,9)) return 12; // invalidate hit
  if(!step(0xffffffff80000000ull,1)) return 13; // refill actual RAM
  cpu.ipu.r[8].u64 = 0xffffffff80004000ull;
  if(!step(0xffffffffa000200cull,1)) return 14; // invalidate miss
  if(!step(0xffffffff80000000ull,1)) return 15; // existing line still hits
  if(!step(0xffffffffa0002010ull,1)) return 16; // explicit fill of page 0x4000
  if(!step(0xffffffff80004000ull,9)) return 17;
  put(0x4000,0x24100008); // RAM changes while the resident word remains 9
  if(!step(0xffffffffa0002014ull,9)) return 18; // writeback hit restores RAM to 9
  if(!step(0xffffffff80004000ull,9)) return 19;
  cpu.ipu.r[8].u64 = 0xffffffff80000000ull;
  if(!step(0xffffffffa0002014ull,9)) return 20; // writeback miss has no bus write
  if(!step(0xffffffffa0004000ull,9)) return 21; // actual uncached RAM result
  #endif

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
  #if defined(PLAID_CACHE_OPERATION_CONTEXT)
  print_cache_operations();
  #endif
  #if defined(PLAID_RDRAM_BURST_CONTEXT)
  print_rdram_bursts();
  #endif
  #if defined(PLAID_ORDERED_HISTORY_CONTEXT)
  print_history();
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
  std::printf("],\"hi\":%lld,\"lo\":%lld,\"count\":%llu,\"exception\":%u,\"epc\":%llu,\"status\":%u,\"configuration\":%u,\"cache_hits\":%lld,\"cache_misses\":%lld,\"ram_sha256\":\"%s\",\"icache_sha256\":\"%s\"",
    (long long)(int64_t)cpu.ipu.hi.u64,(long long)(int64_t)cpu.ipu.lo.u64,
    (unsigned long long)cpu.effectiveCount(),(u32)cpu.scc.cause.exceptionCode,
    (unsigned long long)cpu.scc.epc,(u32)cpu.getControlRegister(12),(u32)cpu.getControlRegister(16),
    (long long)cpu.profile.icacheHits,(long long)cpu.profile.icacheMisses,ramHash.data(),cacheHash.data());
  #if defined(PLAID_CACHE_EXTRA_CASES)
  std::printf(",\"cache_writebacks\":%lld",(long long)cpu.profile.icacheWritebacks);
  #endif
  std::printf("}}\n");
  ares::Nintendo64::system.unload();
  return 0;
}
