/* SPDX-License-Identifier: ISC
 * Plaid research harness: maskable VR4300 interrupt-root and gating cases.
 * The pinned ares implementation is built separately by spike 003's helper.
 */
#include <n64/n64.hpp>
#include <cstdio>
#include <cstdlib>
#include <cstring>
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
  int bev = std::atoi(argv[2]);
  int ie = std::atoi(argv[3]);
  int exl = std::atoi(argv[4]);
  int erl = std::atoi(argv[5]);
  u32 ip = (u32)std::strtoul(argv[6], nullptr, 0);
  u32 im = (u32)std::strtoul(argv[7], nullptr, 0);
  if((bev & ~1) || (ie & ~1) || (exl & ~1) || (erl & ~1) || ip > 0xff || im > 0xff) return 2;

  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid interrupt root fixture");
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

  constexpr u64 startPc = 0xffffffffa0000000ull;
  constexpr u64 epcSentinel = 0x123456789abcdef0ull;
  constexpr u32 causeSentinel = 13;
  constexpr u32 addiuS0 = 0x24101234;  // ADDIU $s0,$zero,0x1234

  put(0, addiuS0);
  put(4, 0);

  cpu.scc.status.vectorLocation = bev;
  cpu.scc.status.interruptEnable = ie;
  cpu.scc.status.exceptionLevel = exl;
  cpu.scc.status.errorLevel = erl;
  cpu.scc.status.interruptMask = im;
  cpu.scc.cause.interruptPending = 0;
  cpu.scc.cause.exceptionCode = causeSentinel;
  cpu.scc.cause.branchDelay = 1;
  cpu.scc.epc = epcSentinel;
  cpu.context.setMode();
  cpu.pipeline.setPc(startPc);

  // Exercise the same pending-bit API used by device/timer sources. It only polls;
  // CPU::instruction decides whether architectural interrupt entry actually occurs.
  for(u32 bit = 0; bit < 8; bit++) {
    if(ip & (1u << bit)) cpu.setInterruptPending(bit, 1);
  }

  if(cpu.instruction()) cpu.synchronize();

  std::printf(
    "{\"name\":\"%s\",\"bev\":%d,\"ie\":%d,\"initial_exl\":%d,\"initial_erl\":%d,"
    "\"ip\":%u,\"im\":%u,\"pc\":%llu,\"s0\":%llu,\"cause\":%u,\"bd\":%u,"
    "\"epc\":%llu,\"final_exl\":%u,\"final_erl\":%u,\"final_ip\":%u}\n",
    name, bev, ie, exl, erl, ip, im,
    (unsigned long long)cpu.ipu.pc,
    (unsigned long long)cpu.ipu.r[16].u64,
    (u32)cpu.scc.cause.exceptionCode,
    (u32)cpu.scc.cause.branchDelay,
    (unsigned long long)cpu.scc.epc,
    (u32)cpu.scc.status.exceptionLevel,
    (u32)cpu.scc.status.errorLevel,
    (u32)cpu.scc.cause.interruptPending);

  ares::Nintendo64::system.unload();
  return 0;
}
