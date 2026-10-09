/* SPDX-License-Identifier: ISC
 * Plaid research fixture: actual CPU-visible IMEM sinks -> SP write-DMA -> RDRAM.
 */
#define main plaid_capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>
#include <array>
#include <vector>

using namespace ares;
using namespace ares::Nintendo64;

#if PLAID_IMEM_EGRESS_SENSOR
#include "observer.hpp"
#endif

static auto digest_bytes(const u8* data, u32 size) -> string {
  return nall::Hash::SHA256(std::span<const u8>{data, size}).digest();
}

static auto logical_imem_digest() -> string {
  std::array<u8, 4096> bytes{};
  for(u32 address = 0; address < bytes.size(); address++) bytes[address] = rsp.imem.read<Byte>(address);
  return digest_bytes(bytes.data(), bytes.size());
}

static auto scoped_egress_digest() -> string {
  std::array<u8, 40> bytes{};
  for(u32 offset = 0; offset < 24; offset++) {
    bytes[offset] = rdram.ram.read<Byte>(0x1000 + offset, RBusDevice::ARES_DEBUGGER);
  }
  for(u32 offset = 0; offset < 16; offset++) {
    bytes[24 + offset] = rdram.ram.read<Byte>(0x2000 + offset, RBusDevice::ARES_DEBUGGER);
  }
  return digest_bytes(bytes.data(), bytes.size());
}

static auto machine_digest() -> string {
  std::vector<u64> words;
  auto add = [&](auto value) { words.push_back(u64(value)); };
  for(auto& r : cpu.ipu.r) add(r.u64);
  add(cpu.ipu.hi.u64); add(cpu.ipu.lo.u64); add(cpu.ipu.pc);
  for(auto& r : rsp.ipu.r) add(r.u32);
  add(rsp.ipu.pc); add(rsp.Thread::clock);
  add(rsp.branch.pc); add(rsp.branch.nextpc); add(rsp.branch.state); add(rsp.branch.nstate);
  for(auto& r : rsp.vpu.r) { add(r.u128.lo); add(r.u128.hi); }
  for(auto* r : {&rsp.vpu.acch,&rsp.vpu.accm,&rsp.vpu.accl,&rsp.vpu.vcoh,&rsp.vpu.vcol,&rsp.vpu.vcch,&rsp.vpu.vccl,&rsp.vpu.vce}) {
    add(r->u128.lo); add(r->u128.hi);
  }
  for(auto* d : {&rsp.dma.pending,&rsp.dma.current}) {
    add(d->pbusRegion); add(d->pbusAddress); add(d->dramAddress); add(d->length);
    add(d->skip); add(d->count); add(d->originPc); add(d->originCpu);
  }
  add(rsp.dma.busy.read); add(rsp.dma.busy.write); add(rsp.dma.full.read); add(rsp.dma.full.write); add(rsp.dma.clock);
  add(rsp.status.halted); add(rsp.status.broken); add(rsp.status.full); add(rsp.status.singleStep);
  nall::Hash::SHA256 hash;
  hash.input(std::span<const u8>{reinterpret_cast<const u8*>(words.data()), words.size() * sizeof(u64)});
  hash.input(std::span<const u8>{rdram.ram.data, rdram.ram.size});
  hash.input(std::span<const u8>{rsp.dmem.data, rsp.dmem.size});
  hash.input(std::span<const u8>{rsp.imem.data, rsp.imem.size});
  return hash.digest();
}

static auto set_phase(u32 phase) -> void {
#if PLAID_IMEM_EGRESS_SENSOR
  imemEgressPhase = phase;
#else
  (void)phase;
#endif
}

static auto cpu_imem_word(u32 phase, u32 offset, u32 value) -> void {
  set_phase(phase);
  rsp.writeWord(0x04001000 | (offset & 0xffc), value, cpu);
  if((u32)rsp.imem.read<Word>(offset) != value) std::abort();
}

static auto queue_write(u32 dram, u32 spAddress, u32 lengthRegister) -> void {
  rsp.writeWord(0x04040000, spAddress & 0x1ff8, cpu);
  rsp.writeWord(0x04040004, dram & 0xfffff8, cpu);
  rsp.writeWord(0x0404000c, lengthRegister, cpu);
  if(!rsp.dma.busy.write) std::abort();
  if((u32)rsp.dma.current.pbusRegion != ((spAddress >> 12) & 1)) std::abort();
  if((u32)rsp.dma.current.pbusAddress != (spAddress & 0xff8)) std::abort();
}

