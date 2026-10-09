/* SPDX-License-Identifier: ISC
 * Exact pinned-ares fixture for decoded CPU producer -> SP Word sink context.
 */
#include <n64/n64.hpp>
#include <cstdio>
#include <cstring>
#include <memory>
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

static constexpr u32 CODE_PA = 0x6000;
static constexpr u64 CODE_VA = 0xffffffffa0006000ull;
static constexpr u64 IMEM = 0xffffffffa4001000ull;

struct Context {
  u32 phase = 0, instruction = 0, rs = 0, rt = 0, gpr = 0;
  u64 pc = 0, fprEven = 0, fprNamed = 0;
  bool fr = false;
};
struct Event {
  u32 ordinal, phase, instruction, rs, rt, gpr, address, bank, offset, value;
  u64 pc, fprEven, fprNamed;
  bool fr;
};
struct Outcome { u32 phase, exception, copError; };

static Context active;
static std::vector<Event> events;
static std::vector<Outcome> outcomes;
static bool tracing = false;

static void spWord(bool write, u32 address, u32 bank, u32 offset, u32 value, bool originCpu) {
  if(!tracing || !write || !originCpu) return;
  events.push_back({(u32)events.size()+1, active.phase, active.instruction, active.rs, active.rt,
    active.gpr, address, bank, offset, value, active.pc, active.fprEven, active.fprNamed, active.fr});
}

static u32 encode(u32 op, u32 rs, u32 rt, s16 imm) {
  return (op << 26) | (rs << 21) | (rt << 16) | u16(imm);
}

static void clearException() {
  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.cause.exceptionCode = 0;
  cpu.scc.cause.coprocessorError = 0;
  cpu.scc.cause.branchDelay = 0;
  cpu.scc.badVirtualAddress = 0;
  cpu.scc.sysadFrozen = false;
  cpu.context.setMode();
}

static void execute(u32 phase, u32 instruction) {
  clearException();
  rdram.ram.write<Word>(CODE_PA, instruction, RBusDevice::ARES_DEBUGGER);
  cpu.pipeline.setPc(CODE_VA);
  u32 rt = instruction >> 16 & 31;
  active.phase = phase;
  active.pc = CODE_VA;
  active.instruction = instruction;
  active.rs = instruction >> 21 & 31;
  active.rt = rt;
  active.gpr = cpu.ipu.r[rt].u32;
  active.fprEven = cpu.fpu.r[rt & ~1].u64;
  active.fprNamed = cpu.fpu.r[rt].u64;
  active.fr = cpu.scc.status.floatingPointMode;
  if(cpu.instruction()) {
    active = {};
    cpu.synchronize();
  } else active = {};
  outcomes.push_back({phase, (u32)cpu.scc.cause.exceptionCode, (u32)cpu.scc.cause.coprocessorError});
}

static void printBytes() {
  std::printf("[");
  for(u32 i=0;i<16;i++) std::printf("%s%u", i ? "," : "", (u32)rsp.imem.read<Byte>(i));
  std::printf("]");
}

