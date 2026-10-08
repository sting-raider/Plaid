/* SPDX-License-Identifier: ISC
 * Plaid research harness for pinned ares VR4300 SB/SH stores.
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
static constexpr u32 SB_VALUE = 0x81;
static constexpr u32 SH_VALUE = 0x92a3;

static void rawReset() {
  cpu.dcache.power(false);
  for(u32 i=0;i<32;i++) rdram.ram.write<Byte>(PHYS+i, 0x10+i, RBusDevice::ARES_DEBUGGER);
  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.cause.exceptionCode = 0;
  cpu.scc.cause.branchDelay = 0;
  cpu.scc.badVirtualAddress = 0;
  cpu.context.setMode();
  cpu.pipeline.setPc(0xffffffffa0001000ull);
  for(auto& r : cpu.ipu.r) r.u64 = 0;
}

static void printRaw(const char* key) {
  std::printf("\"%s\":[", key);
  for(u32 i=0;i<24;i++) {
    std::printf("%s%u", i ? "," : "", (u32)rdram.ram.read<Byte>(PHYS+i, RBusDevice::ARES_DEBUGGER));
  }
  std::printf("]");
}

static u64 readValue(const char* op, u64 address) {
  if(!std::strcmp(op,"SB")) {
    auto value = cpu.read<Byte>(address);
    return value ? (u64)*value : ~0ull;
  }
  auto value = cpu.read<Half>(address);
  return value ? (u64)*value : ~0ull;
}

static void executeOne(const char* op, u64 address, u32 value) {
  cpu.ipu.r[1].u64 = address;
  cpu.ipu.r[2].u64 = value;
  if(!std::strcmp(op,"SB")) cpu.SB(cpu.ipu.r[2], cpu.ipu.r[1], 0);
  else cpu.SH(cpu.ipu.r[2], cpu.ipu.r[1], 0);
}

static void constructWord(const char* op, bool little) {
  if(!std::strcmp(op,"SB")) {
    static constexpr u8 big[4] = {0x11,0x22,0x33,0x44};
    static constexpr u8 littleValues[4] = {0x44,0x33,0x22,0x11};
    auto* values = little ? littleValues : big;
    for(u32 i=0;i<4;i++) executeOne("SB", UNCACHED + 8 + i, values[i]);
  } else {
    if(!little) {
      executeOne("SH", UNCACHED + 8, 0x1122);
      executeOne("SH", UNCACHED + 10, 0x3344);
    } else {
      executeOne("SH", UNCACHED + 8, 0x3344);
      executeOne("SH", UNCACHED + 10, 0x1122);
    }
  }
}

int main(int argc, char** argv) {
  if(argc != 5) return 2;
  const char* mode = argv[1];
  const char* op = argv[2];
  const char* endian = argv[3];
  int offset = std::atoi(argv[4]);
  if(offset < 0 || offset > 7) return 2;
  if(std::strcmp(op,"SB") && std::strcmp(op,"SH")) return 2;
  if(std::strcmp(endian,"big") && std::strcmp(endian,"little")) return 2;
  if(std::strcmp(mode,"uncached") && std::strcmp(mode,"cached") &&
     std::strcmp(mode,"tlbmiss") && std::strcmp(mode,"construct")) return 2;

  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid SB SH store research");
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
  bool little = !std::strcmp(endian,"little");
  cpu.context.endian = little ? CPU::Context::Little : CPU::Context::Big;

  u64 base = !std::strcmp(mode,"cached") ? CACHED
           : !std::strcmp(mode,"tlbmiss") ? 0x2000ull
           : UNCACHED;
  u64 address = base + offset;

  std::printf("{\"mode\":\"%s\",\"op\":\"%s\",\"endian\":\"%s\",\"context_little\":%u,\"offset\":%d,",
    mode,op,endian,(u32)cpu.context.littleEndian(),offset);
  printRaw("before_raw");

  if(!std::strcmp(mode,"construct")) {
    constructWord(op, little);
    auto word = cpu.read<Word>(UNCACHED + 8);
    std::printf(",\"exception\":%u,\"badva\":%llu,\"dirty\":%u,\"constructed\":%llu,",
      (u32)cpu.scc.cause.exceptionCode,
      (unsigned long long)cpu.scc.badVirtualAddress,
      (u32)cpu.dcache.line(UNCACHED + 8).dirty,
      (unsigned long long)(word ? *word : ~0u));
    printRaw("after_raw");
    std::printf("}\n");
    ares::Nintendo64::system.unload();
    return 0;
  }

  u64 aliasBefore = readValue(op, UNCACHED + offset);
  executeOne(op, address, !std::strcmp(op,"SB") ? SB_VALUE : SH_VALUE);

  u32 exception = cpu.scc.cause.exceptionCode;
  u64 badva = cpu.scc.badVirtualAddress;
  u32 dirty = cpu.dcache.line(address).dirty;

  std::printf(",\"exception\":%u,\"badva\":%llu,\"dirty\":%u,",
    exception,(unsigned long long)badva,dirty);
  printRaw("after_raw");

  bool success = exception == 0;
  if(success) {
    u64 readback = readValue(op, address);
    u64 aliasAfter = readValue(op, UNCACHED + offset);
    std::printf(",\"readback\":%llu,\"alias_before\":%llu,\"alias_after\":%llu",
      (unsigned long long)readback,
      (unsigned long long)aliasBefore,
      (unsigned long long)aliasAfter);
  } else {
    std::printf(",\"alias_before\":%llu", (unsigned long long)aliasBefore);
  }
  std::printf("}\n");
  ares::Nintendo64::system.unload();
  return 0;
}
