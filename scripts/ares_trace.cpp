/* SPDX-License-Identifier: ISC
 * Analysis-only device-boundary trace from the pinned ares core (ADR-0329):
 *   ares_trace <rom> <CIC-NUS-xxxx> <vis> <out> [<buttons>@<rdp frame>:<vis>]...
 * A press holds OSContPad button bits on port 1 for <vis> retraces from the
 * retrace after RDP frame <rdp frame> completes, so presses land on the same
 * game frame as a native --press run while frames still match.
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

namespace ares::Nintendo64 {
  extern void (*plaidRdpFrameObserver)(u64 hash, u32 commands, const u32* ops);
  extern void (*plaidRdpCommandObserver)(const u64* words, u32 count);
}
static FILE* out;
static u32 vis = 0, frames = 0;
struct Press { u32 buttons, frame, length, start = 0; bool started = false; };
static std::vector<Press> presses;
// libultra OSContPad bits, as the native runtime's --press takes them.
static u32 held() {
  u32 b = 0;
  for(auto& p : presses) if(p.started && vis - p.start < p.length) b |= p.buttons;
  return b;
}
struct Scripted : Headless {
  auto input(Node::Input::Input node) -> void override {
    static const std::pair<const char*, u32> bits[] = {{"A", 0x8000}, {"B", 0x4000}, {"Z", 0x2000},
      {"Start", 0x1000}, {"Up", 0x0800}, {"Down", 0x0400}, {"Left", 0x0200}, {"Right", 0x0100},
      {"L", 0x0020}, {"R", 0x0010}, {"C-Up", 0x0008}, {"C-Down", 0x0004}, {"C-Left", 0x0002}, {"C-Right", 0x0001}};
    auto button = node->cast<Node::Input::Button>();
    if(!button) return;
    for(auto& [name, bit] : bits) if(node->name() == name) button->setValue(held() & bit);
  }
};

// FNV-1a over the task's data bytes; the native runtime hashes the same span.
static u64 hashRdram(u32 p, u32 n) {
  u64 h = 0xcbf29ce484222325ull;
  for(u32 i = 0; i < n && p + i < rdram.ram.size; i++)
    h = (h ^ rdram.ram.read<Byte>(p + i, RBusDevice::ARES_DEBUGGER)) * 0x100000001b3ull;
  return h;
}

int main(int argc, char** argv) {
  if(argc < 5) return 2;
  for(int i = 5; i < argc; i++) {
    Press p;
    if(std::sscanf(argv[i], "%i@%u:%u", (int*)&p.buttons, &p.frame, &p.length) != 3) return 2;
    presses.push_back(p);
  }
  auto bytes = nall::file::read(argv[1]);
  u32 limit = std::strtoul(argv[3], nullptr, 0);
  if(bytes.size() < 4096 || !limit) return 2;
  out = std::fopen(argv[4], "wb"); if(!out) return 2;
  std::vector<u8> firmware(1984);

  Scripted frontend; platform = &frontend;
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
  // PLAID_TRACE_RDP_DUMP=N: the words of the first N frames, as natively.
  static u32 dump = std::getenv("PLAID_TRACE_RDP_DUMP") ? std::strtoul(std::getenv("PLAID_TRACE_RDP_DUMP"), nullptr, 0) : 0;
  if(dump) ares::Nintendo64::plaidRdpCommandObserver = [](const u64* words, u32 count) {
    if(frames >= dump) return;
    std::fprintf(out, "cmd %u", frames + 1);
    for(u32 i = 0; i < count; i++) std::fprintf(out, " %016llx", (unsigned long long)words[i]);
    std::fputc(10, out);
  };
  // PLAID_TRACE_WATCH=lo-hi: reads of physical [lo, hi) other than the VI's
  // scanout, e.g. a CPU or RSP read of a buffer only the RDP draws.
  static u32 watchLo = 0, watchHi = 0, watched = 0;
  if(auto w = std::getenv("PLAID_TRACE_WATCH")) std::sscanf(w, "%x-%x", &watchLo, &watchHi);
  if(watchHi) {
    static auto watch = [](bool write, u32 a, u32 n, u32 d) {
      if(write || a >= watchHi || a + n <= watchLo || d == (u32)RBusDevice::VI_DMA) return;
      static u32 lastPc = 0, lastFrame = ~0u;  // one line per run of reads from one pc
      if(lastPc == (u32)cpu.ipu.pc && lastFrame == frames) return;
      lastPc = cpu.ipu.pc, lastFrame = frames;
      if(++watched > 20000) return;
      std::fprintf(out, "watch vi %u frame %u pc %08x addr %08x size %u device %u\n", vis, frames, (u32)cpu.ipu.pc, a, n, d);
    };
    plaidRdramScalarObserver = [](bool w, u32 a, u32 n, u32 d, u64) { watch(w, a, n, d); };
    plaidRdramBurstObserver = [](bool w, u32 a, u32 n, u32 d, const u32*) { watch(w, a, n, d); };
  }
  bool halted = rsp.status.halted;
  while(vis < limit) {
    if(cpu.instruction()) cpu.synchronize();
    if(vi.refreshed) {
      vi.refreshed = false;
      for(auto& p : presses) if(!p.started && frames >= p.frame) p.started = true, p.start = vis + 1;
      std::fprintf(out, "vi %u origin %08x field %u\n", ++vis, (u32)vi.io.dramAddress, (u32)vi.io.field);
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
