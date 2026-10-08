/* SPDX-License-Identifier: ISC
 * Controlled dirty D-cache eviction lineage fixture for pinned ares.
 */
#ifndef PLAID_RDRAM_EVICTION_SENSOR
#define PLAID_RDRAM_EVICTION_SENSOR 1
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <cstdlib>
#include <nall/hash/sha256.hpp>
#if PLAID_RDRAM_EVICTION_SENSOR
#include "observer.hpp"
#endif

static constexpr u32 Source = 0x1000;
static constexpr u32 Destination = 0x2000;
static constexpr u32 Conflict = 0x4000;  // same D-cache index as Destination
static constexpr u32 Code = 0x6000;
static constexpr u32 Original = 0x11223344;
static constexpr u32 Decoy = 0xdeadbeef;
static constexpr u32 D1 = 0x01020304;
static constexpr u32 D2 = 0x11223344;
static constexpr u32 D3 = 0x55667788;
static constexpr u32 C0 = 0xcafebabe;
static constexpr u32 C1 = 0x0badf00d;
static constexpr u32 C2 = 0x89abcdef;
static constexpr u32 C3 = 0x13579bdf;

static void set_eviction_observers(bool enabled) {
#if PLAID_RDRAM_EVICTION_SENSOR
  plaidRdramScalarObserver = enabled ? plaid_eviction_scalar_observer : nullptr;
  plaidRdramBurstObserver = enabled ? plaid_eviction_burst_observer : nullptr;
#else
  (void)enabled;
#endif
}

static u32 backing_word(u32 address) {
#if PLAID_RDRAM_EVICTION_SENSOR
  auto saved = plaidRdramScalarObserver;
  plaidRdramScalarObserver = nullptr;
#endif
  u32 value = rdram.ram.read<Word>(address, RBusDevice::ARES_DEBUGGER);
#if PLAID_RDRAM_EVICTION_SENSOR
  plaidRdramScalarObserver = saved;
#endif
  return value;
}

static void append_be(std::vector<u8>& bytes, u64 value, u32 width) {
  for(u32 i = width; i > 0; i--) bytes.push_back(value >> (8 * (i - 1)));
}

