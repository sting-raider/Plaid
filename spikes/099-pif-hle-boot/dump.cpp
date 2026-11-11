/* SPDX-License-Identifier: ISC
 * Development tool: snapshot pinned-ares component state at power-on or at
 * the first IPL3 instruction. Needs the pinned ares PIF ROM (local checkout
 * only); the HLE boot that replaces it never reads that file.
 *   dump rom firmware|- CIC-NUS-6102 power|ipl3|hle out_dir
 */
#define main fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <filesystem>
#include <vector>
#include "../../scripts/ares_hle_boot.hpp"

static void put(const std::filesystem::path& dir, const char* name, serializer s) {
  auto file = std::fopen((dir / name).string().c_str(), "wb");
  std::fwrite(s.data(), 1, s.size(), file);
  std::fclose(file);
}

template<typename T> static void part(const std::filesystem::path& dir, const char* name, T& object) {
  serializer s; s(object); put(dir, name, s);
}

int main(int argc, char** argv) {
  if(argc != 6) return 2;
  auto bytes = nall::file::read(argv[1]);
  std::vector<u8> firmware(1984, 0);
  if(std::strcmp(argv[2], "-")) {
    auto real = nall::file::read(argv[2]);
    if(real.size() != 1984) return 2;
    std::copy(real.begin(), real.end(), firmware.begin());
  }
  std::string mode = argv[4];
  std::filesystem::path out = argv[5];
  std::filesystem::create_directories(out);
  Headless frontend; platform = &frontend;
  frontend.systemPak->append("pif.ntsc.rom", std::span<const u8>{firmware.data(), firmware.size()});
  frontend.cartPak->setAttribute("title", "Plaid HLE state");
  frontend.cartPak->setAttribute("region", "NTSC");
  frontend.cartPak->setAttribute("cic", argv[3]);
  frontend.cartPak->append("program.rom", std::span<const u8>{bytes.data(), bytes.size()});
  Node::System root;
  if(!load(root, "[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak", "true"); option("Deterministic Entropy", "true"); option("Recompiler", "false");
  cartridgeSlot.port->allocate(); cartridgeSlot.port->connect();
  controllerPort1.port->allocate("Gamepad"); controllerPort1.port->connect();
  ares::Nintendo64::system.power(false);
  std::vector<u8> hidden(rdram.ram.size / 2);
  rdram.hidden.data = hidden.data();
  u64 steps = 0;
  u32 vis = 0;
  if(mode == "ipl3") {
    for(; steps < 20000000; steps++) {
      if((u32)cpu.ipu.pc == 0xa4000040u) break;
      if(cpu.instruction()) cpu.synchronize();
      if(vi.refreshed) { vis++; vi.refreshed = false; }
    }
    if((u32)cpu.ipu.pc != 0xa4000040u) return 7;
  } else if(mode == "hle") {
    u32 hleVis = 0;
    steps = plaidHleBoot(bytes.data(), bytes.size(), argv[3], hleVis);
    vis = hleVis;
  } else if(mode != "power") return 2;
  std::printf("steps=%llu vis=%u pc=%08x count=%llu\n", (unsigned long long)steps, vis, (u32)cpu.ipu.pc, (unsigned long long)cpu.scc.count);
  part(out, "cpu.bin", cpu); part(out, "mi.bin", mi); part(out, "vi.bin", vi); part(out, "ai.bin", ai);
  part(out, "pi.bin", pi); part(out, "pif.bin", pif); part(out, "cic.bin", cic); part(out, "ri.bin", ri);
  part(out, "si.bin", si); part(out, "rsp.bin", rsp); part(out, "rdp.bin", rdp); part(out, "rdram.bin", rdram);
  part(out, "queue.bin", ares::Nintendo64::queue);
  if(auto trace = std::getenv("PLAID_TRACE_STEPS")) {
    // Development aid: per-instruction PC/Count after the boot phase, to locate the first divergence.
    auto file = std::fopen((out / "trace.txt").string().c_str(), "wb");
    for(u64 n = 0, count = std::strtoull(trace, nullptr, 0); n < count; n++) {
      std::fprintf(file, "%llu %08x %llu\n", (unsigned long long)n, (u32)cpu.ipu.pc, (unsigned long long)cpu.scc.count);
      if(cpu.instruction()) cpu.synchronize();
    }
    std::fclose(file);
  }
  ares::Nintendo64::system.unload();
  return 0;
}
