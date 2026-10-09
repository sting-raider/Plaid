/* SPDX-License-Identifier: ISC
 * Plaid research harness: guest-visible VR4300 CacheErr register behavior.
 */
#include <n64/n64.hpp>
#include <cstdio>
#include <cstdlib>
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

static auto put(u32 address, u32 word) -> void {
  rdram.ram.write<Word>(address, word, RBusDevice::ARES_DEBUGGER);
}

int main(int argc, char** argv) {
  if(argc != 2) return 2;
  int bev = std::atoi(argv[1]);
  if(bev != 0 && bev != 1) return 2;

  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid CacheErr fixture");
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

  // Guest sequence at uncached KSEG1:
  //   mtc0 $4,$27      ; attempt to write all ones to CacheErr
  //   nop; nop         ; respect CP0 hazards
  //   mfc0 $5,$27      ; hardware-compatible readback should be zero
  //   nop; nop
  put(0x00, 0x4084d800u);
  put(0x04, 0x00000000u);
  put(0x08, 0x00000000u);
  put(0x0c, 0x4005d800u);
  put(0x10, 0x00000000u);
  put(0x14, 0x00000000u);

  constexpr u64 start = 0xffffffffa0000000ull;
  constexpr u64 epcSentinel = 0x123456789abcdef0ull;
  constexpr u64 errorEpcSentinel = 0x0fedcba987654321ull;
  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.status.privilegeMode = 0;
  cpu.scc.status.vectorLocation = bev;
  cpu.scc.epc = epcSentinel;
  cpu.scc.epcError = errorEpcSentinel;
  cpu.scc.cause.exceptionCode = 13;
  cpu.scc.cacheError.unused = 0;
  cpu.context.setMode();
  cpu.ipu.r[4].u64 = 0xffffffffffffffffull;
  cpu.pipeline.setPc(start);

  for(int n = 0; n < 6; n++) {
    if(cpu.instruction()) cpu.synchronize();
  }

  std::printf(
    "{\"bev\":%d,\"pc\":%llu,\"cacheerr\":%u,\"readback\":%llu,"
    "\"exl\":%u,\"erl\":%u,\"cause\":%u,\"epc\":%llu,\"error_epc\":%llu}\n",
    bev,
    (unsigned long long)cpu.ipu.pc,
    (u32)cpu.scc.cacheError.unused,
    (unsigned long long)cpu.ipu.r[5].u64,
    (u32)cpu.scc.status.exceptionLevel,
    (u32)cpu.scc.status.errorLevel,
    (u32)cpu.scc.cause.exceptionCode,
    (unsigned long long)cpu.scc.epc,
    (unsigned long long)cpu.scc.epcError);

  ares::Nintendo64::system.unload();
  return 0;
}
