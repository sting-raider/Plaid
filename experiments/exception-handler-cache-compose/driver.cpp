/* SPDX-License-Identifier: ISC
 * Plaid research fixture: compose exception-root selection with I-cache residency.
 * Pinned ares is built separately by spikes/003-ares-oracle/run.py.
 */
#include <n64/n64.hpp>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <vector>
using namespace ares;
using namespace ares::Nintendo64;

static constexpr u64 VECTOR = 0xffffffff80000180ull;
static constexpr u32 VECTOR_PA = 0x00000180u;
static constexpr u32 HANDLER_A = 0x24100011u;  // ADDIU s0,zero,0x11
static constexpr u32 HANDLER_B = 0x24100022u;  // ADDIU s0,zero,0x22
static constexpr u32 SYSCALL = 0x0000000cu;
static constexpr u32 STORE_T1_T0 = 0xad090000u; // SW t1,0(t0)
static constexpr u32 HIT_INVALIDATE_T0 = 0xbd100000u; // CACHE 0x10,0(t0)

struct FillEvent {
  u32 slot;
  u32 physical;
  u32 index;
  u32 words[8];
};
static std::vector<FillEvent> fillEvents;

static auto fill_observer(u32 slot, u32 physical, u32 index, const u32* words) -> void {
  FillEvent event{slot, physical, index, {}};
  for(u32 i = 0; i < 8; i++) event.words[i] = words[i];
  fillEvents.push_back(event);
}

struct WriteEvent {
  u32 address;
  u32 size;
  u32 device;
  u64 value;
};
static std::vector<WriteEvent> writeEvents;

static auto scalar_observer(bool write, u32 address, u32 size, u32 device, u64 value) -> void {
  if(write && address == VECTOR_PA) writeEvents.push_back({address, size, device, value});
}

struct HandlerFetch {
  u64 pc;
  u32 word;
  u32 physical;
  bool cached;
  u32 tag;
  u32 resident;
  u64 fill_count;
};

struct Headless : ares::Platform {
  std::shared_ptr<vfs::directory> systemPak = std::make_shared<vfs::directory>();
  std::shared_ptr<vfs::directory> cartPak = std::make_shared<vfs::directory>();
  std::vector<HandlerFetch> handlerFetches;

  auto pak(Node::Object node) -> std::shared_ptr<vfs::directory> override {
    return node->name() == "Nintendo 64 Cartridge" ? cartPak : systemPak;
  }

  auto log(Node::Debugger::Tracer::Tracer node, string_view) -> void override {
    if(node != cpu.debugger.tracer.instruction || cpu.ipu.pc != VECTOR) return;
    auto& line = cpu.icache.line(cpu.ipu.pc);
    handlerFetches.push_back({
      cpu.ipu.pc,
      cpu.disassembler.fetchedWord(),
      plaidFetchAccess.physical,
      plaidFetchAccess.cached,
      line.tagKey,
      line.words[VECTOR_PA >> 2 & 7],
      fillEvents.size(),
    });
  }
};

struct Phase {
  const char* name;
  u64 s0;
  u64 pc;
  u64 count;
  u64 hits;
  u64 misses;
  u32 backing;
  u32 tag;
  u32 resident;
  bool valid;
};

static auto put(u32 address, u32 word) -> void {
  rdram.ram.write<Word>(address, word, RBusDevice::ARES_DEBUGGER);
}

static auto step() -> void {
  if(cpu.instruction()) cpu.synchronize();
}

