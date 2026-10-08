/* SPDX-License-Identifier: ISC
 * Original reset/restore cache-lineage experiment for the pinned ares oracle.
 */
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <cstdlib>
#include <nall/hash/sha256.hpp>
#if defined(PLAID_CACHE_FILL_CONTEXT)
#include "../012-ares-cache-fill/observer.hpp"
#endif

struct ResetRestoreHeadless : Headless {};

static auto lineHash() -> string {
  std::vector<u8> bytes;
  auto append = [&](u32 value, u32 count) {
    for(u32 n = count; n; n--) bytes.push_back(value >> (8 * (n - 1)));
  };
  for(const auto& line : cpu.icache.lines) {
    append(line.tagKey, 4);
    append(line.index, 2);
    for(u32 word : line.words) append(word, 4);
  }
  return nall::Hash::SHA256(std::span<const u8>{bytes.data(), bytes.size()}).digest();
}

int main(int argc, char** argv) {
  if(argc != 2 || (strcmp(argv[1], "plain") && strcmp(argv[1], "traced"))) return 2;
  bool traced = !strcmp(argv[1], "traced");
  ResetRestoreHeadless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid cache reset restore fixture");
  frontend.cartPak->setAttribute("region", "NTSC");
  frontend.cartPak->setAttribute("cic", "CIC-NUS-6102");
  frontend.cartPak->append("program.rom", 8192);
  Node::System root;
  if(!load(root, "[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Deterministic Entropy", "true");
  option("Recompiler", "false");
  cartridgeSlot.port->allocate(); cartridgeSlot.port->connect();
  ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;

  std::vector<u8> hidden(rdram.ram.size / 2);
  rdram.hidden.data = hidden.data();
  rdram.mapIdentity = 1;
  for(auto& reg : cpu.ipu.r) reg.u64 = 0;
  cpu.scc.status.errorLevel = cpu.scc.status.exceptionLevel = 0;
  cpu.context.setMode();
  #if defined(PLAID_CACHE_FILL_CONTEXT)
  plaidCacheFillObserver = traced ? cache_fill_observer : nullptr;
  #endif

  auto put = [](u32 pa, u32 value) {
    rdram.ram.write<Word>(pa, value, RBusDevice::ARES_DEBUGGER);
  };
  auto step = [](u64 pc, u64 expected) {
    cpu.pipeline.setPc(pc);
    if(cpu.instruction()) cpu.synchronize();
    return cpu.ipu.r[16].u64 == expected && cpu.scc.cause.exceptionCode == 0;
  };

  constexpr u32 A = 0x24100001;  // addiu s0,zero,1
  constexpr u32 B = 0x24100002;  // addiu s0,zero,2
  constexpr u64 Cached = 0xffff'ffff'8000'0000ull;
  constexpr u64 Uncached = 0xffff'ffff'a000'0000ull;

  put(0, A);
  if(!step(Cached, 1)) return 5;                     // fill #1 when traced
  auto saved = ares::Nintendo64::system.serialize(true);
  auto& line = cpu.icache.line(Cached);
  if(!line.hit(0) || line.words[0] != A) return 6;

  line.setValid(false);
  if(!step(Cached, 1)) return 7;                     // equal-payload fill #2
  #if defined(PLAID_CACHE_FILL_CONTEXT)
  if(traced && cacheFills.size() != 2) return 8;
  #endif

  serializer replay(saved.data(), saved.size());
  if(!ares::Nintendo64::system.unserialize(replay)) return 9;  // power(false), then restore all state
  auto& restored = cpu.icache.line(Cached);
  if(!restored.hit(0) || restored.words[0] != A) return 10;

  u64 naiveFill = 0;
  #if defined(PLAID_CACHE_FILL_CONTEXT)
  if(traced) {
    if(cacheFills.size() != 2) return 11;            // restore emitted no completed fill
    naiveFill = cache_fill_for_fetch(0, 0, restored.index, restored.words);
    if(naiveFill != 2) return 12;                    // false causal join across restore boundary
  }
  #endif

  put(0, B);                                         // backing changes after restored resident line
  if(!step(Cached, 1)) return 13;                    // restored cache still executes A, no fill
  if(!step(Uncached, 2)) return 14;                  // current backing executes B
  #if defined(PLAID_CACHE_FILL_CONTEXT)
  if(traced && cacheFills.size() != 2) return 15;
  #endif

  cpu.icache.power(true);                            // exact subroutine used by CPU::power(reset)
  auto& cleared = cpu.icache.line(Cached);
  if(cleared.valid() || cleared.words[0] != 0) return 16;
  if(!step(Cached, 2)) return 17;                    // reset boundary forces a new fill of B
  #if defined(PLAID_CACHE_FILL_CONTEXT)
  if(traced && cacheFills.size() != 3) return 18;
  #endif

  const auto& finalLine = cpu.icache.line(Cached);
  auto ramHash = nall::Hash::SHA256(std::span<const u8>{rdram.ram.data, rdram.ram.size}).digest();
  auto cacheHash = lineHash();
  std::printf("{\"naive_post_restore_fill\":%llu,\"fill_count\":%llu,\"state\":{",
    (unsigned long long)naiveFill,
    (unsigned long long)
    #if defined(PLAID_CACHE_FILL_CONTEXT)
      cacheFills.size()
    #else
      0
    #endif
  );
  std::printf("\"pc\":%llu,\"s0\":%llu,\"count\":%llu,\"exception\":%u,",
    (unsigned long long)cpu.ipu.pc,
    (unsigned long long)cpu.ipu.r[16].u64,
    (unsigned long long)cpu.effectiveCount(),
    (u32)cpu.scc.cause.exceptionCode);
  std::printf("\"ram0\":%u,\"line_tag\":%u,\"line_word0\":%u,\"ram_sha256\":\"%s\",\"icache_sha256\":\"%s\"}}\n",
    rdram.ram.read<Word>(0, RBusDevice::ARES_DEBUGGER), finalLine.tagKey, finalLine.words[0],
    ramHash.data(), cacheHash.data());
  ares::Nintendo64::system.unload();
  return 0;
}
