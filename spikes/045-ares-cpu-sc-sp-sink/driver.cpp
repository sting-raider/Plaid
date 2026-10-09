/* SPDX-License-Identifier: ISC
 * Exact pinned-ares fixture for VR4300 SC -> CPU-visible SP DMEM/IMEM sinks.
 */
#ifndef PLAID_SC_SP_SENSOR
#define PLAID_SC_SP_SENSOR 1
#endif
#include <n64/n64.hpp>
#include <nall/hash/sha256.hpp>
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

static constexpr u32 CodePA = 0x6000;
static constexpr u64 CodeVA = 0xffffffffa0006000ull;
static constexpr u64 DmemVA = 0xffffffffa4000000ull;
static constexpr u64 ImemVA = 0xffffffffa4001000ull;
static constexpr u32 Initial = 0x11223344u;

struct Active {
  u32 caseId = 0;
  u64 pc = 0;
  u32 instruction = 0;
  u32 preRt = 0;
  bool llbitBefore = false;
};
struct SinkEvent {
  u32 ordinal, caseId, address, bank, offset, value, instruction, preRt;
  u64 pc;
  bool llbitBefore;
};
struct CaseFact {
  u32 id, bank;
  const char* kind;
  u32 initial, source, final, result, exception;
  u64 badva;
  bool llbitAfter;
  string digest;
};

static Active active;
static std::vector<SinkEvent> events;
static bool tracing = false;

#if PLAID_SC_SP_SENSOR
static void spWord(bool write, u32 address, u32 bank, u32 offset, u32 value, bool originCpu) {
  if(!tracing || !write || !originCpu) return;
  events.push_back({(u32)events.size() + 1, active.caseId, address, bank, offset, value,
    active.instruction, active.preRt, active.pc, active.llbitBefore});
}
#endif

