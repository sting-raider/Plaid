/* SPDX-License-Identifier: ISC
 * Plaid research probe: NMI root transfer -> actual PIF-ROM fetch provenance.
 */
#define main plaid_oracle_fixture_main
#include "../../spikes/003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>
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

static auto readFirmware(const char* path) -> std::vector<u8> {
  auto bytes = nall::file::read(path);
  if(bytes.size() != 0x7c0) return {};
  return std::vector<u8>(bytes.begin(), bytes.end());
}

static auto firmwareWord(const std::vector<u8>& firmware, u32 offset) -> u32 {
  return (u32)firmware[offset] << 24 | (u32)firmware[offset + 1] << 16 |
         (u32)firmware[offset + 2] << 8 | firmware[offset + 3];
}

int main(int argc, char** argv) {
  if(argc != 3) return 2;
  const char* mode = argv[1];
  auto firmware = readFirmware(argv[2]);
  if(firmware.size() != 0x7c0) return 3;
  const u32 fw0 = firmwareWord(firmware, 0);

  Headless frontend;
  platform = &frontend;
  frontend.systemPak->append("pif.ntsc.rom", std::span<const u8>{firmware.data(), firmware.size()});
  frontend.cartPak->setAttribute("title", "Plaid NMI root fetch provenance fixture");
  frontend.cartPak->setAttribute("region", "NTSC");
  frontend.cartPak->setAttribute("cic", "CIC-NUS-6102");
  frontend.cartPak->append("program.rom", 8192);
  ares::Nintendo64::system.expansionPak = true;
  Node::System root;
  if(!load(root, "[Nintendo] Nintendo 64 (NTSC)")) return 4;
  option("Deterministic Entropy", "true");
  option("Recompiler", "false");
  cartridgeSlot.port->allocate();
  cartridgeSlot.port->connect();
  ares::Nintendo64::system.power(false);
  std::vector<u8> hidden(rdram.ram.size / 2);
  rdram.hidden.data = hidden.data();
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 5;

  constexpr u64 interruptedPc = 0xffff'ffff'a000'0104ull;
  constexpr u64 rootPc = 0xffff'ffff'bfc0'0000ull;
  cpu.scc.status.vectorLocation = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.softReset = 1;
  cpu.scc.epc = 0x1111'2222'3333'4444ull;
  cpu.scc.epcError = 0x5555'6666'7777'8888ull;
  cpu.pipeline.setPc(interruptedPc);

  bool foreignRead = !strcmp(mode, "foreign_read_then_persistent") || !strcmp(mode, "foreign_read_then_clear_fetch");
  if(foreignRead) {
    volatile u32 decoy = pif.readInt(0);
    (void)decoy;
  }

  cpu.scc.nmiPending = 1;
  if(!cpu.instruction()) return 6;
  u64 firstPc = cpu.ipu.pc;
  u64 firstErrorEpc = cpu.scc.epcError;
  u32 firstPending = cpu.scc.nmiPending;

  if(strcmp(mode, "transfer_only")) {
    if(!strcmp(mode, "clear_fetch") || !strcmp(mode, "clear_busy_equal") ||
       !strcmp(mode, "clear_lockout") || !strcmp(mode, "foreign_read_then_clear_fetch")) {
      cpu.scc.nmiPending = 0;
    }
    if(!strcmp(mode, "clear_busy_equal")) {
      si.io.ioBusy = 1;
      si.io.busLatch = fw0;
    }
    if(!strcmp(mode, "clear_lockout")) {
      pif.io.romLockout = 1;
    }
    if(!cpu.instruction()) return 7;
  }

  if(firstPc != rootPc) return 8;

  auto ramHash = nall::Hash::SHA256(std::span<const u8>{rdram.ram.data, rdram.ram.size}).digest();
  auto pifRamHash = nall::Hash::SHA256(std::span<const u8>{pif.ram.data, pif.ram.size}).digest();
  auto pifRomHash = nall::Hash::SHA256(std::span<const u8>{pif.rom.data, pif.rom.size}).digest();

  std::printf("{\"mode\":\"%s\",\"firmware_word0\":%u,\"first_pc\":%llu,\"first_errorepc\":%llu,\"first_pending\":%u,",
    mode,fw0,(unsigned long long)firstPc,(unsigned long long)firstErrorEpc,firstPending);
  std::printf("\"machine\":{\"pc\":%llu,\"errorepc\":%llu,\"epc\":%llu,\"pending\":%u,\"bev\":%u,\"erl\":%u,\"sr\":%u,",
    (unsigned long long)cpu.ipu.pc,(unsigned long long)cpu.scc.epcError,(unsigned long long)cpu.scc.epc,
    (u32)cpu.scc.nmiPending,(u32)cpu.scc.status.vectorLocation,(u32)cpu.scc.status.errorLevel,(u32)cpu.scc.status.softReset);
  std::printf("\"si_io_busy\":%u,\"si_bus_latch\":%u,\"pif_lockout\":%u,\"count\":%llu,",
    (u32)si.io.ioBusy,si.io.busLatch,(u32)pif.io.romLockout,(unsigned long long)cpu.effectiveCount());
  std::printf("\"ram_sha256\":\"%s\",\"pif_ram_sha256\":\"%s\",\"pif_rom_sha256\":\"%s\"},",
    ramHash.data(),pifRamHash.data(),pifRomHash.data());
  std::printf("\"backing_reads\":%llu,\"unattributed_backing_reads\":%llu,\"fetches\":[",
    (unsigned long long)plaidBackingReads,(unsigned long long)plaidUnattributedBackingReads);
  for(size_t i=0;i<plaidEvents.size();i++) {
    auto& event=plaidEvents[i];
    std::printf("%s{\"id\":%llu,\"vaddr\":%llu,\"translated\":%u,\"physical\":%u,\"cached\":%s,\"returned\":%u,\"ended\":%s,\"witness\":",
      i?",":"",(unsigned long long)event.id,(unsigned long long)event.vaddr,event.translated,event.physical,
      event.cached?"true":"false",event.returned,event.ended?"true":"false");
    if(event.witness.present) std::printf("{\"kind\":\"pif_rom\",\"offset\":%u,\"word\":%u}",event.witness.offset,event.witness.word);
    else std::printf("null");
    std::printf("}");
  }
  std::printf("]}\n");
  std::fflush(stdout);
  ares::Nintendo64::system.unload();
  return 0;
}