int main(int argc, char** argv) {
  if(argc != 2 || (std::strcmp(argv[1], "disabled") && std::strcmp(argv[1], "enabled"))) return 2;
  bool enabled = !std::strcmp(argv[1], "enabled");
  Headless frontend; platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid CPU SP producer context research");
  frontend.cartPak->setAttribute("region", "NTSC");
  frontend.cartPak->setAttribute("cic", "CIC-NUS-6102");
  frontend.cartPak->append("program.rom", 8192);
  Node::System root;
  if(!load(root, "[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak", "true"); option("Deterministic Entropy", "true"); option("Recompiler", "false");
  cartridgeSlot.port->allocate(); cartridgeSlot.port->connect();
  ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;
  std::vector<u8> hidden(rdram.ram.size / 2); rdram.hidden.data = hidden.data(); rdram.mapIdentity = 1;
  cpu.context.endian = CPU::Context::Endian::Big;
  cpu.icache.power(false); cpu.dcache.power(false);
  for(auto& r : cpu.ipu.r) r.u64 = 0;
  for(auto& r : cpu.fpu.r) r.u64 = 0;
  for(u32 i=0;i<16;i++) rsp.imem.write<Byte>(i, 0xa0+i);
  tracing = enabled; plaidSpWordObserver = enabled ? spWord : nullptr;

  // Same PC, same instruction, same payload twice: distinct causal contexts.
  cpu.ipu.r[1].u64 = IMEM; cpu.ipu.r[2].u64 = 0x1122334455667788ull;
  execute(1, encode(0x2b, 1, 2, 0)); // SW
  cpu.ipu.r[1].u64 = IMEM; cpu.ipu.r[2].u64 = 0x1122334455667788ull;
  execute(2, encode(0x2b, 1, 2, 0));

  // Equal-address/value CPU write outside any decoded-instruction context.
  clearException(); active = {};
  auto decoy = cpu.write<Word>(IMEM, 0x55667788u);
  if(!decoy) return 5;

  // SB +1 proves the actual SP sink is a widened Word carrying upper GPR bytes.
  cpu.ipu.r[1].u64 = IMEM; cpu.ipu.r[2].u64 = 0x1122334455667788ull;
  execute(3, encode(0x28, 1, 2, 1)); // SB

  // SWC1: FR=0 even, FR=0 odd, then FR=1 odd.
  cpu.scc.status.enable.coprocessor1 = 1;
  cpu.fpu.r[0].u64 = 0x1122334455667788ull;
  cpu.fpu.r[1].u64 = 0x99aabbccddeeff00ull;
  cpu.ipu.r[1].u64 = IMEM + 4; cpu.scc.status.floatingPointMode = 0;
  execute(4, encode(0x39, 1, 0, 0));
  cpu.ipu.r[1].u64 = IMEM + 8; cpu.scc.status.floatingPointMode = 0;
  execute(5, encode(0x39, 1, 1, 0));
  cpu.ipu.r[1].u64 = IMEM + 12; cpu.scc.status.floatingPointMode = 1;
  execute(6, encode(0x39, 1, 1, 0));

  // CU1-disabled decoded SWC1 must not reach the SP sink.
  cpu.scc.status.enable.coprocessor1 = 0; cpu.scc.status.floatingPointMode = 1;
  cpu.ipu.r[1].u64 = IMEM;
  execute(7, encode(0x39, 1, 1, 0));

  tracing = false; plaidSpWordObserver = nullptr;
  std::printf("{\"mode\":\"%s\",\"events\":[", argv[1]);
  for(size_t i=0;i<events.size();i++) {
    auto& e=events[i];
    std::printf("%s{\"ordinal\":%u,\"phase\":%u,\"pc\":%llu,\"instruction\":%u,\"rs\":%u,\"rt\":%u,\"gpr\":%u,\"fpr_even\":%llu,\"fpr_named\":%llu,\"fr\":%s,\"address\":%u,\"bank\":%u,\"offset\":%u,\"value\":%u}",
      i ? "," : "", e.ordinal,e.phase,(unsigned long long)e.pc,e.instruction,e.rs,e.rt,e.gpr,
      (unsigned long long)e.fprEven,(unsigned long long)e.fprNamed,e.fr?"true":"false",
      e.address,e.bank,e.offset,e.value);
  }
  std::printf("],\"outcomes\":[");
  for(size_t i=0;i<outcomes.size();i++) std::printf("%s{\"phase\":%u,\"exception\":%u,\"cop_error\":%u}",i?",":"",outcomes[i].phase,outcomes[i].exception,outcomes[i].copError);
  std::printf("],\"facts\":{\"imem\":"); printBytes();
  std::printf(",\"pc\":%llu,\"count\":%llu,\"exception\":%u,\"cop_error\":%u,\"r1\":%llu,\"r2\":%llu,\"f0\":%llu,\"f1\":%llu}}\n",
    (unsigned long long)cpu.ipu.pc,(unsigned long long)cpu.effectiveCount(),(u32)cpu.scc.cause.exceptionCode,(u32)cpu.scc.cause.coprocessorError,
    (unsigned long long)cpu.ipu.r[1].u64,(unsigned long long)cpu.ipu.r[2].u64,
    (unsigned long long)cpu.fpu.r[0].u64,(unsigned long long)cpu.fpu.r[1].u64);
  ares::Nintendo64::system.unload();
  return 0;
}
