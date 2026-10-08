/* SPDX-License-Identifier: ISC
 * Original physical-access observer selection; shared experiment stays separate.
 */
#define PLAID_PHYSICAL_FETCH 1
#include "../004-ares-fetch/driver.cpp"

struct FixtureObserver : Headless {
  auto log(Node::Debugger::Tracer::Tracer node, string_view) -> void override {
    if(node != cpu.debugger.tracer.instruction) return;
    std::printf("{\"pc\":%llu,\"word\":%u,\"physical\":%u,\"cached\":%s}\n",
      (unsigned long long)cpu.ipu.pc, cpu.disassembler.fetchedWord(),
      plaidFetchAccess.physical, plaidFetchAccess.cached ? "true" : "false");
  }
};

int physical_fixture() {
  FixtureObserver frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid physical access fixture");
  frontend.cartPak->setAttribute("region", "NTSC");
  frontend.cartPak->setAttribute("cic", "CIC-NUS-6102");
  frontend.cartPak->append("program.rom", 8192);
  Node::System root;
  if(!load(root, "[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Deterministic Entropy", "true");
  option("Recompiler", "false");
  cartridgeSlot.port->allocate(); cartridgeSlot.port->connect();
  ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;
  std::vector<u8> hidden(rdram.ram.size / 2);
  rdram.hidden.data = hidden.data();
  rdram.mapIdentity = 1;
  for(auto& reg : cpu.ipu.r) reg.u64 = 0;
  cpu.scc.status.errorLevel = cpu.scc.status.exceptionLevel = 0;
  cpu.context.setMode();
  cpu.debugger.tracer.instruction->setDepth(0);
  cpu.debugger.tracer.instruction->setMask(false);
  cpu.debugger.tracer.instruction->setEnabled(true);
  auto put = [](u32 pa, u32 word) { rdram.ram.write<Word>(pa, word, RBusDevice::ARES_DEBUGGER); };
  auto step = [](u64 pc, u64 expected) {
    cpu.pipeline.setPc(pc);
    if(cpu.instruction()) cpu.synchronize();
    return cpu.ipu.r[16].u64 == expected && cpu.scc.cause.exceptionCode == 0;
  };
  put(0, 0x24100001); // ADDIU s0,zero,1
  if(!step(0xffffffff80000000ull, 1)) return 5;
  put(0, 0x24100002); // Fixture write leaves the instruction cache stale.
  if(!step(0xffffffff80000000ull, 1)) return 6;
  if(!step(0xffffffffa0000000ull, 2)) return 7;
  cpu.icache.line(0xffffffff80000000ull).setValid(false);
  if(!step(0xffffffff80000000ull, 2)) return 8;
  // One virtual PC, two physical mappings; use the reference's TLB entry API.
  auto& entry = cpu.tlb.entry[0];
  entry = {};
  entry.global[0] = entry.global[1] = 1;
  entry.valid[0] = entry.valid[1] = 1;
  entry.cacheAlgorithm[0] = entry.cacheAlgorithm[1] = 2;
  entry.virtualAddress = 0x4000;
  entry.physicalAddress[0] = 0x2000;
  entry.synchronize();
  put(0x2000, 0x24100003);
  if(!step(0x4000, 3)) return 9;
  entry.physicalAddress[0] = 0x3000;
  entry.synchronize();
  put(0x3000, 0x24100004);
  if(!step(0x4000, 4)) return 10;
  // User reverse-endian fetch selects the other word lane after translation.
  cpu.scc.status.privilegeMode = 2;
  cpu.scc.status.reverseEndian = 1;
  cpu.context.setMode();
  put(0x3004, 0x24100005);
  if(!step(0x4000, 5)) return 11;
  ares::Nintendo64::system.unload();
  return 0;
}

int main(int argc, char** argv) {
  if(argc == 2 && !strcmp(argv[1], "fixture")) return physical_fixture();
  return fetch_observer_main(argc, argv);
}
