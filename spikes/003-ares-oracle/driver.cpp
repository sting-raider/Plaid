/* SPDX-License-Identifier: ISC
 * Original Plaid research harness, 2026. Reference implementation stays separate.
 */
#include <n64/n64.hpp>
#include <cstdio>
#include <cstring>
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
  if(argc != 2 && !(argc == 3 && !strcmp(argv[1], "fixture"))) return 2;
  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid original oracle fixture");
  frontend.cartPak->setAttribute("region", "NTSC");
  frontend.cartPak->setAttribute("cic", "CIC-NUS-6102");
  frontend.cartPak->append("program.rom", 8192);
  if(!strcmp(argv[1], "cartridge")) {
    const u32 words[] = {0x3c08b000,0x35081020,0x0100f809,0x24100005,
      0x26310003,0,0,0,0x26520007,0x03e00008,0x26730002};
    auto rom = frontend.cartPak->write("program.rom");
    rom->seek(0x1000);
    for(auto word : words) rom->writem(word, 4);
  }
  Node::System root;
  if(!load(root, "[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak", "true");
  option("Deterministic Entropy", "true");
  option("Recompiler", "false");
  cartridgeSlot.port->allocate();
  cartridgeSlot.port->connect();
  ares::Nintendo64::system.power(false);
  // Explicit synthetic post-initialization state. No firmware is executed.
  // The frontend renderer normally owns hidden-RAM backing. Supply it for
  // headless CPU writes without altering the reference memory implementation.
  std::vector<u8> hidden(rdram.ram.size / 2);
  rdram.hidden.data = hidden.data();
  for(auto& reg : cpu.ipu.r) reg.u64 = 0;
  rdram.mapIdentity = 1;
  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.context.setMode();
  cpu.pipeline.setPc(0xffffffffa0000000ull);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;
  auto put = [](u32 address, u32 word) { rdram.ram.write<Word>(address, word, RBusDevice::ARES_DEBUGGER); };
  int steps = 1;
  if(!strcmp(argv[1], "cartridge")) {
    cpu.pipeline.setPc(0xffffffffb0001000ull);
    steps = 8;
  } else if(!strcmp(argv[1], "fixture")) {
    auto file = std::fopen(argv[2], "rb");
    if(!file || std::fseek(file, 64, SEEK_SET)) return 6;
    u8 bytes[4]; u32 offset = 0;
    while(std::fread(bytes, 1, 4, file) == 4) {
      if(offset >= 0x10000) return 6;
      put(offset, (u32)bytes[0]<<24 | (u32)bytes[1]<<16 | (u32)bytes[2]<<8 | bytes[3]);
      offset += 4;
    }
    std::fclose(file);
    cpu.ipu.r[10].u64 = 3;
    cpu.ipu.r[25].u64 = 0xffffffff80000000ull; // Shared synthetic SP bootstrap result.
    cpu.pipeline.setPc(0xffffffff80000000ull);
    steps = 10000;
  } else {
    cpu.ipu.r[3].u64 = 0xffffffffa0002000ull;
    rdram.ram.write<Dual>(0x2000,0x123456789abcdef0ull,RBusDevice::ARES_DEBUGGER);
    if(!strcmp(argv[1], "linked")) {
      put(0,0xd0640000); // LLD r4,0(r3)
      put(4,0x64840001); // DADDIU r4,r4,1
      put(8,0xf0640000); // SCD r4,0(r3)
      steps = 3;
    } else if(!strcmp(argv[1], "unaligned")) put(0,0x8c640001);
    else if(!strcmp(argv[1], "slot_exception")) {
      put(0,0x10000001); put(4,0x8c640001); steps = 2;
    } else return 5;
  }
  for(int n=0;n<steps;n++) {
    if(!strcmp(argv[1], "fixture") && (u32)cpu.ipu.pc == 0x80000100) break;
    if(cpu.instruction()) cpu.synchronize();
  }
  if(!strcmp(argv[1], "fixture") && (u32)cpu.ipu.pc != 0x80000100) return 7;
  std::printf("{\"pc\":%u,\"regs\":[", (u32)cpu.ipu.pc);
  for(int n=0;n<32;n++) std::printf("%s%lld",n ? "," : "",(long long)(int64_t)cpu.ipu.r[n].u64);
  std::printf("],\"hi\":%lld,\"lo\":%lld,\"exception\":%u,\"bd\":%u,\"epc\":%llu,\"badva\":%llu,\"lladdr\":%u,\"memory\":%llu}\n",
    (long long)(int64_t)cpu.ipu.hi.u64,(long long)(int64_t)cpu.ipu.lo.u64,
    (u32)cpu.scc.cause.exceptionCode,(u32)cpu.scc.cause.branchDelay,(unsigned long long)cpu.scc.epc,
    (unsigned long long)cpu.scc.badVirtualAddress,(u32)cpu.scc.ll,
    (unsigned long long)rdram.ram.read<Dual>(0x2000,RBusDevice::ARES_DEBUGGER));
  ares::Nintendo64::system.unload();
  return 0;
}
