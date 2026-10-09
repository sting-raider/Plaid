/* SPDX-License-Identifier: ISC
 * Exact pinned-ares RSP vector load->register->store provenance fixture.
 * Executes decoded guest RSP instructions with the recompiler disabled.
 */
#define main plaid_capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <array>
#include <vector>

using namespace ares;
using namespace ares::Nintendo64;

static auto vecMem(u32 op, u32 base, u32 vt, u32 subtype, u32 e, u32 imm7 = 0) -> u32 {
  return (op << 26) | (base << 21) | (vt << 16) | (subtype << 11) | (e << 7) | (imm7 & 0x7f);
}

static auto mtc2(u32 rt, u32 vs, u32 e) -> u32 {
  return (0x12u << 26) | (0x04u << 21) | (rt << 16) | (vs << 11) | (e << 7);
}

static auto bytesAt(u32 address) -> std::array<u8, 16> {
  std::array<u8, 16> out{};
  for(u32 i = 0; i < 16; i++) out[i] = rsp.dmem.data[(address + i) & 0xfff];
  return out;
}

static auto vector2() -> std::array<u8, 16> {
  std::array<u8, 16> out{};
  for(u32 i = 0; i < 16; i++) out[i] = rsp.vpu.r[2].byte(i);
  return out;
}

static auto setVector(const std::array<u8, 16>& values) -> void {
  for(u32 i = 0; i < 16; i++) rsp.vpu.r[2].byte(i) = values[i];
}

static auto put(u32 address, const std::vector<u8>& values) -> void {
  for(u32 i = 0; i < values.size(); i++) rsp.dmem.data[(address + i) & 0xfff] = values[i];
}

static auto runProgram(
    const std::vector<u32>& program, u32 r1, u32 r2, u32 r3, u32 r4 = 0) -> u32 {
  std::memset(rsp.imem.data, 0, rsp.imem.size);
  for(u32 i = 0; i < program.size(); i++) rsp.imem.write<Word>(i * 4, program[i]);
  rsp.imem.write<Word>(program.size() * 4, 0x0000000d);  // BREAK
  for(auto& r : rsp.ipu.r) r.u32 = 0;
  rsp.ipu.r[1].u32 = r1;
  rsp.ipu.r[2].u32 = r2;
  rsp.ipu.r[3].u32 = r3;
  rsp.ipu.r[4].u32 = r4;
  rsp.pipeline = {};
  rsp.branch.setPc(0);
  rsp.ipu.pc = 0;
  rsp.status.halted = 0;
  rsp.status.broken = 0;
  u32 calls = 0;
  while(!rsp.status.halted && calls < 64) {
    rsp.instruction();
    calls++;
  }
  if(!rsp.status.halted || !rsp.status.broken) std::abort();
  return calls;
}

struct Result {
  const char* name;
  std::array<u8, 16> vector;
  std::array<u8, 16> destination;
  std::vector<u32> program;
  u32 calls;
};

static auto printBytes(const std::array<u8, 16>& a) -> void {
  std::printf("[");
  for(u32 i = 0; i < 16; i++) std::printf("%s%u", i ? "," : "", (u32)a[i]);
  std::printf("]");
}

static auto printWords(const std::vector<u32>& a) -> void {
  std::printf("[");
  for(u32 i = 0; i < a.size(); i++) std::printf("%s%u", i ? "," : "", a[i]);
  std::printf("]");
}

