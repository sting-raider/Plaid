/* SPDX-License-Identifier: ISC
 * Controlled composition fixture: translated/degraded RDRAM -> CPU fetch.
 */
#ifndef PLAID_TRANSLATED_FETCH_SENSOR
#define PLAID_TRANSLATED_FETCH_SENSOR 1
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>
#if PLAID_TRANSLATED_FETCH_SENSOR
#include "observer.hpp"
#endif

static constexpr u32 OriT1 = 0x34091234;
static constexpr u32 OriT2 = 0x340a5678;
static constexpr u32 OriT3 = 0x340b1357;
static constexpr u32 EbusCode = 0x8000;
static constexpr u32 MappedBase = 0x200000;

static void set_observers(bool enabled) {
#if PLAID_TRANSLATED_FETCH_SENSOR
  plaidCpuFetchObserver = enabled ? plaid_translated_fetch_boundary : nullptr;
  plaidRdramTranslatedObserver = enabled ? plaid_translated_rdram_read : nullptr;
#else
  (void)enabled;
#endif
}

int main(int argc, char** argv) {
  if(argc != 2 || (strcmp(argv[1], "plain") && strcmp(argv[1], "traced"))) return 2;
  bool traced = !strcmp(argv[1], "traced");

  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid translated fetch join fixture");
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
  for(auto& reg : cpu.ipu.r) reg.u64 = 0;
  cpu.scc.status.errorLevel = cpu.scc.status.exceptionLevel = 0;
  cpu.context.setMode();
  cpu.context.endian = CPU::Context::Endian::Big;
  cpu.dcache.power(false);
  cpu.icache.power(false);

  auto& backing = static_cast<ares::Nintendo64::Memory::Writable&>(rdram.ram);
  auto configureTranslated = [&]() -> RDRAM::Chip& {
    rdram.mapIdentity = 0;
    ri.io.currentLoaded = 1;
    ri.io.select = 0x14;
    for(auto& c : rdram.chips) c.enable = 0;
    auto& chip = rdram.chips[1];
    if(!chip.present) std::abort();
    chip.enable = 1;
    chip.deviceID = 0;
    chip.ccLow = 8;
    chip.ccHigh = 16;
    chip.cci = 63;
    return chip;
  };

  auto& chip = configureTranslated();

  // Phase 1: reliable translated fetch. Request-address backing deliberately
  // contains the same word, so payload equality cannot identify byte origin.
  backing.write<Word>(0x000000, OriT1);
  backing.write<Word>(MappedBase + 0x00, OriT1);
#if PLAID_TRANSLATED_FETCH_SENSOR
  plaidTranslatedFetchPhase = 1;
#endif
  set_observers(traced);
  cpu.ipu.r[9].u64 = 0;
  cpu.pipeline.setPc(0xffffffffa0000000ull);
  if(cpu.instruction()) cpu.synchronize();
  if(cpu.scc.cause.exceptionCode != 0 || cpu.ipu.r[9].u32 != 0x1234) return 5;

  // Phase 2: an equal-valued translated data read happens immediately before
  // an equal-valued instruction fetch. Only the event nested in the fetch
  // boundary is eligible for the fetch witness.
  set_observers(false);
  cpu.ipu.r[9].u64 = 0;
#if PLAID_TRANSLATED_FETCH_SENSOR
  plaidTranslatedFetchPhase = 2;
#endif
  set_observers(traced);
  u32 decoy = rdram.ram.read<Word>(0x000000, RBusDevice::VR4300_UNCACHED);
  if(decoy != OriT1) return 6;
  cpu.pipeline.setPc(0xffffffffa0000000ull);
  if(cpu.instruction()) cpu.synchronize();
  if(cpu.scc.cause.exceptionCode != 0 || cpu.ipu.r[9].u32 != 0x1234) return 7;

  // Phase 3: the raw backing word is a valid ORI, but CCI at ccLow degrades
  // it to zero. The CPU therefore executes NOP. Raw origin and delivered
  // instruction identity are intentionally different.
  set_observers(false);
  backing.write<Word>(0x000000, OriT2);
  backing.write<Word>(MappedBase + 0x00, OriT2);
  chip.cci = 8;
  cpu.ipu.r[10].u64 = 0;
#if PLAID_TRANSLATED_FETCH_SENSOR
  plaidTranslatedFetchPhase = 3;
#endif
  set_observers(traced);
  cpu.pipeline.setPc(0xffffffffa0000000ull);
  if(cpu.instruction()) cpu.synchronize();
  if(cpu.scc.cause.exceptionCode != 0 || cpu.ipu.r[10].u32 != 0) return 8;

  // Phase 4: direct CPU address translation succeeds, but RDRAM chip mapping
  // fails. Fetch returns zero, and there must be no successful translated
  // backing-read event.
  set_observers(false);
  chip.enable = 0;
#if PLAID_TRANSLATED_FETCH_SENSOR
  plaidTranslatedFetchPhase = 4;
#endif
  set_observers(traced);
  cpu.pipeline.setPc(0xffffffffa0000000ull);
  if(cpu.instruction()) cpu.synchronize();
  if(cpu.scc.cause.exceptionCode != 0) return 9;

  // Phase 5: EBUS test mode reads HiddenRAM instead of ordinary RDRAM backing.
  // It shares the CPU fetch boundary class but must not fabricate a translated
  // ordinary-backing witness.
  set_observers(false);
  rdram.mapIdentity = 1;
  backing.write<Word>(EbusCode, OriT1);
  hidden[(EbusCode >> 1) + 0] = 0;
  hidden[(EbusCode >> 1) + 1] = 0;
  mi.writeWord(0, 1u << 10, cpu);
#if PLAID_TRANSLATED_FETCH_SENSOR
  plaidTranslatedFetchPhase = 5;
#endif
  set_observers(traced);
  cpu.pipeline.setPc(0xffffffffa0008000ull);
  if(cpu.instruction()) cpu.synchronize();
  if(cpu.scc.cause.exceptionCode != 0) return 10;
  mi.writeWord(0, 1u << 9, cpu);

  // Phase 6: reverse-endian Word fetch changes post-translation bus paddr 0->4.
  // The translated backing event must join using request==bus_paddr (4), not
  // the pre-endian translated paddr (0).
  set_observers(false);
  configureTranslated();
  chip.cci = 63;
  backing.write<Word>(0x000004, OriT3);
  backing.write<Word>(MappedBase + 0x04, OriT3);
  cpu.context.endian = CPU::Context::Endian::Little;
  cpu.ipu.r[11].u64 = 0;
#if PLAID_TRANSLATED_FETCH_SENSOR
  plaidTranslatedFetchPhase = 6;
#endif
  set_observers(traced);
  cpu.pipeline.setPc(0xffffffffa0000000ull);
  if(cpu.instruction()) cpu.synchronize();
  if(cpu.scc.cause.exceptionCode != 0 || cpu.ipu.r[11].u32 != 0x1357) return 11;
  cpu.context.endian = CPU::Context::Endian::Big;
  set_observers(false);

  auto ramHash = nall::Hash::SHA256(std::span<const u8>{rdram.ram.data, rdram.ram.size}).digest();
  auto hiddenHash = nall::Hash::SHA256(std::span<const u8>{hidden.data(), hidden.size()}).digest();

  std::printf("{");
#if PLAID_TRANSLATED_FETCH_SENSOR
  plaid_print_translated_fetch_events();
#else
  std::printf("\"events\":[]");
#endif
  std::printf(
    ",\"facts\":{\"t1\":%u,\"t2\":%u,\"t3\":%u,\"decoy\":%u,\"ri_error\":%u},"
    "\"state\":{\"pc\":%llu,\"count\":%llu,\"exception\":%u,"
    "\"ram_sha256\":\"%s\",\"hidden_sha256\":\"%s\"}}\n",
    cpu.ipu.r[9].u32, cpu.ipu.r[10].u32, cpu.ipu.r[11].u32, decoy, (u32)ri.io.error,
    (unsigned long long)cpu.ipu.pc, (unsigned long long)cpu.effectiveCount(),
    (u32)cpu.scc.cause.exceptionCode, ramHash.data(), hiddenHash.data()
  );
  ares::Nintendo64::system.unload();
  return 0;
}
