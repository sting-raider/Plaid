/* SPDX-License-Identifier: ISC
 * Controlled uncached instruction-fetch provenance fixture for pinned ares.
 */
#ifndef PLAID_RDRAM_FETCH_SENSOR
#define PLAID_RDRAM_FETCH_SENSOR 1
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <cstdlib>
#include <nall/hash/sha256.hpp>
#if PLAID_RDRAM_FETCH_SENSOR
#include "observer.hpp"
#endif

static constexpr u32 Data = 0x1000;
static constexpr u32 DirectCode = 0x6000;
static constexpr u32 CachedCode = 0x6040;
static constexpr u32 LittleCode = 0x7000;
static constexpr u32 EbusCode = 0x8000;
static constexpr u32 TranslatedBacking = 0x200000;
static constexpr u32 LwT0S0 = 0x8e080000;
static constexpr u32 OriT3 = 0x340b1357;
static constexpr u32 OriT2 = 0x340a5678;
static constexpr u32 OriT1 = 0x34091234;

static void set_fetch_observers(bool enabled) {
#if PLAID_RDRAM_FETCH_SENSOR
  plaidRdramScalarObserver = enabled ? plaid_rdram_fetch_scalar_observer : nullptr;
  plaidCpuFetchObserver = enabled ? plaid_cpu_fetch_boundary_observer : nullptr;
#else
  (void)enabled;
#endif
}

static void append_be(std::vector<u8>& bytes, u64 value, u32 width) {
  for(u32 i = width; i > 0; i--) bytes.push_back(value >> (8 * (i - 1)));
}

