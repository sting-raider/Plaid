/* SPDX-License-Identifier: ISC
 * Exact pinned-ares fixture for VR4300 SCD -> CPU-visible SP DMEM/IMEM sinks.
 */
#ifndef PLAID_SCD_SP_SENSOR
#define PLAID_SCD_SP_SENSOR 1
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
static constexpr u32 InitialHi = 0x11223344u;
static constexpr u32 InitialLo = 0xffffffffu;
static constexpr u64 Initial64 = 0x11223344ffffffffull;
static constexpr u64 Changed64 = 0x1122334500000000ull;

struct Active {
  u32 caseId = 0;
  u64 pc = 0;
  u32 instruction = 0;
  u64 preRt = 0;
  bool llbitBefore = false;
};
struct SinkEvent {
  u32 ordinal, caseId, address, bank, offset, value, instruction;
  u64 pc, preRt;
  bool llbitBefore;
};
struct CaseFact {
  u32 id, bank;
  const char* kind;
  u64 source, result;
  u32 initialHi, initialLo, finalHi, finalLo, exception;
  u64 badva;
  bool llbitAfter;
  string digest;
};

static Active active;
static std::vector<SinkEvent> events;
static bool tracing = false;

#if PLAID_SCD_SP_SENSOR
static void spWord(bool write, u32 address, u32 bank, u32 offset, u32 value, bool originCpu) {
  if(!tracing || !write || !originCpu) return;
  events.push_back({(u32)events.size() + 1, active.caseId, address, bank, offset, value,
    active.instruction, active.pc, active.preRt, active.llbitBefore});
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
  active.preRt = cpu.ipu.r[instruction >> 16 & 31].u64;
  active.llbitBefore = cpu.scc.llbit;
  if(cpu.instruction()) cpu.synchronize();
  active = {};
}

static void setWords(u32 bank, u32 hi, u32 lo) {
  if(bank) {
    rsp.imem.write<Word>(0, hi);
    rsp.imem.write<Word>(4, lo);
  } else {
    rsp.dmem.write<Word>(0, hi);
    rsp.dmem.write<Word>(4, lo);
  }
}
static u32 getWord(u32 bank, u32 offset) {
  return bank ? rsp.imem.read<Word>(offset) : rsp.dmem.read<Word>(offset);
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
#if PLAID_SCD_SP_SENSOR
  plaidSpWordObserver = nullptr;
#endif
  clearException();
  cpu.icache.power(false); cpu.dcache.power(false);
  cpu.scc.llbit = 0; cpu.scc.ll = 0;
  for(auto& r : cpu.ipu.r) r.u64 = 0;
  setWords(bank, InitialHi, InitialLo);
  u64 target = bank ? ImemVA : DmemVA;
  cpu.ipu.r[1].u64 = target;
  cpu.ipu.r[2].u64 = Initial64;

  tracing = true;
#if PLAID_SCD_SP_SENSOR
  plaidSpWordObserver = spWord;
#endif

  bool fail = !std::strcmp(kind, "fail");
  bool fault = !std::strcmp(kind, "fault");
  bool changed = !std::strcmp(kind, "changed");
  if(!fail) execute(id, encodeI(0x34, 1, 2, 0));  // LLD r2,0(r1): establish a real reservation and 64-bit payload.
  if(changed) execute(id, encodeI(0x19, 2, 2, 1)); // DADDIU carries through 0xffffffff into the high Word.
  u64 source = cpu.ipu.r[2].u64;
  execute(id, encodeI(0x3c, 1, 2, fault ? 1 : 0)); // SCD r2,offset(r1)

  tracing = false;
#if PLAID_SCD_SP_SENSOR
  plaidSpWordObserver = nullptr;
#endif
  return {id, bank, kind, source, cpu.ipu.r[2].u64, InitialHi, InitialLo,
    getWord(bank, 0), getWord(bank, 4), (u32)cpu.scc.cause.exceptionCode,
    cpu.scc.badVirtualAddress, (bool)cpu.scc.llbit, digestMachine()};
}

int main(int argc, char** argv) {
  if(argc != 2 || (std::strcmp(argv[1], "disabled") && std::strcmp(argv[1], "enabled"))) return 2;
  bool enabled = !std::strcmp(argv[1], "enabled");
  Headless frontend; platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid SCD SP sink research");
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

  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.status.vectorLocation = 0;
  cpu.scc.status.privilegeMode = 0;
  cpu.scc.status.kernelExtendedAddressing = 1;
  cpu.scc.configuration.bigEndian = 1;
  cpu.context.setMode();
  if(cpu.context.bits != 64 || !cpu.context.bigEndian()) return 5;
  tracing = enabled;

  std::vector<CaseFact> facts;
  for(u32 bank = 0; bank < 2; bank++) {
    u32 base = bank ? 5 : 1;
    facts.push_back(runCase(base + 0, bank, "fail"));
    facts.push_back(runCase(base + 1, bank, "fault"));
    facts.push_back(runCase(base + 2, bank, "changed"));
    facts.push_back(runCase(base + 3, bank, "same"));
  }

  // Equal-valued Dual write outside decoded SCD execution context.
  tracing = enabled;
#if PLAID_SCD_SP_SENSOR
  plaidSpWordObserver = enabled ? spWord : nullptr;
#endif
  active = {};
  auto decoy = cpu.write<Dual>(ImemVA, Initial64);
  if(!decoy) return 6;
  tracing = false;
#if PLAID_SCD_SP_SENSOR
  plaidSpWordObserver = nullptr;
#endif

  std::printf("{\"mode\":\"%s\",\"decoy_ok\":%s,\"events\":[", argv[1], decoy ? "true" : "false");
  for(size_t i = 0; i < events.size(); i++) {
    auto& e = events[i];
    std::printf("%s{\"ordinal\":%u,\"case\":%u,\"pc\":%llu,\"instruction\":%u,\"pre_rt\":%llu,\"llbit_before\":%s,\"address\":%u,\"bank\":%u,\"offset\":%u,\"value\":%u}",
      i ? "," : "", e.ordinal, e.caseId, (unsigned long long)e.pc, e.instruction,
      (unsigned long long)e.preRt, e.llbitBefore ? "true" : "false", e.address, e.bank, e.offset, e.value);
  }
  std::printf("],\"facts\":[");
  for(size_t i = 0; i < facts.size(); i++) {
    auto& f = facts[i];
    std::printf("%s{\"id\":%u,\"bank\":%u,\"kind\":\"%s\",\"initial_hi\":%u,\"initial_lo\":%u,\"source\":%llu,\"final_hi\":%u,\"final_lo\":%u,\"result\":%llu,\"exception\":%u,\"badva\":%llu,\"llbit_after\":%s,\"digest\":\"%s\"}",
      i ? "," : "", f.id, f.bank, f.kind, f.initialHi, f.initialLo,
      (unsigned long long)f.source, f.finalHi, f.finalLo, (unsigned long long)f.result,
      f.exception, (unsigned long long)f.badva, f.llbitAfter ? "true" : "false", f.digest.data());
  }
  std::printf("]}\n");
  ares::Nintendo64::system.unload();
  return 0;
}
