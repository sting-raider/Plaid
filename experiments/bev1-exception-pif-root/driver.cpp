/* SPDX-License-Identifier: ISC
 * Plaid research probe: BEV=1 exception-root fetch -> PIF-ROM provenance.
 * Synthetic original PIF bytes only; no Nintendo firmware is embedded.
 */
#define main plaid_oracle_fixture_main
#include "../../spikes/003-ares-oracle/driver.cpp"
#undef main
#include <vector>

struct PlaidPifWitness {
  bool present = false;
  u32 offset = 0;
  u32 word = 0;
};

struct PlaidPifFetchEvent {
  u64 id = 0;
  u64 vaddr = 0;
  u32 translated = 0;
  u32 physical = 0;
  bool cached = false;
  u32 returned = 0;
  bool ended = false;
  PlaidPifWitness witness;
};

static std::vector<PlaidPifFetchEvent> plaidEvents;
static long long plaidActive = -1;
static u64 plaidNextId = 1;
static u64 plaidBackingReads = 0;
static u64 plaidUnattributedBackingReads = 0;

namespace ares::Nintendo64 {

void plaidPifFetchBoundary(bool begin, u64 vaddr, u32 translated, u32 physical, bool cached, u32 value) {
  if(begin) {
    if(plaidActive != -1) std::abort();
    PlaidPifFetchEvent event;
    event.id = plaidNextId++;
    event.vaddr = vaddr;
    event.translated = translated;
    event.physical = physical;
    event.cached = cached;
    plaidEvents.push_back(event);
    plaidActive = (long long)plaidEvents.size() - 1;
    return;
  }
  if(plaidActive < 0 || (size_t)plaidActive >= plaidEvents.size()) std::abort();
  auto& event = plaidEvents[(size_t)plaidActive];
  if(event.vaddr != vaddr || event.translated != translated || event.physical != physical || event.cached != cached) std::abort();
  event.returned = value;
  event.ended = true;
  plaidActive = -1;
}

void plaidPifRomBackingRead(u32 offset, u32 word) {
  plaidBackingReads++;
  if(plaidActive < 0) {
    plaidUnattributedBackingReads++;
    return;
  }
  auto& event = plaidEvents[(size_t)plaidActive];
  if(event.witness.present) std::abort();
  event.witness = {true, offset, word};
}

}  // namespace ares::Nintendo64

static constexpr u64 VectorVa = 0xffff'ffff'bfc0'0380ull;
static constexpr u32 VectorPhys = 0x1fc0'0380;
static constexpr u32 VectorOffset = 0x380;
static constexpr u64 TriggerVa = 0xffff'ffff'a000'4000ull;
static constexpr u32 TriggerPhys = 0x0000'4000;
static constexpr u32 Syscall = 0x0000000c;
static constexpr u32 Handler = 0x24020007;  // ADDIU v0,zero,7

static auto syntheticFirmware() -> std::vector<u8> {
  std::vector<u8> firmware(0x7c0);
  auto put = [&](u32 offset, u32 word) {
    firmware[offset + 0] = word >> 24;
    firmware[offset + 1] = word >> 16;
    firmware[offset + 2] = word >> 8;
    firmware[offset + 3] = word;
  };
  for(u32 offset = 0; offset < firmware.size(); offset += 4) {
    put(offset, 0xa5000000u ^ (offset * 0x1021u) ^ (offset << 16));
  }
  put(VectorOffset, Handler);
  put(VectorOffset + 8, Handler);  // equal-value decoy at a different PIF offset
  return firmware;
}

static auto backingWrite(u32 address, u32 word) -> void {
  rdram.ram.write<Word>(address, word, RBusDevice::ARES_DEBUGGER);
}

static auto executeAt(u64 pc) -> void {
  cpu.pipeline.setPc(pc);
  if(cpu.instruction()) cpu.synchronize();
}

static auto triggerSyscall() -> bool {
  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.status.vectorLocation = 1;
  cpu.scc.status.privilegeMode = 0;
  cpu.context.setMode();
  executeAt(TriggerVa);
  return cpu.ipu.pc == VectorVa && cpu.scc.cause.exceptionCode == 8;
}