int main() {
  Headless frontend; platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid RSP vector lineage fixture");
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

  std::vector<Result> results;
  auto reset = [&](u8 fill, const std::array<u8,16>& initial) {
    std::memset(rsp.dmem.data, fill, rsp.dmem.size);
    setVector(initial);
  };
  auto range = [](u8 begin, u32 count) {
    std::vector<u8> out;
    for(u32 i = 0; i < count; i++) out.push_back(begin + i);
    return out;
  };

  {
    std::array<u8,16> initial{}; for(u32 i=0;i<16;i++) initial[i]=0xe0+i;
    reset(0xcc, initial);
    put(0x200, range(0x10,16)); put(0x300, std::vector<u8>(16,0x55));
    std::vector<u32> p = {vecMem(0x32,1,2,4,0), vecMem(0x3a,3,2,4,0)};
    u32 calls=runProgram(p,0x200,0,0x300);
    results.push_back({"aligned_lqv_sqv",vector2(),bytesAt(0x300),p,calls});
  }

  {
    std::array<u8,16> initial{}; for(u32 i=0;i<16;i++) initial[i]=0xa0+i;
    reset(0xcc, initial);
    put(0x205, range(0x30,11)); put(0x310, std::vector<u8>(16,0x55));
    std::vector<u32> p = {vecMem(0x32,1,2,4,3), vecMem(0x3a,3,2,4,0)};
    u32 calls=runProgram(p,0x205,0,0x310);
    results.push_back({"partial_lqv_sqv",vector2(),bytesAt(0x310),p,calls});
  }

  {
    std::array<u8,16> initial{}; for(u32 i=0;i<16;i++) initial[i]=0xf0+i;
    reset(0xcc, initial);
    auto same=range(0x70,16);
    put(0x400,same); put(0x500,same); put(0x520,std::vector<u8>(16,0x55));
    std::vector<u32> p = {
      vecMem(0x32,1,2,4,0), vecMem(0x32,2,2,4,0), vecMem(0x3a,3,2,4,0)};
    u32 calls=runProgram(p,0x400,0x500,0x520);
    results.push_back({"equal_decoy_latest_load",vector2(),bytesAt(0x520),p,calls});
  }

  {
    std::array<u8,16> initial{}; for(u32 i=0;i<16;i++) initial[i]=0xb0+i;
    reset(0xcc, initial);
    put(0x600,range(0x90,11)); put(0x700,std::vector<u8>(16,0x55));
    std::vector<u32> p = {vecMem(0x32,1,2,5,0), vecMem(0x3a,3,2,5,0)};
    u32 calls=runProgram(p,0x60b,0,0x70b);
    results.push_back({"lrv_srv_effective_span",vector2(),bytesAt(0x700),p,calls});
  }

  {
    std::array<u8,16> initial{}; initial.fill(0x44);
    reset(0x44, initial);
    put(0x805,std::vector<u8>(11,0x44));
    put(0x900,std::vector<u8>(11,0x44));
    put(0xa00,std::vector<u8>(16,0x44));
    std::vector<u32> p = {
      vecMem(0x32,1,2,4,3), vecMem(0x32,2,2,5,0), vecMem(0x3a,3,2,4,0)};
    u32 calls=runProgram(p,0x805,0x90b,0xa00);
    results.push_back({"mixed_same_value_no_diff",vector2(),bytesAt(0xa00),p,calls});
  }

  {
    std::array<u8,16> initial{}; for(u32 i=0;i<16;i++) initial[i]=0xd0+i;
    reset(0xcc, initial);
    put(0xb00,range(0x20,16)); put(0xc00,std::vector<u8>(16,0x55));
    std::vector<u32> p = {
      vecMem(0x32,1,2,4,0), mtc2(4,2,6), vecMem(0x3a,3,2,4,0)};
    u32 calls=runProgram(p,0xb00,0,0xc00,0xcafe);
    results.push_back({"mtc2_clobber",vector2(),bytesAt(0xc00),p,calls});
  }

  std::printf("{\"cases\":[");
  for(u32 i=0;i<results.size();i++) {
    const auto& r=results[i];
    std::printf("%s{\"name\":\"%s\",\"vector\":",i?",":"",r.name);
    printBytes(r.vector);
    std::printf(",\"destination\":"); printBytes(r.destination);
    std::printf(",\"program\":"); printWords(r.program);
    std::printf(",\"rsp_instruction_calls\":%u}",r.calls);
  }
  std::printf("]}\n");
  ares::Nintendo64::system.unload();
  return results.size()==6 ? 0 : 90;
}
