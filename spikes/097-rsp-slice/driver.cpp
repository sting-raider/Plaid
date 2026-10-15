/* SPDX-License-Identifier: ISC
 * Original Plaid research harness, 2026. Reference implementation stays separate.
 * Runs RSP microcode on the pinned ares interpreter: IMEM and DMEM images from
 * files, a fixed RDRAM pattern, start at a PC, until the RSP halts; then
 * prints the state compared by spike097 (ADR-0167).
 *   driver <imem.bin> <dmem.bin> <pc>
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

static bool loadFile(const char* path, u8* out, u32 size) {
  auto file = std::fopen(path, "rb");
  if(!file) return false;
  bool ok = std::fread(out, 1, size, file) == size;
  std::fclose(file);
  return ok;
}

int main(int argc, char** argv) {
  if(argc != 4) return 2;
  u8 imem[4096], dmem[4096];
  if(!loadFile(argv[1], imem, 4096) || !loadFile(argv[2], dmem, 4096)) return 5;
  u32 pc = (u32)std::strtoul(argv[3], nullptr, 0);
  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid RSP slice oracle");
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
  // RDRAM is unmapped until the IPL configures it; map it as spike096 does.
  std::vector<u8> hidden(rdram.ram.size / 2);
  rdram.hidden.data = hidden.data();
  rdram.mapIdentity = 1;
  // RDRAM pattern, as harness.c builds it
  for(u32 a = 0; a < 0x10000; a += 4) {
    u32 w = 0;
    for(u32 n = 0; n < 4; n++) w = w << 8 | (u8)((a + n) * 7 + 3);
    rdram.ram.write<Word>(a, w, RBusDevice::ARES_DEBUGGER);
  }
  for(u32 a = 0; a < 4096; a += 4) {
    rsp.imem.write<Word>(a, (u32)imem[a] << 24 | (u32)imem[a+1] << 16 | (u32)imem[a+2] << 8 | imem[a+3]);
    rsp.dmem.write<Word>(a, (u32)dmem[a] << 24 | (u32)dmem[a+1] << 16 | (u32)dmem[a+2] << 8 | dmem[a+3]);
  }
  rsp.ipu.pc = pc & 0xffc;
  rsp.branch.setPc(rsp.ipu.pc);
  rsp.status.halted = 0;
  rsp.status.broken = 0;
  int n = 0;
  for(; n < 1000000 && !rsp.status.halted; n++) {
    s64 clock = rsp.clock;
    rsp.instruction();
    rsp.dmaStep(rsp.clock - clock);
  }
  for(int k = 0; k < 100000 && (rsp.dma.busy.any() || rsp.dma.full.any()); k++) rsp.dmaStep(64);
  if(!rsp.status.halted) return 6;
  std::printf("{\"pc\":%u,\"broken\":%u,\"regs\":[", (u32)rsp.ipu.pc, (u32)rsp.status.broken);
  for(int r = 0; r < 32; r++) std::printf("%s%u", r ? "," : "", rsp.ipu.r[r].u32);
  std::printf("],\"dmem\":\"");
  for(u32 a = 0; a < 4096; a++) std::printf("%02x", (u32)rsp.dmem.read<Byte>(a));
  std::printf("\",\"rdram\":\"");
  for(u32 a = 0; a < 0x2000; a += 4) std::printf("%08x", (u32)rdram.ram.read<Word>(a, RBusDevice::ARES_DEBUGGER));
  // vector unit (ADR-0168): 32 registers then ACCH, ACCM, ACCL, as halfwords
  std::printf("\",\"vu\":\"");
  auto& vpu = rsp.vpu;
  for(int r = 0; r < 35; r++) {
    auto& v = r < 32 ? vpu.r[r] : r == 32 ? vpu.acch : r == 33 ? vpu.accm : vpu.accl;
    for(int n = 0; n < 8; n++) std::printf("%04x", (u32)v.u16(n));
  }
  u32 flags[5] = {};
  for(int n = 0; n < 8; n++) {
    flags[0] |= vpu.vcol.get(n) << n | vpu.vcoh.get(n) << (8 + n);
    flags[1] |= vpu.vccl.get(n) << n | vpu.vcch.get(n) << (8 + n);
    flags[2] |= vpu.vce.get(n) << n;
  }
  std::printf("\",\"vflags\":[%u,%u,%u,%u,%u,%u]}\n", flags[0], flags[1], flags[2],
    (u32)(u16)vpu.divin, (u32)(u16)vpu.divout, (u32)vpu.divdp);
  ares::Nintendo64::system.unload();
  return 0;
}
