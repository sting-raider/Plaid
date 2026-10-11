/* SPDX-License-Identifier: ISC
 * Compose a real CPU XORI transform through D-cache writeback and I-cache
 * residency into later executable fetches on the exact pinned ares interpreter.
 */
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main

static constexpr u32 Helper = 0x3000;
static constexpr u32 Source = 0x1000;
static constexpr u32 Decoy = 0x1100;
static constexpr u32 OldInstruction = 0x24020001;  // ADDIU v0,zero,1
static constexpr u32 NewInstruction = 0x24020002;  // ADDIU v0,zero,2
static constexpr u64 HelperVa = 0xffffffff80003000ull;
static constexpr u64 SourceVa = 0xffffffffa0001000ull;
static constexpr u64 DecoyVa = 0xffffffffa0001100ull;

struct ScenarioFacts {
  u32 after_store = 0;
  u32 after_writeback = 0;
  u32 final_fetch = 0;
  u32 source_word = 0;
  u32 decoy_word = 0;
  u32 transform_word = 0;
  u32 backing_word = 0;
  u32 icache_word = 0;
  u32 dcache_word = 0;
};

static u32 backing_word(u32 address) {
  return rdram.ram.read<Word>(address, RBusDevice::ARES_DEBUGGER);
}

static void put(u32 address, u32 word) {
  rdram.ram.write<Word>(address, word, RBusDevice::ARES_DEBUGGER);
}

static bool execute_one(u64 pc) {
  cpu.pipeline.setPc(pc);
  if(cpu.instruction()) cpu.synchronize();
  return cpu.scc.cause.exceptionCode == 0;
}

static void reset_cpu_state() {
  for(auto& reg : cpu.ipu.r) reg.u64 = 0;
  cpu.scc.cause.exceptionCode = 0;
  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.context.setMode();
  cpu.dcache.power(false);
  cpu.icache.power(false);
}

static void install_helper(u16 imm) {
  put(Helper + 0x00, 0x8e690000);           // LW   t1,0(s3): equal-valued decoy
  put(Helper + 0x04, 0x8e280000);           // LW   t0,0(s1): actual source
  put(Helper + 0x08, 0x39080000 | imm);     // XORI t0,t0,imm
  put(Helper + 0x0c, 0xae080000);           // SW   t0,0(s0): cacheable target
  put(Helper + 0x10, 0xbe190000);           // CACHE 0x19: D$ hit writeback
  put(Helper + 0x14, 0xbe100000);           // CACHE 0x10: I$ hit invalidate
  put(Helper + 0x18, 0xae4a0000);           // SW   t2,0(s2): uncached target alias
}

