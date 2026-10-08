/* SPDX-License-Identifier: ISC
 * Direct-component fixture for successful translated/degraded scalar RDRAM reads.
 */
#ifndef PLAID_TRANSLATED_SENSOR
#define PLAID_TRANSLATED_SENSOR 1
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>
#if PLAID_TRANSLATED_SENSOR
#include "observer.hpp"
#endif

int main(int argc, char** argv) {
  if(argc != 2 || (strcmp(argv[1], "plain") && strcmp(argv[1], "traced"))) return 2;
  bool traced = !strcmp(argv[1], "traced");

  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid translated RDRAM backing fixture");
  frontend.cartPak->setAttribute("region", "NTSC");
  frontend.cartPak->setAttribute("cic", "CIC-NUS-6102");
  frontend.cartPak->append("program.rom", 8192);
  Node::System root;
  if(!load(root, "[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Deterministic Entropy", "true");
  option("Recompiler", "false");
  cartridgeSlot.port->allocate();
  cartridgeSlot.port->connect();
  ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;

  std::vector<u8> hidden(rdram.ram.size / 2);
  rdram.hidden.data = hidden.data();

#if PLAID_TRANSLATED_SENSOR
  plaidRdramTranslatedObserver = traced ? plaid_translated_read_observer : nullptr;
#endif

  auto& backing = static_cast<ares::Nintendo64::Memory::Writable&>(rdram.ram);
  backing.write<Word>(0x000000, 0x11223344);
  backing.write<Word>(0x000004, 0xdeadbeef);  // Equal-value decoy at request-address backing.
  backing.write<Word>(0x200000, 0xf0f0aa55);
  backing.write<Word>(0x200004, 0xdeadbeef);  // Actual source for request 0x000004.
  backing.write<Word>(0x200008, 0xffffffff);
  backing.write<Word>(0x20000c, 0xffffffff);

  rdram.mapIdentity = 0;
  ri.io.currentLoaded = 1;
  ri.io.select = 0x14;
  for(auto& chip : rdram.chips) chip.enable = 0;
  auto& chip0 = rdram.chips[0];
  auto& chip1 = rdram.chips[1];
  if(!chip0.present || !chip1.present) return 5;

  // Cross the first two bus pages: request page 0 -> backing chip 1, request page 1 -> backing chip 0.
  chip0.enable = 1;
  chip0.deviceID = 2;
  chip0.ccLow = 8;
  chip0.ccHigh = 16;
  chip0.cci = 63;
  chip1.enable = 1;
  chip1.deviceID = 0;
  chip1.ccLow = 8;
  chip1.ccHigh = 16;
  chip1.cci = 63;

  std::vector<u64> results;
  auto read = [&](u32 address) {
    results.push_back(rdram.ram.read<Word>(address, RBusDevice::VR4300_UNCACHED));
  };

  read(0x000000);  // mapped 0x200000, reliable
  read(0x200000);  // mapped 0x000000, reliable
  read(0x000004);  // equal-valued request backing is a decoy; actual mapped source is 0x200004

  chip1.cci = 8;
  read(0x000008);  // raw 0xffffffff, delivered zero

  chip1.cci = 12;
  read(0x00000c);  // raw 0xffffffff, deterministic partial degradation

  size_t beforeFailure = 0;
#if PLAID_TRANSLATED_SENSOR
  beforeFailure = plaidTranslatedReads.size();
#endif
  chip1.enable = 0;
  read(0x000010);  // missing mapping: zero, no successful backing read
#if PLAID_TRANSLATED_SENSOR
  if(plaidTranslatedReads.size() != beforeFailure) return 6;
#endif

  chip1.enable = 1;
  ri.io.select = 0;
  read(0x000014);  // inactive RI: zero, no successful backing read
#if PLAID_TRANSLATED_SENSOR
  if(plaidTranslatedReads.size() != beforeFailure) return 7;
#endif

  // Identity reads have a different witness class and must not appear here.
  ri.io.select = 0x14;
  rdram.mapIdentity = 1;
  read(0x000000);
#if PLAID_TRANSLATED_SENSOR
  if(plaidTranslatedReads.size() != beforeFailure) return 8;
#endif

  // EBus reads source HiddenRAM, not ordinary Memory::Writable backing bytes.
  rdram.mapIdentity = 0;
  chip1.cci = 63;
  rdram.ram.ebusWrite<Word>(0x000020, 0xa1b2c3d4);
  results.push_back(rdram.ram.ebusRead<Word>(0x000020));
#if PLAID_TRANSLATED_SENSOR
  if(plaidTranslatedReads.size() != beforeFailure) return 9;
#endif

  std::printf("{\"results\":[");
  for(size_t i = 0; i < results.size(); i++) {
    std::printf("%s%llu", i ? "," : "", (unsigned long long)results[i]);
  }
  std::printf("]");
#if PLAID_TRANSLATED_SENSOR
  print_plaid_translated_reads();
#else
  std::printf(",\"translated_reads\":[]");
#endif

  auto ramHash = nall::Hash::SHA256(std::span<const u8>{rdram.ram.data, rdram.ram.size}).digest();
  auto hiddenHash = nall::Hash::SHA256(std::span<const u8>{hidden.data(), hidden.size()}).digest();
  std::printf(",\"state\":{\"pc\":%llu,\"regs\":[", (unsigned long long)cpu.ipu.pc);
  for(u32 i = 0; i < 32; i++) std::printf("%s%lld", i ? "," : "", (long long)(int64_t)cpu.ipu.r[i].u64);
  std::printf(
    "],\"hi\":%lld,\"lo\":%lld,\"count\":%llu,\"ri_error\":%u,\"ram_sha256\":\"%s\",\"hidden_sha256\":\"%s\"}}\n",
    (long long)(int64_t)cpu.ipu.hi.u64, (long long)(int64_t)cpu.ipu.lo.u64,
    (unsigned long long)cpu.effectiveCount(), (u32)ri.io.error, ramHash.data(), hiddenHash.data()
  );

  ares::Nintendo64::system.unload();
  return 0;
}