int main(int argc, char** argv) {
  if(argc != 2) return 2;
  const char* mode = argv[1];
  auto firmware = syntheticFirmware();

  Headless frontend;
  platform = &frontend;
  frontend.systemPak->append("pif.ntsc.rom", std::span<const u8>{firmware.data(), firmware.size()});
  frontend.cartPak->setAttribute("title", "Plaid BEV1 exception PIF root fixture");
  frontend.cartPak->setAttribute("region", "NTSC");
  frontend.cartPak->setAttribute("cic", "CIC-NUS-6102");
  frontend.cartPak->append("program.rom", 8192);
  ares::Nintendo64::system.expansionPak = true;
  Node::System root;
  if(!load(root, "[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Deterministic Entropy", "true");
  option("Recompiler", "false");
  cartridgeSlot.port->allocate();
  cartridgeSlot.port->connect();
  ares::Nintendo64::system.power(false);
  std::vector<u8> hidden(rdram.ram.size / 2);
  rdram.hidden.data = hidden.data();
  rdram.mapIdentity = 1;
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;

  for(auto& reg : cpu.ipu.r) reg.u64 = 0;
  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.status.vectorLocation = 1;
  cpu.scc.status.privilegeMode = 0;
  cpu.context.setMode();
  cpu.icache.power(false);
  cpu.dcache.power(false);
  pif.io.romLockout = 0;
  si.io.ioBusy = 0;
  backingWrite(TriggerPhys, Syscall);

  u32 decoy = 0;
  if(!strcmp(mode, "equal_offset_decoy")) {
    decoy = pif.readInt(VectorOffset + 8);
    if(decoy != Handler) return 5;
  } else if(!strcmp(mode, "mirror_decoy")) {
    decoy = pif.readInt(0xb80);  // masked by PIF to the same 0x380 backing offset
    if(decoy != Handler) return 6;
  } else if(strcmp(mode, "normal") && strcmp(mode, "busy_latch") && strcmp(mode, "lockout")) {
    return 7;
  }

  if(!triggerSyscall()) return 8;
  u64 rootPc = cpu.ipu.pc;

  if(!strcmp(mode, "busy_latch")) {
    si.io.ioBusy = 1;
    si.io.busLatch = Handler;
  } else if(!strcmp(mode, "lockout")) {
    pif.io.romLockout = 1;
  }

  cpu.ipu.r[2].u64 = 0;
  if(cpu.instruction()) cpu.synchronize();
  u32 handlerV0 = cpu.ipu.r[2].u32;
  u64 postPc = cpu.ipu.pc;

  std::printf("{\"mode\":\"%s\",\"machine\":{", mode);
  std::printf("\"root_pc\":%llu,\"post_pc\":%llu,\"v0\":%u,\"exception\":%u,\"epc\":%llu,",
    (unsigned long long)rootPc, (unsigned long long)postPc, handlerV0,
    (u32)cpu.scc.cause.exceptionCode, (unsigned long long)cpu.scc.epc);
  std::printf("\"bev\":%u,\"exl\":%u,\"pif_lockout\":%u,\"si_io_busy\":%u,\"si_bus_latch\":%u,\"decoy\":%u},",
    (u32)cpu.scc.status.vectorLocation, (u32)cpu.scc.status.exceptionLevel,
    (u32)pif.io.romLockout, (u32)si.io.ioBusy, si.io.busLatch, decoy);
  std::printf("\"backing_reads\":%llu,\"unattributed_backing_reads\":%llu,\"fetches\":[",
    (unsigned long long)plaidBackingReads, (unsigned long long)plaidUnattributedBackingReads);
  for(size_t i = 0; i < plaidEvents.size(); i++) {
    auto& event = plaidEvents[i];
    std::printf("%s{\"id\":%llu,\"vaddr\":%llu,\"translated\":%u,\"physical\":%u,\"cached\":%s,\"returned\":%u,\"ended\":%s,\"witness\":",
      i ? "," : "", (unsigned long long)event.id, (unsigned long long)event.vaddr,
      event.translated, event.physical, event.cached ? "true" : "false", event.returned,
      event.ended ? "true" : "false");
    if(event.witness.present) {
      std::printf("{\"kind\":\"pif_rom\",\"offset\":%u,\"word\":%u}", event.witness.offset, event.witness.word);
    } else {
      std::printf("null");
    }
    std::printf("}");
  }
  std::printf("]}\n");
  std::fflush(stdout);
  ares::Nintendo64::system.unload();
  return 0;
}
