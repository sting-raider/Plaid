/* SPDX-License-Identifier: ISC
 * Exact pinned-ares experiment: synchronized restore of RSP executable state
 * across later SP-DMA/direct-write provenance generations.
 */
#define main capability_fixture_main
#include "../../spikes/003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

using namespace ares;
using namespace ares::Nintendo64;

static constexpr u32 ImemPc = 0x200;
static constexpr u64 ImageA = 0x2401000124020002ull;
static constexpr u64 ImageB = 0x2401000324020004ull;
static constexpr u32 InstA0 = 0x24010001;
static constexpr u32 InstA1 = 0x24020002;
static constexpr u32 InstB0 = 0x24010003;

struct InstallRecord {
  u64 generation;
  std::string hash;
};

static auto digestImem() -> std::string {
  return nall::Hash::SHA256(std::span<const u8>{rsp.imem.data, rsp.imem.size}).digest().data();
}

static auto clearDma() -> void {
  rsp.dma.pending = {};
  rsp.dma.current = {};
  rsp.dma.busy = {};
  rsp.dma.full = {};
  rsp.dma.clock = 0;
  rsp.clock = 0;
  cpu.clock = 0;
}

static auto put64(u32 address, u64 value) -> void {
  rdram.ram.write<Dual>(address, value, RBusDevice::ARES_DEBUGGER);
}

static auto queueRead(u32 dram, u32 imem) -> void {
  rsp.writeWord(0x04040000, 0x1000 | (imem & 0xff8), cpu);
  rsp.writeWord(0x04040004, dram & 0xfffff8, cpu);
  rsp.writeWord(0x04040008, 0x000, cpu);
}

static auto installImage(u32 dram, u32 imem, u64 image) -> void {
  clearDma();
  put64(dram, image);
  queueRead(dram, imem);
  if(!rsp.dma.busy.any()) std::abort();
  rsp.dmaTransferStep();
  if(rsp.dma.busy.any() || rsp.dma.full.any()) std::abort();
}

static auto fetchOne(u32 pc) -> u32 {
  rsp.pipeline = {};
  rsp.branch.setPc(pc);
  rsp.ipu.pc = pc;
  rsp.status.halted = 0;
  rsp.instruction();
  return rsp.pipeline.instruction;
}

static auto stateSignature() -> std::string {
  char out[256];
  std::snprintf(out, sizeof(out), "%u:%u:%u:%u:%u:%u",
    (u32)rsp.ipu.pc,
    (u32)rsp.pipeline.address,
    (u32)rsp.pipeline.instruction,
    rsp.ipu.r[1].u32,
    rsp.ipu.r[2].u32,
    rsp.ipu.r[7].u32);
  return out;
}

