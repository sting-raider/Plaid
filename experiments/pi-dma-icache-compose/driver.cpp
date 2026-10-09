/* SPDX-License-Identifier: ISC
 * Exact-pinned ares fixture composing PI byte effects, queue completion, and
 * instruction-cache resident visibility.
 */
#ifndef PLAID_PI_CACHE_COMPOSE_SENSOR
#define PLAID_PI_CACHE_COMPOSE_SENSOR 1
#endif
#define main plaid_capability_fixture_main
#include "../../spikes/003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>

static constexpr u32 Target = 0x4000;
static constexpr u32 Helper = 0x3000;
static constexpr u64 TargetVa = 0xffffffff80004000ull;
static constexpr u64 HelperVa = 0xffffffff80003000ull;
static constexpr u32 OldInstruction = 0x34080000;   // ORI t0,zero,0
static constexpr u32 FirstInstruction = 0x34081111; // ORI t0,zero,0x1111
static constexpr u32 SecondInstruction = 0x34083333;// ORI t0,zero,0x3333

#if PLAID_PI_CACHE_COMPOSE_SENSOR
static bool composeEnabled = false;
static bool composePiCopying = false;
static u64 composeSeq = 0;
static u32 composeStage = 0;
static u32 composeTransfer = 0;
static u32 composePending = 0;
static std::vector<std::string> composeEvents;

template<typename... Args>
static void compose_record(const char* kind, const char* format, Args... args) {
  if(!composeEnabled) return;
  char payload[4096], prefix[192];
  int length = std::snprintf(payload, sizeof(payload), format, args...);
  if(length < 0 || (size_t)length >= sizeof(payload)) std::abort();
  std::snprintf(prefix, sizeof(prefix),
      "{\"seq\":%llu,\"stage\":%u,\"kind\":\"%s\",",
      (unsigned long long)++composeSeq, composeStage, kind);
  composeEvents.emplace_back(std::string(prefix) + payload + "}");
}

static std::string compose_words(const u32* words) {
  std::string result = "[";
  for(u32 i=0;i<8;i++) result += (i ? "," : "") + std::to_string(words[i]);
  return result + "]";
}

static void compose_pi(u32 event, u32 dram, u32 pbus, u32 length, u32 lane, u32 value) {
  if(event == 1) {
    ++composeTransfer;
    composePending = composeTransfer;
    composePiCopying = true;
  }
  if(composeEnabled && (event == 1 || event == 7 || event == 8)) {
    compose_record(event == 1 ? "pi_copy_begin" : event == 7 ? "pi_copy_return" : "pi_completion",
        "\"event\":%u,\"transfer\":%u,\"dram\":%u,\"pbus\":%u,\"length\":%u,\"lane\":%u,\"value\":%u",
        event, event == 8 ? composePending : composeTransfer, dram, pbus, length, lane, value);
  }
  if(event == 7) composePiCopying = false;
  if(event == 8) composePending = 0;
}

struct ComposeRom : PIDevice {
  auto piAddress(u32 address, PIDeviceTiming timing) -> bool override {
    return cartridge.romDevice.piAddress(address, timing);
  }
  auto piReadHalf(PIDeviceTiming timing) -> maybe<u16> override {
    u32 offset = cartridge.romDevice.piViewOffset;
    auto value = cartridge.romDevice.piReadHalf(timing);
    if(value && composePiCopying) {
      compose_record("pi_source_half", "\"transfer\":%u,\"offset\":%u,\"value\":%u",
          composeTransfer, offset, (u32)*value);
    }
    return value;
  }
  auto piWriteHalf(u16 value, PIDeviceTiming timing) -> void override {
    cartridge.romDevice.piWriteHalf(value, timing);
  }
};

static void compose_scalar(bool write, u32 address, u32 bytes, u32 device, u64 value) {
  if(write && device == (u32)RBusDevice::PI_DMA && address >= Target && address < Target + 32) {
    compose_record("pi_rdram_write",
        "\"transfer\":%u,\"address\":%u,\"bytes\":%u,\"device\":%u,\"value\":%llu",
        composeTransfer, address, bytes, device, (unsigned long long)value);
  }
}

static void compose_burst(bool write, u32 address, u32 bytes, u32 device, const u32* words) {
  if(!write && address == Target && bytes == 32 && device == (u32)RBusDevice::VR4300_ICACHE) {
    auto payload = compose_words(words);
    compose_record("icache_backing_read",
        "\"address\":%u,\"bytes\":%u,\"device\":%u,\"words\":%s",
        address, bytes, device, payload.c_str());
  }
}

static void compose_fill(u32 slot, u32 physical, u32 index, const u32* words) {
  if((physical & ~31u) == Target) {
    auto payload = compose_words(words);
    compose_record("icache_fill",
        "\"slot\":%u,\"physical\":%u,\"index\":%u,\"words\":%s",
        slot, physical, index, payload.c_str());
  }
}

