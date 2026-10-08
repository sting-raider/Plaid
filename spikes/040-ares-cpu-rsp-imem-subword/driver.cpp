/* SPDX-License-Identifier: ISC
 * Plaid research fixture: VR4300 SB/SH stores into RSP IMEM on pinned ares.
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

static constexpr u64 DATA = 0x1122334455667788ull;
static constexpr u64 IMEM_UNCACHED = 0xffffffffa4001000ull;  // paddr 0x04001000

static void printImem(const char* key) {
  std::printf("\"%s\":[", key);
  for(u32 i=0;i<16;i++) {
    std::printf("%s%u", i ? "," : "", (u32)rsp.imem.read<Byte>(i));
  }
  std::printf("]");
}

int main(int argc, char** argv) {
  if(argc != 4) return 2;
  const char* op = argv[1];
  const char* endian = argv[2];
  int offset = std::atoi(argv[3]);
  if(std::strcmp(op, "SB") && std::strcmp(op, "SH")) return 2;
  if(std::strcmp(endian, "big") && std::strcmp(endian, "little")) return 2;
  if(offset < 0 || offset > 7) return 2;

  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid CPU to RSP IMEM subword research");
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
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;

  std::vector<u8> hidden(rdram.ram.size / 2);
  rdram.hidden.data = hidden.data();
  rdram.mapIdentity = 1;

  for(u32 i=0;i<16;i++) rsp.imem.write<Byte>(i, 0xa0 + i);
  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.cause.exceptionCode = 0;
  cpu.scc.cause.branchDelay = 0;
  cpu.scc.badVirtualAddress = 0;
  cpu.scc.sysadFrozen = false;
  cpu.context.setMode();
  cpu.context.endian = !std::strcmp(endian, "little") ? CPU::Context::Little : CPU::Context::Big;
  cpu.pipeline.setPc(0xffffffffa0001000ull);
  for(auto& r : cpu.ipu.r) r.u64 = 0;
  cpu.ipu.r[1].u64 = IMEM_UNCACHED;
  cpu.ipu.r[2].u64 = DATA;

  std::printf("{\"op\":\"%s\",\"endian\":\"%s\",\"offset\":%d,", op, endian, offset);
  printImem("before"); std::printf(",");

  if(!std::strcmp(op, "SB")) cpu.SB(cpu.ipu.r[2], cpu.ipu.r[1], offset);
  else cpu.SH(cpu.ipu.r[2], cpu.ipu.r[1], offset);

  std::printf("\"exception\":%u,\"badva\":%llu,\"sysad_frozen\":%s,",
    (u32)cpu.scc.cause.exceptionCode,
    (unsigned long long)cpu.scc.badVirtualAddress,
    cpu.scc.sysadFrozen ? "true" : "false");
  printImem("after");
  std::printf("}\n");

  ares::Nintendo64::system.unload();
  return 0;
}
