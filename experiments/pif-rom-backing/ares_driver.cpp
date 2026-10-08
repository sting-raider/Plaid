/* SPDX-License-Identifier: ISC
 * Plaid research probe: causal CPU-fetch -> PIF-ROM-backing provenance.
 * No firmware bytes are embedded other than a synthetic original fixture.
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

static auto syntheticFirmware() -> std::vector<u8> {
  std::vector<u8> firmware(0x7c0);
  auto put = [&](u32 offset, u32 word) {
    firmware[offset + 0] = word >> 24;
    firmware[offset + 1] = word >> 16;
    firmware[offset + 2] = word >> 8;
    firmware[offset + 3] = word;
  };
  for(u32 offset = 0; offset < firmware.size(); offset += 4) {
    put(offset, (0xa5000000u ^ (offset * 0x1021u) ^ (offset << 16)));
  }
  put(0, 0x3c1abfc0);  // valid LUI; useful equal-value fixture word
  put(4, 0x00000000);  // deliberate collision with lockout zero
  put(8, 0x3c1abfc0);  // deliberate duplicate defeats value->offset inference
  return firmware;
}

static auto readFirmware(const char* path) -> std::vector<u8> {
  if(!path) return syntheticFirmware();
  auto bytes = nall::file::read(path);
  if(bytes.size() != 0x7c0) return {};
  return std::vector<u8>(bytes.begin(), bytes.end());
}

static auto firmwareWord(const std::vector<u8>& firmware, u32 offset) -> u32 {
  return (u32)firmware[offset] << 24 | (u32)firmware[offset + 1] << 16 |
         (u32)firmware[offset + 2] << 8 | firmware[offset + 3];
}

static auto directFetch(u32 physical, bool cached) -> u32 {
  u64 vaddr = 0xffff'ffff'a000'0000ull | physical;
  auto result = cpu.fetch(CPU::PhysAccess{true, cached, physical, vaddr});
  if(!result) std::abort();
  return *result;
}

int main(int argc, char** argv) {
  if(argc != 2 && argc != 3) return 2;
  const char* mode = argv[1];
  auto firmware = readFirmware(argc == 3 ? argv[2] : nullptr);
  if(firmware.size() != 0x7c0) return 3;
  const u32 fw0 = firmwareWord(firmware, 0);

  Headless frontend;
  platform = &frontend;
  frontend.systemPak->append("pif.ntsc.rom", std::span<const u8>{firmware.data(), firmware.size()});
  frontend.cartPak->setAttribute("title", "Plaid PIF backing research fixture");
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

  u32 returned = 0;
  if(!strcmp(mode, "natural")) {
    auto access = cpu.devirtualize<Read, Word>(cpu.ipu.pc);
    if(!access) return 6;
    auto result = cpu.fetch(access);
    if(!result) return 6;
    returned = *result;
  } else if(!strcmp(mode, "mirror")) {
    returned = directFetch(0x1fc00800, false);
  } else if(!strcmp(mode, "high_mirror")) {
    returned = directFetch(0x1fcff800, false);
  } else if(!strcmp(mode, "busy_latch")) {
    si.io.ioBusy = 1;
    si.io.busLatch = fw0;
    returned = directFetch(0x1fc00000, false);
  } else if(!strcmp(mode, "lockout_zero")) {
    pif.io.romLockout = 1;
    returned = directFetch(0x1fc00004, false);
  } else if(!strcmp(mode, "pif_ram_same_value")) {
    pif.ram.write<Word>(0x7c0, fw0);
    returned = directFetch(0x1fc007c0, false);
  } else if(!strcmp(mode, "cached_pif")) {
    returned = directFetch(0x1fc00000, true);
  } else if(!strcmp(mode, "stale_decoy")) {
    volatile u32 decoy = pif.readInt(0);
    (void)decoy;
    si.io.ioBusy = 1;
    si.io.busLatch = fw0;
    returned = directFetch(0x1fc00000, false);
  } else if(!strcmp(mode, "nonfetch_rom")) {
    returned = pif.readInt(0);
  } else {
    return 7;
  }

  auto ramHash = nall::Hash::SHA256(std::span<const u8>{rdram.ram.data, rdram.ram.size}).digest();
  auto spHash = nall::Hash::SHA256(std::span<const u8>{rsp.dmem.data, rsp.dmem.size}).digest();
  auto pifRamHash = nall::Hash::SHA256(std::span<const u8>{pif.ram.data, pif.ram.size}).digest();
  std::printf("{\"mode\":\"%s\",\"returned\":%u,\"machine\":{", mode, returned);
  std::printf("\"pc\":%llu,\"regs\":[", (unsigned long long)cpu.ipu.pc);
  for(int n = 0; n < 32; n++) std::printf("%s%lld", n ? "," : "", (long long)(int64_t)cpu.ipu.r[n].u64);
  std::printf("],\"hi\":%lld,\"lo\":%lld,\"count\":%llu,\"exception\":%u,\"epc\":%llu,",
    (long long)(int64_t)cpu.ipu.hi.u64, (long long)(int64_t)cpu.ipu.lo.u64,
    (unsigned long long)cpu.effectiveCount(), (u32)cpu.scc.cause.exceptionCode,
    (unsigned long long)cpu.scc.epc);
  std::printf("\"pif_state\":%u,\"pif_lockout\":%u,\"si_io_busy\":%u,\"si_dma_busy\":%u,\"si_bus_latch\":%u,",
    (u32)pif.state, (u32)pif.io.romLockout, (u32)si.io.ioBusy, (u32)si.io.dmaBusy, si.io.busLatch);
  std::printf("\"ram_sha256\":\"%s\",\"sp_sha256\":\"%s\",\"pif_ram_sha256\":\"%s\"},",
    ramHash.data(), spHash.data(), pifRamHash.data());
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
