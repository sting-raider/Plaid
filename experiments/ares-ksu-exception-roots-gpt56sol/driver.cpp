/* SPDX-License-Identifier: ISC
 * Plaid research harness: KSU/X-bit composition with exception roots.
 * Builds against the exact pinned ares research reference only.
 */
#include <n64/n64.hpp>
#include <cstdio>
#include <cstdlib>
#include <cstring>
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

static auto parse_u64(const char* text) -> u64 {
  char* end = nullptr;
  unsigned long long value = std::strtoull(text, &end, 0);
  if(!end || *end) std::exit(2);
  return (u64)value;
}

int main(int argc, char** argv) {
  if(argc != 5) return 2;
  const char* modeName = argv[1];
  int bits = std::atoi(argv[2]);
  int bev = std::atoi(argv[3]);
  u64 va = parse_u64(argv[4]);
  if((bits != 32 && bits != 64) || (bev != 0 && bev != 1)) return 2;

  u32 mode = 0;
  if(!std::strcmp(modeName, "kernel")) mode = 0;
  else if(!std::strcmp(modeName, "supervisor")) mode = 1;
  else if(!std::strcmp(modeName, "user")) mode = 2;
  else return 2;

  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid KSU exception root fixture");
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

  // If a privileged direct/RDRAM path is accidentally admitted, make execution
  // observable without relying on the post-fetch PC alone.
  put(0, 0x24020001);  // ADDIU $v0,$zero,1
  put(4, 0x00000000);  // NOP

  // Start with no usable TLB entry. A mapped address must therefore become a
  // true TLB miss, while an architecturally unused segment must become AdEL.
  for(auto& entry : cpu.tlb.entry) entry = {};
  for(auto& cached : cpu.tlb.tlbCache.entry) {
    cached.entry = nullptr;
    cached.frequency = 0;
  }

  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.status.privilegeMode = mode;
  cpu.scc.status.vectorLocation = bev;
  cpu.scc.status.userExtendedAddressing = mode == 2 && bits == 64;
  cpu.scc.status.supervisorExtendedAddressing = mode == 1 && bits == 64;
  cpu.scc.status.kernelExtendedAddressing = mode == 0 && bits == 64;
  cpu.scc.epc = 0x123456789abcdef0ull;
  cpu.scc.badVirtualAddress = 0x0badf00dull;
  cpu.scc.cause.exceptionCode = 31;
  cpu.scc.cause.branchDelay = 0;
  cpu.context.setMode();

  u32 initialContextBits = cpu.context.bits;
  u32 initialContextMode = (u32)cpu.context.mode;
  cpu.pipeline.setPc(va);
  if(cpu.instruction()) cpu.synchronize();

  std::printf(
    "{\"mode\":\"%s\",\"requested_bits\":%d,\"bev\":%d,\"va\":%llu,"
    "\"initial_context_bits\":%u,\"initial_context_mode\":%u,"
    "\"pc\":%llu,\"cause\":%u,\"epc\":%llu,\"badva\":%llu,"
    "\"final_exl\":%u,\"v0\":%llu}\n",
    modeName, bits, bev, (unsigned long long)va,
    initialContextBits, initialContextMode,
    (unsigned long long)cpu.ipu.pc,
    (u32)cpu.scc.cause.exceptionCode,
    (unsigned long long)cpu.scc.epc,
    (unsigned long long)cpu.scc.badVirtualAddress,
    (u32)cpu.scc.status.exceptionLevel,
    (unsigned long long)cpu.ipu.r[2].u64);

  ares::Nintendo64::system.unload();
  return 0;
}