int main(int argc, char** argv) {
  if(argc != 2 || (strcmp(argv[1], "plain") && strcmp(argv[1], "traced"))) return 2;
  bool traced = !strcmp(argv[1], "traced");
  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid D-cache eviction lineage fixture");
  frontend.cartPak->setAttribute("region", "NTSC");
  frontend.cartPak->setAttribute("cic", "CIC-NUS-6102");
  frontend.cartPak->append("program.rom", 8192);
  Node::System root;
  if(!load(root, "[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak", "true");
  option("Deterministic Entropy", "true");
  option("Recompiler", "false");
  cartridgeSlot.port->allocate();
  cartridgeSlot.port->connect();
  ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;

  std::vector<u8> hidden(rdram.ram.size / 2);
  rdram.hidden.data = hidden.data();
  rdram.mapIdentity = 1;
  for(auto& reg : cpu.ipu.r) reg.u64 = 0;
  cpu.scc.status.errorLevel = cpu.scc.status.exceptionLevel = 0;
  cpu.context.setMode();
  cpu.dcache.power(false);
  cpu.icache.power(false);

  auto put = [](u32 address, u32 word) {
    rdram.ram.write<Word>(address, word, RBusDevice::ARES_DEBUGGER);
  };

  // Cached source load, cached destination store, uncached backing decoy, then
  // a conflicting cached load. Destination and Conflict differ by 0x2000, so
  // (vaddr >> 4) & 0x1ff selects the same D-cache slot.
  put(Code + 0x00, 0x8e080000);  // LW t0,0(s0)
  put(Code + 0x04, 0xae280000);  // SW t0,0(s1)
  put(Code + 0x08, 0xae4a0000);  // SW t2,0(s2) -- uncached alias of destination
  put(Code + 0x0c, 0x8e6b0000);  // LW t3,0(s3) -- conflicting cached line

  put(Source, Original);
  put(Destination + 0x0, 0xaabbccdd);
  put(Destination + 0x4, D1);
  put(Destination + 0x8, D2);
  put(Destination + 0xc, D3);
  put(Conflict + 0x0, C0);
  put(Conflict + 0x4, C1);
  put(Conflict + 0x8, C2);
  put(Conflict + 0xc, C3);

  cpu.ipu.r[10].u64 = Decoy;
  cpu.ipu.r[16].u64 = 0xffffffff80001000ull;
  cpu.ipu.r[17].u64 = 0xffffffff80002000ull;
  cpu.ipu.r[18].u64 = 0xffffffffa0002000ull;
  cpu.ipu.r[19].u64 = 0xffffffff80004000ull;
#if PLAID_RDRAM_EVICTION_SENSOR
  plaidEvictionPhase = 1;
#endif
  set_eviction_observers(traced);
  cpu.pipeline.setPc(0xffffffff80006000ull);

  // Stop immediately before the conflicting access, while the outgoing victim
  // still exists in the slot and backing contains the uncached decoy.
  for(u32 i = 0; i < 3; i++) if(cpu.instruction()) cpu.synchronize();
  if(cpu.scc.cause.exceptionCode != 0 || cpu.ipu.r[8].u32 != Original) return 5;

  const auto& outgoing = cpu.dcache.line(cpu.ipu.r[17].u64);
  if(!outgoing.hit(Destination) || outgoing.dirty != 0x000f) return 6;
  u32 outgoingTag = outgoing.tagKey;
  u16 outgoingIndex = outgoing.index;
  u16 outgoingDirty = outgoing.dirty;
  u32 outgoingWords[4] = {outgoing.words[0], outgoing.words[1], outgoing.words[2], outgoing.words[3]};
  u32 backingBefore[4] = {
    backing_word(Destination + 0x0), backing_word(Destination + 0x4),
    backing_word(Destination + 0x8), backing_word(Destination + 0xc)
  };
  if(outgoingWords[0] != Original || outgoingWords[1] != D1 || outgoingWords[2] != D2 || outgoingWords[3] != D3) return 7;
  if(backingBefore[0] != Decoy || backingBefore[1] != D1 || backingBefore[2] != D2 || backingBefore[3] != D3) return 8;

  // The conflict miss synchronously writes back the outgoing dirty victim and
  // then fills/reuses this same cache slot for physical 0x4000.
  if(cpu.instruction()) cpu.synchronize();
  if(cpu.scc.cause.exceptionCode != 0 || cpu.ipu.r[11].u32 != C0) return 9;

  const auto& incoming = cpu.dcache.line(cpu.ipu.r[19].u64);
  if(!incoming.hit(Conflict) || incoming.dirty != 0) return 10;
  u32 incomingTag = incoming.tagKey;
  u16 incomingIndex = incoming.index;
  u32 incomingWords[4] = {incoming.words[0], incoming.words[1], incoming.words[2], incoming.words[3]};
  u32 backingAfter[4] = {
    backing_word(Destination + 0x0), backing_word(Destination + 0x4),
    backing_word(Destination + 0x8), backing_word(Destination + 0xc)
  };
  if(backingAfter[0] != Original || backingAfter[1] != D1 || backingAfter[2] != D2 || backingAfter[3] != D3) return 11;
  if(outgoingIndex != incomingIndex || outgoingTag == incomingTag) return 12;
  if(incomingWords[0] != C0 || incomingWords[1] != C1 || incomingWords[2] != C2 || incomingWords[3] != C3) return 13;
  set_eviction_observers(false);

  auto ramHash = nall::Hash::SHA256(std::span<const u8>{rdram.ram.data, rdram.ram.size}).digest();
  auto hiddenHash = nall::Hash::SHA256(std::span<const u8>{hidden.data(), hidden.size()}).digest();
  std::vector<u8> dcacheBytes;
  for(const auto& line : cpu.dcache.lines) {
    append_be(dcacheBytes, line.tagKey, 4);
    append_be(dcacheBytes, line.dirty, 2);
    append_be(dcacheBytes, line.index, 2);
    append_be(dcacheBytes, line.fillPc, 8);
    append_be(dcacheBytes, line.dirtyPc, 8);
    for(u32 word : line.words) append_be(dcacheBytes, word, 4);
  }
  auto dcacheHash = nall::Hash::SHA256(std::span<const u8>{dcacheBytes.data(), dcacheBytes.size()}).digest();

  std::printf("{");
#if PLAID_RDRAM_EVICTION_SENSOR
  plaid_print_eviction_events();
#else
  std::printf("\"scalar_events\":[],\"burst_events\":[]");
#endif
  std::printf(",\"facts\":{");
  std::printf("\"outgoing_tag\":%u,\"incoming_tag\":%u,\"slot_index\":%u,\"dirty_before\":%u,",
    outgoingTag, incomingTag, (u32)outgoingIndex, (u32)outgoingDirty);
  std::printf("\"outgoing_words\":[%u,%u,%u,%u],\"backing_before\":[%u,%u,%u,%u],",
    outgoingWords[0], outgoingWords[1], outgoingWords[2], outgoingWords[3],
    backingBefore[0], backingBefore[1], backingBefore[2], backingBefore[3]);
  std::printf("\"incoming_words\":[%u,%u,%u,%u],\"backing_after\":[%u,%u,%u,%u]}",
    incomingWords[0], incomingWords[1], incomingWords[2], incomingWords[3],
    backingAfter[0], backingAfter[1], backingAfter[2], backingAfter[3]);
  std::printf(",\"state\":{\"pc\":%llu,\"t0\":%u,\"t3\":%u,\"count\":%llu,\"exception\":%u,\"dcache_hits\":%llu,\"dcache_misses\":%llu,\"dcache_writebacks\":%llu,\"ram_sha256\":\"%s\",\"hidden_sha256\":\"%s\",\"dcache_sha256\":\"%s\"}}\n",
    (unsigned long long)cpu.ipu.pc, cpu.ipu.r[8].u32, cpu.ipu.r[11].u32,
    (unsigned long long)cpu.effectiveCount(), (u32)cpu.scc.cause.exceptionCode,
    (unsigned long long)cpu.profile.dcacheHits, (unsigned long long)cpu.profile.dcacheMisses,
    (unsigned long long)cpu.profile.dcacheWritebacks,
    ramHash.data(), hiddenHash.data(), dcacheHash.data());
  ares::Nintendo64::system.unload();
  return 0;
}
