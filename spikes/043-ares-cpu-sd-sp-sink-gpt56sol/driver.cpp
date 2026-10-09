/* SPDX-License-Identifier: ISC
 * Plaid research harness for pinned ares integer SD stores into SP DMEM/IMEM.
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

struct Sink { u32 address, bank, offset, value; bool cpu; };
static std::vector<Sink> sinks;
static void spWord(bool write, u32 address, u32 bank, u32 offset, u32 value, bool originCpu) {
  if(write) sinks.push_back({address, bank, offset, value, originCpu});
}

static constexpr u64 DATA = 0x1122334455667788ull;
static constexpr u32 HIGH = 0x11223344u;
static constexpr u32 DINIT[4] = {0x80818283, 0x84858687, 0x88898a8b, 0x8c8d8e8f};
static constexpr u32 IINIT[4] = {0xc0c1c2c3, 0xc4c5c6c7, 0xc8c9cacb, 0xcccdcecf};

static void resetCpu() {
  cpu.dcache.power(false);
  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.cause.exceptionCode = 0;
  cpu.scc.cause.coprocessorError = 0;
  cpu.scc.cause.branchDelay = 0;
  cpu.scc.badVirtualAddress = 0;
  cpu.context.setMode();
  cpu.context.endian = CPU::Context::Big;
  cpu.pipeline.setPc(0xffffffffa0001000ull);
  for(auto& r : cpu.ipu.r) r.u64 = 0;
}

static void resetSp(bool imem, bool same, u32 offset) {
  for(u32 i = 0; i < 4; i++) {
    u32 d = DINIT[i];
    u32 m = IINIT[i];
    if(same && i == offset / 4) {
      if(imem) m = HIGH;
      else d = HIGH;
    }
    rsp.dmem.write<Word>(i * 4, d);
    rsp.imem.write<Word>(i * 4, m);
  }
}

static void printWords(const char* key, bool imem) {
  std::printf("\"%s\":[", key);
  auto& memory = imem ? rsp.imem : rsp.dmem;
  for(u32 i = 0; i < 4; i++) std::printf("%s%u", i ? "," : "", (u32)memory.read<Word>(i * 4));
  std::printf("]");
}

static void printBytes(const char* key, bool imem) {
  std::printf("\"%s\":[", key);
  auto& memory = imem ? rsp.imem : rsp.dmem;
  for(u32 i = 0; i < 16; i++) std::printf("%s%u", i ? "," : "", (u32)memory.read<Byte>(i));
  std::printf("]");
}

static void printSinks() {
  std::printf("\"sinks\":[");
  for(size_t i = 0; i < sinks.size(); i++) {
    const auto& s = sinks[i];
    std::printf("%s{\"address\":%u,\"bank\":%u,\"offset\":%u,\"value\":%u,\"cpu\":%s}",
      i ? "," : "", s.address, s.bank, s.offset, s.value, s.cpu ? "true" : "false");
  }
  std::printf("]");
}

int main(int argc, char** argv) {
  if(argc != 5) return 2;
  const char* bank = argv[1];
  const char* mode = argv[2];
  int requestedOffset = std::atoi(argv[3]);
  const char* observeArg = argv[4];
  if(std::strcmp(bank, "dmem") && std::strcmp(bank, "imem")) return 2;
  if(std::strcmp(mode, "ok") && std::strcmp(mode, "same") && std::strcmp(mode, "misalign") && std::strcmp(mode, "reserved")) return 2;
  if(requestedOffset < 0 || requestedOffset > 15) return 2;
  if(std::strcmp(observeArg, "on") && std::strcmp(observeArg, "off")) return 2;
  bool isImem = !std::strcmp(bank, "imem");
  bool observe = !std::strcmp(observeArg, "on");
  bool same = !std::strcmp(mode, "same");

  Headless frontend; platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid integer SD SP sink fixture");
  frontend.cartPak->setAttribute("region", "NTSC");
  frontend.cartPak->setAttribute("cic", "CIC-NUS-6102");
  frontend.cartPak->append("program.rom", 8192);
  Node::System root;
  if(!load(root, "[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak", "true");
  option("Deterministic Entropy", "true");
  option("Recompiler", "false");
  cartridgeSlot.port->allocate(); cartridgeSlot.port->connect();
  ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;

  resetCpu();
  u32 offset = requestedOffset;
  if(!std::strcmp(mode, "misalign")) offset = 4;
  resetSp(isImem, same, offset);
  sinks.clear();

  u64 base = isImem ? 0xffffffffa4001000ull : 0xffffffffa4000000ull;
  cpu.ipu.r[1].u64 = base;
  cpu.ipu.r[2].u64 = DATA;
  if(!std::strcmp(mode, "reserved")) {
    cpu.context.mode = CPU::Context::User;
    cpu.context.bits = 32;
  }

  std::printf("{\"bank\":\"%s\",\"mode\":\"%s\",\"requested_offset\":%d,\"offset\":%u,\"observer\":\"%s\",\"source\":%llu,",
    bank, mode, requestedOffset, offset, observeArg, (unsigned long long)DATA);
  printWords("before_target_words", isImem); std::printf(",");
  printWords("before_other_words", !isImem); std::printf(",");
  printBytes("before_target_bytes", isImem); std::printf(",");

  if(observe) plaidSpWordObserver = spWord;
  cpu.SD(cpu.ipu.r[2], cpu.ipu.r[1], offset);
  plaidSpWordObserver = nullptr;

  std::printf("\"exception\":%u,\"coprocessor_error\":%u,\"badva\":%llu,",
    (u32)cpu.scc.cause.exceptionCode, (u32)cpu.scc.cause.coprocessorError,
    (unsigned long long)cpu.scc.badVirtualAddress);
  printWords("after_target_words", isImem); std::printf(",");
  printWords("after_other_words", !isImem); std::printf(",");
  printBytes("after_target_bytes", isImem); std::printf(",");
  printSinks(); std::printf("}\n");

  ares::Nintendo64::system.unload();
  return 0;
}
