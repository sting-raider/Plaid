/* SPDX-License-Identifier: ISC
 * Controlled overlapping uncached LW -> SW copy fixture for pinned ares.
 */
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>

static constexpr u32 DataBase = 0x1000;
static constexpr u32 CodeBase = 0x6000;
static constexpr u32 A = 0x11111111;
static constexpr u32 B = 0x22222222;
static constexpr u32 C = 0x33333333;
static constexpr u32 D = 0x44444444;
static constexpr u32 EQUAL = 0xa5a5a5a5;

static void put(u32 address, u32 word) {
  rdram.ram.write<Word>(address, word, RBusDevice::ARES_DEBUGGER);
}

static u32 backing(u32 address) {
  return rdram.ram.read<Word>(address, RBusDevice::ARES_DEBUGGER);
}

static void init_words(bool equal) {
  put(DataBase + 0x00, equal ? EQUAL : A);
  put(DataBase + 0x04, equal ? EQUAL : B);
  put(DataBase + 0x08, equal ? EQUAL : C);
  put(DataBase + 0x0c, equal ? EQUAL : D);
  put(DataBase + 0x10, equal ? EQUAL : 0x55555555);
}

static void run_case(u32 code_offset) {
  cpu.ipu.r[16].u64 = 0xffffffffa0001000ull;
  cpu.ipu.r[17].u64 = 0xffffffffa0001004ull;
  cpu.ipu.r[8].u64 = 0;
  cpu.pipeline.setPc(0xffffffff80000000ull | (CodeBase + code_offset));
  for(u32 i = 0; i < 6; i++) if(cpu.instruction()) cpu.synchronize();
}

static void print_words(const char* name) {
  std::printf("\"%s\":[%u,%u,%u,%u]", name,
    backing(DataBase + 0x00), backing(DataBase + 0x04),
    backing(DataBase + 0x08), backing(DataBase + 0x0c));
}

int main() {
  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid overlap CPU copy fixture");
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
  for(auto& reg : cpu.ipu.r) reg.u64 = 0;
  cpu.scc.status.errorLevel = cpu.scc.status.exceptionLevel = 0;
  cpu.context.setMode();
  cpu.dcache.power(false);
  cpu.icache.power(false);

  // Forward overlap: src=0x1000, dst=0x1004, three words.
  put(CodeBase + 0x00, 0x8e080000); // LW t0,0(s0)
  put(CodeBase + 0x04, 0xae280000); // SW t0,0(s1)
  put(CodeBase + 0x08, 0x8e080004); // LW t0,4(s0), reads prior destination
  put(CodeBase + 0x0c, 0xae280004);
  put(CodeBase + 0x10, 0x8e080008); // LW t0,8(s0), reads prior destination
  put(CodeBase + 0x14, 0xae280008);

  // Backward overlap: same logical span, highest word first.
  put(CodeBase + 0x40, 0x8e080008);
  put(CodeBase + 0x44, 0xae280008);
  put(CodeBase + 0x48, 0x8e080004);
  put(CodeBase + 0x4c, 0xae280004);
  put(CodeBase + 0x50, 0x8e080000);
  put(CodeBase + 0x54, 0xae280000);

  std::printf("{");
  init_words(false);
  run_case(0x00);
  print_words("forward_unique");
  std::printf(",");

  init_words(false);
  run_case(0x40);
  print_words("backward_unique");
  std::printf(",");

  init_words(true);
  run_case(0x00);
  print_words("forward_equal");
  std::printf(",");

  init_words(true);
  run_case(0x40);
  print_words("backward_equal");

  auto ramHash = nall::Hash::SHA256(std::span<const u8>{rdram.ram.data, rdram.ram.size}).digest();
  std::printf(",\"state\":{\"pc\":%llu,\"count\":%llu,\"ram_sha256\":\"%s\"}}\n",
    (unsigned long long)cpu.ipu.pc, (unsigned long long)cpu.effectiveCount(), ramHash.data());
  ares::Nintendo64::system.unload();
  return 0;
}
