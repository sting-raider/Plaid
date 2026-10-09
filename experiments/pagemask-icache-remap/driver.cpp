/* SPDX-License-Identifier: ISC
 * Compose large-PageMask TLB geometry with cacheable I-cache resident lifetime.
 */
#define main capability_fixture_main
#include "../../spikes/003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>
#include <vector>

static constexpr u32 Mask16K = 0b11u << 13;
static constexpr u32 Mask64K = 0b1111u << 13;
static constexpr u64 Va16 = 0x00021000ull;      // 16K even; bit12=1 but selector bit14=0
static constexpr u64 Va64Odd = 0x00070000ull;   // 64K odd; bit12=0 but selector bit16=1
static constexpr u32 Pa16A = 0x011000;
static constexpr u32 Pa16B = 0x031000;
static constexpr u32 Pa64A = 0x051000;
static constexpr u32 Pa64Odd = 0x0a0000;
static constexpr u32 Decoy16A = 0x020000;
static constexpr u32 Decoy64A = 0x070000;
static constexpr u32 Decoy64Odd = 0x080000;
static constexpr u32 OriOld = 0x34091111;   // ori t1,zero,0x1111
static constexpr u32 OriNew = 0x34092222;   // ori t1,zero,0x2222
static constexpr u32 OriThird = 0x34093333; // ori t1,zero,0x3333
static constexpr u32 OriFourth = 0x34094444;// ori t1,zero,0x4444
static constexpr u32 OriOdd = 0x340a5555;   // ori t2,zero,0x5555

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

static void write_tlb(u32 index, u32 pageMask, u64 vbase, u32 pbase0, u32 pbase1,
                      u32 asid = 7, bool global = false) {
  CPU::TLB::Entry entry{};
  entry.pageMask = pageMask;
  entry.virtualAddress = vbase;
  entry.addressSpaceID = asid;
  entry.region = vbase >> 62;
  entry.global[0] = entry.global[1] = global;
  entry.valid[0] = entry.valid[1] = true;
  entry.dirty[0] = entry.dirty[1] = true;
  entry.cacheAlgorithm[0] = entry.cacheAlgorithm[1] = 3; // cacheable
  entry.physicalAddress[0] = pbase0;
  entry.physicalAddress[1] = pbase1;
  cpu.scc.index.tlbEntry = index;
  cpu.scc.tlb = entry;
  cpu.TLBWI();
}

static void reset_exception() {
  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.cause.exceptionCode = 0;
  cpu.scc.cause.branchDelay = 0;
  cpu.scc.badVirtualAddress = 0;
  cpu.context.setMode();
}

static u32 execute_one(u64 pc, u32 reg) {
  reset_exception();
  cpu.ipu.r[reg].u64 = 0;
  cpu.pipeline.setPc(pc);
  if(cpu.instruction()) cpu.synchronize();
  if(cpu.scc.cause.exceptionCode != 0) std::abort();
  return cpu.ipu.r[reg].u32;
}

static u32 execute_fault(u64 pc) {
  reset_exception();
  cpu.pipeline.setPc(pc);
  if(cpu.instruction()) cpu.synchronize();
  return cpu.scc.cause.exceptionCode;
}

static void append_be(std::vector<u8>& out, u64 value, u32 width) {
  for(u32 i = width; i > 0; --i) out.push_back(value >> (8 * (i - 1)));
}