int main() {
  Headless frontend; platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid RSP IMEM DMA egress fixture");
  frontend.cartPak->setAttribute("region", "NTSC");
  frontend.cartPak->setAttribute("cic", "CIC-NUS-6102");
  frontend.cartPak->append("program.rom", 8192);
  Node::System root;
  if(!load(root, "[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak", "true");
  option("Deterministic Entropy", "true");
  option("Recompiler", "false");
  cartridgeSlot.port->allocate(); cartridgeSlot.port->connect();
  ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;

  std::vector<u8> hidden(rdram.ram.size / 2);
  rdram.hidden.data = hidden.data();
  rdram.mapIdentity = 1;
  std::memset(rdram.ram.data, 0, rdram.ram.size);

  for(u32 address = 0; address < 4096; address++) {
    rsp.imem.write<Byte>(address, u8((address * 29u + 7u) & 0xffu));
    rsp.dmem.write<Byte>(address, u8((address * 17u + 0x83u) & 0xffu));
  }
  // Deliberately make the wrapped DMEM bytes disagree with IMEM. If bank
  // identity were recomputed from wrapped pbusAddress, the second wrap fragment
  // below would expose these words instead of executable IMEM bytes.
  rsp.dmem.write<Word>(0x000, 0xfeedface);
  rsp.dmem.write<Word>(0x004, 0xc001d00d);
  auto initialImem = logical_imem_digest();

#if PLAID_IMEM_EGRESS_SENSOR
  if(!std::getenv("PLAID_IMEM_EGRESS_DISABLE")) {
    plaidSpWordObserver = imem_egress_spword;
    plaidRdramScalarObserver = imem_egress_rdram;
  }
#endif

  // Phase 1: a successful same-value executable-memory rewrite. Byte diffs see
  // nothing, but storage history must mint a fresh writer generation.
  u32 sameWord = (u32)rsp.imem.read<Word>(0x040);
  cpu_imem_word(1, 0x040, sameWord);

  // Phase 2: changed executable bytes in the rest of the first two DMA rows.
  cpu_imem_word(2, 0x044, 0x11223344);
  cpu_imem_word(2, 0x048, 0x55667788);
  cpu_imem_word(2, 0x04c, 0x99aabbcc);

  // Phase 3: equal-payload decoy. This 8-byte sequence exactly matches source
  // 0x040..0x047 but must never steal provenance from the descriptor-selected
  // source 0x040.
  cpu_imem_word(3, 0x080, sameWord);
  cpu_imem_word(3, 0x084, 0x11223344);

  // Two-row reverse DMA. Each row is 8 bytes; count=1 and skip=8 makes RDRAM
  // rows 0x1000 and 0x1010 while IMEM advances 0x040 -> 0x048.
  set_phase(100);
  queue_write(0x1000, 0x1040, (1u << 12) | (1u << 23));
  rsp.dmaTransferStep();
  if((u32)rsp.dma.current.count != 0 || (u32)rsp.dma.current.dramAddress != 0x1010 ||
     (u32)rsp.dma.current.pbusAddress != 0x048 || !(u32)rsp.dma.current.pbusRegion) return 20;
  rsp.dmaTransferStep();
  if(rsp.dma.busy.any()) return 21;

  // Phase 4: install distinct executable bytes at both sides of the 12-bit
  // source-offset wrap. The bank bit remains a separate descriptor field.
  cpu_imem_word(4, 0xff8, 0xdeadbeef);
  cpu_imem_word(4, 0xffc, 0x01234567);
  cpu_imem_word(4, 0x000, 0x89abcdef);
  cpu_imem_word(4, 0x004, 0x13579bdf);

  set_phase(200);
  queue_write(0x2000, 0x1ff8, 0x008);  // 16 bytes: IMEM 0xff8 then IMEM 0x000.
  rsp.dmaTransferStep();
  if(rsp.dma.busy.any() || (u32)rsp.dma.current.pbusAddress != 0x008 ||
     !(u32)rsp.dma.current.pbusRegion) return 30;

  auto finalImem = logical_imem_digest();
  auto finalRam = digest_bytes(rdram.ram.data, rdram.ram.size);
  auto egressHash = scoped_egress_digest();
  auto finalMachine = machine_digest();

  std::printf("{\"state\":{\"initial_imem_sha256\":\"%s\",\"imem_sha256\":\"%s\",\"rdram_sha256\":\"%s\",\"egress_sha256\":\"%s\",\"rdram_bytes\":%u,\"machine_sha256\":\"%s\",\"dmem_wrap\":[%u,%u],\"multi\":[%u,%u,%u,%u],\"wrap\":[%u,%u,%u,%u]},\"events\":",
    initialImem.data(), finalImem.data(), finalRam.data(), egressHash.data(), rdram.ram.size, finalMachine.data(),
    (u32)rsp.dmem.read<Word>(0x000), (u32)rsp.dmem.read<Word>(0x004),
    (u32)rdram.ram.read<Word>(0x1000, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x1004, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x1010, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x1014, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x2000, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x2004, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x2008, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x200c, RBusDevice::ARES_DEBUGGER));
#if PLAID_IMEM_EGRESS_SENSOR
  imem_egress_print_events();
#else
  std::printf("[]");
#endif
  std::printf("}\n");

  ares::Nintendo64::system.unload();
  return 0;
}
