/* SPDX-License-Identifier: ISC
 * Plaid research harness: guest-triggered R4300 exception-vector cases.
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
  if(argc != 6) return 2;
  const char* kind = argv[1];
  int bits = std::atoi(argv[2]);
  int bev = std::atoi(argv[3]);
  int exl = std::atoi(argv[4]);
  int delay = std::atoi(argv[5]);
  if((bits != 32 && bits != 64) || (bev != 0 && bev != 1) ||
     (exl != 0 && exl != 1) || (delay != 0 && delay != 1)) return 2;
  bool syscall = !std::strcmp(kind, "syscall");
  bool loadMiss = !std::strcmp(kind, "tlb_load_miss");
  bool storeMiss = !std::strcmp(kind, "tlb_store_miss");
  bool fetchMiss = !std::strcmp(kind, "tlb_fetch_miss");
  bool invalid = !std::strcmp(kind, "tlb_invalid");
  if(!(syscall || loadMiss || storeMiss || fetchMiss || invalid)) return 2;
  if(fetchMiss && delay) return 2;

  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid exception vector fixture");
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

  constexpr u64 epcSentinel = 0x123456789abcdef0ull;
  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.privilegeMode = 0;
  cpu.scc.status.vectorLocation = bev;
  cpu.scc.status.exceptionLevel = exl;
  cpu.scc.status.kernelExtendedAddressing = bits == 64;
  cpu.scc.epc = epcSentinel;
  cpu.scc.cause.branchDelay = exl ? 1 : 0;
  cpu.context.setMode();

  if(invalid) {
    auto& entry = cpu.tlb.entry[0];
    entry = {};
    entry.global[0] = entry.global[1] = 1;
    entry.valid[0] = entry.valid[1] = 0;
    entry.dirty[0] = entry.dirty[1] = 1;
    entry.cacheAlgorithm[0] = entry.cacheAlgorithm[1] = 2;
    entry.pageMask = 0;
    entry.virtualAddress = 0x4000;
    entry.addressSpaceID = 0;
    entry.region = 0;
    entry.synchronize();
    for(auto& cached : cpu.tlb.tlbCache.entry) {
      cached.entry = nullptr;
      cached.frequency = 0;
    }
  }

  int steps = 1;
  if(fetchMiss) {
    cpu.pipeline.setPc(0x4000ull);
  } else {
    u32 fault = syscall ? 0x0000000c : storeMiss ? 0xac640000 : 0x8c640000;
    if(delay) {
      put(0, 0x10000001);  // BEQ $zero,$zero,+1
      put(4, fault);       // fault in the architected delay slot
      put(8, 0);
      steps = 2;
    } else {
      put(0, fault);
    }
    cpu.ipu.r[3].u64 = 0x4000ull;  // mapped segment, intentionally absent/invalid TLB entry
    cpu.pipeline.setPc(0xffffffffa0000000ull);  // uncached direct instruction source
  }

  for(int n = 0; n < steps; n++) {
    if(cpu.instruction()) cpu.synchronize();
  }

  std::printf(
    "{\"kind\":\"%s\",\"requested_bits\":%d,\"bev\":%d,\"initial_exl\":%d,\"delay\":%d,"
    "\"pc\":%llu,\"cause\":%u,\"bd\":%u,\"epc\":%llu,\"badva\":%llu,\"final_exl\":%u,\"context_bits\":%u}\n",
    kind, bits, bev, exl, delay,
    (unsigned long long)cpu.ipu.pc,
    (u32)cpu.scc.cause.exceptionCode,
    (u32)cpu.scc.cause.branchDelay,
    (unsigned long long)cpu.scc.epc,
    (unsigned long long)cpu.scc.badVirtualAddress,
    (u32)cpu.scc.status.exceptionLevel,
    (u32)cpu.context.bits);
  ares::Nintendo64::system.unload();
  return 0;
}
