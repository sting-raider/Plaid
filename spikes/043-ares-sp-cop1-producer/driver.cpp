/* SPDX-License-Identifier: ISC
 * Exact-pinned-ares fixture for VR4300 SWC1 -> SP DMEM/IMEM producer lineage.
 */
#ifndef PLAID_SP_SENSOR
#define PLAID_SP_SENSOR 0
#endif
#include <n64/n64.hpp>
#include <nall/hash/sha256.hpp>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <string>
#include <vector>
using namespace ares;
using namespace ares::Nintendo64;

struct Headless : ares::Platform {
  std::shared_ptr<vfs::directory> systemPak = std::make_shared<vfs::directory>();
  std::shared_ptr<vfs::directory> cartPak = std::make_shared<vfs::directory>();
  auto pak(Node::Object node) -> std::shared_ptr<vfs::directory> override {
    return node->name() == "Nintendo 64 Cartridge" ? cartPak : systemPak;
  }
};

static constexpr u32 CODE = 0x6000;
static constexpr u64 CODE_VA = 0xffffffffa0006000ull;
static constexpr u64 DMEM_VA = 0xffffffffa4000000ull;
static constexpr u64 IMEM_VA = 0xffffffffa4001000ull;
static constexpr u64 FPRS[4] = {
  0x1122334455667788ull,
  0x99aabbccddeeff00ull,
  0xaabbccdd55667788ull,
  0x13579bdf2468ace0ull,
};

struct Phase {
  u32 phase, instruction;
  u64 pc, vaddr;
  u32 fr, rt9, exception;
  bool frozen;
};
struct Event {
  u64 ordinal;
  u32 phase, address, bank, offset, value;
  bool write, cpu;
};
static std::vector<Phase> phases;
static std::vector<Event> events;
static u32 currentPhase = 0;
static bool sensorEnabled = false;

#if PLAID_SP_SENSOR
static void sp_word(bool write, u32 address, u32 bank, u32 offset, u32 value, bool originCpu) {
  if(!sensorEnabled) return;
  events.push_back({events.size() + 1, currentPhase, address, bank, offset, value, write, originCpu});
}
#endif

static std::string hash(const u8* data, u32 size) {
  return std::string(nall::Hash::SHA256(std::span<const u8>{data,size}).digest().data());
}
static u32 swc1(u32 ft, s16 imm = 0) { return (0x39u << 26) | (16u << 21) | (ft << 16) | (u16)imm; }
static u32 sw(u32 rt, s16 imm = 0) { return (0x2bu << 26) | (16u << 21) | (rt << 16) | (u16)imm; }

static void clear_control() {
  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.cause.exceptionCode = 0;
  cpu.scc.cause.coprocessorError = 0;
  cpu.scc.cause.branchDelay = 0;
  cpu.scc.badVirtualAddress = 0;
  cpu.scc.sysadFrozen = false;
  cpu.context.setMode();
  cpu.context.endian = CPU::Context::Big;
}

static void step(u32 phase, u32 instruction, u64 base, u32 fr, bool cu1, u32 rt9 = 0) {
  clear_control();
  cpu.scc.status.enable.coprocessor1 = cu1;
  cpu.scc.status.floatingPointMode = fr;
  cpu.ipu.r[16].u64 = base;
  cpu.ipu.r[9].u64 = rt9;
  u32 paddr = CODE + (phase - 1) * 4;
  u64 pc = CODE_VA + (phase - 1) * 4;
  rdram.ram.write<Word>(paddr, instruction, RBusDevice::ARES_DEBUGGER);
  currentPhase = phase;
  cpu.pipeline.setPc(pc);
  if(cpu.instruction()) cpu.synchronize();
  phases.push_back({phase, instruction, pc, base + (s16)(instruction & 0xffff), fr, rt9,
                    (u32)cpu.scc.cause.exceptionCode, (bool)cpu.scc.sysadFrozen});
}

static void init_memory() {
  for(u32 n=0;n<0x100;n+=4) {
    rsp.dmem.write<Word>(n, 0xd0000000u | n);
    rsp.imem.write<Word>(n, 0xe0000000u | n);
  }
  for(auto& r : cpu.ipu.r) r.u64 = 0;
  for(auto& r : cpu.fpu.r) r.u64 = 0;
  for(u32 n=0;n<4;n++) cpu.fpu.r[n].u64 = FPRS[n];
  cpu.icache.power(false);
  cpu.dcache.power(false);
}

