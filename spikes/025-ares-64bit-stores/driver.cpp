/* SPDX-License-Identifier: ISC
 * Plaid research harness for pinned ares VR4300 64-bit stores.
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
static constexpr u32 PHYS = 0x2000;
static constexpr u64 CACHED = 0xffffffff80002000ull;
static constexpr u64 UNCACHED = 0xffffffffa0002000ull;

static void rawReset() {
  cpu.dcache.power(false);
  for(u32 i=0;i<32;i++) rdram.ram.write<Byte>(PHYS+i, 0xa0+i, RBusDevice::ARES_DEBUGGER);
  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.cause.exceptionCode = 0;
  cpu.scc.cause.branchDelay = 0;
  cpu.scc.badVirtualAddress = 0;
  cpu.context.setMode();
  cpu.pipeline.setPc(0xffffffffa0001000ull);
  for(auto& r : cpu.ipu.r) r.u64 = 0;
}

static void printGuestBytes(const char* key, u64 guest) {
  std::printf("\"%s\":[", key);
  for(u32 i=0;i<24;i++) {
    auto value = cpu.read<Byte>(guest+i);
    std::printf("%s%u", i ? "," : "", value ? (u32)*value : 0u);
  }
  std::printf("]");
}

static void printRaw(const char* key) {
  std::printf("\"%s\":[", key);
  for(u32 i=0;i<24;i++) std::printf("%s%u", i ? "," : "", (u32)rdram.ram.read<Byte>(PHYS+i, RBusDevice::ARES_DEBUGGER));
  std::printf("]");
}

static void execute(const char* op, u64 base, int offset) {
  cpu.ipu.r[1].u64 = base;
  cpu.ipu.r[2].u64 = DATA;
  if(!std::strcmp(op,"SD")) cpu.SD(cpu.ipu.r[2], cpu.ipu.r[1], offset);
  else if(!std::strcmp(op,"SDL")) cpu.SDL(cpu.ipu.r[2], cpu.ipu.r[1], offset);
  else if(!std::strcmp(op,"SDR")) cpu.SDR(cpu.ipu.r[2], cpu.ipu.r[1], offset);
}

int main(int argc, char** argv) {
  if(argc != 5) return 2;
  const char* mode = argv[1];
  const char* op = argv[2];
  const char* endian = argv[3];
  int offset = std::atoi(argv[4]);
  if(offset < 0 || offset > 7) return 2;
  if(std::strcmp(op,"SD") && std::strcmp(op,"SDL") && std::strcmp(op,"SDR")) return 2;
  if(std::strcmp(endian,"big") && std::strcmp(endian,"little")) return 2;

  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid 64-bit store research");
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
  rawReset();
  cpu.context.endian = !std::strcmp(endian,"little") ? CPU::Context::Little : CPU::Context::Big;

  u64 base = !std::strcmp(mode,"cached") ? CACHED : !std::strcmp(mode,"tlbmiss") ? 0x2000ull : UNCACHED;
  std::printf("{\"mode\":\"%s\",\"op\":\"%s\",\"endian\":\"%s\",\"context_little\":%u,\"offset\":%d,",
    mode,op,endian,(u32)cpu.context.littleEndian(),offset);
  if(std::strcmp(mode,"tlbmiss")) { printGuestBytes("before_guest",UNCACHED); std::printf(","); }
  printRaw("before_raw"); std::printf(",");

  if(!std::strcmp(mode,"pair")) {
    int target = offset;
    if(!std::strcmp(endian,"big")) {
      execute("SDL", UNCACHED, target);
      execute("SDR", UNCACHED, target + 7);
    } else {
      execute("SDR", UNCACHED, target);
      execute("SDL", UNCACHED, target + 7);
    }
    base = UNCACHED;
  } else execute(op, base, offset);

  std::printf("\"exception\":%u,\"badva\":%llu,\"dirty\":%u,",
    (u32)cpu.scc.cause.exceptionCode,
    (unsigned long long)cpu.scc.badVirtualAddress,
    (u32)cpu.dcache.line(base).dirty);
  printRaw("after_raw"); std::printf(",");
  if(!std::strcmp(mode,"tlbmiss")) {
    printGuestBytes("alias_after",UNCACHED);
  } else {
    printGuestBytes("after_guest",base); std::printf(",");
    printGuestBytes("alias_after",UNCACHED);
  }
  std::printf("}\n");
  ares::Nintendo64::system.unload();
  return 0;
}
