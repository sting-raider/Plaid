/* SPDX-License-Identifier: ISC
 * Compose exception-vector entry with instruction-cache resident generations.
 */
#define main capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main

static constexpr u32 VectorPhys = 0x00000180;
static constexpr u64 VectorVa = 0xffffffff80000180ull;
static constexpr u32 TriggerPhys = 0x00004000;
static constexpr u64 TriggerVa = 0xffffffffa0004000ull;
static constexpr u32 InvalidatePhys = 0x00005000;
static constexpr u64 InvalidateVa = 0xffffffffa0005000ull;
static constexpr u32 OldHandler = 0x24020001;  // ADDIU v0,zero,1
static constexpr u32 NewHandler = 0x24020002;  // ADDIU v0,zero,2
static constexpr u32 Syscall = 0x0000000c;
static constexpr u32 IcacheHitInvalidateS0 = 0xbe100000; // CACHE 0x10,0(s0)

static auto backingWrite(u32 address, u32 word) -> void {
  rdram.ram.write<Word>(address, word, RBusDevice::ARES_DEBUGGER);
}

static auto backingRead(u32 address) -> u32 {
  return rdram.ram.read<Word>(address, RBusDevice::ARES_DEBUGGER);
}

static auto executeAt(u64 pc) -> void {
  cpu.pipeline.setPc(pc);
  if(cpu.instruction()) cpu.synchronize();
}

static auto triggerSyscall() -> bool {
  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.status.vectorLocation = 0;
  cpu.scc.status.privilegeMode = 0;
  cpu.context.setMode();
  executeAt(TriggerVa);
  return cpu.ipu.pc == VectorVa && cpu.scc.cause.exceptionCode == 8;
}

int main() {
  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid exception root generation fixture");
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
  cpu.scc.status.vectorLocation = 0;
  cpu.scc.status.privilegeMode = 0;
  cpu.context.setMode();
  cpu.dcache.power(false);
  cpu.icache.power(false);

  backingWrite(VectorPhys, OldHandler);
  backingWrite(TriggerPhys, Syscall);
  backingWrite(InvalidatePhys, IcacheHitInvalidateS0);

  // Warm the BEV=0 general exception vector into I-cache from generation A.
  cpu.ipu.r[2].u64 = 0;
  executeAt(VectorVa);
  if(cpu.ipu.r[2].u32 != 1) return 4;
  auto& line = cpu.icache.line(VectorVa);
  if(!line.hit(VectorPhys) || line.read(VectorPhys) != OldHandler) return 5;
  u32 warmHandler = cpu.ipu.r[2].u32;

  // Replace backing generation A with B without touching the already-resident line.
  backingWrite(VectorPhys, NewHandler);
  if(backingRead(VectorPhys) != NewHandler) return 6;
  if(!line.hit(VectorPhys) || line.read(VectorPhys) != OldHandler) return 7;

  // The architectural exception transfer reaches the correct vector address, but
  // the first handler fetch must still execute resident generation A.
  if(!triggerSyscall()) return 8;
  u64 staleRootPc = cpu.ipu.pc;
  cpu.ipu.r[2].u64 = 0;
  if(cpu.instruction()) cpu.synchronize();
  if(cpu.ipu.r[2].u32 != 1) return 9;
  u32 staleHandler = cpu.ipu.r[2].u32;
  u32 staleResidentWord = line.read(VectorPhys);

  // Guest I-cache hit invalidate executed from an uncached helper.  Only after the
  // next exception-root fetch misses/refills may generation B become executable.
  cpu.ipu.r[16].u64 = VectorVa;
  executeAt(InvalidateVa);
  if(line.hit(VectorPhys)) return 10;

  if(!triggerSyscall()) return 11;
  u64 refilledRootPc = cpu.ipu.pc;
  cpu.ipu.r[2].u64 = 0;
  if(cpu.instruction()) cpu.synchronize();
  if(cpu.ipu.r[2].u32 != 2) return 12;
  u32 refilledHandler = cpu.ipu.r[2].u32;
  if(!line.hit(VectorPhys) || line.read(VectorPhys) != NewHandler) return 13;

  std::printf("{\"vector_va\":%llu,\"backing_word\":%u,\"warm_handler\":%u,",
    (unsigned long long)VectorVa, backingRead(VectorPhys), warmHandler);
  std::printf("\"stale_root_pc\":%llu,\"stale_handler\":%u,\"stale_resident_word\":%u,",
    (unsigned long long)staleRootPc, staleHandler, staleResidentWord);
  std::printf("\"refilled_root_pc\":%llu,\"refilled_handler\":%u,\"refilled_resident_word\":%u,",
    (unsigned long long)refilledRootPc, refilledHandler, line.read(VectorPhys));
  std::printf("\"icache_hits\":%llu,\"icache_misses\":%llu}\n",
    (unsigned long long)cpu.profile.icacheHits,
    (unsigned long long)cpu.profile.icacheMisses);

  ares::Nintendo64::system.unload();
  return 0;
}
