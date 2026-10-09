/* SPDX-License-Identifier: ISC
 * Cacheable TLB synonym/remap I-cache fixture for exact pinned ares.
 */
#define main capability_fixture_main
#include "../../spikes/003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>
#include <vector>

static constexpr u64 VaA = 0x00004000ull;
static constexpr u64 VaB = 0x00005000ull;  // different I-cache virtual index color
static constexpr u64 VaC = 0x00008000ull;  // same I-cache virtual index as VaA
static constexpr u32 PaA = 0x001000;
static constexpr u32 PaB = 0x003000;
static constexpr u32 PaC = 0x005000;
static constexpr u32 OriOld = 0x34091111;  // ori t1,zero,0x1111
static constexpr u32 OriNew = 0x34092222;  // ori t1,zero,0x2222
static constexpr u32 OriThird = 0x34093333;// ori t1,zero,0x3333

static void clear_tlb_cache() {
  for(auto& slot : cpu.tlb.tlbCache.entry) {
    slot.entry = nullptr;
    slot.frequency = 0;
  }
  cpu.devirtualizeCache = {};
}

static void clear_tlb_entries() {
  for(auto& entry : cpu.tlb.entry) entry = {};
  clear_tlb_cache();
}

static void write_tlb(u32 index, u64 vbase, u32 pbase0, u32 pbase1, u32 cca = 3) {
  CPU::TLB::Entry entry{};
  entry.pageMask = 0;
  entry.virtualAddress = vbase;
  entry.addressSpaceID = 7;
  entry.region = vbase >> 62;
  entry.global[0] = entry.global[1] = 0;
  entry.valid[0] = entry.valid[1] = 1;
  entry.dirty[0] = entry.dirty[1] = 1;
  entry.cacheAlgorithm[0] = entry.cacheAlgorithm[1] = cca;
  entry.physicalAddress[0] = pbase0;
  entry.physicalAddress[1] = pbase1;
  cpu.scc.index.tlbEntry = index;
  cpu.scc.tlb = entry;
  cpu.TLBWI();
}

static u32 execute_one(u64 pc) {
  cpu.ipu.r[9].u64 = 0;
  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.cause.exceptionCode = 0;
  cpu.scc.badVirtualAddress = 0;
  cpu.context.setMode();
  cpu.pipeline.setPc(pc);
  if(cpu.instruction()) cpu.synchronize();
  if(cpu.scc.cause.exceptionCode != 0) std::abort();
  return cpu.ipu.r[9].u32;
}

static void append_be(std::vector<u8>& out, u64 value, u32 width) {
  for(u32 i = width; i > 0; --i) out.push_back(value >> (8 * (i - 1)));
}

