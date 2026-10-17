/* SPDX-License-Identifier: ISC
 * Analysis-only observer. Addresses and stop entry are experiment arguments.
 * No reference code or captured RAM is used as compiler input.
 */
#define main boot_adapter_main
#include "../spikes/003-ares-oracle/driver.cpp"
#undef main
#include <map>
#include <algorithm>
#include <cstdlib>

static u32 slotLo, slotHi, currentPc;
static std::map<u32, u64> stores;
static std::array<std::array<u32, 7>, 32> calls;
static size_t callCount;
static void trace(bool before, u64 address, u32 word) {
  if(!before) return;
  currentPc = address;
  u32 op = word >> 26;
  if(op == 3 || (op == 0 && (word & 63) == 9)) {
    auto& c = calls[callCount++ % calls.size()];
    c = {currentPc, op == 3 ? ((currentPc + 4) & 0xf0000000) | ((word & 0x3ffffff) << 2)
                           : (u32)cpu.ipu.r[(word >> 21) & 31].u64,
         (u32)cpu.ipu.r[4].u64, (u32)cpu.ipu.r[5].u64,
         (u32)cpu.ipu.r[6].u64, (u32)cpu.ipu.r[7].u64, (u32)cpu.ipu.r[29].u64};
  }
  // Observe effective addresses before ordinary CPU stores, including cached
  // stores whose eventual RAM writeback has a different instruction PC.
  if(op < 40 || op > 46) return;
  u32 dst = (u32)cpu.ipu.r[(word >> 21) & 31].u64 + (s16)word;
  if(dst < slotLo || dst >= slotHi) return;
  if(stores[currentPc]++ != 0) return;
  std::printf("{\"store_pc\":%u,\"destination\":%u,\"word\":%u,\"calls\":[", currentPc, dst, word);
  size_t count = std::min(callCount, calls.size());
  for(size_t i = 0; i < count; i++) {
    auto& c = calls[(callCount - count + i) % calls.size()];
    std::printf("%s[%u,%u,%u,%u,%u,%u,%u]", i ? "," : "", c[0],c[1],c[2],c[3],c[4],c[5],c[6]);
  }
  std::printf("]}\n");
}

int main(int argc, char** argv) {
  if(argc != 8) return 2;
  auto bytes = nall::file::read(argv[1]);
  auto firmware = nall::file::read(argv[2]);
  slotLo = std::strtoul(argv[4], nullptr, 0);
  slotHi = std::strtoul(argv[5], nullptr, 0);
  u32 stop = std::strtoul(argv[6], nullptr, 0);
  if(bytes.size() < 4096 || firmware.size() != 1984 || slotLo >= slotHi) return 2;
  Headless frontend; platform = &frontend;
  frontend.systemPak->append("pif.ntsc.rom", std::span<const u8>{firmware.data(), firmware.size()});
  frontend.cartPak->setAttribute("title", "Plaid slot writer experiment");
  frontend.cartPak->setAttribute("region", "NTSC");
  frontend.cartPak->setAttribute("cic", argv[3]);
  frontend.cartPak->append("program.rom", std::span<const u8>{bytes.data(), bytes.size()});
  Node::System root;
  if(!load(root, "[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak", "true"); option("Deterministic Entropy", "true"); option("Recompiler", "false");
  cartridgeSlot.port->allocate(); cartridgeSlot.port->connect();
  controllerPort1.port->allocate("Gamepad"); controllerPort1.port->connect();
  ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;
  std::vector<u8> hidden(rdram.ram.size / 2); rdram.hidden.data = hidden.data();
  plaidCpuInstructionObserver = trace;
  u64 budget = std::strtoull(argv[7], nullptr, 0), n = 0;
  for(; n < budget && (u32)cpu.ipu.pc != stop; n++)
    if(cpu.instruction()) cpu.synchronize();
  std::printf("{\"stop_pc\":%u,\"steps\":%llu,\"stores\":[", (u32)cpu.ipu.pc, (unsigned long long)n);
  bool comma = false;
  for(auto [pc, count] : stores) {
    std::printf("%s[%u,%llu]", comma ? "," : "", pc, (unsigned long long)count); comma = true;
  }
  std::printf("]}\n");
  ares::Nintendo64::system.unload();
  return n == budget ? 5 : 0;
}
