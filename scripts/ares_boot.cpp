/* SPDX-License-Identifier: ISC
 * Analysis-only adapter to the separately built pinned ares core. No guest
 * semantics are implemented here; observers never issue guest bus accesses.
 */
#define main fixture_main
#include "../spikes/003-ares-oracle/driver.cpp"
#undef main
#include <algorithm>
#include <cstdlib>
#include <vector>
#include <set>

static std::vector<u8> written(8 * 1024 * 1024);
static bool entered = false;
static u32 boot;
static std::set<u32> targets;
static u64 steps = 0;
static FILE* result;
static bool exactMany = false;
static std::vector<std::array<u32, 3>> dma;
static std::vector<u8> sp; // DMEM then IMEM at the first entry fetch
static std::vector<u8> ram_prefix; // IPL3's vector/boot-parameter area, before game entry
static void mark(bool write, u32 address, u32 size, u32 device) {
  if(!entered || !write || !rdram.mapIdentity || address >= written.size()) return;
  u8 origin = device == (u32)RBusDevice::VR4300_DCACHE || device == (u32)RBusDevice::VR4300_UNCACHED ? 1
    : device == (u32)RBusDevice::PI_DMA ? 2 : 4;
  for(u32 n = address; n < std::min<u32>(address + size, written.size()); n++) written[n] |= origin;
}
static void ranges(FILE* f, u32 lo, u32 hi, u8 mask) {
  bool comma = false;
  std::fprintf(f, "[");
  for(u32 at = lo; at < hi;) {
    if(!(written[at] & mask)) { at++; continue; }
    u32 start = at++;
    while(at < hi && (written[at] & mask)) at++;
    std::fprintf(f, "%s[%u,%u]", comma ? "," : "", start, at); comma = true;
  }
  std::fprintf(f, "]");
}
static void observe(u64 address, u32 word) {
    u32 pc = address;
    if(pc == boot && !entered) {
      entered = true; std::fill(written.begin(), written.end(), 0);
      for(u32 a = 0; a < 0x400; a++)
        ram_prefix.push_back(rdram.ram.read<Byte>(a, RBusDevice::ARES_DEBUGGER));
      // SP memory as the ROM's own IPL3 leaves it (ADR-0195).
      for(u32 a = 0; a < 0x2000; a += 4) {
        u32 w = a < 0x1000 ? rsp.dmem.read<Word>(a) : rsp.imem.read<Word>(a - 0x1000);
        for(int s = 24; s >= 0; s -= 8) sp.push_back(u8(w >> s));
      }
    }
    if(!targets.contains(pc) || !entered) return;
    targets.erase(pc); // Only the first fetch can authorize this generation.
    auto reject = [&](const char* reason) {
      std::fprintf(result, "{\"rejected_entry\":%u,\"steps\":%llu,\"reason\":\"%s\"}\n", pc, (unsigned long long)steps, reason);
    };
    u32 p = plaidFetchAccess.physical;
    if(p >= written.size() || !written[p]) { reject("no completed RAM producer"); return; }
    u32 lo = p, hi = p;
    while(lo && written[lo-1] && !(written[lo-1] & 4)) lo--;
    while(hi < written.size() && written[hi] && !(written[hi] & 4)) hi++;
    lo = (lo + 3) & ~3u; hi &= ~3u;
    if(lo > p || hi < p + 4) { reject("incomplete produced instruction"); return; }
    // RAM must represent the instruction cache, including previously filled
    // lines in the candidate. A stale cache image is never accepted.
    for(auto& line : cpu.icache.lines) {
      if(!line.valid()) continue;
      u32 a = (line.tagKey & ~1u) | line.index;
      for(u32 i = 0; i < 8; i++) {
        u32 at = a + i * 4;
        if(at >= lo && at < hi && line.words[i] != rdram.ram.read<Word>(at, RBusDevice::ARES_DEBUGGER)) { reject("stale instruction cache"); return; }
      }
    }
    if(rdram.ram.read<Word>(p, RBusDevice::ARES_DEBUGGER) != word) { reject("fetched word differs from RAM"); return; }
    std::fprintf(result, "{\"entry\":%u,\"destination\":%u,\"steps\":%llu,\"cpu_writes\":", pc, 0x80000000u | lo, (unsigned long long)steps);
    ranges(result, lo, hi, 1);
    std::fprintf(result, ",\"pi_dma\":[");
    for(size_t i = 0; i < dma.size(); i++) std::fprintf(result, "%s[%u,%u,%u]", i ? "," : "", dma[i][0], dma[i][1], dma[i][2]);
    std::fprintf(result, "],\"bytes\":[");
    for(u32 a = lo; a < hi; a++) std::fprintf(result, "%s%u", a == lo ? "" : ",", (u32)rdram.ram.read<Byte>(a, RBusDevice::ARES_DEBUGGER));
    std::fprintf(result, "]}\n");
    if(!exactMany) {
      for(auto it = targets.begin(); it != targets.end();) {
        if(*it >= (0x80000000u | lo) && *it < (0x80000000u | hi)) it = targets.erase(it);
        else ++it;
      }
    }
}
int main(int argc, char** argv) {
  if(argc != 8 && argc != 9) return 2;
  if(argc == 9 && std::strcmp(argv[8], "exact-many") != 0) return 2;
  exactMany = argc == 9;
  auto bytes = nall::file::read(argv[1]);
  auto firmware = nall::file::read(argv[2]);
  boot = std::strtoul(argv[3], nullptr, 0);
  std::string targetList = argv[4];
  for(size_t at = 0; at < targetList.size();) {
    char* end; targets.insert(std::strtoul(targetList.c_str() + at, &end, 0));
    at = end - targetList.c_str(); if(at < targetList.size()) at++;
  }
  u64 budget = std::strtoull(argv[5], nullptr, 0);
  if(bytes.size() < 4096 || firmware.size() != 1984 || budget > 100000000) return 2;
  result = std::fopen(argv[7], "wb"); if(!result) return 2;
  Headless frontend; platform = &frontend;
  frontend.systemPak->append("pif.ntsc.rom", std::span<const u8>{firmware.data(), firmware.size()});
  frontend.cartPak->setAttribute("title", "Plaid analysis boot");
  frontend.cartPak->setAttribute("region", "NTSC");
  frontend.cartPak->setAttribute("cic", argv[6]);
  frontend.cartPak->append("program.rom", std::span<const u8>{bytes.data(), bytes.size()});
  Node::System root;
  if(!load(root, "[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak", "true"); option("Deterministic Entropy", "true"); option("Recompiler", "false");
  cartridgeSlot.port->allocate(); cartridgeSlot.port->connect();
  controllerPort1.port->allocate("Gamepad"); controllerPort1.port->connect();
  ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;
  std::vector<u8> hidden(rdram.ram.size / 2); rdram.hidden.data = hidden.data();
  // Test-only declared post-IPL state, never selected by the ROM-only adapter.
  if(!std::strcmp(argv[6], "fixture")) {
    rdram.mapIdentity = 1;
    for(u32 a = 0; a < 0x400; a++)
      rdram.ram.write<Byte>(a, bytes[a], RBusDevice::ARES_DEBUGGER);
    for(u32 a = 0x1000; a + 4 <= bytes.size(); a += 4)
      rdram.ram.write<Word>(a - 0xc00, (u32)bytes[a] << 24 | (u32)bytes[a+1] << 16 | (u32)bytes[a+2] << 8 | bytes[a+3], RBusDevice::ARES_DEBUGGER);
    for(auto& r : cpu.ipu.r) r.u64 = 0;
    cpu.scc.status.errorLevel = cpu.scc.status.exceptionLevel = 0;
    cpu.context.setMode(); cpu.pipeline.setPc(0xffffffff00000000ull | boot);
  }
  plaidRdramBurstObserver = [](bool w, u32 a, u32 n, u32 d, const u32*) { mark(w,a,n,d); };
  plaidRdramScalarObserver = [](bool w, u32 a, u32 n, u32 d, u64) { mark(w,a,n,d); };
  plaidPiDmaObserver = [](u32 kind,u32 a,u32 p,u32 n,u32,u32) { if(kind == 1) dma.push_back({a,p,n}); };
  plaidCpuInstructionObserver = [](bool before, u64 pc, u32 word) { if(before) observe(pc, word); };
  u32 vis = 0;
  for(; steps < budget && vis < 3600 && !targets.empty(); steps++) {
    if(cpu.instruction()) cpu.synchronize();
    if(vi.refreshed) { vis++; vi.refreshed = false; }
  }
  std::fprintf(result, "{\"stop_pc\":%u,\"steps\":%llu,\"vi\":%u,\"entered\":%s,\"remaining\":%zu,\"sp\":[", (u32)cpu.ipu.pc, (unsigned long long)steps, vis, entered ? "true" : "false", targets.size());
  for(size_t i = 0; i < sp.size(); i++) std::fprintf(result, "%s%u", i ? "," : "", (u32)sp[i]);
  std::fprintf(result, "],\"boot_entry\":%u,\"ram_prefix\":[", boot);
  for(size_t i = 0; i < ram_prefix.size(); i++) std::fprintf(result, "%s%u", i ? "," : "", (u32)ram_prefix[i]);
  std::fprintf(result, "]}\n");
  bool error = std::ferror(result); if(std::fclose(result)) error = true;
  ares::Nintendo64::system.unload();
  return error ? 5 : 0;
}
