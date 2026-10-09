/* SPDX-License-Identifier: ISC
 * Controlled cached self-modifying-code visibility fixture for pinned ares.
 */
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main

static constexpr u32 Target = 0x2000;
static constexpr u32 Helper = 0x3000;  // distinct I-cache index from Target
static constexpr u32 OldInstruction = 0x24020001;  // ADDIU v0,zero,1
static constexpr u32 NewInstruction = 0x24020002;  // ADDIU v0,zero,2
static constexpr u64 TargetVa = 0xffffffff80002000ull;
static constexpr u64 HelperVa = 0xffffffff80003000ull;

static u32 backing_word(u32 address) {
  return rdram.ram.read<Word>(address, RBusDevice::ARES_DEBUGGER);
}

static bool execute_one(u64 pc) {
  cpu.pipeline.setPc(pc);
  if(cpu.instruction()) cpu.synchronize();
  return cpu.scc.cause.exceptionCode == 0;
}

int main() {
  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid cached code patch visibility fixture");
  frontend.cartPak->setAttribute("region", "NTSC");
  frontend.cartPak->setAttribute("cic", "CIC-NUS-6102");
  frontend.cartPak->append("program.rom", 8192);
  Node::System root;
  if(!load(root, "[Nintendo] Nintendo 64 (NTSC)")) return 2;
  option("Expansion Pak", "true");
  option("Deterministic Entropy", "true");
  option("Recompiler", "false");
  cartridgeSlot.port->allocate();
  cartridgeSlot.port->connect();
  ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 3;

  std::vector<u8> hidden(rdram.ram.size / 2);
  rdram.hidden.data = hidden.data();
  rdram.mapIdentity = 1;
  for(auto& reg : cpu.ipu.r) reg.u64 = 0;
  cpu.scc.status.errorLevel = cpu.scc.status.exceptionLevel = 0;
  cpu.context.setMode();
  cpu.dcache.power(false);
  cpu.icache.power(false);

  auto put = [](u32 address, u32 word) {
    rdram.ram.write<Word>(address, word, RBusDevice::ARES_DEBUGGER);
  };
  put(Target, OldInstruction);
  put(Helper + 0x00, 0xae080000);  // SW t0,0(s0): cached patch into Target D-cache line
  put(Helper + 0x04, 0xbe190000);  // CACHE 0x19: D-cache hit write back,0(s0)
  put(Helper + 0x08, 0xbe100000);  // CACHE 0x10: I-cache hit invalidate,0(s0)

  // Fill the target instruction-cache line from old backing and execute it.
  cpu.ipu.r[2].u64 = 0;
  if(!execute_one(TargetVa) || cpu.ipu.r[2].u32 != 1) return 4;
  auto& iline = cpu.icache.line(TargetVa);
  if(!iline.hit(Target) || iline.read(Target) != OldInstruction) return 5;

  // Execute an ordinary cached SW patch. It must mutate D-cache residency while
  // leaving both backing RDRAM and the already-resident I-cache line old.
  cpu.ipu.r[8].u64 = NewInstruction;
  cpu.ipu.r[16].u64 = TargetVa;
  if(!execute_one(HelperVa + 0x00)) return 6;
  auto& dline = cpu.dcache.line(TargetVa);
  if(!dline.hit(Target) || dline.words[0] != NewInstruction || dline.dirty != 0x000f) return 7;
  if(backing_word(Target) != OldInstruction) return 8;
  if(!iline.hit(Target) || iline.read(Target) != OldInstruction) return 9;

  cpu.ipu.r[2].u64 = 0;
  if(!execute_one(TargetVa) || cpu.ipu.r[2].u32 != 1) return 10;
  u32 afterStoreFetch = cpu.ipu.r[2].u32;

  // Guest D-cache writeback makes backing new. It does not mutate the independent
  // valid I-cache resident line, so the next cached fetch must still execute old.
  if(!execute_one(HelperVa + 0x04)) return 11;
  if(backing_word(Target) != NewInstruction || dline.dirty != 0) return 12;
  if(!iline.hit(Target) || iline.read(Target) != OldInstruction) return 13;

  cpu.ipu.r[2].u64 = 0;
  if(!execute_one(TargetVa) || cpu.ipu.r[2].u32 != 1) return 14;
  u32 afterWritebackFetch = cpu.ipu.r[2].u32;

  // Only after explicit I-cache invalidation does the next target fetch miss,
  // refill from the new backing word, and execute the patch.
  if(!execute_one(HelperVa + 0x08)) return 15;
  if(iline.hit(Target)) return 16;
  cpu.ipu.r[2].u64 = 0;
  if(!execute_one(TargetVa) || cpu.ipu.r[2].u32 != 2) return 17;
  u32 afterRefillFetch = cpu.ipu.r[2].u32;
  if(!iline.hit(Target) || iline.read(Target) != NewInstruction) return 18;

  std::printf("{\"after_store_fetch\":%u,\"after_writeback_fetch\":%u,\"after_refill_fetch\":%u,", afterStoreFetch, afterWritebackFetch, afterRefillFetch);
  std::printf("\"backing_word\":%u,\"icache_word\":%u,\"dcache_word\":%u,\"dcache_dirty\":%u,", backing_word(Target), iline.read(Target), dline.words[0], (u32)dline.dirty);
  std::printf("\"icache_hits\":%llu,\"icache_misses\":%llu,\"dcache_hits\":%llu,\"dcache_misses\":%llu,\"dcache_writebacks\":%llu,\"exception\":%u}\n",
    (unsigned long long)cpu.profile.icacheHits, (unsigned long long)cpu.profile.icacheMisses,
    (unsigned long long)cpu.profile.dcacheHits, (unsigned long long)cpu.profile.dcacheMisses,
    (unsigned long long)cpu.profile.dcacheWritebacks, (u32)cpu.scc.cause.exceptionCode);
  ares::Nintendo64::system.unload();
  return 0;
}
