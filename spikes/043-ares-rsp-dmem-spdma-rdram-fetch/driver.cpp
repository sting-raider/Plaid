/* SPDX-License-Identifier: ISC
 * Exact pinned-ares composed provenance fixture.
 */
#define main plaid_capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>
#include <vector>
#include "observer.hpp"

using namespace ares;
using namespace ares::Nintendo64;

#ifndef PLAID_COMPOSE_SENSOR
#define PLAID_COMPOSE_SENSOR 0
#endif

struct CaseResult {
  const char* name;
  u32 phase, target, initialWord, finalWord, t0, expectedRspSinks;
};
static std::vector<CaseResult> caseResults;

static void setObservers(bool enabled) {
#if PLAID_COMPOSE_SENSOR
  plaidRspInstructionObserver = enabled ? plaid_rsp_instruction : nullptr;
  plaidRspDmemObserver = enabled ? plaid_rsp_sink : nullptr;
  plaidRdramScalarObserver = enabled ? plaid_rdram : nullptr;
  plaidCpuFetchObserver = enabled ? plaid_fetch : nullptr;
#else
  (void)enabled;
#endif
}

static void clearDma() {
  rsp.dma.pending = {};
  rsp.dma.current = {};
  rsp.dma.busy = {};
  rsp.dma.full = {};
  rsp.dma.clock = 0;
}

static void setupCase(u32 phase, u32 initialWord, u32 target) {
  setObservers(false);
  plaidPhase = phase;
  clearDma();
  rsp.dmem.fill(0);
  rsp.imem.fill(0);
  rsp.dmem.write<Word>(0, initialWord);
  rsp.dmem.write<Word>(4, 0);
  rdram.ram.write<Dual>(target, 0, RBusDevice::ARES_DEBUGGER);
  // Uncached CPU store fixture: SW r9,0(r10), then NOP. This code is prepared
  // outside the measured phase so its debugger write cannot masquerade as provenance.
  rdram.ram.write<Word>(0x7000, 0xad490000, RBusDevice::ARES_DEBUGGER);
  rdram.ram.write<Word>(0x7004, 0x00000000, RBusDevice::ARES_DEBUGGER);
  for(auto& r : rsp.ipu.r) r.u32 = 0;
  for(auto& r : cpu.ipu.r) r.u64 = 0;
  cpu.scc.cause.exceptionCode = 0;
}

static void runRspStore(u32 instruction, u32 base, u32 rt) {
  rsp.ipu.r[1].u32 = base;
  rsp.ipu.r[2].u32 = rt;
  rsp.imem.write<Word>(0, instruction);
  rsp.imem.write<Word>(4, 0x0000000d); // BREAK
  rsp.pipeline = {};
  rsp.branch.setPc(0);
  rsp.ipu.pc = 0;
  rsp.status.halted = 0;
  for(u32 guard=0; guard<8 && !rsp.status.halted; guard++) rsp.instruction();
  if(!rsp.status.halted) std::abort();
}

static void reverseDma(u32 target) {
  rsp.writeWord(0x04040000, 0x000, cpu); // DMEM, offset 0
  rsp.writeWord(0x04040004, target, cpu);
  rsp.writeWord(0x0404000c, 0x000, cpu); // SP_WRITE_LENGTH, 8 bytes
  if(!rsp.dma.busy.write || (u32)rsp.dma.current.pbusRegion != 0 ||
     (u32)rsp.dma.current.pbusAddress != 0 || (u32)rsp.dma.current.dramAddress != target) std::abort();
  rsp.dmaTransferStep();
  if(rsp.dma.busy.any()) std::abort();
}

static void runCpuOverwrite(u32 target, u32 data) {
  cpu.ipu.r[9].u64 = data;
  cpu.ipu.r[10].u64 = 0xffffffffa0000000ull | target;
  cpu.scc.cause.exceptionCode = 0;
  cpu.pipeline.setPc(0xffffffffa0007000ull);
  if(cpu.instruction()) cpu.synchronize();
  if(cpu.scc.cause.exceptionCode != 0) std::abort();
}

static u32 fetchOne(u32 target) {
  cpu.ipu.r[8].u64 = 0;
  cpu.scc.cause.exceptionCode = 0;
  cpu.pipeline.setPc(0xffffffffa0000000ull | target);
  if(cpu.instruction()) cpu.synchronize();
  if(cpu.scc.cause.exceptionCode != 0) std::abort();
  return cpu.ipu.r[8].u32;
}

