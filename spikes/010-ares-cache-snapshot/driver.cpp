/* SPDX-License-Identifier: ISC
 * Original prologue/cache-state experiment; no guest-memory observer accesses.
 */
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <cstdlib>
#include <nall/hash/sha256.hpp>

struct CacheSample {
  u64 pc;
  u32 word, physical;
  bool cached;
  u32 slot, tagKey, index, words[8];
};

struct CacheObserver : Headless {
  std::vector<CacheSample> samples;
  auto log(Node::Debugger::Tracer::Tracer node, string_view) -> void override {
    if(node != cpu.debugger.tracer.instruction) return;
    CacheSample sample{};
    sample.pc = cpu.ipu.pc;
    sample.word = cpu.disassembler.fetchedWord();
    sample.physical = plaidFetchAccess.physical;
    sample.cached = plaidFetchAccess.cached;
    if(sample.cached) {
      sample.slot = sample.pc >> 5 & 0x1ff;
      const auto& line = cpu.icache.line(sample.pc);
      sample.tagKey = line.tagKey; sample.index = line.index;
      for(u32 i=0;i<8;i++) sample.words[i] = line.words[i];
      // Pure field checks; never call a memory/coherence/translation helper.
      if(!line.hit(sample.physical) || sample.words[sample.physical >> 2 & 7] != sample.word)
        std::abort();
    }
    samples.push_back(sample);
  }
};

static void print_line(u32 tag, u32 index, const u32* words) {
  std::printf("{\"tag_key\":%u,\"index\":%u,\"words\":[",tag,index);
  for(u32 i=0;i<8;i++) std::printf("%s%u",i ? "," : "",words[i]);
  std::printf("]}");
}

