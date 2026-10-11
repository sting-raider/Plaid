/* SPDX-License-Identifier: ISC
 * Plaid research fixture: actual decoded RSP DMEM stores -> SP write-DMA -> RDRAM.
 */
#define main plaid_capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>
#include <array>
#include <vector>

using namespace ares;
using namespace ares::Nintendo64;

#if PLAID_EGRESS_SENSOR
#include "observer.hpp"
#endif

static auto digest_bytes(const u8* data, u32 size) -> string {
  return nall::Hash::SHA256(std::span<const u8>{data, size}).digest();
}

static auto logical_dmem_digest() -> string {
  std::array<u8, 4096> bytes{};
  for(u32 address = 0; address < bytes.size(); address++) {
    bytes[address] = rsp.dmem.read<Byte>(address);
  }
  return digest_bytes(bytes.data(), bytes.size());
}

static auto scoped_egress_digest() -> string {
  // Hash logical guest bytes, not ares' host-endian backing layout. Pinned N64
  // ares uses the lsb memory wrapper, where guest Byte addresses are XORed by 3.
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
#if PLAID_EGRESS_SENSOR
  egressPhase = phase;
#else
  (void)phase;
#endif
}

static auto execute_store(u32 phase, u32 instruction, u32 base, bool scalar, u32 scalarValue = 0) -> void {
  set_phase(phase);
  for(auto& r : rsp.ipu.r) r.u32 = 0;
  rsp.ipu.r[1].u32 = base;
  if(scalar) rsp.ipu.r[2].u32 = scalarValue;
  if(!scalar) {
    for(u32 byte = 0; byte < 16; byte++) rsp.vpu.r[2].byte(byte) = u8(0xa0 + byte);
  }
  rsp.imem.write<Word>(0x000, instruction);
  rsp.imem.write<Word>(0x004, 0x0000000d);  // BREAK
  rsp.pipeline = {};
  rsp.branch.setPc(0);
  rsp.ipu.pc = 0;
  rsp.status.halted = 0;
  for(u32 guard = 0; guard < 8 && !rsp.status.halted; guard++) rsp.instruction();
  if(!rsp.status.halted) std::abort();
}

static auto queue_write(u32 dram, u32 dmem, u32 lengthRegister) -> void {
  rsp.writeWord(0x04040000, dmem & 0xff8, cpu);
  rsp.writeWord(0x04040004, dram & 0xfffff8, cpu);
  rsp.writeWord(0x0404000c, lengthRegister, cpu);
  if(!rsp.dma.busy.write || rsp.dma.current.pbusRegion) std::abort();
}

int main() {
  Headless frontend; platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid RSP DMEM DMA egress fixture");
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
  rsp.imem.fill(0);
  for(u32 address = 0; address < 4096; address++) {
    rsp.dmem.write<Byte>(address, u8((address * 37u + 11u) & 0xffu));
  }
  auto initialDmem = logical_dmem_digest();

#if PLAID_EGRESS_SENSOR
  if(!std::getenv("PLAID_EGRESS_DISABLE")) {
    plaidRspInstructionObserver = egress_instruction;
    plaidRspDmemObserver = egress_dmem;
    plaidRdramScalarObserver = egress_rdram;
  }
#endif

  // Phase 1: same-value scalar store. Storage effect is real even though bytes do not change.
  u8 same = rsp.dmem.read<Byte>(0x040);
  execute_store(1, 0xa0220000, 0x040, true, same);  // SB r2,0(r1)

  // Phase 2: ordinary four-byte RSP producer.
  execute_store(2, 0xac220000, 0x044, true, 0x11223344);  // SW

  // Phase 3: vector producer. SDV subtype=3, base=r1, vt=v2, element=0, imm=0.
  u32 sdv = (58u << 26) | (1u << 21) | (2u << 16) | (3u << 11);
  execute_store(3, sdv, 0x048, false);

  // Phase 4: an actual CPU-origin SP-memory write replaces only the covered lineage.
  set_phase(4);
#if PLAID_EGRESS_SENSOR
  egressCpuScope = true;
#endif
  rsp.writeWord(0x0400004c, 0x55667788, cpu);
#if PLAID_EGRESS_SENSOR
  egressCpuScope = false;
#endif

  // Multi-row SP write-DMA: source 0x040..0x04f; destination rows are
  // 0x1000..0x1007 and 0x1010..0x1017 because skip=8.
  set_phase(100);
  queue_write(0x1000, 0x040, (1u << 12) | (1u << 23));
  rsp.dmaTransferStep();
  if((u32)rsp.dma.current.count != 0 || (u32)rsp.dma.current.dramAddress != 0x1010 || (u32)rsp.dma.current.pbusAddress != 0x048) return 20;
  rsp.dmaTransferStep();
  if(rsp.dma.busy.any()) return 21;

  // Phase 5: an unaligned scalar SW crosses the DMEM modulo-bank boundary.
  execute_store(5, 0xac220000, 0x0ffe, true, 0xa1b2c3d4);

  // One 16-byte write-DMA starts at 0xff8 and wraps its source to 0x000.
  set_phase(200);
  queue_write(0x2000, 0xff8, 0x008);
  rsp.dmaTransferStep();
  if(rsp.dma.busy.any() || (u32)rsp.dma.current.pbusAddress != 0x008) return 30;

  auto finalDmem = logical_dmem_digest();
  auto finalRam = digest_bytes(rdram.ram.data, rdram.ram.size);
  auto egressHash = scoped_egress_digest();
  auto finalMachine = machine_digest();

  std::printf("{\"state\":{\"initial_dmem_sha256\":\"%s\",\"dmem_sha256\":\"%s\",\"rdram_sha256\":\"%s\",\"egress_sha256\":\"%s\",\"rdram_bytes\":%u,\"machine_sha256\":\"%s\",\"multi\":[%u,%u,%u,%u],\"wrap\":[%u,%u,%u,%u]},\"events\":",
    initialDmem.data(), finalDmem.data(), finalRam.data(), egressHash.data(), rdram.ram.size, finalMachine.data(),
    (u32)rdram.ram.read<Word>(0x1000, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x1004, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x1010, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x1014, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x2000, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x2004, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x2008, RBusDevice::ARES_DEBUGGER),
    (u32)rdram.ram.read<Word>(0x200c, RBusDevice::ARES_DEBUGGER));
#if PLAID_EGRESS_SENSOR
  egress_print_events();
#else
  std::printf("[]");
#endif
  std::printf("}\n");

  ares::Nintendo64::system.unload();
  return 0;
}
