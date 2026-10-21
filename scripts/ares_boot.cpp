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
static bool seekUncovered = false;
static std::vector<std::array<u32, 2>> covered;
static u32 uncoveredEntry = 0;
static std::set<u32> openSites;
static std::set<std::pair<u32, u32>> observedTargets;
static std::set<u32> seenSites;
static std::set<u32> requestedSites;
struct ReplayBinding { u32 mapped, runtime, size; long long source; };
static std::vector<ReplayBinding> bindings;
static std::vector<u8> sourceRom;
static u32 canonical(u32 pc) {
  return pc >= 0x80000000u && pc < 0xc0000000u ? 0x80000000u | (pc & 0x1fffffffu) : pc;
}
static bool bindingMatches(const ReplayBinding& b) {
  if(b.source == -2) return true; // fixed image, no competing slot identity
  u32 runtime = canonical(b.runtime);
  if(b.source < 0 || runtime < 0x80000000u || runtime >= 0x80800000u ||
     (u64)runtime + b.size > 0x80800000u || (u64)b.source + b.size > sourceRom.size()) return false;
  u32 p = runtime & 0x1fffffffu;
  for(u32 i = 0; i < b.size; i++)
    if(rdram.ram.read<Byte>(p + i, RBusDevice::ARES_DEBUGGER) != sourceRom[b.source + i]) return false;
  // Source identity must describe executed cache bytes too, not only new RAM.
  for(auto& line : cpu.icache.lines) {
    if(!line.valid()) continue;
    u32 a = (line.tagKey & ~1u) | line.index;
    for(u32 i = 0; i < 8; i++) {
      u32 at = a + i * 4;
      if(at >= p && at < p + b.size && line.words[i] != rdram.ram.read<Word>(at, RBusDevice::ARES_DEBUGGER)) return false;
    }
  }
  return true;
}
static bool project(u32 pc, u32& mapped) {
  std::set<u32> matches;
  bool declared = false;
  for(auto& b : bindings) {
    u32 offset = canonical(pc) - canonical(b.runtime);
    if(offset >= b.size) continue;
    declared = true;
    if(bindingMatches(b)) matches.insert(b.mapped + offset);
  }
  if(!declared) { mapped = pc; return true; } // not yet discovered RAM
  if(matches.size() != 1) return false;
  mapped = *matches.begin(); return true;
}
static std::array<std::array<u32, 2>, 2> previousFetches{};
static std::vector<std::array<u32, 3>> dma;
static std::vector<u8> sp; // DMEM then IMEM at the first entry fetch
static std::vector<u8> ram_prefix; // IPL3's vector/boot-parameter area, before game entry
// Only complete aligned ROM-to-RAM transfers can supply a new raw occupant.
struct RawDma { u32 ram, rom, size, site; };
static std::vector<RawDma> completed;
static RawDma pending{};
static u32 copied = 0;
static bool validCopy = false, foundOccupant = false;
static void observeDma(u32 kind, u32 a, u32 p, u32 n, u32, u32 value) {
  if(!entered) return;
  if(kind == 1) {
    dma.push_back({a,p,n});
    pending = {a, p - 0x10000000u, n, (u32)cpu.ipu.pc}; copied = 0;
    validCopy = !(a & 7) && !(n & 3) && n && (u64)a + n <= written.size()
      && p >= 0x10000000u && (u64)pending.rom + n <= sourceRom.size();
    // Ordinary snapshots and non-slot data need no raw-occupant history.
    validCopy = validCopy && seekUncovered && (std::any_of(bindings.begin(), bindings.end(), [&](auto b) {
      u32 runtime = canonical(b.runtime);
      return b.source >= 0 && runtime >= 0x80000000u && runtime < 0x80800000u &&
        (u64)a < (runtime & 0x1fffffffu) + (u64)b.size && (runtime & 0x1fffffffu) < (u64)a + n;
    }) || std::any_of(completed.begin(), completed.end(), [&](auto d) {
      return d.ram + d.size == a && d.rom + d.size == pending.rom && d.site == pending.site;
    }));
  }
  if(kind == 5 && validCopy) {
    if(copied >= pending.size || a != pending.ram + copied || !rdram.mapIdentity ||
       value != sourceRom[pending.rom + copied]) validCopy = false;
    else copied++;
  }
  if(kind == 7 && validCopy && copied == pending.size) {
    // Join only adjacent complete transfers with the same ROM/RAM displacement.
    for(auto it = completed.begin(); it != completed.end();) {
      if(it->ram + it->size == pending.ram && it->rom + it->size == pending.rom && it->site == pending.site) {
        pending.ram = it->ram; pending.rom = it->rom; pending.size += it->size;
        it = completed.erase(it);
      } else ++it;
    }
    completed.push_back(pending); validCopy = false;
  }
}
static void mark(bool write, u32 address, u32 size, u32 device) {
  if(!entered || !write) return;
  if(!rdram.mapIdentity) { completed.clear(); validCopy = false; return; }
  if(address >= written.size()) return;
  completed.erase(std::remove_if(completed.begin(), completed.end(), [&](auto d) {
    return (u64)address < (u64)d.ram + d.size && (u64)d.ram < (u64)address + size;
  }), completed.end());
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
    auto previous = previousFetches;
    previousFetches = {previous[1], {pc, word}};
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
    if(!entered) return;
    // An unproven indirect transfer's target, read from its register before it
    // executes: discovery evidence, never a target certificate (ADR-0222).
    if(openSites.contains(pc) && word >> 26 == 0 && ((word & 63) == 8 || (word & 63) == 9)) {
      u32 site, target;
      if(project(pc, site) && project((u32)cpu.ipu.r[word >> 21 & 31].u64, target)) {
        observedTargets.insert({site, target});
        seenSites.insert(canonical(pc));
      }
    }
    // Numeric coverage cannot identify a different generation in a shared slot.
    // Test once per completed producer, at its first actual instruction fetch.
    if(seekUncovered && !foundOccupant) {
      u32 at = canonical(pc);
      for(auto it = completed.begin(); it != completed.end(); ++it) {
        auto d = *it;
        if(at < (0x80000000u | d.ram) || (u64)at >= 0x80000000ull + d.ram + d.size) continue;
        bool slot = false, matched = false;
        for(auto& b : bindings) {
          if(at - canonical(b.runtime) >= b.size || b.source < 0) continue;
          slot = true;
          u32 offset = (0x80000000u | d.ram) - canonical(b.runtime);
          // A complete subrange of the same declared ROM source is not new
          // text merely because unrelated bytes elsewhere no longer match.
          matched |= offset < b.size && d.size <= b.size - offset &&
            ((u64)b.source + offset == d.rom || bindingMatches(b));
        }
        completed.erase(it);
        if(!slot || matched) break;
        ReplayBinding candidate{0x80000000u | d.ram, 0x80000000u | d.ram, d.size, d.rom};
        if(!bindingMatches(candidate) || plaidFetchAccess.physical != (at & 0x1fffffffu) ||
           rdram.ram.read<Word>(at & 0x1fffffffu, RBusDevice::ARES_DEBUGGER) != word) break;
        std::fprintf(result, "{\"raw_occupant\":true,\"entry\":%u,\"destination\":%u,\"rom\":%u,\"size\":%u,\"load_site\":%u,\"steps\":%llu,\"bytes\":[",
          pc, 0x80000000u | d.ram, d.rom, d.size, d.site, (unsigned long long)steps);
        for(u32 i = 0; i < d.size; i++) std::fprintf(result, "%s%u", i ? "," : "", (u32)sourceRom[d.rom + i]);
        std::fprintf(result, "]}\n"); foundOccupant = true; return;
      }
    }
    // Extended replay supplies call roots and completed raw sources only.
    // Snapshot composition retains its reproducible 100M-instruction contract (including its Rust verifier).
    if(steps >= 100000000) return;
    bool uncovered = seekUncovered && pc >= 0x80000000u && pc < 0x80800000u
      && std::none_of(covered.begin(), covered.end(), [&](auto r) { return r[0] <= pc && pc < r[1]; });
    if(!targets.contains(pc) && !uncovered) return;
    if(uncovered) { uncoveredEntry = pc; seekUncovered = false; }
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
    std::fprintf(result, "],\"previous_fetches\":[[%u,%u],[%u,%u]],\"bytes\":[", previous[0][0], previous[0][1], previous[1][0], previous[1][1]);
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
  if(argc < 8 || argc > 12) return 2;
  if(argc == 9 && std::strcmp(argv[8], "exact-many") != 0) return 2;
  exactMany = argc == 9;
  if(argc >= 10) {
    if(std::strcmp(argv[8], "uncovered")) return 2;
    FILE* f = std::fopen(argv[9], "rb"); if(!f) return 2;
    u32 lo, hi;
    while(std::fscanf(f, "%u %u", &lo, &hi) == 2) {
      if(lo >= hi || (lo | hi) & 3) { std::fclose(f); return 2; }
      covered.push_back({lo, hi});
    }
    bool valid = std::feof(f) && !covered.empty(); std::fclose(f);
    if(!valid) return 2;
    seekUncovered = true;
  }
  if(argc >= 11) {
    FILE* f = std::fopen(argv[10], "rb"); if(!f) return 2;
    u32 site;
    while(std::fscanf(f, "%u", &site) == 1) {
      if(site & 3) { std::fclose(f); return 2; }
      openSites.insert(site); requestedSites.insert(canonical(site));
    }
    bool valid = std::feof(f); std::fclose(f);
    if(!valid) return 2;
  }
  if(argc == 12) {
    FILE* f = std::fopen(argv[11], "rb"); if(!f) return 2;
    ReplayBinding b;
    int fields;
    while((fields = std::fscanf(f, "%u %u %u %lld", &b.mapped, &b.runtime, &b.size, &b.source)) == 4) {
      if((b.mapped | b.runtime | b.size) & 3 || !b.size || b.source < -2 ||
         (u64)b.mapped + b.size > 0x100000000ull || (u64)b.runtime + b.size > 0x100000000ull) { std::fclose(f); return 2; }
      bindings.push_back(b);
    }
    bool valid = fields == EOF; std::fclose(f); if(!valid) return 2;
  }
  auto bytes = nall::file::read(argv[1]);
  auto firmware = nall::file::read(argv[2]);
  boot = std::strtoul(argv[3], nullptr, 0);
  std::string targetList = argv[4];
  for(size_t at = 0; at < targetList.size();) {
    char* end; targets.insert(std::strtoul(targetList.c_str() + at, &end, 0));
    at = end - targetList.c_str(); if(at < targetList.size()) at++;
  }
  u64 budget = std::strtoull(argv[5], nullptr, 0);
  if(bytes.size() < 4096 || firmware.size() != 1984 || budget > 2000000000) return 2;
  sourceRom.assign(bytes.data(), bytes.data() + bytes.size());
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
  plaidPiDmaObserver = observeDma;
  plaidCpuInstructionObserver = [](bool before, u64 pc, u32 word) { if(before) observe(pc, word); };
  u32 vis = 0;
  for(; steps < budget && vis < 3600 && (!targets.empty() || seekUncovered) && !uncoveredEntry && !foundOccupant; steps++) {
    if(cpu.instruction()) cpu.synchronize();
    if(vi.refreshed) { vis++; vi.refreshed = false; }
    // Extend only while the declared observation frontier remains uncovered.
    if(steps + 1 >= 100000000 && !requestedSites.empty() && seenSites == requestedSites) { steps++; break; }
  }
  std::fprintf(result, "{");
  if(argc >= 10) {
    if(uncoveredEntry) std::fprintf(result, "\"uncovered_entry\":%u,", uncoveredEntry);
    else std::fprintf(result, "\"uncovered_entry\":null,");
  }
  if(argc >= 11) {
    std::fprintf(result, "\"indirect_targets\":[");
    bool comma = false;
    for(auto [site, target] : observedTargets) {
      std::fprintf(result, "%s[%u,%u]", comma ? "," : "", site, target); comma = true;
    }
    std::fprintf(result, "],\"observed_runtime_sites\":[");
    bool first = true;
    for(auto site : seenSites) { std::fprintf(result, "%s%u", first ? "" : ",", site); first = false; }
    std::fprintf(result, "],\"unobserved_runtime_sites\":[");
    first = true;
    for(auto site : requestedSites) if(!seenSites.contains(site)) { std::fprintf(result, "%s%u", first ? "" : ",", site); first = false; }
    std::fprintf(result, "],");
  }
  const char* reason = foundOccupant ? "undeclared_slot_occupant" : uncoveredEntry ? "uncovered_fetch" : steps >= budget ? "instruction_budget"
    : vis >= 3600 ? "vi_budget" : !targets.empty() || seekUncovered ? "sites_covered" : "entries_complete";
  std::fprintf(result, "\"stop_reason\":\"%s\",", reason);
  std::fprintf(result, "\"stop_pc\":%u,\"steps\":%llu,\"vi\":%u,\"entered\":%s,\"remaining\":%zu,\"sp\":[", (u32)cpu.ipu.pc, (unsigned long long)steps, vis, entered ? "true" : "false", targets.size());
  for(size_t i = 0; i < sp.size(); i++) std::fprintf(result, "%s%u", i ? "," : "", (u32)sp[i]);
  std::fprintf(result, "],\"boot_entry\":%u,\"ram_prefix\":[", boot);
  for(size_t i = 0; i < ram_prefix.size(); i++) std::fprintf(result, "%s%u", i ? "," : "", (u32)ram_prefix[i]);
  std::fprintf(result, "]}\n");
  bool error = std::ferror(result); if(std::fclose(result)) error = true;
  ares::Nintendo64::system.unload();
  return error ? 5 : 0;
}
