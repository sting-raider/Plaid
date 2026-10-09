/* SPDX-License-Identifier: ISC
 * Plaid research fixture: RSP scalar DMEM load -> GPR -> scalar store lineage.
 */
#define main plaid_oracle_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>
#include <array>
#include <string>
#include <utility>
#include <vector>

#ifndef PLAID_SENSOR
#define PLAID_SENSOR 0
#endif

static auto digest4096(const u8* data) -> string {
  return nall::Hash::SHA256(std::span<const u8>{data, 4096}).digest();
}

static auto hex4096(const u8* data) -> std::string {
  static const char* digits = "0123456789abcdef";
  std::string out;
  out.reserve(8192);
  for(u32 i = 0; i < 4096; i++) {
    out.push_back(digits[data[i] >> 4]);
    out.push_back(digits[data[i] & 15]);
  }
  return out;
}

struct TraceEvent {
  u32 kind = 0;      // 0 begin, 1 completed primitive DMEM sink, 2 end
  u32 ordinal = 0;
  u32 context = 0;
  u32 phase = 0;
  u32 pc = 0;
  u32 word = 0;
  u32 rs = 0, rt = 0, rd = 0;
  u32 rsValue = 0, rtValue = 0, rdValue = 0;
  u32 offset = 0, bytes = 0, next = 0;
  u64 value = 0;
  bool halted = false;
};

static std::vector<TraceEvent> traceEvents;
static u32 tracePhase = 0;
static u32 traceOrdinal = 0;
static u32 traceContextSerial = 0;
static u32 traceContext = 0;
static u32 tracePc = 0;
static u32 traceWord = 0;
static bool traceArmed = false;

#if PLAID_SENSOR
static void rsp_instruction_observer(bool begin, u32 pc, u32 word, u32 next, bool halted) {
  if(!traceArmed) return;
  u32 rs = word >> 21 & 31;
  u32 rt = word >> 16 & 31;
  u32 rd = word >> 11 & 31;
  if(begin) {
    if(traceContext) std::abort();
    traceContext = ++traceContextSerial;
    tracePc = pc;
    traceWord = word;
    traceEvents.push_back({0, ++traceOrdinal, traceContext, tracePhase, pc, word, rs, rt, rd,
      rsp.ipu.r[rs].u32, rsp.ipu.r[rt].u32, rsp.ipu.r[rd].u32, 0, 0, next, 0, halted});
  } else {
    if(!traceContext || pc != tracePc || word != traceWord) std::abort();
    traceEvents.push_back({2, ++traceOrdinal, traceContext, tracePhase, pc, word, rs, rt, rd,
      rsp.ipu.r[rs].u32, rsp.ipu.r[rt].u32, rsp.ipu.r[rd].u32, 0, 0, next, 0, halted});
    traceContext = 0;
  }
}

static void rsp_dmem_observer(u32 offset, u32 bytes, u64 value) {
  if(!traceArmed) return;
  if(!traceContext) std::abort();
  traceEvents.push_back({1, ++traceOrdinal, traceContext, tracePhase, tracePc, traceWord,
    traceWord >> 21 & 31, traceWord >> 16 & 31, traceWord >> 11 & 31,
    0, 0, 0, offset, bytes, 0, value, false});
}
#endif

struct ScenarioResult {
  std::string name;
  std::vector<u32> program;
  std::string initialHex;
  string finalDmem;
  string finalImem;
  std::array<u32, 32> regs{};
  u32 pc = 0;
  u32 halted = 0;
  u32 broken = 0;
  s64 clock = 0;
  u32 clocksTotal = 0;
};

static auto encI(u32 op, u32 rs, u32 rt, s16 imm) -> u32 {
  return op << 26 | rs << 21 | rt << 16 | u16(imm);
}
static auto encAddu(u32 rd, u32 rs, u32 rt) -> u32 {
  return rs << 21 | rt << 16 | rd << 11 | 0x21;
}

