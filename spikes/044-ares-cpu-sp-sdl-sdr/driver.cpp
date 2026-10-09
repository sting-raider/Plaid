/* SPDX-License-Identifier: ISC
 * Exact pinned-ares fixture: decoded VR4300 SD/SDL/SDR into CPU-visible SP memory.
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

static constexpr u64 CODE_VADDR = 0xffffffffa0006000ull;
static constexpr u32 CODE_PADDR = 0x00006000u;
static constexpr u64 DMEM_VADDR = 0xffffffffa4000000ull;
static constexpr u64 IMEM_VADDR = 0xffffffffa4001000ull;
static constexpr u64 PAYLOAD = 0x1122334455667788ull;
static constexpr u32 WINDOW = 24;

static auto encode_store(u32 opcode, u32 rs, u32 rt, s16 imm) -> u32 {
  return opcode << 26 | rs << 21 | rt << 16 | (u16)imm;
}

static auto put_instruction(u64 vaddr, u32 word, bool little) -> void {
  u32 paddr = (u32)vaddr & 0x1fffffffu;
  if(little) paddr ^= 4;
  rdram.ram.write<Word>(paddr, word, RBusDevice::ARES_DEBUGGER);
}

static auto set_byte(bool imem, u32 offset, u8 value) -> void {
  if(imem) rsp.imem.write<Byte>(offset, value);
  else rsp.dmem.write<Byte>(offset, value);
}

static auto get_byte(bool imem, u32 offset) -> u8 {
  return imem ? (u8)rsp.imem.read<Byte>(offset) : (u8)rsp.dmem.read<Byte>(offset);
}

static auto snapshot(bool imem) -> std::vector<u8> {
  std::vector<u8> out;
  for(u32 i=0;i<WINDOW;i++) out.push_back(get_byte(imem, i));
  return out;
}

static auto print_array(const char* key, const std::vector<u8>& bytes, bool comma) -> void {
  std::printf("\"%s\":[", key);
  for(size_t i=0;i<bytes.size();i++) std::printf("%s%u", i ? "," : "", (unsigned)bytes[i]);
  std::printf("]%s", comma ? "," : "");
}

int main(int argc, char** argv) {
  if(argc != 5) return 2;
  const char* kind = argv[1];
  const char* endian = argv[2];
  const char* bank = argv[3];
  int offset = std::atoi(argv[4]);
  bool little = !std::strcmp(endian, "little");
  bool big = !std::strcmp(endian, "big");
  bool imem = !std::strcmp(bank, "imem");
  bool dmem = !std::strcmp(bank, "dmem");
  bool sd = !std::strcmp(kind, "SD");
  bool sdl = !std::strcmp(kind, "SDL");
  bool sdr = !std::strcmp(kind, "SDR");
  bool pair = !std::strcmp(kind, "PAIR");
  if((!little && !big) || (!imem && !dmem) || (!sd && !sdl && !sdr && !pair)) return 2;
  if(offset < 0 || offset > 7 || (sd && offset != 0)) return 2;

  Headless frontend; platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid CPU SDL SDR SP sink research");
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

  std::vector<u8> hidden(rdram.ram.size / 2); rdram.hidden.data = hidden.data(); rdram.mapIdentity = 1;
  cpu.icache.power(false); cpu.dcache.power(false);
  for(auto& reg : cpu.ipu.r) reg.u64 = 0;

  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.status.vectorLocation = 0;
  cpu.scc.status.privilegeMode = 0;
  cpu.scc.status.kernelExtendedAddressing = 1;
  cpu.scc.configuration.bigEndian = little ? 0 : 1;
  cpu.scc.cause.exceptionCode = 0;
  cpu.scc.cause.branchDelay = 0;
  cpu.scc.badVirtualAddress = 0;
  cpu.scc.sysadFrozen = false;
  cpu.context.setMode();
  if(cpu.context.bits != 64 || cpu.context.littleEndian() != little) return 5;

  for(u32 i=0;i<WINDOW;i++) {
    set_byte(imem, i, (u8)(0xa0u + i));
    set_byte(!imem, i, (u8)(0x50u + i));
  }
  auto before = snapshot(imem);
  auto otherBefore = snapshot(!imem);

  constexpr u32 RS = 3, RT = 4;
  u64 target = imem ? IMEM_VADDR : DMEM_VADDR;
  int steps = 1;
  if(pair) {
    cpu.ipu.r[RS].u64 = target + (u64)offset;
    s16 leftImm = little ? 7 : 0;
    s16 rightImm = little ? 0 : 7;
    put_instruction(CODE_VADDR + 0, encode_store(0x2c, RS, RT, leftImm), little);
    put_instruction(CODE_VADDR + 4, encode_store(0x2d, RS, RT, rightImm), little);
    steps = 2;
  } else {
    cpu.ipu.r[RS].u64 = target;
    u32 opcode = sd ? 0x3f : sdl ? 0x2c : 0x2d;
    put_instruction(CODE_VADDR, encode_store(opcode, RS, RT, (s16)offset), little);
  }
  cpu.ipu.r[RT].u64 = PAYLOAD;
  cpu.pipeline.setPc(CODE_VADDR);

  for(int n=0;n<steps;n++) {
    if(cpu.instruction()) cpu.synchronize();
    if(cpu.scc.status.exceptionLevel) break;
  }

  auto after = snapshot(imem);
  auto otherAfter = snapshot(!imem);
  std::printf("{\"kind\":\"%s\",\"endian\":\"%s\",\"bank\":\"%s\",\"offset\":%d,", kind,endian,bank,offset);
  std::printf("\"pc\":%llu,\"cause\":%u,\"epc\":%llu,\"badva\":%llu,\"exl\":%u,",
    (unsigned long long)cpu.ipu.pc,(u32)cpu.scc.cause.exceptionCode,
    (unsigned long long)cpu.scc.epc,(unsigned long long)cpu.scc.badVirtualAddress,
    (u32)cpu.scc.status.exceptionLevel);
  print_array("before", before, true);
  print_array("after", after, true);
  print_array("other_before", otherBefore, true);
  print_array("other_after", otherAfter, false);
  std::printf("}\n");

  ares::Nintendo64::system.unload();
  return 0;
}