int main() {
  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid PageMask I-cache compose fixture");
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

  // 16K even mapping. Bit 12 deliberately points at the wrong EntryLo under a
  // fixed-4K reconstruction, and that decoy contains equal bytes.
  put(Pa16A, OriOld);
  put(Decoy16A, OriOld);
  write_tlb(0, Mask16K, 0x00020000, 0x010000, 0x020000);
  u32 select16 = cpu.tlb.entry[0].addressSelect;
  u32 mask16 = cpu.tlb.entry[0].pageMask;
  auto& line = cpu.icache.line(Va16);
  u64 miss0 = cpu.profile.icacheMisses;
  u32 first = execute_one(Va16, 9);
  u64 miss1 = cpu.profile.icacheMisses;
  u32 tagFirst = line.tagKey;
  if(first != 0x1111 || miss1 != miss0 + 1 || tagFirst != ((Pa16A & ~0xfffu) | 1u)) return 5;

  // A legal same-value TLBWI is still an ordered mapping operation. It must not
  // be inferred from snapshot inequality, and in pinned ares it does not retire
  // the selected resident cache line.
  bool validBeforeSame = line.valid();
  write_tlb(0, Mask16K, 0x00020000, 0x010000, 0x020000);
  bool validAfterSame = line.valid();
  u32 tagAfterSame = line.tagKey;
  if(!validBeforeSame || !validAfterSame || tagAfterSame != tagFirst) return 6;

  // Current backing changes, but the cached fetch must stay on the resident
  // generation. Value equality is not used to infer provenance.
  put(Pa16A, OriNew);
  u32 stale = execute_one(Va16, 9);
  u64 missStale = cpu.profile.icacheMisses;
  if(stale != 0x1111 || missStale != miss1) return 7;

  // Same VA, same instruction payload, different translated physical tag.
  // TLBWI preserves the old line immediately; the next fetch must miss/refill.
  put(Pa16B, OriOld);
  put(0x040000, OriOld); // equal-valued fixed-4K/odd-half decoy
  bool preRemapValid = line.valid();
  u32 preRemapTag = line.tagKey;
  write_tlb(0, Mask16K, 0x00020000, 0x030000, 0x040000);
  bool postTlbwiValid = line.valid();
  u32 postTlbwiTag = line.tagKey;
  u64 missBeforeEqual = cpu.profile.icacheMisses;
  u32 equalRemap = execute_one(Va16, 9);
  u64 missAfterEqual = cpu.profile.icacheMisses;
  u32 tagEqual = line.tagKey;
  if(!preRemapValid || !postTlbwiValid || preRemapTag != postTlbwiTag) return 8;
  if(equalRemap != 0x1111 || missAfterEqual != missBeforeEqual + 1) return 9;
  if(tagEqual != ((Pa16B & ~0xfffu) | 1u) || tagEqual == tagFirst) return 10;

  // Mutating the new backing again leaves the equal-payload remap resident stale.
  put(Pa16B, OriThird);
  u32 staleNew = execute_one(Va16, 9);
  if(staleNew != 0x1111 || cpu.profile.icacheMisses != missAfterEqual) return 11;

  // Return to the original 16K mapping and fetch once to establish a fresh
  // resident generation there (the backing currently contains 0x2222).
  write_tlb(0, Mask16K, 0x00020000, 0x010000, 0x020000);
  u32 freshOriginal = execute_one(Va16, 9);
  u64 missFreshOriginal = cpu.profile.icacheMisses;
  u32 tagOriginalAgain = line.tagKey;
  if(freshOriginal != 0x2222 || missFreshOriginal != missAfterEqual + 1 || tagOriginalAgain != tagFirst) return 12;

  // Change original backing, then make that mapping temporarily unreachable by
  // both a remap and an ASID mismatch. Neither event is itself a resident-cache
  // retirement. Returning without a conflicting fetch must expose the stale line.
  put(Pa16A, OriFourth);
  write_tlb(0, Mask16K, 0x00020000, 0x030000, 0x040000);
  bool validWhileAway = line.valid();
  u32 tagWhileAway = line.tagKey;
  write_tlb(0, Mask16K, 0x00020000, 0x010000, 0x020000);
  bool validAfterBack = line.valid();
  u32 tagAfterBack = line.tagKey;
  u64 missBeforeAwayBack = cpu.profile.icacheMisses;
  u32 awayBack = execute_one(Va16, 9);
  u64 missAfterAwayBack = cpu.profile.icacheMisses;
  if(!validWhileAway || !validAfterBack || tagWhileAway != tagFirst || tagAfterBack != tagFirst) return 13;
  if(awayBack != 0x2222 || missAfterAwayBack != missBeforeAwayBack) return 14;

  cpu.scc.tlb.addressSpaceID = 0x22;
  u32 asidException = execute_fault(Va16);
  u64 missAfterAsidFail = cpu.profile.icacheMisses;
  bool validAfterAsidFail = line.valid();
  u32 tagAfterAsidFail = line.tagKey;
  if(asidException != 2 || missAfterAsidFail != missAfterAwayBack || !validAfterAsidFail || tagAfterAsidFail != tagFirst) return 15;
  cpu.scc.tlb.addressSpaceID = 7;
  u32 asidReturn = execute_one(Va16, 9);
  u64 missAfterAsidReturn = cpu.profile.icacheMisses;
  if(asidReturn != 0x2222 || missAfterAsidReturn != missAfterAsidFail) return 16;

  // Change only the mapping geometry to 64K for the same VA. Actual PageMask
  // translation is PA 0x051000; fixed bit12 would choose the equal-valued decoy.
  put(Pa64A, OriNew);
  put(Decoy64A, OriNew);
  write_tlb(0, Mask64K, 0x00020000, 0x050000, 0x070000);
  u32 select64 = cpu.tlb.entry[0].addressSelect;
  u32 mask64 = cpu.tlb.entry[0].pageMask;
  u64 missBeforeGeometry = cpu.profile.icacheMisses;
  u32 geometryRemap = execute_one(Va16, 9);
  u64 missAfterGeometry = cpu.profile.icacheMisses;
  u32 tagGeometry = line.tagKey;
  if(geometryRemap != 0x2222 || missAfterGeometry != missBeforeGeometry + 1) return 17;
  if(tagGeometry != ((Pa64A & ~0xfffu) | 1u) || tagGeometry == tagFirst) return 18;

  // 64K odd control with bit12 clear. The fixed-4K guess points at EntryLo0,
  // while actual PageMask geometry selects EntryLo1. Equal payload masks values.
  put(Decoy64Odd, OriOdd);
  put(Pa64Odd, OriOdd);
  write_tlb(1, Mask64K, 0x00060000, 0x080000, 0x0a0000);
  u64 missBeforeOdd = cpu.profile.icacheMisses;
  u32 odd = execute_one(Va64Odd, 10);
  u64 missAfterOdd = cpu.profile.icacheMisses;
  auto& oddLine = cpu.icache.line(Va64Odd);
  u32 oddTag = oddLine.tagKey;
  if(odd != 0x5555 || missAfterOdd != missBeforeOdd + 1 || oddTag != ((Pa64Odd & ~0xfffu) | 1u)) return 19;

  if(select16 != 0x4000 || select64 != 0x10000) return 20;

  std::vector<u8> cacheBytes;
  for(const auto& l : cpu.icache.lines) {
    append_be(cacheBytes, l.tagKey, 4);
    append_be(cacheBytes, l.index, 2);
    for(u32 word : l.words) append_be(cacheBytes, word, 4);
  }
  auto cacheHash = nall::Hash::SHA256(std::span<const u8>{cacheBytes.data(), cacheBytes.size()}).digest();

  std::printf("{\"select16\":%u,\"select64\":%u,\"mask16\":%u,\"mask64\":%u,", select16, select64, mask16, mask64);
  std::printf("\"first\":%u,\"stale\":%u,\"equal_remap\":%u,\"stale_new\":%u,\"fresh_original\":%u,", first, stale, equalRemap, staleNew, freshOriginal);
  std::printf("\"away_back\":%u,\"asid_exception\":%u,\"asid_return\":%u,\"geometry_remap\":%u,\"odd\":%u,", awayBack, asidException, asidReturn, geometryRemap, odd);
  std::printf("\"tags\":{\"first\":%u,\"equal\":%u,\"original_again\":%u,\"geometry\":%u,\"odd\":%u},", tagFirst, tagEqual, tagOriginalAgain, tagGeometry, oddTag);
  std::printf("\"resident_preservation\":{\"same_value_tlbwi\":%s,\"away_back\":%s,\"asid_fail\":%s},", (validAfterSame && tagAfterSame == tagFirst) ? "true" : "false", (validWhileAway && validAfterBack && tagAfterBack == tagFirst) ? "true" : "false", (validAfterAsidFail && tagAfterAsidFail == tagFirst) ? "true" : "false");
  std::printf("\"misses\":{\"start\":%llu,\"first\":%llu,\"stale\":%llu,\"equal\":%llu,\"fresh_original\":%llu,\"away_back\":%llu,\"asid_fail\":%llu,\"asid_return\":%llu,\"geometry\":%llu,\"odd\":%llu},", (unsigned long long)miss0, (unsigned long long)miss1, (unsigned long long)missStale, (unsigned long long)missAfterEqual, (unsigned long long)missFreshOriginal, (unsigned long long)missAfterAwayBack, (unsigned long long)missAfterAsidFail, (unsigned long long)missAfterAsidReturn, (unsigned long long)missAfterGeometry, (unsigned long long)missAfterOdd);
  std::printf("\"icache_sha256\":\"%s\"}\n", cacheHash.data());
  return 0;
}