static u32 encodeI(u32 op, u32 rs, u32 rt, s16 imm) {
  return op << 26 | rs << 21 | rt << 16 | u16(imm);
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

static void putCode(u32 instruction) {
  rdram.ram.write<Word>(CodePA, instruction, RBusDevice::ARES_DEBUGGER);
}

static void execute(u32 caseId, u32 instruction) {
  putCode(instruction);
  cpu.pipeline.setPc(CodeVA);
  active.caseId = caseId;
  active.pc = CodeVA;
  active.instruction = instruction;
  active.preRt = cpu.ipu.r[instruction >> 16 & 31].u32;
  active.llbitBefore = cpu.scc.llbit;
  if(cpu.instruction()) cpu.synchronize();
  active = {};
}

static void setWord(u32 bank, u32 value) {
  if(bank) rsp.imem.write<Word>(0, value);
  else rsp.dmem.write<Word>(0, value);
}
static u32 getWord(u32 bank) {
  return bank ? rsp.imem.read<Word>(0) : rsp.dmem.read<Word>(0);
}

static void append64(std::vector<u8>& out, u64 value) {
  for(int i = 7; i >= 0; i--) out.push_back(value >> (i * 8));
}
static string digestMachine() {
  std::vector<u8> bytes;
  for(auto& r : cpu.ipu.r) append64(bytes, r.u64);
  append64(bytes, cpu.ipu.hi.u64); append64(bytes, cpu.ipu.lo.u64); append64(bytes, cpu.ipu.pc);
  append64(bytes, cpu.effectiveCount()); append64(bytes, cpu.scc.ll); append64(bytes, cpu.scc.llbit);
  append64(bytes, cpu.scc.cause.exceptionCode); append64(bytes, cpu.scc.badVirtualAddress);
  for(u32 i = 0; i < 16; i++) bytes.push_back(rsp.dmem.read<Byte>(i));
  for(u32 i = 0; i < 16; i++) bytes.push_back(rsp.imem.read<Byte>(i));
  return nall::Hash::SHA256(std::span<const u8>{bytes.data(), bytes.size()}).digest();
}

static CaseFact runCase(u32 id, u32 bank, const char* kind) {
  tracing = false;
#if PLAID_SC_SP_SENSOR
  plaidSpWordObserver = nullptr;
#endif
  clearException();
  cpu.icache.power(false); cpu.dcache.power(false);
  cpu.scc.llbit = 0; cpu.scc.ll = 0;
  for(auto& r : cpu.ipu.r) r.u64 = 0;
  setWord(bank, Initial);
  u64 target = bank ? ImemVA : DmemVA;
  cpu.ipu.r[1].u64 = target;
  cpu.ipu.r[2].u64 = 0x55667788u;

  tracing = true;
#if PLAID_SC_SP_SENSOR
  plaidSpWordObserver = spWord;
#endif

  bool fail = !std::strcmp(kind, "fail");
  bool fault = !std::strcmp(kind, "fault");
  bool changed = !std::strcmp(kind, "changed");
  if(!fail) execute(id, encodeI(0x30, 1, 2, 0));  // LL r2,0(r1): establish a real linked load from this SP word.
  if(changed) execute(id, encodeI(0x0e, 2, 2, 0x00ff));  // XORI changes the payload while preserving the reservation.
  u32 source = cpu.ipu.r[2].u32;
  execute(id, encodeI(0x38, 1, 2, fault ? 1 : 0));  // SC r2,offset(r1)

  tracing = false;
#if PLAID_SC_SP_SENSOR
  plaidSpWordObserver = nullptr;
#endif
  return {id, bank, kind, Initial, source, getWord(bank), cpu.ipu.r[2].u32,
    (u32)cpu.scc.cause.exceptionCode, cpu.scc.badVirtualAddress, (bool)cpu.scc.llbit, digestMachine()};
}

int main(int argc, char** argv) {
  if(argc != 2 || (std::strcmp(argv[1], "disabled") && std::strcmp(argv[1], "enabled"))) return 2;
  bool enabled = !std::strcmp(argv[1], "enabled");
  Headless frontend; platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid SC SP sink research");
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
  tracing = enabled;

  std::vector<CaseFact> facts;
  for(u32 bank = 0; bank < 2; bank++) {
    u32 base = bank ? 5 : 1;
    facts.push_back(runCase(base + 0, bank, "fail"));
    facts.push_back(runCase(base + 1, bank, "fault"));
    facts.push_back(runCase(base + 2, bank, "changed"));
    facts.push_back(runCase(base + 3, bank, "same"));
  }

  // Equal-valued, CPU-origin SP write outside decoded SC execution context.
  tracing = enabled;
#if PLAID_SC_SP_SENSOR
  plaidSpWordObserver = enabled ? spWord : nullptr;
#endif
  active = {};
  auto decoy = cpu.write<Word>(ImemVA, Initial);
  if(!decoy) return 5;
  tracing = false;
#if PLAID_SC_SP_SENSOR
  plaidSpWordObserver = nullptr;
#endif

  std::printf("{\"mode\":\"%s\",\"decoy_ok\":%s,\"events\":[", argv[1], decoy ? "true" : "false");
  for(size_t i = 0; i < events.size(); i++) {
    auto& e = events[i];
    std::printf("%s{\"ordinal\":%u,\"case\":%u,\"pc\":%llu,\"instruction\":%u,\"pre_rt\":%u,\"llbit_before\":%s,\"address\":%u,\"bank\":%u,\"offset\":%u,\"value\":%u}",
      i ? "," : "", e.ordinal, e.caseId, (unsigned long long)e.pc, e.instruction, e.preRt,
      e.llbitBefore ? "true" : "false", e.address, e.bank, e.offset, e.value);
  }
  std::printf("],\"facts\":[");
  for(size_t i = 0; i < facts.size(); i++) {
    auto& f = facts[i];
    std::printf("%s{\"id\":%u,\"bank\":%u,\"kind\":\"%s\",\"initial\":%u,\"source\":%u,\"final\":%u,\"result\":%u,\"exception\":%u,\"badva\":%llu,\"llbit_after\":%s,\"digest\":\"%s\"}",
      i ? "," : "", f.id, f.bank, f.kind, f.initial, f.source, f.final, f.result, f.exception,
      (unsigned long long)f.badva, f.llbitAfter ? "true" : "false", f.digest.data());
  }
  std::printf("]}\n");
  ares::Nintendo64::system.unload();
  return 0;
}