static void compose_fetch(bool begin, u64 vaddr, u32 translated, u32 bus, bool cached, u32 value) {
  if((translated & ~31u) == Target && cached) {
    compose_record(begin ? "fetch_begin" : "fetch_end",
        "\"vaddr\":%llu,\"translated\":%u,\"bus\":%u,\"cached\":true,\"value\":%u",
        (unsigned long long)vaddr, translated, bus, value);
  }
}
#endif

struct Checkpoint {
  u32 stage;
  u32 t0;
  u32 backing;
  u32 resident;
  u32 residentHit;
  u32 busy;
  u32 interrupt;
};

static u32 backing_word() {
  return rdram.ram.read<Word>(Target, RBusDevice::ARES_DEBUGGER);
}

static bool execute_one(u64 pc) {
  cpu.pipeline.setPc(pc);
  if(cpu.instruction()) cpu.synchronize();
  return cpu.scc.cause.exceptionCode == 0;
}

int main(int argc, char** argv) {
  if(argc != 2 || (strcmp(argv[1], "plain") && strcmp(argv[1], "traced"))) return 2;
  bool traced = !strcmp(argv[1], "traced");

  Headless frontend;
  platform = &frontend;
  std::vector<u8> rom(16384);
  auto putRom = [&](u32 offset, u32 word) {
    for(u32 i=0;i<4;i++) rom[offset+i] = word >> (24 - i*8);
  };
  putRom(0, 0x80371240);
  putRom(0x1000, FirstInstruction);
  putRom(0x3000, SecondInstruction);
  frontend.cartPak->setAttribute("title", "Plaid PI DMA I-cache composition fixture");
  frontend.cartPak->setAttribute("region", "NTSC");
  frontend.cartPak->setAttribute("cic", "CIC-NUS-6102");
  frontend.cartPak->append("program.rom", std::span<const u8>{rom.data(), rom.size()});

  Node::System root;
  if(!load(root, "[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak", "true");
  option("Deterministic Entropy", "true");
  option("Recompiler", "false");
  cartridgeSlot.port->allocate();
  cartridgeSlot.port->connect();
  ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled || rdram.ram.size != 8388608) return 4;

  std::vector<u8> hidden(rdram.ram.size / 2);
  rdram.hidden.data = hidden.data();
  rdram.mapIdentity = 1;
  std::memset(rdram.ram.data, 0, rdram.ram.size);
  for(auto& reg : cpu.ipu.r) reg.u64 = 0;
  cpu.scc.status.errorLevel = cpu.scc.status.exceptionLevel = 0;
  cpu.context.setMode();
  cpu.context.endian = CPU::Context::Endian::Big;
  cpu.icache.power(false);
  cpu.dcache.power(false);

  rdram.ram.write<Word>(Target, OldInstruction, RBusDevice::ARES_DEBUGGER);
  rdram.ram.write<Word>(Helper, 0xbe100000, RBusDevice::ARES_DEBUGGER); // CACHE 0x10,0(s0)
  cpu.ipu.r[16].u64 = TargetVa;

#if PLAID_PI_CACHE_COMPOSE_SENSOR
  ComposeRom wrapper;
  pi.detach(cartridge.romDevice);
  pi.attach(wrapper, 0);
  composeEnabled = traced;
  plaidPiDmaObserver = traced ? compose_pi : nullptr;
  plaidRdramScalarObserver = traced ? compose_scalar : nullptr;
  plaidRdramBurstObserver = traced ? compose_burst : nullptr;
  plaidCacheFillObserver = traced ? compose_fill : nullptr;
  plaidCpuFetchObserver = traced ? compose_fetch : nullptr;
#endif

  std::vector<Checkpoint> checkpoints;
  auto checkpoint = [&](u32 stage) {
#if PLAID_PI_CACHE_COMPOSE_SENSOR
    bool was = composeEnabled;
    composeEnabled = false;
#endif
    auto& line = cpu.icache.line(TargetVa);
    bool hit = line.hit(Target);
    checkpoints.push_back({stage, cpu.ipu.r[8].u32, backing_word(), hit ? line.read(Target) : 0,
        (u32)hit, (u32)pi.io.dmaBusy, (u32)pi.io.interrupt});
#if PLAID_PI_CACHE_COMPOSE_SENSOR
    composeEnabled = was;
#endif
  };
  auto stage = [&](u32 value) {
#if PLAID_PI_CACHE_COMPOSE_SENSOR
    composeStage = value;
#else
    (void)value;
#endif
  };
  auto requestWrite = [&](u32 destination, u32 source, u32 length) {
    pi.ioWrite(0x00, destination);
    pi.ioWrite(0x04, source);
    pi.ioWrite(0x0c, length - 1);
  };
  auto dispatchNext = [&]() {
    s32 delay = queue.timeToNextEvent();
    if(delay < 0 || delay > 100000000) std::abort();
    cpu.step((u32)delay);
    cpu.synchronize();
  };
  auto invalidateTarget = [&]() {
    cpu.ipu.r[16].u64 = TargetVa;
    if(!execute_one(HelperVa)) std::abort();
  };

  // Establish an old resident instruction before either PI copy.
  stage(1);
  cpu.ipu.r[8].u64 = 0xdeadbeef;
  if(!execute_one(TargetVa) || cpu.ipu.r[8].u32 != 0) return 5;
  checkpoint(1);

  // Normal request: synchronous copy first, then a real queued completion.
  stage(2);
  requestWrite(Target, 0x10001000, 32);
  if(backing_word() != FirstInstruction || !pi.io.dmaBusy) return 6;
  checkpoint(2);

  stage(3);
  dispatchNext();
  if(pi.io.dmaBusy || !pi.io.interrupt) return 7;
  checkpoint(3);

  // Completion does not replace the old valid resident line.
  stage(4);
  cpu.ipu.r[8].u64 = 0xdeadbeef;
  if(!execute_one(TargetVa) || cpu.ipu.r[8].u32 != 0) return 8;
  checkpoint(4);

  // Invalidate/refill is the visibility transition to the first PI writer.
  stage(5);
  invalidateTarget();
  stage(6);
  cpu.ipu.r[8].u64 = 0;
  if(!execute_one(TargetVa) || cpu.ipu.r[8].u32 != 0x1111) return 9;
  checkpoint(6);

  // Clear only the completed PI interrupt, then saturate every queue slot.
  pi.ioWrite(0x10, 2);
  if(pi.io.interrupt || pi.io.dmaBusy) return 10;
  u32 filled = 0;
  for(u32 i=0;i<512;i++) if(queue.insert(Queue::GDB_Poll, 100000)) filled++;
  if(filled != 512) return 11;

  // Full queue: CPU::queueInsert fails, but dmaWrite still copies synchronously.
  stage(8);
  requestWrite(Target, 0x10003000, 32);
  if(backing_word() != SecondInstruction || !pi.io.dmaBusy || pi.io.interrupt) return 12;
  checkpoint(8);

  // No completion exists, and the old resident line still executes.
  stage(9);
  cpu.ipu.r[8].u64 = 0;
  if(!execute_one(TargetVa) || cpu.ipu.r[8].u32 != 0x1111) return 13;
  checkpoint(9);

  // Yet the queue-less PI byte effect becomes executable after refill.
  stage(10);
  invalidateTarget();
  stage(11);
  cpu.ipu.r[8].u64 = 0;
  if(!execute_one(TargetVa) || cpu.ipu.r[8].u32 != 0x3333) return 14;
  checkpoint(11);

#if PLAID_PI_CACHE_COMPOSE_SENSOR
  composeEnabled = false;
#endif
  auto ramHash = nall::Hash::SHA256(std::span<const u8>{rdram.ram.data, rdram.ram.size}).digest();
  std::printf("{\"checkpoints\":[");
  for(size_t i=0;i<checkpoints.size();i++) {
    auto& c = checkpoints[i];
    std::printf("%s{\"stage\":%u,\"t0\":%u,\"backing\":%u,\"resident\":%u,\"resident_hit\":%u,\"busy\":%u,\"interrupt\":%u}",
        i ? "," : "", c.stage, c.t0, c.backing, c.resident, c.residentHit, c.busy, c.interrupt);
  }
  std::printf("],\"events\":[");
#if PLAID_PI_CACHE_COMPOSE_SENSOR
  for(size_t i=0;i<composeEvents.size();i++) std::printf("%s%s", i ? "," : "", composeEvents[i].c_str());
#endif
  std::printf("],\"state\":{\"pc\":%llu,\"count\":%llu,\"exception\":%u,\"t0\":%u,\"backing\":%u,\"busy\":%u,\"interrupt\":%u,\"ram_sha256\":\"%s\"}}\n",
      (unsigned long long)cpu.ipu.pc, (unsigned long long)cpu.effectiveCount(),
      (u32)cpu.scc.cause.exceptionCode, cpu.ipu.r[8].u32, backing_word(),
      (u32)pi.io.dmaBusy, (u32)pi.io.interrupt, ramHash.data());

#if PLAID_PI_CACHE_COMPOSE_SENSOR
  plaidPiDmaObserver = nullptr;
  plaidRdramScalarObserver = nullptr;
  plaidRdramBurstObserver = nullptr;
  plaidCacheFillObserver = nullptr;
  plaidCpuFetchObserver = nullptr;
#endif
  ares::Nintendo64::system.unload();
  return 0;
}