static ScenarioFacts run_scenario(u32 target, u16 imm, bool foreign_same_value,
                                  bool prefill_before_writeback) {
  reset_cpu_state();
  install_helper(imm);

  const u64 target_va = 0xffffffff80000000ull | target;
  const u64 target_uncached = 0xffffffffa0000000ull | target;
  const u32 source_word = NewInstruction ^ imm;

  put(target, OldInstruction);
  put(Source, source_word);
  put(Decoy, source_word);

  // Establish a stale resident I-cache generation with the old instruction.
  cpu.ipu.r[2].u64 = 0;
  if(!execute_one(target_va) || cpu.ipu.r[2].u32 != 1) std::exit(10);
  auto& iline = cpu.icache.line(target_va);
  if(!iline.hit(target) || iline.read(target) != OldInstruction) std::exit(11);

  // Run equal-valued decoy load, exact source load, XORI, and cacheable SW.
  cpu.ipu.r[16].u64 = target_va;       // s0: cached executable destination
  cpu.ipu.r[17].u64 = SourceVa;        // s1: exact source
  cpu.ipu.r[18].u64 = target_uncached; // s2: foreign uncached writer alias
  cpu.ipu.r[19].u64 = DecoyVa;         // s3: equal-valued decoy source
  cpu.ipu.r[10].u64 = NewInstruction;  // t2: later same-value foreign store

  if(!execute_one(HelperVa + 0x00)) std::exit(12);
  if(cpu.ipu.r[9].u32 != source_word) std::exit(13);
  if(!execute_one(HelperVa + 0x04)) std::exit(14);
  if(cpu.ipu.r[8].u32 != source_word) std::exit(15);
  if(!execute_one(HelperVa + 0x08)) std::exit(16);
  if(cpu.ipu.r[8].u32 != NewInstruction) std::exit(17);
  if(!execute_one(HelperVa + 0x0c)) std::exit(18);

  auto& dline = cpu.dcache.line(target_va);
  if(!dline.hit(target) || dline.words[(target & 0x1f) >> 2] != NewInstruction || dline.dirty == 0)
    std::exit(19);
  if(backing_word(target) != OldInstruction) std::exit(20);
  if(!iline.hit(target) || iline.read(target) != OldInstruction) std::exit(21);

  cpu.ipu.r[2].u64 = 0;
  if(!execute_one(target_va) || cpu.ipu.r[2].u32 != 1) std::exit(22);
  const u32 after_store = cpu.ipu.r[2].u32;

  if(prefill_before_writeback) {
    // Invalidate/refill while backing is still old. The resulting resident line
    // must remain old even after the later D-cache writeback.
    if(!execute_one(HelperVa + 0x14)) std::exit(23);
    if(iline.hit(target)) std::exit(24);
    cpu.ipu.r[2].u64 = 0;
    if(!execute_one(target_va) || cpu.ipu.r[2].u32 != 1) std::exit(25);
    if(!iline.hit(target) || iline.read(target) != OldInstruction) std::exit(26);
  }

  if(!execute_one(HelperVa + 0x10)) std::exit(27);
  if(backing_word(target) != NewInstruction || dline.dirty != 0) std::exit(28);

  cpu.ipu.r[2].u64 = 0;
  if(!execute_one(target_va) || cpu.ipu.r[2].u32 != 1) std::exit(29);
  const u32 after_writeback = cpu.ipu.r[2].u32;

  if(foreign_same_value) {
    // A second successful writer stores identical bits after the transform
    // writeback. Final payload equality cannot tell which backing generation the
    // later I-cache fill consumed.
    if(!execute_one(HelperVa + 0x18)) std::exit(30);
    if(backing_word(target) != NewInstruction) std::exit(31);
  }

  u32 final_fetch = 0;
  if(prefill_before_writeback) {
    cpu.ipu.r[2].u64 = 0;
    if(!execute_one(target_va) || cpu.ipu.r[2].u32 != 1) std::exit(32);
    final_fetch = cpu.ipu.r[2].u32;
    if(!iline.hit(target) || iline.read(target) != OldInstruction) std::exit(33);
  } else {
    if(!execute_one(HelperVa + 0x14)) std::exit(34);
    if(iline.hit(target)) std::exit(35);
    cpu.ipu.r[2].u64 = 0;
    if(!execute_one(target_va) || cpu.ipu.r[2].u32 != 2) std::exit(36);
    final_fetch = cpu.ipu.r[2].u32;
    if(!iline.hit(target) || iline.read(target) != NewInstruction) std::exit(37);
  }

  return {
    .after_store = after_store,
    .after_writeback = after_writeback,
    .final_fetch = final_fetch,
    .source_word = source_word,
    .decoy_word = source_word,
    .transform_word = NewInstruction,
    .backing_word = backing_word(target),
    .icache_word = iline.read(target),
    .dcache_word = dline.words[(target & 0x1f) >> 2],
  };
}

int main() {
  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid XORI cache fetch composition fixture");
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

  // Separate target lines prevent one scenario's resident line from carrying
  // into another; caches are also explicitly powered/reset per scenario.
  auto normal = run_scenario(0x2000, 0x00ff, false, false);
  auto foreign = run_scenario(0x4000, 0x00ff, true, false);
  auto prefill = run_scenario(0x6000, 0x00ff, false, true);
  auto identity = run_scenario(0x8000, 0x0000, false, false);

  std::printf("{");
  std::printf("\"normal_after_store\":%u,\"normal_after_writeback\":%u,\"normal_final\":%u,", normal.after_store, normal.after_writeback, normal.final_fetch);
  std::printf("\"normal_source\":%u,\"normal_transform\":%u,\"normal_backing\":%u,\"normal_icache\":%u,", normal.source_word, normal.transform_word, normal.backing_word, normal.icache_word);
  std::printf("\"foreign_after_store\":%u,\"foreign_after_writeback\":%u,\"foreign_final\":%u,\"foreign_backing\":%u,\"foreign_icache\":%u,", foreign.after_store, foreign.after_writeback, foreign.final_fetch, foreign.backing_word, foreign.icache_word);
  std::printf("\"prefill_after_store\":%u,\"prefill_after_writeback\":%u,\"prefill_final\":%u,\"prefill_backing\":%u,\"prefill_icache\":%u,", prefill.after_store, prefill.after_writeback, prefill.final_fetch, prefill.backing_word, prefill.icache_word);
  std::printf("\"identity_source\":%u,\"identity_transform\":%u,\"identity_final\":%u,\"identity_backing\":%u,", identity.source_word, identity.transform_word, identity.final_fetch, identity.backing_word);
  std::printf("\"exception\":%u}\n", (u32)cpu.scc.cause.exceptionCode);

  ares::Nintendo64::system.unload();
  return 0;
}
