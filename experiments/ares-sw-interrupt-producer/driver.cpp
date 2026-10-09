/* SPDX-License-Identifier: ISC
 * Plaid research harness: guest MTC0 Cause software-interrupt production.
 * The pinned ares implementation is built separately by spike 003's helper.
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
  if(argc != 10) return 2;
  const char* name = argv[1];
  int bev = std::atoi(argv[2]);
  int ie = std::atoi(argv[3]);
  int exl = std::atoi(argv[4]);
  int erl = std::atoi(argv[5]);
  u32 initialIp = (u32)std::strtoul(argv[6], nullptr, 0);
  u32 initialIm = (u32)std::strtoul(argv[7], nullptr, 0);
  u32 writeValue = (u32)std::strtoul(argv[8], nullptr, 0);
  u32 finalIm = (u32)std::strtoul(argv[9], nullptr, 0);
  if((bev & ~1) || (ie & ~1) || (exl & ~1) || (erl & ~1)
      || initialIp > 0xff || initialIm > 0xff || finalIm > 0xff) return 2;

  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid software interrupt producer fixture");
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
  constexpr u32 mtc0T0Cause = 0x40886800; // MTC0 $t0,$13 (Cause)
  constexpr u32 addiuS0 = 0x24101234;     // ADDIU $s0,$zero,0x1234

  put(0, mtc0T0Cause);
  put(4, addiuS0);
  put(8, 0);

  cpu.scc.status.vectorLocation = bev;
  cpu.scc.status.interruptEnable = ie;
  cpu.scc.status.exceptionLevel = exl;
  cpu.scc.status.errorLevel = erl;
  cpu.scc.status.interruptMask = initialIm;
  cpu.scc.cause.interruptPending = initialIp;
  cpu.scc.cause.exceptionCode = causeSentinel;
  cpu.scc.cause.branchDelay = 1;
  cpu.scc.epc = epcSentinel;
  cpu.ipu.r[8].u64 = writeValue;
  cpu.context.setMode();
  cpu.pipeline.setPc(startPc);

  // First boundary executes the actual guest MTC0 Cause. Any eligible initial
  // pending state is deliberately masked in cases that need to mutate it first.
  if(cpu.instruction()) cpu.synchronize();
  u64 firstPc = cpu.ipu.pc;
  u32 firstIp = (u32)cpu.scc.cause.interruptPending;
  u32 firstCause = (u32)cpu.scc.cause.exceptionCode;
  u32 firstBd = (u32)cpu.scc.cause.branchDelay;
  u64 firstEpc = cpu.scc.epc;

  // Some adversaries enable a mask only after the guest write, so a software
  // clear can be distinguished from an initial interrupt preempting the MTC0.
  cpu.scc.status.interruptMask = finalIm;

  // Second boundary either enters the interrupt before fetch or retires ADDIU.
  if(cpu.instruction()) cpu.synchronize();

  std::printf(
    "{\"name\":\"%s\",\"bev\":%d,\"ie\":%d,\"initial_exl\":%d,\"initial_erl\":%d,"
    "\"initial_ip\":%u,\"initial_im\":%u,\"write_value\":%u,\"final_im\":%u,"
    "\"first_pc\":%llu,\"first_ip\":%u,\"first_cause\":%u,\"first_bd\":%u,\"first_epc\":%llu,"
    "\"pc\":%llu,\"s0\":%llu,\"cause\":%u,\"bd\":%u,\"epc\":%llu,"
    "\"final_exl\":%u,\"final_erl\":%u,\"final_ip\":%u}\n",
    name, bev, ie, exl, erl, initialIp, initialIm, writeValue, finalIm,
    (unsigned long long)firstPc, firstIp, firstCause, firstBd, (unsigned long long)firstEpc,
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
