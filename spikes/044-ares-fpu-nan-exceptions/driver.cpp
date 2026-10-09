/* SPDX-License-Identifier: ISC
 * Original Plaid research harness, 2026. Reference implementation stays separate.
 */
#include <n64/n64.hpp>
#include <cstdio>
#include <cstring>
using namespace ares;
using namespace ares::Nintendo64;

struct Headless : ares::Platform {
  std::shared_ptr<vfs::directory> systemPak = std::make_shared<vfs::directory>();
  std::shared_ptr<vfs::directory> cartPak = std::make_shared<vfs::directory>();
  auto pak(Node::Object node) -> std::shared_ptr<vfs::directory> override {
    return node->name() == "Nintendo 64 Cartridge" ? cartPak : systemPak;
  }
};

struct Fixture {
  const char* name;
  u32 fs;
  u32 ft;
  u32 initialFcsr;
};

static auto fixtureFor(const char* name) -> Fixture {
  // The labels use the legacy-MIPS convention implemented by the pinned ares
  // source: snan(f32) is true when fraction bit 22 is one. That convention is
  // the reverse of modern IEEE-754 quiet-bit naming, so raw bits are canonical.
  if(!std::strcmp(name, "finite")) return {name, 0x3f800000u, 0x40000000u, 0u};
  if(!std::strcmp(name, "mips_snan_masked")) return {name, 0x7fc00001u, 0x3f800000u, 0u};
  if(!std::strcmp(name, "mips_snan_enabled")) return {name, 0x7fc00001u, 0x3f800000u, 1u << 11};
  if(!std::strcmp(name, "mips_qnan")) return {name, 0x7fa00001u, 0x3f800000u, 0u};
  if(!std::strcmp(name, "subnormal")) return {name, 0x00000001u, 0x3f800000u, 0u};
  return {nullptr, 0, 0, 0};
}

int main(int argc, char** argv) {
  if(argc != 2) return 2;
  auto fx = fixtureFor(argv[1]);
  if(!fx.name) return 5;

  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid FPU exception fixture");
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

  // Synthetic post-initialization state. No firmware is executed.
  std::vector<u8> hidden(rdram.ram.size / 2);
  rdram.hidden.data = hidden.data();
  for(auto& reg : cpu.ipu.r) reg.u64 = 0;
  for(auto& reg : cpu.fpu.r) reg.u64 = 0;
  rdram.mapIdentity = 1;
  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.status.enable.coprocessor1 = 1;
  cpu.scc.status.floatingPointMode = 1; // FR=1: 32 independent 64-bit FPRs.
  cpu.context.setMode();
  cpu.pipeline.setPc(0xffffffffa0000000ull);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;

  // ADD.S f6,f2,f4. Execute through the real interpreter fetch/decode path.
  constexpr u32 add_s_f6_f2_f4 = 0x46041180u;
  rdram.ram.write<Word>(0, add_s_f6_f2_f4, RBusDevice::ARES_DEBUGGER);

  cpu.fpu.r[2].u64 = fx.fs;
  cpu.fpu.r[4].u64 = fx.ft;
  constexpr u64 sentinel = 0xa5a5a5a5deadbeefull;
  cpu.fpu.r[6].u64 = sentinel;
  cpu.setControlRegisterFPU(31, fx.initialFcsr);

  const u64 before = cpu.fpu.r[6].u64;
  if(cpu.instruction()) cpu.synchronize();
  const u64 after = cpu.fpu.r[6].u64;
  const u32 fcsr = cpu.getControlRegisterFPU(31);

  std::printf(
    "{\"case\":\"%s\",\"opcode\":%u,\"fs\":%u,\"ft\":%u,"
    "\"initial_fcsr\":%u,\"dest_before\":%llu,\"dest_after\":%llu,"
    "\"fcsr\":%u,\"exception\":%u,\"epc\":%llu,\"pc\":%llu}\n",
    fx.name, add_s_f6_f2_f4, fx.fs, fx.ft, fx.initialFcsr,
    (unsigned long long)before, (unsigned long long)after, fcsr,
    (u32)cpu.scc.cause.exceptionCode, (unsigned long long)cpu.scc.epc,
    (unsigned long long)cpu.ipu.pc);

  ares::Nintendo64::system.unload();
  return 0;
}