int main() {
  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid TLB I-cache synonym fixture");
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
  for(auto& reg : cpu.ipu.r) reg.u64 = 0;
  cpu.scc.status.errorLevel = cpu.scc.status.exceptionLevel = 0;
  cpu.scc.status.privilegeMode = 0;
  cpu.scc.status.kernelExtendedAddressing = 0;
  cpu.context.setMode();
  cpu.context.endian = CPU::Context::Endian::Big;
  cpu.dcache.power(false);
  cpu.icache.power(false);
  clear_tlb_entries();
  cpu.scc.tlb.addressSpaceID = 7;

  auto put = [](u32 address, u32 word) {
    rdram.ram.write<Word>(address, word, RBusDevice::ARES_DEBUGGER);
  };

  // One TLB row maps adjacent virtual pages A/B to the same physical page.
  // A and B differ in virtual I-cache index bits 12..13. A separate row maps C
  // to the same physical page but C has the same I-cache index as A.
  put(PaA, OriOld);
  write_tlb(0, VaA, PaA, PaA);
  write_tlb(1, VaC, PaA, PaA);

  auto idxA = (u32)(VaA >> 5 & 0x1ff);
  auto idxB = (u32)(VaB >> 5 & 0x1ff);
  auto idxC = (u32)(VaC >> 5 & 0x1ff);
  if(idxA == idxB || idxA != idxC) return 5;

  u64 miss0 = cpu.profile.icacheMisses;
  u32 firstA = execute_one(VaA);
  u64 miss1 = cpu.profile.icacheMisses;
  u32 firstC = execute_one(VaC);
  u64 miss2 = cpu.profile.icacheMisses;
  u32 firstB = execute_one(VaB);
  u64 miss3 = cpu.profile.icacheMisses;
  if(firstA != 0x1111 || firstB != 0x1111 || firstC != 0x1111) return 6;
  if(miss1 != miss0 + 1 || miss2 != miss1 || miss3 != miss2 + 1) return 7;

  auto& lineA = cpu.icache.line(VaA);
  auto& lineB = cpu.icache.line(VaB);
  if(&lineA == &lineB || &cpu.icache.line(VaA) != &cpu.icache.line(VaC)) return 8;
  u32 tagA0 = lineA.tagKey;
  u32 tagB0 = lineB.tagKey;

  // Change backing only. Both resident virtual colors must remain stale.
  put(PaA, OriNew);
  u32 staleA = execute_one(VaA);
  u32 staleB = execute_one(VaB);
  u64 missAfterStale = cpu.profile.icacheMisses;
  if(staleA != 0x1111 || staleB != 0x1111 || missAfterStale != miss3) return 9;

  // Invalidate/refill only A's virtual color. B must remain an independently
  // resident stale generation despite identical physical backing.
  lineA.setValid(false);
  u32 freshA = execute_one(VaA);
  u64 missAfterA = cpu.profile.icacheMisses;
  u32 stillStaleB = execute_one(VaB);
  if(freshA != 0x2222 || stillStaleB != 0x1111 || missAfterA != miss3 + 1) return 10;
  if(cpu.profile.icacheMisses != missAfterA) return 11;
  u32 divergentA = cpu.icache.line(VaA).words[0];
  u32 divergentB = cpu.icache.line(VaB).words[0];

  lineB.setValid(false);
  u32 freshB = execute_one(VaB);
  if(freshB != 0x2222 || cpu.profile.icacheMisses != missAfterA + 1) return 12;

  // Remap the same VA to a different physical page with equal payload. TLBWI
  // itself does not invalidate the resident line, but the physical tag mismatch
  // must force a refill on the next fetch even though instruction bytes match.
  put(PaB, OriNew);
  u32 preRemapTag = cpu.icache.line(VaA).tagKey;
  bool preRemapValid = cpu.icache.line(VaA).valid();
  write_tlb(0, VaA, PaB, PaA);
  bool afterTlbwiStillValid = cpu.icache.line(VaA).valid();
  u32 afterTlbwiTag = cpu.icache.line(VaA).tagKey;
  u64 missBeforeEqualRemap = cpu.profile.icacheMisses;
  u32 equalRemap = execute_one(VaA);
  u64 missAfterEqualRemap = cpu.profile.icacheMisses;
  u32 equalRemapTag = cpu.icache.line(VaA).tagKey;
  if(!preRemapValid || !afterTlbwiStillValid || preRemapTag != afterTlbwiTag) return 13;
  if(equalRemap != 0x2222 || missAfterEqualRemap != missBeforeEqualRemap + 1) return 14;
  if((equalRemapTag & ~1u) == (preRemapTag & ~1u)) return 15;

  // Repeat with different bytes to make the remapped generation externally clear.
  put(PaC, OriThird);
  write_tlb(0, VaA, PaC, PaA);
  u64 missBeforeDifferentRemap = cpu.profile.icacheMisses;
  u32 differentRemap = execute_one(VaA);
  u64 missAfterDifferentRemap = cpu.profile.icacheMisses;
  if(differentRemap != 0x3333 || missAfterDifferentRemap != missBeforeDifferentRemap + 1) return 16;

  std::vector<u8> cacheBytes;
  for(const auto& line : cpu.icache.lines) {
    append_be(cacheBytes, line.tagKey, 4);
    append_be(cacheBytes, line.index, 2);
    for(u32 word : line.words) append_be(cacheBytes, word, 4);
  }
  auto cacheHash = nall::Hash::SHA256(std::span<const u8>{cacheBytes.data(), cacheBytes.size()}).digest();

  std::printf("{\"idx_a\":%u,\"idx_b\":%u,\"idx_c\":%u,", idxA, idxB, idxC);
  std::printf("\"first\":[%u,%u,%u],\"stale\":[%u,%u],\"divergent_words\":[%u,%u],", firstA, firstB, firstC, staleA, staleB, divergentA, divergentB);
  std::printf("\"fresh\":[%u,%u],\"equal_remap\":%u,\"different_remap\":%u,", freshA, freshB, equalRemap, differentRemap);
  std::printf("\"misses\":[%llu,%llu,%llu,%llu,%llu,%llu,%llu],", (unsigned long long)miss0, (unsigned long long)miss1, (unsigned long long)miss2, (unsigned long long)miss3, (unsigned long long)missAfterA, (unsigned long long)missAfterEqualRemap, (unsigned long long)missAfterDifferentRemap);
  std::printf("\"initial_tags\":[%u,%u],\"pre_remap_tag\":%u,\"post_equal_remap_tag\":%u,", tagA0, tagB0, preRemapTag, equalRemapTag);
  std::printf("\"tlbwi_preserved_resident_valid\":%s,\"icache_sha256\":\"%s\"}\n", afterTlbwiStillValid ? "true" : "false", cacheHash.data());
  return 0;
}