static void run_matrix() {
  step(1, swc1(0), DMEM_VA + 0x00, 0, true);
  step(2, swc1(1), DMEM_VA + 0x04, 0, true);
  step(3, swc1(1), DMEM_VA + 0x08, 1, true);
  step(4, swc1(1), IMEM_VA + 0x00, 0, true);
  step(5, swc1(1), IMEM_VA + 0x04, 1, true);
  step(6, swc1(3), IMEM_VA + 0x08, 0, true);
  step(7, swc1(0), DMEM_VA + 0x20, 1, true);
  step(8, swc1(2), DMEM_VA + 0x20, 1, true);
  step(9, swc1(0), DMEM_VA + 0x24, 1, true);
  step(10, sw(9), DMEM_VA + 0x24, 1, true, 0x55667788u);
  step(11, swc1(2), DMEM_VA + 0x28, 1, true);
}

static void run_single(const char* scenario) {
  if(!std::strcmp(scenario, "cu1off")) { step(1, swc1(1), DMEM_VA + 0x40, 1, false); return; }
  if(!std::strcmp(scenario, "misalign")) { step(1, swc1(1), DMEM_VA + 0x41, 1, true); return; }
  if(!std::strcmp(scenario, "tlbmiss")) { step(1, swc1(1), 0x2000ull, 1, true); return; }
  if(!std::strcmp(scenario, "status")) {
    step(1, swc1(1), 0xffffffffa4040014ull, 1, true);
    return;
  }
  std::abort();
}

int main(int argc, char** argv) {
  if(argc != 3) return 2;
  bool enable = !std::strcmp(argv[1], "enabled");
  if(std::strcmp(argv[1], "enabled") && std::strcmp(argv[1], "disabled")) return 2;
  const char* scenario = argv[2];
  if(std::strcmp(scenario,"matrix") && std::strcmp(scenario,"cu1off") &&
     std::strcmp(scenario,"misalign") && std::strcmp(scenario,"tlbmiss") &&
     std::strcmp(scenario,"status")) return 2;

  Headless frontend; platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid SP COP1 producer research");
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
  std::vector<u8> hidden(rdram.ram.size / 2); rdram.hidden.data = hidden.data(); rdram.mapIdentity = 1;
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;
  init_memory(); clear_control();
#if PLAID_SP_SENSOR
  sensorEnabled = enable;
  plaidSpWordObserver = enable ? sp_word : nullptr;
#else
  (void)enable;
#endif

  if(!std::strcmp(scenario,"matrix")) run_matrix(); else run_single(scenario);
#if PLAID_SP_SENSOR
  plaidSpWordObserver = nullptr; sensorEnabled = false;
#endif

  std::printf("{\"scenario\":\"%s\",\"events\":[", scenario);
  for(size_t i=0;i<events.size();i++) {
    auto& e=events[i];
    std::printf("%s{\"ordinal\":%llu,\"phase\":%u,\"address\":%u,\"bank\":%u,\"offset\":%u,\"value\":%u,\"write\":%s,\"cpu\":%s}",
      i ? "," : "", (unsigned long long)e.ordinal, e.phase, e.address, e.bank, e.offset, e.value,
      e.write ? "true" : "false", e.cpu ? "true" : "false");
  }
  std::printf("],\"phases\":[");
  for(size_t i=0;i<phases.size();i++) {
    auto& p=phases[i];
    std::printf("%s{\"phase\":%u,\"instruction\":%u,\"pc\":%llu,\"vaddr\":%llu,\"fr\":%u,\"rt9\":%u,\"exception\":%u,\"frozen\":%s}",
      i ? "," : "", p.phase,p.instruction,(unsigned long long)p.pc,(unsigned long long)p.vaddr,p.fr,p.rt9,p.exception,p.frozen ? "true" : "false");
  }
  std::printf("],\"state\":{\"dmem_sha256\":\"%s\",\"imem_sha256\":\"%s\",\"rdram_sha256\":\"%s\",\"exception\":%u,\"frozen\":%s}}\n",
    hash(rsp.dmem.data,rsp.dmem.size).c_str(),hash(rsp.imem.data,rsp.imem.size).c_str(),hash(rdram.ram.data,rdram.ram.size).c_str(),
    (u32)cpu.scc.cause.exceptionCode,cpu.scc.sysadFrozen ? "true" : "false");
  ares::Nintendo64::system.unload();
  return 0;
}
