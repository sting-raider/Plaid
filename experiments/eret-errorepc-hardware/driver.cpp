/* SPDX-License-Identifier: ISC
 * Plaid research harness: exact pinned ares ERL/ErrorEPC ERET behavior.
 */
#include <n64/n64.hpp>
#include <cstdio>
#include <cstdlib>
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

static auto put(u32 address, u32 word) -> void {
  rdram.ram.write<Word>(address, word, RBusDevice::ARES_DEBUGGER);
}

int main(int argc, char** argv) {
  if(argc != 8) return 2;
  const char* name = argv[1];
  int erl = std::atoi(argv[2]);
  int exl = std::atoi(argv[3]);
  int guestWrite = std::atoi(argv[4]);
  u64 initialError = std::strtoull(argv[5], nullptr, 0);
  u64 writeValue = std::strtoull(argv[6], nullptr, 0);
  u64 epc = std::strtoull(argv[7], nullptr, 0);
  if((erl & ~1) || (exl & ~1) || (guestWrite & ~1)) return 2;

  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid ErrorEPC ERET fixture");
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

  std::vector<u8> hidden(rdram.ram.size / 2);
  rdram.hidden.data = hidden.data();
  rdram.mapIdentity = 1;
  for(auto& reg : cpu.ipu.r) reg.u64 = 0;
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;

  constexpr u64 startPc = 0xffff'ffff'a000'0000ull;
  constexpr u64 targetError = 0xffff'ffff'a000'0100ull;
  constexpr u64 targetEpc = 0xffff'ffff'a000'0200ull;
  constexpr u32 dmtc0T0ErrorEpc = 0x40a8f000; // DMTC0 $t0,$30
  constexpr u32 eret = 0x42000018;
  constexpr u32 markError = 0x24111111; // ADDIU $s1,$zero,0x1111
  constexpr u32 markEpc = 0x24112222;   // ADDIU $s1,$zero,0x2222

  put(0x000, guestWrite ? dmtc0T0ErrorEpc : 0);
  put(0x004, 0); put(0x008, 0); put(0x00c, 0); put(0x010, 0);
  put(0x014, eret);
  put(0x100, markError);
  put(0x104, 0);
  put(0x200, markEpc);
  put(0x204, 0);

  cpu.scc.status.interruptEnable = 0;
  cpu.scc.status.exceptionLevel = exl;
  cpu.scc.status.errorLevel = erl;
  cpu.scc.cause.interruptPending = 0;
  cpu.scc.nmiPending = 0;
  cpu.scc.epc = epc;
  cpu.scc.epcError = initialError;
  cpu.ipu.r[8].u64 = writeValue; // $t0
  cpu.context.setMode();
  cpu.pipeline.setPc(startPc);

  // Execute optional guest DMTC0, four hazard NOPs, then the real ERET decoder path.
  for(int i = 0; i < 6; i++) {
    if(!cpu.instruction()) return 5;
  }
  u64 pcAfterEret = cpu.ipu.pc;
  u64 errorAfterEret = cpu.scc.epcError;
  u32 erlAfterEret = cpu.scc.status.errorLevel;
  u32 exlAfterEret = cpu.scc.status.exceptionLevel;

  // Execute one instruction at the selected return target to discriminate ErrorEPC/EPC.
  if(!cpu.instruction()) return 6;

  std::printf(
    "{\"name\":\"%s\",\"erl_in\":%d,\"exl_in\":%d,\"guest_write\":%d,"
    "\"initial_errorepc\":%llu,\"write_value\":%llu,\"epc\":%llu,"
    "\"errorepc_after\":%llu,\"pc_after_eret\":%llu,\"erl_after\":%u,\"exl_after\":%u,"
    "\"s1_after_target\":%llu,\"pc_final\":%llu,"
    "\"target_error_constant\":%llu,\"target_epc_constant\":%llu}\n",
    name, erl, exl, guestWrite,
    (unsigned long long)initialError,
    (unsigned long long)writeValue,
    (unsigned long long)epc,
    (unsigned long long)errorAfterEret,
    (unsigned long long)pcAfterEret,
    erlAfterEret, exlAfterEret,
    (unsigned long long)cpu.ipu.r[17].u64,
    (unsigned long long)cpu.ipu.pc,
    (unsigned long long)targetError,
    (unsigned long long)targetEpc);

  ares::Nintendo64::system.unload();
  return 0;
}