int main(int argc, char** argv) {
  if(argc != 2 || (strcmp(argv[1],"plain") && strcmp(argv[1],"traced"))) return 2;
  bool traced = !strcmp(argv[1],"traced");
  CacheObserver frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title","Plaid cache snapshot fixture");
  frontend.cartPak->setAttribute("region","NTSC");
  frontend.cartPak->setAttribute("cic","CIC-NUS-6102");
  frontend.cartPak->append("program.rom",8192);
  Node::System root;
  if(!load(root,"[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Deterministic Entropy","true"); option("Recompiler","false");
  cartridgeSlot.port->allocate(); cartridgeSlot.port->connect();
  ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;
  std::vector<u8> hidden(rdram.ram.size / 2); rdram.hidden.data = hidden.data();
  rdram.mapIdentity = 1;
  for(auto& reg : cpu.ipu.r) reg.u64 = 0;
  cpu.scc.status.errorLevel = cpu.scc.status.exceptionLevel = 0;
  cpu.context.setMode();
  cpu.debugger.tracer.instruction->setDepth(0);
  cpu.debugger.tracer.instruction->setMask(false);
  cpu.debugger.tracer.instruction->setEnabled(traced);
  auto put = [](u32 pa,u32 value) { rdram.ram.write<Word>(pa,value,RBusDevice::ARES_DEBUGGER); };
  auto step = [](u64 pc,u64 expected) {
    cpu.pipeline.setPc(pc);
    if(cpu.instruction()) cpu.synchronize();
    return cpu.ipu.r[16].u64 == expected && cpu.scc.cause.exceptionCode == 0;
  };
  put(0,0x24100001);
  if(!step(0xffffffff80000000ull,1)) return 5;
  put(0,0x24100002);
  if(!step(0xffffffff80000000ull,1)) return 6;
  if(!step(0xffffffffa0000000ull,2)) return 7;
  cpu.icache.line(0xffffffff80000000ull).setValid(false);
  if(!step(0xffffffff80000000ull,2)) return 8;
  put(0x4000,0x24100003);
  if(!step(0xffffffff80004000ull,3)) return 9;
  if(!step(0xffffffff80000000ull,2)) return 10;
  auto& entry = cpu.tlb.entry[0]; entry = {};
  entry.global[0] = entry.global[1] = 1;
  entry.valid[0] = entry.valid[1] = 1;
  entry.cacheAlgorithm[0] = entry.cacheAlgorithm[1] = 3;
  entry.virtualAddress = 0x4000; entry.physicalAddress[0] = 0x2000;
  entry.synchronize(); put(0x2000,0x24100004);
  if(!step(0x4000,4)) return 11;
  entry.physicalAddress[0] = 0x3000; entry.synchronize();
  put(0x3000,0x24100005); put(0x3004,0x24100006);
  if(!step(0x4000,5)) return 12;
  cpu.scc.status.privilegeMode = 2; cpu.scc.status.reverseEndian = 1;
  cpu.context.setMode();
  if(!step(0x4000,6)) return 13;
  // Nonzero index and two virtual banks holding the same physical line.
  cpu.scc.status.privilegeMode = 0; cpu.scc.status.reverseEndian = 0;
  cpu.context.setMode();
  put(0x1024,0x24100007);
  if(!step(0xffffffff80001024ull,7)) return 14;
  entry.physicalAddress[0] = 0x1000; entry.synchronize();
  if(!step(0x4024,7)) return 15;
  put(0x5024,0x24100008);
  if(!step(0xffffffff80005024ull,8)) return 16;

  std::printf("{\"events\":[");
  for(size_t i=0;i<frontend.samples.size();i++) {
    const auto& sample = frontend.samples[i];
    std::printf("%s{\"pc\":%llu,\"word\":%u,\"physical\":%u,\"cached\":%s",
      i ? "," : "",(unsigned long long)sample.pc,sample.word,sample.physical,sample.cached ? "true" : "false");
    if(sample.cached) {
      std::printf(",\"cache_slot\":%u,\"cache_line\":",sample.slot);
      print_line(sample.tagKey,sample.index,sample.words);
    }
    std::printf("}");
  }
  std::printf("],\"state\":{\"pc\":%llu,\"regs\":[",(unsigned long long)cpu.ipu.pc);
  for(u32 i=0;i<32;i++) std::printf("%s%lld",i ? "," : "",(long long)(int64_t)cpu.ipu.r[i].u64);
  auto ramHash = nall::Hash::SHA256(std::span<const u8>{rdram.ram.data,rdram.ram.size}).digest();
  // Hash explicit fields in big-endian order; no padding/host-pointer bytes.
  std::vector<u8> cacheBytes;
  auto append = [&](u32 value,u32 bytes) {
    for(u32 i=bytes;i>0;i--) cacheBytes.push_back(value >> (8*(i-1)));
  };
  for(const auto& line : cpu.icache.lines) {
    append(line.tagKey,4); append(line.index,2);
    for(u32 word : line.words) append(word,4);
  }
  auto cacheHash = nall::Hash::SHA256(std::span<const u8>{cacheBytes.data(),cacheBytes.size()}).digest();
  std::printf("],\"hi\":%lld,\"lo\":%lld,\"count\":%llu,\"exception\":%u,\"epc\":%llu,\"status\":%u,\"cache_hits\":%lld,\"cache_misses\":%lld,\"ram_sha256\":\"%s\",\"icache_sha256\":\"%s\",\"cache_line0\":",
    (long long)(int64_t)cpu.ipu.hi.u64,(long long)(int64_t)cpu.ipu.lo.u64,
    (unsigned long long)cpu.effectiveCount(),(u32)cpu.scc.cause.exceptionCode,
    (unsigned long long)cpu.scc.epc,(u32)cpu.getControlRegister(12),
    (long long)cpu.profile.icacheHits,(long long)cpu.profile.icacheMisses,ramHash.data(),cacheHash.data());
  auto& finalLine = cpu.icache.line(0);
  print_line(finalLine.tagKey,finalLine.index,finalLine.words);
  std::printf("}}\n");
  ares::Nintendo64::system.unload();
  return 0;
}
