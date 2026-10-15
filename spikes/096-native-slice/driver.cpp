/* SPDX-License-Identifier: ISC
 * Original Plaid research harness, 2026. Reference implementation stays separate.
 * Runs raw big-endian words at 0x80000000 on the pinned ares interpreter until
 * PC reaches the exit address, then prints the state compared by spike096.
 */
#include <n64/n64.hpp>
#include <cstdio>
#include <cstdlib>
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
  if(argc != 3) return 2;
  u32 exit = (u32)std::strtoul(argv[2], nullptr, 0);
  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid native slice oracle");
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
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;
  for(auto& reg : cpu.ipu.r) reg.u64 = 0;
  cpu.ipu.hi.u64 = cpu.ipu.lo.u64 = 0;
  for(auto& reg : cpu.fpu.r) reg.s64 = 0;
  rdram.mapIdentity = 1;
  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.status.enable.coprocessor1 = 1;  // CU1 = 1, FR = 1 (ADR-0131)
  cpu.scc.status.floatingPointMode = 1;
  cpu.context.setMode();
  auto file = std::fopen(argv[1], "rb");
  if(!file) return 5;
  u8 b[4]; u32 offset = 0;
  while(std::fread(b, 1, 4, file) == 4) {
    rdram.ram.write<Word>(offset, (u32)b[0]<<24 | (u32)b[1]<<16 | (u32)b[2]<<8 | b[3], RBusDevice::ARES_DEBUGGER);
    offset += 4;
  }
  std::fclose(file);
  cpu.pipeline.setPc(0xffffffff80000000ull);
  int n = 0;
  for(; n < 1000000 && (u32)cpu.ipu.pc != exit; n++) if(cpu.instruction()) cpu.synchronize();
  if((u32)cpu.ipu.pc != exit || cpu.scc.cause.exceptionCode) return 6;
  std::printf("{\"pc\":%u,\"regs\":[", (u32)cpu.ipu.pc);
  for(int r = 0; r < 32; r++) std::printf("%s%llu", r ? "," : "", (unsigned long long)cpu.ipu.r[r].u64);
  std::printf("],\"hi\":%llu,\"lo\":%llu,\"fpr\":[", (unsigned long long)cpu.ipu.hi.u64, (unsigned long long)cpu.ipu.lo.u64);
  for(int r = 0; r < 32; r++) std::printf("%s%llu", r ? "," : "", (unsigned long long)cpu.fpu.r[r].s64);
  std::printf("],\"fcc\":%u,\"fcsr\":%u,\"ram\":[", (unsigned)cpu.fpu.csr.compare, (unsigned)cpu.getControlRegisterFPU(31));
  // CPU-coherent view through the write-back D-cache, without line fills.
  // The pinned core instantiates only the Byte debug read.
  for(u32 a = 0x1000; a < 0x1100; a += 4) {
    u32 word = 0;
    for(u32 n = 0; n < 4; n++) word = word << 8 | (u8)cpu.dcache.readDebug<Byte>(0xffffffff80000000ull | (a + n), a + n);
    std::printf("%s%u", a != 0x1000 ? "," : "", word);
  }
  std::printf("]}\n");
  ares::Nintendo64::system.unload();
  return 0;
}
