/* SPDX-License-Identifier: ISC
 * Controlled VR4300 CPU-copy provenance fixture for pinned ares.
 */
#ifndef PLAID_RDRAM_COPY_SENSOR
#define PLAID_RDRAM_COPY_SENSOR 1
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <cstdlib>
#include <nall/hash/sha256.hpp>
#if PLAID_RDRAM_COPY_SENSOR
#include "observer.hpp"
#endif

static constexpr u32 Source = 0x1000;
static constexpr u32 Destination = 0x2000;
static constexpr u32 UncachedCode = 0x6000;
static constexpr u32 CachedCode = 0x6040;
static constexpr u32 Original = 0x11223344;
static constexpr u32 OldDestination = 0xaabbccdd;
static constexpr u32 AliasMutation = 0x55667788;

static void set_copy_observers(bool enabled) {
#if PLAID_RDRAM_COPY_SENSOR
  plaidRdramScalarObserver = enabled ? plaid_copy_scalar_observer : nullptr;
  plaidRdramBurstObserver = enabled ? plaid_copy_burst_observer : nullptr;
#else
  (void)enabled;
#endif
}

static u32 backing_word(u32 address) {
#if PLAID_RDRAM_COPY_SENSOR
  auto saved = plaidRdramScalarObserver;
  plaidRdramScalarObserver = nullptr;
#endif
  u32 value = rdram.ram.read<Word>(address, RBusDevice::ARES_DEBUGGER);
#if PLAID_RDRAM_COPY_SENSOR
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
  frontend.cartPak->setAttribute("title", "Plaid CPU copy fixture");
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

  // Phase 1: an uncached KSEG1 copy. Both data operations must become completed
  // scalar RDRAM transactions with the same payload.
  put(UncachedCode + 0x00, 0x8e080000);  // LW t0,0(s0)
  put(UncachedCode + 0x04, 0xae280000);  // SW t0,0(s1)
  put(CachedCode + 0x00, 0x8e080000);    // LW t0,0(s0), cached source
  put(CachedCode + 0x04, 0xae4a0000);    // SW t2,0(s2), uncached alias mutation
  put(CachedCode + 0x08, 0xae280000);    // SW t0,0(s1), cached destination
  put(CachedCode + 0x0c, 0xbe390000);    // CACHE dcache hit write back,0(s1)
  put(Source, Original);
  put(Destination, OldDestination);

#if PLAID_RDRAM_COPY_SENSOR
  plaidCopyPhase = 1;
#endif
  set_copy_observers(traced);
  cpu.ipu.r[16].u64 = 0xffffffffa0001000ull;
  cpu.ipu.r[17].u64 = 0xffffffffa0002000ull;
  cpu.pipeline.setPc(0xffffffff80006000ull);
  for(u32 i = 0; i < 2; i++) if(cpu.instruction()) cpu.synchronize();
  if(cpu.scc.cause.exceptionCode != 0 || cpu.ipu.r[8].u32 != Original) return 5;
  u32 uncachedDestination = backing_word(Destination);
  if(uncachedDestination != Original) return 6;

  // Phase 2: cached source and destination with an uncached alias write inserted
  // between load and store. The source D-cache line intentionally remains stale.
  set_copy_observers(false);
  cpu.dcache.power(false);
  put(Source, Original);
  put(Destination, OldDestination);
  cpu.ipu.r[8].u64 = 0;
  cpu.ipu.r[10].u64 = AliasMutation;
  cpu.ipu.r[16].u64 = 0xffffffff80001000ull;
  cpu.ipu.r[17].u64 = 0xffffffff80002000ull;
  cpu.ipu.r[18].u64 = 0xffffffffa0001000ull;
#if PLAID_RDRAM_COPY_SENSOR
  plaidCopyPhase = 2;
#endif
  set_copy_observers(traced);
  cpu.pipeline.setPc(0xffffffff80006040ull);
  for(u32 i = 0; i < 3; i++) if(cpu.instruction()) cpu.synchronize();
  if(cpu.scc.cause.exceptionCode != 0 || cpu.ipu.r[8].u32 != Original) return 7;

  u32 cachedBackingBeforeWriteback = backing_word(Destination);
  u32 mutatedSourceBacking = backing_word(Source);
  const auto& sourceLineBefore = cpu.dcache.line(cpu.ipu.r[16].u64);
  const auto& destinationLineBefore = cpu.dcache.line(cpu.ipu.r[17].u64);
  if(!sourceLineBefore.hit(Source) || !destinationLineBefore.hit(Destination)) return 8;
  u32 cachedSourceResident = sourceLineBefore.words[Source >> 2 & 3];
  u32 cachedDestinationResident = destinationLineBefore.words[Destination >> 2 & 3];
  u16 dirtyBeforeWriteback = destinationLineBefore.dirty;
  if(cachedBackingBeforeWriteback != OldDestination || mutatedSourceBacking != AliasMutation ||
     cachedSourceResident != Original || cachedDestinationResident != Original || !dirtyBeforeWriteback) return 9;

  if(cpu.instruction()) cpu.synchronize();  // guest CACHE 0x19 hit writeback
  if(cpu.scc.cause.exceptionCode != 0) return 10;
  u32 cachedBackingAfterWriteback = backing_word(Destination);
  u32 dirtyAfterWriteback = cpu.dcache.line(cpu.ipu.r[17].u64).dirty;
  if(cachedBackingAfterWriteback != Original || dirtyAfterWriteback != 0) return 11;
  set_copy_observers(false);

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
  std::vector<u8> icacheBytes;
  for(const auto& line : cpu.icache.lines) {
    append_be(icacheBytes, line.tagKey, 4);
    append_be(icacheBytes, line.index, 2);
    for(u32 word : line.words) append_be(icacheBytes, word, 4);
  }
  auto icacheHash = nall::Hash::SHA256(std::span<const u8>{icacheBytes.data(), icacheBytes.size()}).digest();

  std::printf("{");
#if PLAID_RDRAM_COPY_SENSOR
  plaid_print_copy_events();
#else
  std::printf("\"scalar_events\":[],\"burst_events\":[]");
#endif
  std::printf(",\"facts\":{\"uncached_destination\":%u,\"cached_backing_before_writeback\":%u,\"mutated_source_backing\":%u,\"cached_source_resident\":%u,\"cached_destination_resident\":%u,\"cached_backing_after_writeback\":%u,\"dirty_before_writeback\":%u,\"dirty_after_writeback\":%u}",
    uncachedDestination, cachedBackingBeforeWriteback, mutatedSourceBacking,
    cachedSourceResident, cachedDestinationResident, cachedBackingAfterWriteback,
    (u32)dirtyBeforeWriteback, dirtyAfterWriteback);
  std::printf(",\"state\":{\"pc\":%llu,\"t0\":%u,\"t2\":%u,\"count\":%llu,\"exception\":%u,\"dcache_hits\":%llu,\"dcache_misses\":%llu,\"dcache_writebacks\":%llu,\"ram_sha256\":\"%s\",\"hidden_sha256\":\"%s\",\"dcache_sha256\":\"%s\",\"icache_sha256\":\"%s\"}}\n",
    (unsigned long long)cpu.ipu.pc, cpu.ipu.r[8].u32, cpu.ipu.r[10].u32,
    (unsigned long long)cpu.effectiveCount(), (u32)cpu.scc.cause.exceptionCode,
    (unsigned long long)cpu.profile.dcacheHits, (unsigned long long)cpu.profile.dcacheMisses,
    (unsigned long long)cpu.profile.dcacheWritebacks,
    ramHash.data(), hiddenHash.data(), dcacheHash.data(), icacheHash.data());
  ares::Nintendo64::system.unload();
  return 0;
}