static string machineDigest() {
  std::vector<u64> words;
  auto add=[&](auto v){ words.push_back(u64(v)); };
  for(auto& r:cpu.ipu.r) add(r.u64);
  add(cpu.ipu.pc); add(cpu.ipu.hi.u64); add(cpu.ipu.lo.u64);
  for(auto& r:rsp.ipu.r) add(r.u32);
  add(rsp.ipu.pc); add(rsp.status.halted); add(rsp.status.broken);
  add(rsp.dma.busy.read); add(rsp.dma.busy.write); add(rsp.dma.full.read); add(rsp.dma.full.write);
  nall::Hash::SHA256 h;
  h.input(std::span<const u8>{reinterpret_cast<const u8*>(words.data()),words.size()*sizeof(u64)});
  h.input(std::span<const u8>{rdram.ram.data,rdram.ram.size});
  h.input(std::span<const u8>{rsp.dmem.data,rsp.dmem.size});
  h.input(std::span<const u8>{rsp.imem.data,rsp.imem.size});
  return h.digest();
}

static void finishCase(const char* name, u32 phase, u32 target, u32 initialWord,
                       u32 expectedWord, u32 expectedT0, u32 expectedRspSinks) {
  setObservers(false);
  u32 finalWord = rdram.ram.read<Word>(target, RBusDevice::ARES_DEBUGGER);
  if(finalWord != expectedWord || cpu.ipu.r[8].u32 != expectedT0) std::abort();
  caseResults.push_back({name,phase,target,initialWord,finalWord,cpu.ipu.r[8].u32,expectedRspSinks});
}

int main() {
  Headless frontend; platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid RSP DMEM reverse DMA provenance fixture");
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
  std::vector<u8> hidden(rdram.ram.size / 2); rdram.hidden.data = hidden.data();
  rdram.mapIdentity = 1;

  bool traced = PLAID_COMPOSE_SENSOR && !std::getenv("PLAID_COMPOSE_DISABLE");

  // Phase 1: a real decoded RSP SW creates the four instruction bytes.
  setupCase(1, 0x00000000, 0x6000);
  setObservers(traced);
  runRspStore(0xac220000, 0, 0x34081234); // SW r2,0(r1): ORI t0,zero,0x1234
  if(rsp.dmem.read<Word>(0) != 0x34081234) return 10;
  reverseDma(0x6000);
  if(fetchOne(0x6000) != 0x1234) return 11;
  finishCase("rsp_sw_dma_fetch",1,0x6000,0x00000000,0x34081234,0x1234,1);

  // Phase 2: two same-value RSP stores must remain two distinct writer contexts.
  setupCase(2, 0x34081234, 0x6100);
  setObservers(traced);
  runRspStore(0xac220000, 0, 0x34081234);
  runRspStore(0xac220000, 0, 0x34081234);
  reverseDma(0x6100);
  if(fetchOne(0x6100) != 0x1234) return 20;
  finishCase("same_value_latest_writer",2,0x6100,0x34081234,0x34081234,0x1234,2);

  // Phase 3: a one-byte RSP SB changes only the instruction's low immediate byte.
  setupCase(3, 0x34081234, 0x6200);
  setObservers(traced);
  runRspStore(0xa0220003, 0, 0x00000056); // SB r2,3(r1)
  if(rsp.dmem.read<Word>(0) != 0x34081256) return 30;
  reverseDma(0x6200);
  if(fetchOne(0x6200) != 0x1256) return 31;
  finishCase("partial_byte_lineage",3,0x6200,0x34081234,0x34081256,0x1256,1);

  // Phase 4: a decoded VR4300 uncached SW writes the same value after DMA.
  // The equal payload must still replace the DMA/RSP destination generation.
  setupCase(4, 0x00000000, 0x6300);
  setObservers(traced);
  runRspStore(0xac220000, 0, 0x34081234);
  reverseDma(0x6300);
  runCpuOverwrite(0x6300, 0x34081234);
  if(fetchOne(0x6300) != 0x1234) return 40;
  finishCase("same_value_cpu_overwrite",4,0x6300,0x00000000,0x34081234,0x1234,1);

  string digest = machineDigest();
  std::printf("{\"revision\":\"9408cb43d4948fc3ea6e152a307a34348df3fe04\",\"machine_sha256\":\"%s\",\"cases\":[",digest.data());
  for(size_t i=0;i<caseResults.size();i++) {
    auto& c=caseResults[i];
    std::printf("%s{\"name\":\"%s\",\"phase\":%u,\"target\":%u,\"source\":0,\"initial_word\":%u,\"final_word\":%u,\"t0\":%u,\"expected_rsp_sinks\":%u}",
      i?",":"",c.name,c.phase,c.target,c.initialWord,c.finalWord,c.t0,c.expectedRspSinks);
  }
  std::printf("]}\n");
  if(traced) plaid_print_history();
  else std::printf("{\"format\":\"plaid-rsp-dmem-spdma-rdram-fetch-v0\",\"rsp_instructions\":[],\"rsp_sinks\":[],\"rdram\":[],\"fetch\":[]}\n");

  setObservers(false);
  ares::Nintendo64::system.unload();
  return caseResults.size()==4 ? 0 : 70;
}
