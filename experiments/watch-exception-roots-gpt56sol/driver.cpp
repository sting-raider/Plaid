/* SPDX-License-Identifier: ISC
 * Plaid research harness: exact-pinned-ares VR4300 Watch exception probe.
 *
 * The guest itself writes WatchLo with MTC0 and then executes one data access.
 * This intentionally asks whether ares turns its modeled Watch registers into
 * an architectural exception, rather than merely proving that the fields exist.
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
  if(argc != 7) return 2;
  const char* name = argv[1];
  const char* kind = argv[2];
  int bev = std::atoi(argv[3]);
  int exl = std::atoi(argv[4]);
  u32 watchlo = (u32)std::strtoul(argv[5], nullptr, 0);
  u32 offset = (u32)std::strtoul(argv[6], nullptr, 0);
  bool loadAccess = !std::strcmp(kind, "load");
  bool storeAccess = !std::strcmp(kind, "store");
  if(!(loadAccess || storeAccess) || (bev & ~1) || (exl & ~1) || offset > 0x100) return 2;

  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid Watch exception fixture");
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
  constexpr u64 dataVirtualBase = 0xffffffffa0001000ull;
  constexpr u32 dataPhysicalBase = 0x1000;
  constexpr u32 initialData = 0x11223344;
  constexpr u32 storeData = 0x55667788;
  constexpr u32 mtc0T0WatchLo = 0x40889000;  // MTC0 $t0,$18
  constexpr u32 lwS1S2 = 0x8e510000;         // LW $s1,0($s2)
  constexpr u32 swS1S2 = 0xae510000;         // SW $s1,0($s2)

  // Guest program: configure WatchLo, give the CP0 write generous hazard space,
  // then issue one ordinary uncached load/store to the requested physical block.
  put(0x00, mtc0T0WatchLo);
  put(0x04, 0);
  put(0x08, 0);
  put(0x0c, 0);
  put(0x10, 0);
  put(0x14, loadAccess ? lwS1S2 : swS1S2);
  put(0x18, 0);
  put(dataPhysicalBase + offset, initialData);

  cpu.ipu.r[8].u64 = watchlo;  // $t0 -> WatchLo
  cpu.ipu.r[18].u64 = dataVirtualBase + offset;  // $s2
  cpu.ipu.r[17].u64 = storeData;  // $s1 for store; overwritten by successful load
  cpu.scc.status.vectorLocation = bev;
  cpu.scc.status.exceptionLevel = exl;
  cpu.scc.status.errorLevel = 0;
  cpu.scc.cause.exceptionCode = causeSentinel;
  cpu.scc.cause.branchDelay = 1;
  cpu.scc.epc = epcSentinel;
  cpu.context.setMode();
  cpu.pipeline.setPc(startPc);

  // Stop immediately after the access. If a Watch exception exists, this leaves
  // PC at its selected vector. Otherwise the access retires and PC advances.
  for(int n = 0; n < 6; n++) {
    if(cpu.instruction()) cpu.synchronize();
  }

  u32 finalData = rdram.ram.read<Word>(dataPhysicalBase + offset, RBusDevice::ARES_DEBUGGER);
  std::printf(
    "{\"name\":\"%s\",\"kind\":\"%s\",\"bev\":%d,\"initial_exl\":%d,"
    "\"watchlo_requested\":%u,\"watch_write\":%u,\"watch_read\":%u,\"watch_base\":%u,"
    "\"offset\":%u,\"pc\":%llu,\"s1\":%llu,\"cause\":%u,\"bd\":%u,\"epc\":%llu,"
    "\"final_exl\":%u,\"final_data\":%u}\n",
    name, kind, bev, exl, watchlo,
    (u32)cpu.scc.watchLo.trapOnWrite,
    (u32)cpu.scc.watchLo.trapOnRead,
    (u32)cpu.scc.watchLo.physicalAddress,
    offset,
    (unsigned long long)cpu.ipu.pc,
    (unsigned long long)cpu.ipu.r[17].u64,
    (u32)cpu.scc.cause.exceptionCode,
    (u32)cpu.scc.cause.branchDelay,
    (unsigned long long)cpu.scc.epc,
    (u32)cpu.scc.status.exceptionLevel,
    finalData);

  ares::Nintendo64::system.unload();
  return 0;
}
