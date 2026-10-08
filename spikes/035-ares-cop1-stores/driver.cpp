/* SPDX-License-Identifier: ISC
 * Plaid research harness for pinned ares VR4300 COP1 stores.
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

static constexpr u32 PHYS = 0x2000;
static constexpr u64 CACHED = 0xffffffff80002000ull;
static constexpr u64 UNCACHED = 0xffffffffa0002000ull;
static constexpr u64 FPRS[4] = {
  0x1122334455667788ull, 0x99aabbccddeeff00ull,
  0x0123456789abcdefull, 0xfedcba9876543210ull,
};

static void resetState(bool fr, bool cu1, bool little) {
  cpu.dcache.power(false);
  for(u32 i=0;i<32;i++) rdram.ram.write<Byte>(PHYS+i, 0xa0+i, RBusDevice::ARES_DEBUGGER);
  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.status.enable.coprocessor1 = cu1;
  cpu.scc.status.floatingPointMode = fr;
  cpu.scc.cause.exceptionCode = 0;
  cpu.scc.cause.coprocessorError = 0;
  cpu.scc.cause.branchDelay = 0;
  cpu.scc.badVirtualAddress = 0;
  cpu.context.setMode();
  cpu.context.endian = little ? CPU::Context::Little : CPU::Context::Big;
  cpu.pipeline.setPc(0xffffffffa0001000ull);
  for(auto& r : cpu.ipu.r) r.u64 = 0;
  for(auto& r : cpu.fpu.r) r.u64 = 0;
  for(u32 i=0;i<4;i++) cpu.fpu.r[i].u64 = FPRS[i];
}

static void printRaw(const char* key) {
  std::printf("\"%s\":[", key);
  for(u32 i=0;i<16;i++) std::printf("%s%u", i ? "," : "", (u32)rdram.ram.read<Byte>(PHYS+i, RBusDevice::ARES_DEBUGGER));
  std::printf("]");
}

static void printGuest(const char* key, u64 address) {
  std::printf("\"%s\":[", key);
  for(u32 i=0;i<16;i++) {
    auto value = cpu.read<Byte>(address+i);
    std::printf("%s%u", i ? "," : "", value ? (u32)*value : 0u);
  }
  std::printf("]");
}

int main(int argc, char** argv) {
  if(argc != 7) return 2;
  const char* op = argv[1];
  const char* mode = argv[2];
  int fr = std::atoi(argv[3]);
  int ft = std::atoi(argv[4]);
  const char* endian = argv[5];
  int offset = std::atoi(argv[6]);
  if(std::strcmp(op,"SWC1") && std::strcmp(op,"SDC1")) return 2;
  if(fr < 0 || fr > 1 || ft < 0 || ft > 3 || offset < 0 || offset > 7) return 2;
  if(std::strcmp(endian,"big") && std::strcmp(endian,"little")) return 2;
  bool cu1 = std::strcmp(mode,"cu1off") && std::strcmp(mode,"cu1off_misalign");
  bool little = !std::strcmp(endian,"little");

  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid COP1 store research");
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

  resetState(fr, cu1, little);
  u64 base = !std::strcmp(mode,"cached") ? CACHED : !std::strcmp(mode,"tlbmiss") ? 0x2000ull : UNCACHED;
  if(!std::strcmp(mode,"cu1off_misalign")) offset = 1;

  std::printf("{\"op\":\"%s\",\"mode\":\"%s\",\"fr\":%d,\"ft\":%d,\"endian\":\"%s\",\"offset\":%d,", op,mode,fr,ft,endian,offset);
  printRaw("before_raw"); std::printf(",");
  printGuest("before_alias", UNCACHED); std::printf(",");

  cpu.ipu.r[1].u64 = base;
  if(!std::strcmp(op,"SWC1")) cpu.SWC1(ft, cpu.ipu.r[1], offset);
  else cpu.SDC1(ft, cpu.ipu.r[1], offset);

  u32 dirty = cpu.dcache.line(CACHED).dirty;
  std::printf("\"exception\":%u,\"coprocessor_error\":%u,\"badva\":%llu,\"dirty\":%u,", (u32)cpu.scc.cause.exceptionCode, (u32)cpu.scc.cause.coprocessorError, (unsigned long long)cpu.scc.badVirtualAddress, dirty);
  printRaw("after_raw"); std::printf(",");
  printGuest("after_alias", UNCACHED);
  if(!std::strcmp(mode,"cached")) { std::printf(","); printGuest("after_cached", CACHED); }
  std::printf("}\n");

  ares::Nintendo64::system.unload();
  return 0;
}