int main() {
  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid RSP savestate microcode epoch fixture");
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

  u64 installGeneration = 0;
  u64 writerGeneration = 0;
  u64 restoreEpoch = 0;
  std::vector<InstallRecord> installs;

  // S0: establish one genuine completed RDRAM -> IMEM SP-DMA installation.
  installImage(0x1000, ImemPc, ImageA);
  installGeneration++; writerGeneration++;
  installs.push_back({installGeneration, digestImem()});
  if(rsp.imem.read<Word>(ImemPc) != InstA0 || rsp.imem.read<Word>(ImemPc + 4) != InstA1) return 5;
  if(fetchOne(ImemPc) != InstA0) return 6;
  rsp.ipu.r[7].u32 = 0x11111111;
  const std::string s0Hash = digestImem();
  const std::string s0State = stateSignature();
  const u32 s0Word0 = rsp.imem.read<Word>(ImemPc);
  const u32 s0Word1 = rsp.imem.read<Word>(ImemPc + 4);
  auto saved = ares::Nintendo64::system.serialize(true);

  // Abandoned S1 future: replace executable IMEM and execution state.
  installImage(0x2000, ImemPc, ImageB);
  installGeneration++; writerGeneration++;
  installs.push_back({installGeneration, digestImem()});
  if(rsp.imem.read<Word>(ImemPc) != InstB0 || fetchOne(ImemPc) != InstB0) return 7;
  rsp.ipu.r[7].u32 = 0x22222222;
  if(digestImem() == s0Hash || stateSignature() == s0State) return 8;

  // Restore S0. Local provenance counters intentionally live outside ares
  // serialization and therefore must not silently rewind or receive replay.
  const u64 installBeforeRestore1 = installGeneration;
  const u64 writerBeforeRestore1 = writerGeneration;
  serializer replay1(saved.data(), saved.size());
  if(!ares::Nintendo64::system.unserialize(replay1)) return 9;
  restoreEpoch++;
  if(installGeneration != installBeforeRestore1 || writerGeneration != writerBeforeRestore1) return 10;
  if(digestImem() != s0Hash || stateSignature() != s0State) return 11;
  if(rsp.imem.read<Word>(ImemPc) != s0Word0 || rsp.imem.read<Word>(ImemPc + 4) != s0Word1) return 12;
  if(fetchOne(ImemPc) != InstA0) return 13;

  // Strong equality adversary: mint a later byte-identical completed install.
  installImage(0x3000, ImemPc, ImageA);
  installGeneration++; writerGeneration++;
  installs.push_back({installGeneration, digestImem()});
  if(digestImem() != s0Hash || fetchOne(ImemPc) != InstA0) return 14;
  rsp.ipu.r[7].u32 = 0x11111111;

  // Then mint an even later same-value direct writer to the first IMEM word.
  rsp.writeWord(0x04001000 | ImemPc, InstA0, cpu);
  writerGeneration++;
  if(rsp.imem.read<Word>(ImemPc) != InstA0 || digestImem() != s0Hash) return 15;
  const bool equalStateBeforeRestore2 = stateSignature() == s0State;
  if(!equalStateBeforeRestore2) return 16;

  const u64 installBeforeRestore2 = installGeneration;
  const u64 writerBeforeRestore2 = writerGeneration;
  serializer replay2(saved.data(), saved.size());
  if(!ares::Nintendo64::system.unserialize(replay2)) return 17;
  restoreEpoch++;
  if(installGeneration != installBeforeRestore2 || writerGeneration != writerBeforeRestore2) return 18;
  if(digestImem() != s0Hash || stateSignature() != s0State) return 19;

  // Deliberately naive value-based matchers. They return abandoned-future
  // generations even though deserialization installed the post-load state.
  u64 naiveLatestMatchingInstall = 0;
  const std::string restoredHash = digestImem();
  for(const auto& rec : installs) if(rec.hash == restoredHash) naiveLatestMatchingInstall = rec.generation;
  const u64 naiveLatestMatchingWriter = writerGeneration;
  if(naiveLatestMatchingInstall != 3 || naiveLatestMatchingWriter != 4) return 20;
  if(fetchOne(ImemPc) != InstA0) return 21;

  std::printf("{\"external_generations\":{\"install\":%llu,\"writer\":%llu,\"restore_epoch\":%llu},",
    (unsigned long long)installGeneration,
    (unsigned long long)writerGeneration,
    (unsigned long long)restoreEpoch);
  std::printf("\"naive\":{\"latest_matching_install\":%llu,\"latest_matching_writer\":%llu},",
    (unsigned long long)naiveLatestMatchingInstall,
    (unsigned long long)naiveLatestMatchingWriter);
  std::printf("\"state\":{\"s0_install_generation\":1,\"imem_word0\":%u,\"imem_word1\":%u,\"imem_sha256\":\"%s\",\"distinct_rollback\":true,\"equal_state_before_second_restore\":%s,\"equal_state_restore\":true,\"post_restore_fetch\":%u}}\n",
    rsp.imem.read<Word>(ImemPc),
    rsp.imem.read<Word>(ImemPc + 4),
    restoredHash.c_str(),
    equalStateBeforeRestore2 ? "true" : "false",
    InstA0);

  ares::Nintendo64::system.unload();
  return 0;
}
