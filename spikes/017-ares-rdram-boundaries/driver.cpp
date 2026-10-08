/* SPDX-License-Identifier: ISC
 * Original direct-component mapping/degradation/failure boundary fixture.
 */
#ifndef PLAID_RDRAM_SENSOR
#define PLAID_RDRAM_SENSOR 1
#endif
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <cstdlib>
#include <nall/hash/sha256.hpp>
#if PLAID_RDRAM_SENSOR
#include "../016-ares-rdram-bursts/observer.hpp"
#endif

int main(int argc,char** argv) {
  if(argc != 2 || (strcmp(argv[1],"plain") && strcmp(argv[1],"traced"))) return 2;
  bool traced = !strcmp(argv[1],"traced");
  Headless frontend; platform = &frontend;
  frontend.cartPak->setAttribute("title","Plaid RAM boundaries fixture");
  frontend.cartPak->setAttribute("region","NTSC");
  frontend.cartPak->setAttribute("cic","CIC-NUS-6102");
  frontend.cartPak->append("program.rom",8192);
  Node::System root;
  if(!load(root,"[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Deterministic Entropy","true"); option("Recompiler","false");
  cartridgeSlot.port->allocate(); cartridgeSlot.port->connect();
  ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;
  std::vector<u8> hidden(rdram.ram.size/2); rdram.hidden.data = hidden.data();
  #if PLAID_RDRAM_SENSOR
  plaidRdramBurstObserver = traced ? rdram_burst_observer : nullptr;
  #endif
  u32 initial[8], replacement[8], translated[8];
  auto& backing = static_cast<ares::Nintendo64::Memory::Writable&>(rdram.ram);
  for(u32 i=0;i<8;i++) {
    initial[i] = 0x11223300+i;
    replacement[i] = 0x55667700+i;
    translated[i] = 0xffffffff;
    backing.write<Word>(i*4,initial[i]);
    backing.write<Word>(0x200000+i*4,0xaabbcc00+i);
  }
  std::vector<std::vector<u32>> results;
  auto read = [&]() {
    u32 words[8]; rdram.ram.readBurst<ICache>(0,words,RBusDevice::VR4300_ICACHE);
    results.emplace_back(words,words+8);
  };
  rdram.mapIdentity = 1;
  read(); // Actual identity witness.
  rdram.ram.writeBurst<ICache>(0,replacement,RBusDevice::VR4300_ICACHE);
  rdram.mapIdentity = 0;
  ri.io.currentLoaded = 1; ri.io.select = 0x14;
  for(auto& chip : rdram.chips) chip.enable = 0;
  auto& chip = rdram.chips[1];
  if(!chip.present) return 5;
  chip.enable = 1; chip.deviceID = 0;
  chip.ccLow = 8; chip.ccHigh = 16; chip.cci = 63;
  read(); // Bus page zero maps to backing chip one, not address zero.
  rdram.ram.writeBurst<ICache>(0,translated,RBusDevice::VR4300_ICACHE);
  read(); // Successful translated store, still outside the observer policy.
  chip.cci = 8; read(); // All bits degrade to zero.
  chip.cci = 12; read(); // Deterministic partial-bit degradation.
  chip.enable = 0; read(); // Missing mapping: zero result and RI acknowledgement.
  chip.enable = 1; ri.io.select = 0; read(); // Inactive RI: no mapping.
  rdram.mapIdentity = 1;
  u32 tail[8]; for(auto& word : tail) word = 0xdeadbeef;
  rdram.ram.readBurst<ICache>(rdram.ram.size,tail,RBusDevice::VR4300_ICACHE);
  results.emplace_back(tail,tail+8);
  rdram.ram.writeBurst<ICache>(rdram.ram.size,translated,RBusDevice::VR4300_ICACHE);
  u32 small[4]; rdram.ram.readBurst<DCache>(0,small,RBusDevice::VR4300_DCACHE);
  results.emplace_back(small,small+4); // Actual 16-byte identity witness.
  for(u32 i=0;i<8;i++) {
    if(backing.read<Word>(i*4) != replacement[i]) return 6;
    if(backing.read<Word>(0x200000+i*4) != translated[i]) return 7;
  }
  std::printf("{\"results\":[");
  for(size_t i=0;i<results.size();i++) {
    std::printf("%s[",i ? "," : "");
    for(size_t j=0;j<results[i].size();j++) std::printf("%s%u",j ? "," : "",results[i][j]);
    std::printf("]");
  }
  std::printf("]");
  #if PLAID_RDRAM_SENSOR
  print_rdram_bursts();
  #else
  std::printf(",\"rdram_bursts\":[]");
  #endif
  auto ramHash = nall::Hash::SHA256(std::span<const u8>{rdram.ram.data,rdram.ram.size}).digest();
  auto hiddenHash = nall::Hash::SHA256(std::span<const u8>{hidden.data(),hidden.size()}).digest();
  std::printf(",\"state\":{\"pc\":%llu,\"regs\":[",(unsigned long long)cpu.ipu.pc);
  for(u32 i=0;i<32;i++) std::printf("%s%lld",i ? "," : "",(long long)(int64_t)cpu.ipu.r[i].u64);
  std::printf("],\"hi\":%lld,\"lo\":%lld,\"count\":%llu,\"ri_error\":%u,\"ram_sha256\":\"%s\",\"hidden_sha256\":\"%s\"}}\n",
    (long long)(int64_t)cpu.ipu.hi.u64,(long long)(int64_t)cpu.ipu.lo.u64,
    (unsigned long long)cpu.effectiveCount(),(u32)ri.io.error,ramHash.data(),hiddenHash.data());
  ares::Nintendo64::system.unload();
  return 0;
}
