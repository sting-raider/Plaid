/* SPDX-License-Identifier: ISC
 * Decoded VR4300 COP1 load->FPR->store provenance fixture for pinned ares.
 */
#define main plaid_base_ares_oracle_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <cstdlib>
#include <cstring>
#include <vector>

static constexpr u32 SourcePhys = 0x4000;
static constexpr u32 DestinationPhys = 0x5000;
static constexpr u32 CodePhys = 0x6000;
static constexpr u64 SourceUncached = 0xffffffffa0004000ull;
static constexpr u64 DestinationUncached = 0xffffffffa0005000ull;
static constexpr u64 CodeCached = 0xffffffff80006000ull;
static constexpr u32 SourceWord = 0x10213243u;
static constexpr u64 SourceDual = 0x1021324354657687ull;
static constexpr u64 InitialF0 = 0x1021324355667788ull;
static constexpr u64 InitialF1 = 0x99aabbcc10213243ull;

struct ScalarEvent {
  u64 ordinal;
  u32 phase, address, bytes, device;
  bool write;
  u64 value;
};
static std::vector<ScalarEvent> events;
static u64 nextOrdinal = 0;
static u32 phase = 0;

static void scalar_observer(bool write, u32 address, u32 bytes, u32 device, u64 value) {
  events.push_back({++nextOrdinal, phase, address, bytes, device, write, value});
}

static u32 mem_opcode(const char* op) {
  if(!std::strcmp(op, "LWC1")) return 0x31;
  if(!std::strcmp(op, "LDC1")) return 0x35;
  if(!std::strcmp(op, "SWC1")) return 0x39;
  if(!std::strcmp(op, "SDC1")) return 0x3d;
  std::abort();
}

static u32 encode_mem(const char* op, u32 base, u32 ft) {
  return mem_opcode(op) << 26 | (base & 31) << 21 | (ft & 31) << 16;
}

static u32 encode_move(const char* loadOp, u32 rt, u32 ft) {
  u32 rs = !std::strcmp(loadOp, "LWC1") ? 4 : 5;  // MTC1 / DMTC1
  return 0x11u << 26 | rs << 21 | (rt & 31) << 16 | (ft & 31) << 11;
}

static void put_word(u32 address, u32 value) {
  auto saved = plaidRdramScalarObserver;
  plaidRdramScalarObserver = nullptr;
  rdram.ram.write<Word>(address, value, RBusDevice::ARES_DEBUGGER);
  plaidRdramScalarObserver = saved;
}

static std::vector<u8> raw_bytes(u32 address, u32 count) {
  auto saved = plaidRdramScalarObserver;
  plaidRdramScalarObserver = nullptr;
  std::vector<u8> out;
  for(u32 i = 0; i < count; i++) out.push_back(rdram.ram.read<Byte>(address + i, RBusDevice::ARES_DEBUGGER));
  plaidRdramScalarObserver = saved;
  return out;
}

static bool step() {
  if(cpu.instruction()) cpu.synchronize();
  return cpu.scc.cause.exceptionCode == 0;
}

static void print_bytes(const char* key, const std::vector<u8>& values) {
  std::printf("\"%s\":[", key);
  for(size_t i = 0; i < values.size(); i++) std::printf("%s%u", i ? "," : "", (u32)values[i]);
  std::printf("]");
}

