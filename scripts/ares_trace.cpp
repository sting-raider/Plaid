/* SPDX-License-Identifier: ISC
 * Analysis-only device-boundary trace from the pinned ares core (ADR-0329):
 *   ares_trace <rom> <CIC-NUS-xxxx> <vis> <out>
 * One line per retrace (`vi <n> origin <x>`), per RSP task start
 * (`task <type> data <phys> size <n> hash <fnv> vi <n>`) and per RDP
 * SYNC_FULL (`rdp <n> commands <n> hash <fnv> vi <n>`), the formats
 * PLAID_TRACE_VI/_TASK/_RDP print natively. Built with ares_rdp_queue.py's
 * recipe; observers only read state.
 */
#define main fixture_main
#include "../spikes/003-ares-oracle/driver.cpp"
#undef main
#include <cstdlib>
#include <vector>
#include "ares_hle_boot.hpp"

namespace ares::Nintendo64 { extern void (*plaidRdpFrameObserver)(u64 hash, u32 commands, const u32* ops); }
static FILE* out;
static u32 vis = 0, frames = 0;

// FNV-1a over the task's data bytes; the native runtime hashes the same span.
static u64 hashRdram(u32 p, u32 n) {
  u64 h = 0xcbf29ce484222325ull;
  for(u32 i = 0; i < n && p + i < rdram.ram.size; i++)
    h = (h ^ rdram.ram.read<Byte>(p + i, RBusDevice::ARES_DEBUGGER)) * 0x100000001b3ull;
  return h;
}

int main(int argc, char** argv) {
  if(argc != 5) return 2;
  auto bytes = nall::file::read(argv[1]);
  u32 limit = std::strtoul(argv[3], nullptr, 0);
  if(bytes.size() < 4096 || !limit) return 2;
  out = std::fopen(argv[4], "wb"); if(!out) return 2;
  std::vector<u8> firmware(1984);

  Headless frontend; platform = &frontend;
  frontend.systemPak->append("pif.ntsc.rom", std::span<const u8>{firmware.data(), firmware.size()});
  frontend.cartPak->setAttribute("title", "Plaid device trace");
  frontend.cartPak->setAttribute("region", "NTSC");
  frontend.cartPak->setAttribute("cic", argv[2]);
  frontend.cartPak->append("program.rom", std::span<const u8>{bytes.data(), bytes.size()});
  Node::System root;
  if(!load(root, "[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak", "true"); option("Deterministic Entropy", "true"); option("Recompiler", "false");
  cartridgeSlot.port->allocate(); cartridgeSlot.port->connect();
  // A neutral gamepad in port 1, as ares_boot and the native runtime have.
  controllerPort1.port->allocate("Gamepad"); controllerPort1.port->connect();
  ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;
  std::vector<u8> hidden(rdram.ram.size / 2); rdram.hidden.data = hidden.data();
  if(plaidHleBoot(bytes.data(), bytes.size(), argv[2], vis) == ~0ull) return 4;
  vis = 0;  // count retraces from the game's entry, as the native runtime does

  ares::Nintendo64::plaidRdpFrameObserver = [](u64 hash, u32 commands, const u32* ops) {
    std::fprintf(out, "rdp %u commands %u hash %016llx vi %u ops", ++frames, commands, (unsigned long long)hash, vis);
    for(u32 i = 0; i < 64; i++) if(ops[i]) std::fprintf(out, " %02x:%u", i, ops[i]);
    std::fputc(10, out);
  };
  bool halted = rsp.status.halted;
  while(vis < limit) {
    if(cpu.instruction()) cpu.synchronize();
    if(vi.refreshed) {
      vi.refreshed = false;
      std::fprintf(out, "vi %u origin %08x\n", ++vis, (u32)vi.io.dramAddress);
    }
    if(halted && !rsp.status.halted) {
      // osSpTaskLoad placed the OSTask at DMEM 0xfc0 with physical pointers.
      u32 type = rsp.dmem.read<Word>(0xfc0), flags = rsp.dmem.read<Word>(0xfc4);
      u32 data = rsp.dmem.read<Word>(0xff0) & 0x1fffffff, size = rsp.dmem.read<Word>(0xff4);
      u32 span = !size ? 1024 : size < 65536 ? size : 65536;
      // A resumed yield repeats a task the native runtime ran once.
      if(!(flags & 1))
        std::fprintf(out, "task %u data %08x size %u hash %016llx vi %u\n", type, data, size,
                     (unsigned long long)hashRdram(data, span), vis);
    }
    halted = rsp.status.halted;
  }
  bool error = std::ferror(out); if(std::fclose(out)) error = true;
  ares::Nintendo64::system.unload();
  return error ? 5 : 0;
}
