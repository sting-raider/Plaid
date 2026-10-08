/* SPDX-License-Identifier: ISC
 * Plaid research harness: guest-triggered VR4300 SD/SDL/SDR mutation cases.
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

static constexpr u64 CODE_VADDR = 0xffffffffa0000000ull;
static constexpr u64 DATA_VADDR = 0xffffffffa0000100ull;
static constexpr u32 DATA_PADDR = 0x00000100u;
static constexpr u64 PAYLOAD = 0x1122334455667788ull;
static constexpr u32 WINDOW = 24;

static auto encode_store(u32 opcode, u32 rs, u32 rt, s16 imm) -> u32 {
  return opcode << 26 | rs << 21 | rt << 16 | (u16)imm;
}

static auto physical_byte(u64 vaddr, bool little) -> u32 {
  u32 paddr = (u32)vaddr & 0x1fffffffu;
  if(little) paddr ^= 7;
  return paddr;
}

static auto put_instruction(u64 vaddr, u32 word, bool little) -> void {
  u32 paddr = (u32)vaddr & 0x1fffffffu;
  if(little) paddr ^= 4;
  rdram.ram.write<Word>(paddr, word, RBusDevice::ARES_DEBUGGER);
}

static auto put_guest_byte(u64 vaddr, u8 value, bool little) -> void {
  rdram.ram.write<Byte>(physical_byte(vaddr, little), value, RBusDevice::ARES_DEBUGGER);
}

static auto guest_byte(u64 vaddr, bool little) -> u8 {
  return (u8)rdram.ram.read<Byte>(physical_byte(vaddr, little), RBusDevice::ARES_DEBUGGER);
}

static auto physical_byte_at(u32 paddr) -> u8 {
  return (u8)rdram.ram.read<Byte>(paddr, RBusDevice::ARES_DEBUGGER);
}

static auto print_array(const char* name, const std::vector<u8>& bytes, bool comma) -> void {
  std::printf("\"%s\":[", name);
  for(size_t i = 0; i < bytes.size(); i++) {
    if(i) std::printf(",");
    std::printf("%u", (unsigned)bytes[i]);
  }
  std::printf("]%s", comma ? "," : "");
}

int main(int argc, char** argv) {
  if(argc != 5) return 2;
  const char* kind = argv[1];
  int offset = std::atoi(argv[2]);
  int littleArg = std::atoi(argv[3]);
  const char* addressKind = argv[4];
  if(offset < 0 || offset > 7 || (littleArg != 0 && littleArg != 1)) return 2;
  bool little = littleArg != 0;
  bool sd = !std::strcmp(kind, "sd");
  bool sdl = !std::strcmp(kind, "sdl");
  bool sdr = !std::strcmp(kind, "sdr");
  bool pair = !std::strcmp(kind, "pair");
  bool direct = !std::strcmp(addressKind, "direct");
  bool tlb = !std::strcmp(addressKind, "tlb");
  if(!(sd || sdl || sdr || pair) || !(direct || tlb) || (pair && tlb)) return 2;

  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid SD SDL SDR fixture");
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

  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.status.vectorLocation = 0;
  cpu.scc.status.privilegeMode = 0;
  cpu.scc.status.kernelExtendedAddressing = 1;
  cpu.scc.configuration.bigEndian = little ? 0 : 1;
  cpu.context.setMode();
  if(cpu.context.bits != 64 || cpu.context.littleEndian() != little) return 5;

  for(u32 i = 0; i < WINDOW; i++) put_guest_byte(DATA_VADDR + i, (u8)(0xa0u + i), little);
  std::vector<u8> before, physicalBefore;
  for(u32 i = 0; i < WINDOW; i++) before.push_back(guest_byte(DATA_VADDR + i, little));
  for(u32 i = 0; i < WINDOW; i++) physicalBefore.push_back(physical_byte_at(DATA_PADDR + i));

  constexpr u32 RS = 3, RT = 4;
  u32 opcode = sd ? 0x3f : sdl ? 0x2c : 0x2d;
  u64 base = direct ? DATA_VADDR : 0x4000ull;
  s16 imm = (s16)offset;
  int steps = 1;
  if(pair) {
    base = DATA_VADDR + (u64)offset;
    s16 leftImm = little ? 7 : 0;
    s16 rightImm = little ? 0 : 7;
    put_instruction(CODE_VADDR + 0, encode_store(0x2c, RS, RT, leftImm), little);
    put_instruction(CODE_VADDR + 4, encode_store(0x2d, RS, RT, rightImm), little);
    steps = 2;
  } else {
    put_instruction(CODE_VADDR, encode_store(opcode, RS, RT, imm), little);
  }
  cpu.ipu.r[RS].u64 = base;
  cpu.ipu.r[RT].u64 = PAYLOAD;
  cpu.pipeline.setPc(CODE_VADDR);

  for(int n = 0; n < steps; n++) {
    if(cpu.instruction()) cpu.synchronize();
    if(cpu.scc.status.exceptionLevel) break;
  }

  std::vector<u8> after, physicalAfter;
  for(u32 i = 0; i < WINDOW; i++) after.push_back(guest_byte(DATA_VADDR + i, little));
  for(u32 i = 0; i < WINDOW; i++) physicalAfter.push_back(physical_byte_at(DATA_PADDR + i));

  std::printf("{\"kind\":\"%s\",\"offset\":%d,\"little\":%d,\"address_kind\":\"%s\",", kind, offset, littleArg, addressKind);
  std::printf("\"pc\":%llu,\"cause\":%u,\"epc\":%llu,\"badva\":%llu,\"exl\":%u,",
    (unsigned long long)cpu.ipu.pc,
    (u32)cpu.scc.cause.exceptionCode,
    (unsigned long long)cpu.scc.epc,
    (unsigned long long)cpu.scc.badVirtualAddress,
    (u32)cpu.scc.status.exceptionLevel);
  print_array("before", before, true);
  print_array("after", after, true);
  print_array("physical_before", physicalBefore, true);
  print_array("physical_after", physicalAfter, false);
  std::printf("}\n");
  ares::Nintendo64::system.unload();
  return 0;
}