int main(int argc, char** argv) {
  if(argc != 9) return 2;
  bool traced = !std::strcmp(argv[1], "traced");
  if(!traced && std::strcmp(argv[1], "plain")) return 2;
  const char* loadOp = argv[2];
  u32 loadFr = std::strtoul(argv[3], nullptr, 0);
  u32 loadFt = std::strtoul(argv[4], nullptr, 0);
  const char* storeOp = argv[5];
  u32 storeFr = std::strtoul(argv[6], nullptr, 0);
  u32 storeFt = std::strtoul(argv[7], nullptr, 0);
  const char* action = argv[8];
  if((std::strcmp(loadOp,"LWC1") && std::strcmp(loadOp,"LDC1")) ||
     (std::strcmp(storeOp,"SWC1") && std::strcmp(storeOp,"SDC1")) ||
     loadFr > 1 || storeFr > 1 || loadFt > 1 || storeFt > 1) return 2;
  bool success = !std::strcmp(action,"success") || !std::strcmp(action,"overwrite_equal");
  bool overwrite = !std::strcmp(action,"overwrite_equal");
  bool cu1off = !std::strcmp(action,"cu1off");
  bool misalign = !std::strcmp(action,"misalign");
  bool tlbmiss = !std::strcmp(action,"tlbmiss");
  if(!success && !cu1off && !misalign && !tlbmiss) return 2;

  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid COP1 load/store lineage fixture");
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
  plaidRdramScalarObserver = nullptr;
  cpu.dcache.power(false);
  cpu.icache.power(false);
  for(auto& reg : cpu.ipu.r) reg.u64 = 0;
  for(auto& reg : cpu.fpu.r) reg.u64 = 0x7000000000000000ull + (&reg - &cpu.fpu.r[0]);
  cpu.fpu.r[0].u64 = InitialF0;
  cpu.fpu.r[1].u64 = InitialF1;
  cpu.scc.status.errorLevel = 0;
  cpu.scc.status.exceptionLevel = 0;
  cpu.scc.status.enable.coprocessor1 = !cu1off;
  cpu.scc.status.floatingPointMode = loadFr;
  cpu.scc.cause.exceptionCode = 0;
  cpu.scc.cause.coprocessorError = 0;
  cpu.scc.cause.branchDelay = 0;
  cpu.scc.badVirtualAddress = 0;
  cpu.context.setMode();
  cpu.context.endian = CPU::Context::Big;

  put_word(SourcePhys + 0, (u32)(SourceDual >> 32));
  put_word(SourcePhys + 4, (u32)SourceDual);
  for(u32 i = 0; i < 8; i++) {
    auto saved = plaidRdramScalarObserver;
    plaidRdramScalarObserver = nullptr;
    rdram.ram.write<Byte>(DestinationPhys + i, 0xee, RBusDevice::ARES_DEBUGGER);
    plaidRdramScalarObserver = saved;
  }

  put_word(CodePhys + 0, encode_mem(loadOp, 16, loadFt));
  u32 storeOffset = 4;
  if(overwrite) {
    put_word(CodePhys + 4, encode_move(loadOp, 8, loadFt));
    storeOffset = 8;
  }
  put_word(CodePhys + storeOffset, encode_mem(storeOp, 17, storeFt));
  cpu.ipu.r[16].u64 = tlbmiss ? 0x4000ull : SourceUncached + (misalign ? 1 : 0);
  cpu.ipu.r[17].u64 = DestinationUncached;
  cpu.ipu.r[8].u64 = !std::strcmp(loadOp, "LWC1") ? SourceWord : SourceDual;
  cpu.pipeline.setPc(CodeCached);

  u64 beforeF0 = cpu.fpu.r[0].u64, beforeF1 = cpu.fpu.r[1].u64;
  events.clear(); nextOrdinal = 0;
  plaidRdramScalarObserver = traced ? scalar_observer : nullptr;
  phase = 1;
  bool loadOk = step();
  u64 afterLoadF0 = cpu.fpu.r[0].u64, afterLoadF1 = cpu.fpu.r[1].u64;
  u64 afterOverwriteF0 = afterLoadF0, afterOverwriteF1 = afterLoadF1;

  if(success && !loadOk) return 5;
  if(success && overwrite) {
    phase = 2;
    cpu.scc.status.floatingPointMode = loadFr;
    if(!step()) return 6;
    afterOverwriteF0 = cpu.fpu.r[0].u64;
    afterOverwriteF1 = cpu.fpu.r[1].u64;
  }
  if(success) {
    phase = 3;
    cpu.scc.status.floatingPointMode = storeFr;
    if(!step()) return 7;
  }
  plaidRdramScalarObserver = nullptr;

  auto sourceBytes = raw_bytes(SourcePhys, 8);
  auto destinationBytes = raw_bytes(DestinationPhys, 8);
  std::printf("{\"mode\":\"%s\",\"load_op\":\"%s\",\"load_fr\":%u,\"load_ft\":%u,\"store_op\":\"%s\",\"store_fr\":%u,\"store_ft\":%u,\"action\":\"%s\",",
    traced ? "traced" : "plain", loadOp, loadFr, loadFt, storeOp, storeFr, storeFt, action);
  std::printf("\"before_f0\":%llu,\"before_f1\":%llu,\"after_load_f0\":%llu,\"after_load_f1\":%llu,\"after_overwrite_f0\":%llu,\"after_overwrite_f1\":%llu,\"final_f0\":%llu,\"final_f1\":%llu,",
    (unsigned long long)beforeF0, (unsigned long long)beforeF1,
    (unsigned long long)afterLoadF0, (unsigned long long)afterLoadF1,
    (unsigned long long)afterOverwriteF0, (unsigned long long)afterOverwriteF1,
    (unsigned long long)cpu.fpu.r[0].u64, (unsigned long long)cpu.fpu.r[1].u64);
  std::printf("\"exception\":%u,\"coprocessor_error\":%u,\"badva\":%llu,",
    (u32)cpu.scc.cause.exceptionCode, (u32)cpu.scc.cause.coprocessorError,
    (unsigned long long)cpu.scc.badVirtualAddress);
  print_bytes("source", sourceBytes); std::printf(","); print_bytes("destination", destinationBytes);
  std::printf(",\"events\":[");
  for(size_t i = 0; i < events.size(); i++) {
    const auto& e = events[i];
    std::printf("%s{\"ordinal\":%llu,\"phase\":%u,\"write\":%s,\"address\":%u,\"bytes\":%u,\"device\":%u,\"uncached_cpu\":%s,\"value\":%llu}",
      i ? "," : "", (unsigned long long)e.ordinal, e.phase, e.write ? "true" : "false",
      e.address, e.bytes, e.device,
      e.device == (u32)RBusDevice::VR4300_UNCACHED ? "true" : "false",
      (unsigned long long)e.value);
  }
  std::printf("]}\n");
  ares::Nintendo64::system.unload();
  return 0;
}
