/* SPDX-License-Identifier: ISC
 * Plaid research harness: pinned ares N64 external-NMI entry behavior.
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

int main(int argc, char** argv) {
  if(argc != 7) return 2;
  int bev = std::atoi(argv[1]);
  int exl = std::atoi(argv[2]);
  int erl = std::atoi(argv[3]);
  int sr = std::atoi(argv[4]);
  int delay = std::atoi(argv[5]);
  int repeat = std::atoi(argv[6]);
  if((bev & ~1) || (exl & ~1) || (erl & ~1) || (sr & ~1) || (delay & ~1)) return 2;
  if(repeat != 1 && repeat != 2) return 2;

  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid NMI root fixture");
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
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;

  constexpr u64 entryPc = 0xffff'ffff'a000'0104ull;
  constexpr u64 epcSentinel = 0x1111'2222'3333'4444ull;
  constexpr u64 errorSentinel = 0x5555'6666'7777'8888ull;

  cpu.scc.status.vectorLocation = bev;
  cpu.scc.status.exceptionLevel = exl;
  cpu.scc.status.errorLevel = erl;
  cpu.scc.status.softReset = sr;
  cpu.scc.status.tlbShutdown = 1;
  cpu.scc.epc = epcSentinel;
  cpu.scc.epcError = errorSentinel;
  cpu.pipeline.setPc(entryPc);
  if(delay) cpu.pipeline.state |= CPU::Pipeline::DelaySlot;
  cpu.scc.nmiPending = 1;

  u64 firstPc = 0;
  u64 firstErrorEpc = 0;
  u32 firstPending = 0;
  for(int i = 0; i < repeat; i++) {
    if(!cpu.instruction()) return 5;
    if(i == 0) {
      firstPc = cpu.ipu.pc;
      firstErrorEpc = cpu.scc.epcError;
      firstPending = cpu.scc.nmiPending;
    }
  }

  std::printf(
    "{\"bev_in\":%d,\"exl_in\":%d,\"erl_in\":%d,\"sr_in\":%d,\"delay_in\":%d,\"repeat\":%d,"
    "\"first_pc\":%llu,\"first_errorepc\":%llu,\"first_pending\":%u,"
    "\"pc\":%llu,\"errorepc\":%llu,\"epc\":%llu,"
    "\"bev\":%u,\"exl\":%u,\"erl\":%u,\"sr\":%u,\"ts\":%u,"
    "\"pending\":%u,\"pipeline_delay\":%u}\n",
    bev, exl, erl, sr, delay, repeat,
    (unsigned long long)firstPc,
    (unsigned long long)firstErrorEpc,
    firstPending,
    (unsigned long long)cpu.ipu.pc,
    (unsigned long long)cpu.scc.epcError,
    (unsigned long long)cpu.scc.epc,
    (u32)cpu.scc.status.vectorLocation,
    (u32)cpu.scc.status.exceptionLevel,
    (u32)cpu.scc.status.errorLevel,
    (u32)cpu.scc.status.softReset,
    (u32)cpu.scc.status.tlbShutdown,
    (u32)cpu.scc.nmiPending,
    (u32)cpu.pipeline.inDelaySlot());

  ares::Nintendo64::system.unload();
  return 0;
}
