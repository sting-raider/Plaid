/* SPDX-License-Identifier: ISC
 * Original Plaid research harness, 2026. Reference implementation stays separate.
 * Runs one captured RSP task (ADR-0169) on the pinned ares RSP: all of RDRAM,
 * IMEM, DMEM and the RSP state as the native runtime had them when the task
 * started, from PC 0 until the RSP halts. Writes the resulting RDRAM, IMEM
 * and DMEM, and prints the register state.
 *   driver <before-rdram.bin> <before-imem.bin> <before-dmem.bin> <state.bin> <out dir>
 * state.bin: little-endian u32s: pc, 32 scalar registers, 35 x 8 vector
 * halfwords (v0..v31, ACCH, ACCM, ACCL), vco, vcc, vce, divin, divout, divdp,
 * 8 signals, semaphore, interrupt_on_break.
 */
#include <n64/n64.hpp>
#include <cstdio>
#include <cstdlib>
#include <string>
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

static bool loadFile(const char* path, std::vector<u8>& out, size_t size) {
  out.resize(size);
  auto file = std::fopen(path, "rb");
  if(!file) return false;
  bool ok = std::fread(out.data(), 1, size, file) == size;
  std::fclose(file);
  return ok;
}
static bool saveFile(const std::string& path, const u8* data, size_t size) {
  auto file = std::fopen(path.c_str(), "wb");
  if(!file) return false;
  bool ok = std::fwrite(data, 1, size, file) == size;
  return std::fclose(file) == 0 && ok;
}

int main(int argc, char** argv) {
  if(argc != 6) return 2;
  const u32 ramSize = 8 * 1024 * 1024;
  std::vector<u8> ram, imem, dmem, stateBytes;
  if(!loadFile(argv[1], ram, ramSize) || !loadFile(argv[2], imem, 4096) || !loadFile(argv[3], dmem, 4096)) return 5;
  const size_t words = 1 + 32 + 35 * 8 + 6 + 8 + 2;
  if(!loadFile(argv[4], stateBytes, words * 4)) return 5;
  auto state = [&](size_t i) -> u32 {
    return stateBytes[4*i] | stateBytes[4*i+1] << 8 | stateBytes[4*i+2] << 16 | (u32)stateBytes[4*i+3] << 24;
  };
  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid RSP task oracle");
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
  for(u32 a = 0; a < ramSize; a += 4)
    rdram.ram.write<Word>(a, (u32)ram[a] << 24 | (u32)ram[a+1] << 16 | (u32)ram[a+2] << 8 | ram[a+3], RBusDevice::ARES_DEBUGGER);
  for(u32 a = 0; a < 4096; a += 4) {
    rsp.imem.write<Word>(a, (u32)imem[a] << 24 | (u32)imem[a+1] << 16 | (u32)imem[a+2] << 8 | imem[a+3]);
    rsp.dmem.write<Word>(a, (u32)dmem[a] << 24 | (u32)dmem[a+1] << 16 | (u32)dmem[a+2] << 8 | dmem[a+3]);
  }
  size_t k = 0;
  u32 pc = state(k++);
  for(u32 r = 0; r < 32; r++) rsp.ipu.r[r].u32 = state(k++);
  auto& vpu = rsp.vpu;
  for(u32 r = 0; r < 35; r++) {
    auto& v = r < 32 ? vpu.r[r] : r == 32 ? vpu.acch : r == 33 ? vpu.accm : vpu.accl;
    for(u32 n = 0; n < 8; n++) v.u16(n) = state(k++);
  }
  u32 vco = state(k++), vcc = state(k++), vce = state(k++);
  for(u32 n = 0; n < 8; n++) {
    vpu.vcol.set(n, vco >> n & 1); vpu.vcoh.set(n, vco >> (8 + n) & 1);
    vpu.vccl.set(n, vcc >> n & 1); vpu.vcch.set(n, vcc >> (8 + n) & 1);
    vpu.vce.set(n, vce >> n & 1);
  }
  vpu.divin = (s16)state(k++); vpu.divout = (s16)state(k++); vpu.divdp = state(k++);
  for(u32 n = 0; n < 8; n++) rsp.status.signal[n] = state(k++);
  rsp.status.semaphore = state(k++);
  rsp.status.interruptOnBreak = state(k++);
  rsp.status.singleStep = 0;
  rsp.status.broken = 0;
  rsp.status.halted = 0;
  rsp.ipu.pc = pc & 0xffc;
  rsp.branch.setPc(rsp.ipu.pc);
  long n = 0;
  for(; n < 200000000 && !rsp.status.halted; n++) {
    s64 clock = rsp.clock;
    rsp.instruction();
    rsp.dmaStep(rsp.clock - clock);
  }
  for(int i = 0; i < 100000 && (rsp.dma.busy.any() || rsp.dma.full.any()); i++) rsp.dmaStep(64);
  if(!rsp.status.halted) return 6;
  std::string out = argv[5];
  for(u32 a = 0; a < ramSize; a += 4) {
    u32 w = rdram.ram.read<Word>(a, RBusDevice::ARES_DEBUGGER);
    ram[a] = w >> 24; ram[a+1] = w >> 16; ram[a+2] = w >> 8; ram[a+3] = w;
  }
  for(u32 a = 0; a < 4096; a++) { imem[a] = rsp.imem.read<Byte>(a); dmem[a] = rsp.dmem.read<Byte>(a); }
  if(!saveFile(out + "/oracle-rdram.bin", ram.data(), ramSize) || !saveFile(out + "/oracle-imem.bin", imem.data(), 4096)
     || !saveFile(out + "/oracle-dmem.bin", dmem.data(), 4096)) return 7;
  std::printf("{\"instructions\":%ld,\"pc\":%u,\"halted\":%u,\"broken\":%u,\"regs\":[", n, (u32)rsp.ipu.pc,
              (u32)rsp.status.halted, (u32)rsp.status.broken);
  for(int r = 0; r < 32; r++) std::printf("%s%u", r ? "," : "", rsp.ipu.r[r].u32);
  std::printf("],\"vu\":\"");
  for(int r = 0; r < 35; r++) {
    auto& v = r < 32 ? vpu.r[r] : r == 32 ? vpu.acch : r == 33 ? vpu.accm : vpu.accl;
    for(int e = 0; e < 8; e++) std::printf("%04x", (u32)v.u16(e));
  }
  u32 f[3] = {};
  for(int e = 0; e < 8; e++) {
    f[0] |= vpu.vcol.get(e) << e | vpu.vcoh.get(e) << (8 + e);
    f[1] |= vpu.vccl.get(e) << e | vpu.vcch.get(e) << (8 + e);
    f[2] |= vpu.vce.get(e) << e;
  }
  std::printf("\",\"vflags\":[%u,%u,%u,%u,%u,%u],\"signals\":[", f[0], f[1], f[2], (u32)(u16)vpu.divin,
              (u32)(u16)vpu.divout, (u32)vpu.divdp);
  for(int s = 0; s < 8; s++) std::printf("%s%u", s ? "," : "", (u32)rsp.status.signal[s]);
  std::printf("],\"semaphore\":%u,\"interrupt_on_break\":%u}\n", (u32)rsp.status.semaphore,
              (u32)rsp.status.interruptOnBreak);
  ares::Nintendo64::system.unload();
  return 0;
}