int main(int argc, char** argv) {
  if(argc != 2 || (strcmp(argv[1], "plain") && strcmp(argv[1], "traced"))) return 2;
  bool traced = !strcmp(argv[1], "traced");
  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid uncached fetch fixture");
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
  cpu.context.endian = CPU::Context::Endian::Big;
  cpu.dcache.power(false);
  cpu.icache.power(false);

  auto put = [](u32 address, u32 word) {
    rdram.ram.write<Word>(address, word, RBusDevice::ARES_DEBUGGER);
  };

  // Phase 1: KSEG1 instruction fetch + same-valued data read decoy.  The LW
  // reads zero, immediately followed by a zero-valued NOP instruction fetch.
  put(DirectCode + 0x00, LwT0S0);
  put(DirectCode + 0x04, 0x00000000);
  put(Data, 0x00000000);
  cpu.ipu.r[16].u64 = 0xffffffffa0001000ull;
#if PLAID_RDRAM_FETCH_SENSOR
  plaidRdramFetchPhase = 1;
#endif
  set_fetch_observers(traced);
  cpu.pipeline.setPc(0xffffffffa0006000ull);
  for(u32 i = 0; i < 2; i++) if(cpu.instruction()) cpu.synchronize();
  if(cpu.scc.cause.exceptionCode != 0 || cpu.ipu.r[8].u32 != 0) return 5;

  // Phase 2: KSEG0 fetch. It may fill I-cache from RDRAM, but must not create
  // an ordinary scalar read witness for the instruction itself.
  set_fetch_observers(false);
  cpu.icache.power(false);
  put(CachedCode, OriT3);
  cpu.ipu.r[11].u64 = 0;
#if PLAID_RDRAM_FETCH_SENSOR
  plaidRdramFetchPhase = 2;
#endif
  set_fetch_observers(traced);
  cpu.pipeline.setPc(0xffffffff80006040ull);
  if(cpu.instruction()) cpu.synchronize();
  if(cpu.scc.cause.exceptionCode != 0 || cpu.ipu.r[11].u32 != 0x1357) return 6;

  // Phase 3: reverse-endian context changes the actual word-lane bus address.
  // Raw translated paddr 0x7000 must read backing word 0x7004.
  set_fetch_observers(false);
  rdram.mapIdentity = 1;
  put(LittleCode + 0x00, 0x00000000);
  put(LittleCode + 0x04, OriT2);
  cpu.ipu.r[10].u64 = 0;
  cpu.context.endian = CPU::Context::Endian::Little;
#if PLAID_RDRAM_FETCH_SENSOR
  plaidRdramFetchPhase = 3;
#endif
  set_fetch_observers(traced);
  cpu.pipeline.setPc(0xffffffffa0007000ull);
  if(cpu.instruction()) cpu.synchronize();
  if(cpu.scc.cause.exceptionCode != 0 || cpu.ipu.r[10].u32 != 0x5678) return 7;
  cpu.context.endian = CPU::Context::Endian::Big;

  // Phase 4: successful non-identity RDRAM translation.  Backing chip one is
  // read and executes ORI, but the identity-only scalar observer must stay quiet.
  set_fetch_observers(false);
  auto& backing = static_cast<ares::Nintendo64::Memory::Writable&>(rdram.ram);
  backing.write<Word>(TranslatedBacking, OriT1);
  rdram.mapIdentity = 0;
  ri.io.currentLoaded = 1;
  ri.io.select = 0x14;
  for(auto& chip : rdram.chips) chip.enable = 0;
  auto& chip = rdram.chips[1];
  if(!chip.present) return 8;
  chip.enable = 1;
  chip.deviceID = 0;
  chip.ccLow = 8;
  chip.ccHigh = 16;
  chip.cci = 63;
  cpu.ipu.r[9].u64 = 0;
#if PLAID_RDRAM_FETCH_SENSOR
  plaidRdramFetchPhase = 4;
#endif
  set_fetch_observers(traced);
  cpu.pipeline.setPc(0xffffffffa0000000ull);
  if(cpu.instruction()) cpu.synchronize();
  if(cpu.scc.cause.exceptionCode != 0 || cpu.ipu.r[9].u32 != 0x1234) return 9;

  // Phase 5: identity-mapped but out-of-range RDRAM fetch returns zero/NOP.
  // It is a bus outcome, not a successful backing read.
  set_fetch_observers(false);
  rdram.mapIdentity = 1;
#if PLAID_RDRAM_FETCH_SENSOR
  plaidRdramFetchPhase = 5;
#endif
  set_fetch_observers(traced);
  u64 oobPc = 0xffffffffa0000000ull | (u64)rdram.ram.size;
  cpu.pipeline.setPc(oobPc);
  if(cpu.instruction()) cpu.synchronize();
  if(cpu.scc.cause.exceptionCode != 0) return 10;

  // Phase 6: non-identity missing mapping also returns zero/NOP and must not
  // fabricate a backing witness.
  set_fetch_observers(false);
  rdram.mapIdentity = 0;
  for(auto& c : rdram.chips) c.enable = 0;
#if PLAID_RDRAM_FETCH_SENSOR
  plaidRdramFetchPhase = 6;
#endif
  set_fetch_observers(traced);
  cpu.pipeline.setPc(0xffffffffa0000000ull);
  if(cpu.instruction()) cpu.synchronize();
  if(cpu.scc.cause.exceptionCode != 0) return 11;

  // Phase 7: successful translated read with CCI at/below ccLow degrades every
  // set bit to zero. It executes as NOP but is intentionally outside the
  // identity-backing witness policy.
  set_fetch_observers(false);
  chip.enable = 1;
  chip.deviceID = 0;
  chip.ccLow = 8;
  chip.ccHigh = 16;
  chip.cci = 8;
  rdram.mapIdentity = 0;
#if PLAID_RDRAM_FETCH_SENSOR
  plaidRdramFetchPhase = 7;
#endif
  set_fetch_observers(traced);
  cpu.pipeline.setPc(0xffffffffa0000000ull);
  if(cpu.instruction()) cpu.synchronize();
  if(cpu.scc.cause.exceptionCode != 0) return 12;

  // Phase 8: MI EBUS test mode bypasses RDRAM::Writable::read entirely for
  // uncached CPU traffic. Force the hidden nibble to zero so the fetched word
  // is a deterministic NOP, and require no ordinary-RDRAM backing witness.
  set_fetch_observers(false);
  rdram.mapIdentity = 1;
  put(EbusCode, OriT1);
  hidden[(EbusCode >> 1) + 0] = 0;
  hidden[(EbusCode >> 1) + 1] = 0;
  mi.writeWord(0, 1u << 10, cpu);
#if PLAID_RDRAM_FETCH_SENSOR
  plaidRdramFetchPhase = 8;
#endif
  set_fetch_observers(traced);
  cpu.pipeline.setPc(0xffffffffa0008000ull);
  if(cpu.instruction()) cpu.synchronize();
  if(cpu.scc.cause.exceptionCode != 0) return 13;
  mi.writeWord(0, 1u << 9, cpu);
  set_fetch_observers(false);

  auto ramHash = nall::Hash::SHA256(std::span<const u8>{rdram.ram.data, rdram.ram.size}).digest();
  auto hiddenHash = nall::Hash::SHA256(std::span<const u8>{hidden.data(), hidden.size()}).digest();
  std::vector<u8> icacheBytes;
  for(const auto& line : cpu.icache.lines) {
    append_be(icacheBytes, line.tagKey, 4);
    append_be(icacheBytes, line.index, 2);
    for(u32 word : line.words) append_be(icacheBytes, word, 4);
  }
  auto icacheHash = nall::Hash::SHA256(std::span<const u8>{icacheBytes.data(), icacheBytes.size()}).digest();

  std::printf("{");
#if PLAID_RDRAM_FETCH_SENSOR
  plaid_print_rdram_fetch_events();
#else
  std::printf("\"scalar_events\":[],\"fetch_events\":[]");
#endif
  std::printf(",\"facts\":{\"direct_lw\":%u,\"cached_ori\":%u,\"little_ori\":%u,\"translated_ori\":%u,\"oob_pc\":%llu,\"ri_error\":%u}",
    cpu.ipu.r[8].u32, cpu.ipu.r[11].u32, cpu.ipu.r[10].u32, cpu.ipu.r[9].u32,
    (unsigned long long)oobPc, (u32)ri.io.error);
  std::printf(",\"state\":{\"pc\":%llu,\"count\":%llu,\"exception\":%u,\"icache_hits\":%llu,\"icache_misses\":%llu,\"ram_sha256\":\"%s\",\"hidden_sha256\":\"%s\",\"icache_sha256\":\"%s\"}}\n",
    (unsigned long long)cpu.ipu.pc, (unsigned long long)cpu.effectiveCount(),
    (u32)cpu.scc.cause.exceptionCode, (unsigned long long)cpu.profile.icacheHits,
    (unsigned long long)cpu.profile.icacheMisses, ramHash.data(), hiddenHash.data(), icacheHash.data());
  ares::Nintendo64::system.unload();
  return 0;
}