int main(int argc, char** argv) {
  if(argc != 2 || (std::strcmp(argv[1], "plain") && std::strcmp(argv[1], "traced"))) return 2;
  const bool traced = !std::strcmp(argv[1], "traced");

  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid exception handler cache compose");
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
  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.status.privilegeMode = 0;
  cpu.scc.status.vectorLocation = 0;
  cpu.scc.status.reverseEndian = 0;
  cpu.context.setMode();

  // All fixture setup happens before observers are enabled. The two later writes
  // to VECTOR_PA are actual guest SW operations through the uncached KSEG1 alias.
  put(VECTOR_PA, HANDLER_A);
  put(0x00000000u, SYSCALL);
  put(0x00000040u, STORE_T1_T0);
  put(0x00000080u, HIT_INVALIDATE_T0);

  plaidCacheFillObserver = traced ? fill_observer : nullptr;
  plaidRdramScalarObserver = traced ? scalar_observer : nullptr;
  cpu.debugger.tracer.instruction->setDepth(0);
  cpu.debugger.tracer.instruction->setMask(false);
  cpu.debugger.tracer.instruction->setEnabled(traced);

  std::vector<Phase> phases;
  auto record = [&](const char* name) {
    auto& line = cpu.icache.line(VECTOR);
    phases.push_back({
      name,
      cpu.ipu.r[16].u64,
      cpu.ipu.pc,
      cpu.effectiveCount(),
      (u64)cpu.profile.icacheHits,
      (u64)cpu.profile.icacheMisses,
      (u32)rdram.ram.read<Word>(VECTOR_PA, RBusDevice::ARES_DEBUGGER),
      line.tagKey,
      line.words[VECTOR_PA >> 2 & 7],
      line.valid(),
    });
  };

  auto trigger = [&](const char* name) {
    cpu.scc.status.errorLevel = 0;
    cpu.scc.status.exceptionLevel = 0;
    cpu.scc.status.privilegeMode = 0;
    cpu.scc.status.vectorLocation = 0;
    cpu.scc.cause.exceptionCode = 0;
    cpu.context.setMode();
    cpu.ipu.r[16].u64 = 0;
    cpu.pipeline.setPc(0xffffffffa0000000ull);
    step();
    if(cpu.ipu.pc != VECTOR || cpu.scc.cause.exceptionCode != 8 || !cpu.scc.status.exceptionLevel) std::abort();
    step();
    record(name);
  };

  auto guest_store = [&](u32 value) {
    cpu.scc.cause.exceptionCode = 0;
    cpu.ipu.r[8].u64 = 0xffffffffa0000180ull;
    cpu.ipu.r[9].u64 = value;
    cpu.pipeline.setPc(0xffffffffa0000040ull);
    step();
    if(cpu.scc.cause.exceptionCode != 0) std::abort();
    if((u32)rdram.ram.read<Word>(VECTOR_PA, RBusDevice::ARES_DEBUGGER) != value) std::abort();
  };

  auto invalidate = [&] {
    cpu.scc.cause.exceptionCode = 0;
    cpu.ipu.r[8].u64 = VECTOR;
    cpu.pipeline.setPc(0xffffffffa0000080ull);
    step();
    if(cpu.scc.cause.exceptionCode != 0) std::abort();
    if(cpu.icache.line(VECTOR).valid()) std::abort();
  };

  // Cold root fetch: establishes resident generation A.
  trigger("cold_a");
  if(cpu.ipu.r[16].u64 != 0x11) return 10;

  // Changed backing generation through KSEG1. No CACHE operation follows.
  guest_store(HANDLER_B);
  trigger("stale_after_changed_write");
  if(cpu.ipu.r[16].u64 != 0x11) return 11;

  // Explicit invalidation ends the stale resident lifetime and forces B to fill.
  invalidate();
  trigger("refill_b");
  if(cpu.ipu.r[16].u64 != 0x22) return 12;

  // A successful same-value backing write is still a fresh storage operation.
  guest_store(HANDLER_B);
  trigger("stale_after_same_value_write");
  if(cpu.ipu.r[16].u64 != 0x22) return 13;

  // Same bits, new resident fill generation after explicit invalidation.
  invalidate();
  trigger("refill_same_value_b");
  if(cpu.ipu.r[16].u64 != 0x22) return 14;

  std::printf("{\"mode\":\"%s\",\"phases\":[", traced ? "traced" : "plain");
  for(size_t i = 0; i < phases.size(); i++) {
    const auto& p = phases[i];
    std::printf("%s{\"name\":\"%s\",\"s0\":%llu,\"pc\":%llu,\"count\":%llu,\"hits\":%llu,\"misses\":%llu,\"backing\":%u,\"tag\":%u,\"resident\":%u,\"valid\":%s}",
      i ? "," : "", p.name,
      (unsigned long long)p.s0, (unsigned long long)p.pc, (unsigned long long)p.count,
      (unsigned long long)p.hits, (unsigned long long)p.misses,
      p.backing, p.tag, p.resident, p.valid ? "true" : "false");
  }
  std::printf("],\"handler_fetches\":[");
  for(size_t i = 0; i < frontend.handlerFetches.size(); i++) {
    const auto& f = frontend.handlerFetches[i];
    std::printf("%s{\"pc\":%llu,\"word\":%u,\"physical\":%u,\"cached\":%s,\"tag\":%u,\"resident\":%u,\"fill_count\":%llu}",
      i ? "," : "", (unsigned long long)f.pc, f.word, f.physical,
      f.cached ? "true" : "false", f.tag, f.resident, (unsigned long long)f.fill_count);
  }
  std::printf("],\"fills\":[");
  for(size_t i = 0; i < fillEvents.size(); i++) {
    const auto& f = fillEvents[i];
    std::printf("%s{\"id\":%llu,\"slot\":%u,\"physical\":%u,\"index\":%u,\"word0\":%u}",
      i ? "," : "", (unsigned long long)i + 1, f.slot, f.physical, f.index, f.words[0]);
  }
  std::printf("],\"writes\":[");
  for(size_t i = 0; i < writeEvents.size(); i++) {
    const auto& w = writeEvents[i];
    std::printf("%s{\"id\":%llu,\"address\":%u,\"size\":%u,\"device\":%u,\"value\":%llu}",
      i ? "," : "", (unsigned long long)i + 1, w.address, w.size, w.device,
      (unsigned long long)w.value);
  }
  std::printf("],\"final\":{\"pc\":%llu,\"s0\":%llu,\"count\":%llu,\"hits\":%llu,\"misses\":%llu,\"backing\":%u}}\n",
    (unsigned long long)cpu.ipu.pc, (unsigned long long)cpu.ipu.r[16].u64,
    (unsigned long long)cpu.effectiveCount(), (unsigned long long)cpu.profile.icacheHits,
    (unsigned long long)cpu.profile.icacheMisses,
    (u32)rdram.ram.read<Word>(VECTOR_PA, RBusDevice::ARES_DEBUGGER));

  ares::Nintendo64::system.unload();
  return 0;
}