int main() {
  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid RSP scalar lineage fixture");
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

#if PLAID_SENSOR
  if(!std::getenv("PLAID_RSP_DISABLE")) {
    plaidRspInstructionObserver = rsp_instruction_observer;
    plaidRspDmemObserver = rsp_dmem_observer;
  }
#endif

  std::vector<ScenarioResult> results;
  auto run = [&](const char* name, std::vector<u32> program, u32 sourceBase, u32 destBase,
                 std::vector<std::pair<u32,u8>> setup) {
    ++tracePhase;
    traceArmed = false;
    rsp.dmem.fill(0);
    rsp.imem.fill(0);
    for(auto& r : rsp.ipu.r) r.u32 = 0;
    for(auto [offset,value] : setup) rsp.dmem.data[offset & 0xfff] = value;
    rsp.ipu.r[1].u32 = sourceBase;
    rsp.ipu.r[3].u32 = destBase;
    for(u32 i = 0; i < program.size(); i++) rsp.imem.write<Word>(i * 4, program[i]);
    rsp.imem.write<Word>(u32(program.size()) * 4, 0x0000000d); // BREAK
    std::string initial = hex4096(rsp.dmem.data);

    rsp.pipeline = {};
    rsp.branch.setPc(0);
    rsp.ipu.pc = 0;
    rsp.status.halted = 0;
    rsp.status.broken = 0;
    traceArmed = true;
    for(u32 guard = 0; guard < 32 && !rsp.status.halted; guard++) rsp.instruction();
    traceArmed = false;
    if(traceContext || !rsp.status.halted || !rsp.status.broken) std::abort();

    ScenarioResult result;
    result.name = name;
    result.program = program;
    result.program.push_back(0x0000000d);
    result.initialHex = std::move(initial);
    result.finalDmem = digest4096(rsp.dmem.data);
    result.finalImem = digest4096(rsp.imem.data);
    for(u32 i = 0; i < 32; i++) result.regs[i] = rsp.ipu.r[i].u32;
    result.pc = rsp.ipu.pc;
    result.halted = rsp.status.halted;
    result.broken = rsp.status.broken;
    result.clock = rsp.Thread::clock;
    result.clocksTotal = rsp.pipeline.clocksTotal;
    results.push_back(std::move(result));
  };

  // Same-width load/store pairs. High-bit byte/half cases exercise sign versus zero extension
  // while the stored low lanes should retain the same concrete DMEM byte origins.
  run("lb_sb",  {encI(0x20,1,2,0), encI(0x28,3,2,0)}, 0x100,0x300, {{0x100,0x80}});
  run("lbu_sb", {encI(0x24,1,2,0), encI(0x28,3,2,0)}, 0x100,0x300, {{0x100,0x80}});
  run("lh_sh",  {encI(0x21,1,2,0), encI(0x29,3,2,0)}, 0x120,0x320, {{0x120,0x80},{0x121,0x01}});
  run("lhu_sh", {encI(0x25,1,2,0), encI(0x29,3,2,0)}, 0x120,0x320, {{0x120,0x80},{0x121,0x01}});
  run("lw_sw",  {encI(0x23,1,2,0), encI(0x2b,3,2,0)}, 0x140,0x340,
      {{0x140,0x89},{0x141,0xab},{0x142,0xcd},{0x143,0xef}});
  run("lwu_sw", {encI(0x27,1,2,0), encI(0x2b,3,2,0)}, 0x140,0x340,
      {{0x140,0x89},{0x141,0xab},{0x142,0xcd},{0x143,0xef}});

  // Unaligned accesses wrap through the physical 4 KiB DMEM address domain.
  run("lh_wrap", {encI(0x21,1,2,0), encI(0x29,3,2,0)}, 0x0fff,0x360,
      {{0x0fff,0x12},{0x0000,0x34}});
  run("lw_wrap", {encI(0x23,1,2,0), encI(0x2b,3,2,0)}, 0x0ffe,0x380,
      {{0x0ffe,0xa1},{0x0fff,0xb2},{0x0000,0xc3},{0x0001,0xd4}});
  run("bit12_alias", {encI(0x23,1,2,0), encI(0x2b,3,2,0)}, 0x1000,0x3a0,
      {{0x0000,0x01},{0x0001,0x23},{0x0002,0x45},{0x0003,0x67}});

  // Equal payloads are deliberately ambiguous by value. The later load must own the GPR generation.
  run("equal_two_loads", {encI(0x23,1,2,0), encI(0x23,1,2,4), encI(0x2b,3,2,0)}, 0x180,0x3c0,
      {{0x180,0x11},{0x181,0x22},{0x182,0x33},{0x183,0x44},
       {0x184,0x11},{0x185,0x22},{0x186,0x33},{0x187,0x44}});
  run("same_source_reload", {encI(0x23,1,2,0), encI(0x23,1,2,0), encI(0x2b,3,2,0)}, 0x1a0,0x3e0,
      {{0x1a0,0x55},{0x1a1,0x66},{0x1a2,0x77},{0x1a3,0x88}});

  // A whole-GPR writer must kill old load provenance even when it recreates the same value.
  run("ori_same_value_clobber", {encI(0x23,1,2,0), encI(0x0d,0,2,0x1234), encI(0x2b,3,2,0)}, 0x1c0,0x400,
      {{0x1c0,0x00},{0x1c1,0x00},{0x1c2,0x12},{0x1c3,0x34}});
  run("addu_same_value_clobber", {encI(0x23,1,2,0), encAddu(2,2,0), encI(0x2b,3,2,0)}, 0x1e0,0x420,
      {{0x1e0,0xde},{0x1e1,0xad},{0x1e2,0xbe},{0x1e3,0xef}});

  // An unrelated same-value-ish writer to r4 must not kill r2's load generation.
  run("unrelated_writer", {encI(0x23,1,2,0), encI(0x0d,0,4,0x3344), encI(0x2b,3,2,0)}, 0x200,0x440,
      {{0x200,0x11},{0x201,0x22},{0x202,0x33},{0x203,0x44}});

  std::printf("{\"scenario_count\":%zu,\"scenarios\":[", results.size());
  for(size_t s = 0; s < results.size(); s++) {
    const auto& r = results[s];
    std::printf("%s{\"name\":\"%s\",\"program\":[", s ? "," : "", r.name.c_str());
    for(size_t i = 0; i < r.program.size(); i++) std::printf("%s%u", i ? "," : "", r.program[i]);
    std::printf("],\"initial_hex\":\"%s\",\"final_dmem_sha256\":\"%s\",\"final_imem_sha256\":\"%s\",\"regs\":[",
      r.initialHex.c_str(), r.finalDmem.data(), r.finalImem.data());
    for(u32 i = 0; i < 32; i++) std::printf("%s%u", i ? "," : "", r.regs[i]);
    std::printf("],\"pc\":%u,\"halted\":%u,\"broken\":%u,\"clock\":%lld,\"clocks_total\":%u}",
      r.pc,r.halted,r.broken,(long long)r.clock,r.clocksTotal);
  }
  std::printf("]}\n");

  std::printf("{\"format\":\"plaid-rsp-scalar-lineage-v0\",\"events\":[");
  for(size_t i = 0; i < traceEvents.size(); i++) {
    const auto& e = traceEvents[i];
    std::printf("%s{\"kind\":%u,\"ordinal\":%u,\"context\":%u,\"phase\":%u,\"pc\":%u,\"word\":%u,\"rs\":%u,\"rt\":%u,\"rd\":%u,\"rs_value\":%u,\"rt_value\":%u,\"rd_value\":%u,\"offset\":%u,\"bytes\":%u,\"next\":%u,\"value\":%llu,\"halted\":%s}",
      i ? "," : "", e.kind,e.ordinal,e.context,e.phase,e.pc,e.word,e.rs,e.rt,e.rd,e.rsValue,e.rtValue,e.rdValue,
      e.offset,e.bytes,e.next,(unsigned long long)e.value,e.halted ? "true" : "false");
  }
  std::printf("]}\n");

  ares::Nintendo64::system.unload();
  return results.size() == 14 ? 0 : 70;
}
