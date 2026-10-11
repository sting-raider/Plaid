/* SPDX-License-Identifier: ISC
 * Plaid research harness: actual VI coincidence -> MI.VI -> CPU interrupt root.
 * Exact pinned ares is built separately; no upstream source is patched.
 */
#include <n64/n64.hpp>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
using namespace ares;
using namespace ares::Nintendo64;

struct Headless : ares::Platform {
  std::shared_ptr<vfs::directory> systemPak = std::make_shared<vfs::directory>();
  std::shared_ptr<vfs::directory> cartPak = std::make_shared<vfs::directory>();
  auto pak(Node::Object node) -> std::shared_ptr<vfs::directory> override {
    return node->name() == "Nintendo 64 Cartridge" ? cartPak : systemPak;
  }
};

struct Snap {
  u32 vcounter;
  u32 coincidence;
  u32 miIntr;
  u32 miMask;
  u32 causeIp;
};

static auto snap() -> Snap {
  return {
    (u32)vi.io.vcounter,
    (u32)vi.io.coincidence,
    (u32)mi.readWord(8, cpu),
    (u32)mi.readWord(12, cpu),
    (u32)cpu.scc.cause.interruptPending,
  };
}

static auto put(u32 address, u32 word) -> void {
  rdram.ram.write<Word>(address, word, RBusDevice::ARES_DEBUGGER);
}

static auto fireViCoincidence() -> void {
  // One actual VI::main iteration: 0 -> 1, progressive coincidence 2 >> 1 == 1.
  vi.io.vcounter = 0;
  vi.io.field = 0;
  vi.clock = -1;
  vi.main();
}

int main(int argc, char** argv) {
  if(argc != 9) return 2;
  const char* name = argv[1];
  const char* mode = argv[2];
  int bev = std::atoi(argv[3]);
  int viMask = std::atoi(argv[4]);
  int cpuIm = std::atoi(argv[5]);
  int ie = std::atoi(argv[6]);
  int exl = std::atoi(argv[7]);
  int erl = std::atoi(argv[8]);
  if((bev & ~1) || (viMask & ~1) || (cpuIm & ~1) || (ie & ~1) || (exl & ~1) || (erl & ~1)) return 2;

  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid VI interrupt root fixture");
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

  std::vector<u8> hidden(rdram.ram.size / 2);
  rdram.hidden.data = hidden.data();
  rdram.mapIdentity = 1;
  for(auto& reg : cpu.ipu.r) reg.u64 = 0;
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;

  constexpr u64 startPc = 0xffffffffa0000000ull;
  constexpr u64 epcSentinel = 0x123456789abcdef0ull;
  constexpr u32 causeSentinel = 13;
  constexpr u32 addiuS0 = 0x24101234;
  put(0, addiuS0);
  put(4, 0);

  // Start from explicit RCP-source state rather than treating reset values as proof.
  mi.lower(MI::IRQ::SP);
  mi.lower(MI::IRQ::SI);
  mi.lower(MI::IRQ::AI);
  mi.lower(MI::IRQ::VI);
  mi.lower(MI::IRQ::PI);
  mi.lower(MI::IRQ::DP);

  // MI mask writes are clear/set pairs. VI clear/set = bits 6/7.
  mi.writeWord(12, viMask ? (1u << 7) : (1u << 6), cpu);

  cpu.scc.status.vectorLocation = bev;
  cpu.scc.status.interruptEnable = ie;
  cpu.scc.status.exceptionLevel = exl;
  cpu.scc.status.errorLevel = erl;
  cpu.scc.status.interruptMask = cpuIm ? (1u << CPU::Interrupt::RCP) : 0;
  cpu.scc.cause.interruptPending = 0;
  cpu.scc.cause.exceptionCode = causeSentinel;
  cpu.scc.cause.branchDelay = 1;
  cpu.scc.epc = epcSentinel;
  cpu.context.setMode();
  cpu.pipeline.setPc(startPc);
  mi.poll();

  // Program an active progressive VI whose next actual VI::main step hits V_INTR.
  vi.writeWord(0, 1, cpu);             // VI_CONTROL: active color depth
  vi.writeWord(12, 2, cpu);            // VI_V_INTR: coincidence halfline 2
  vi.writeWord(24, 3, cpu);            // VI_V_TOTAL: odd => progressive branch
  vi.writeWord(28, 2, cpu);            // VI_H_TOTAL: finite positive step
  vi.writeWord(40, 10u << 16, cpu);    // VI_V_VIDEO: avoid frame callback at vcounter=1

  Snap initial = snap();
  Snap afterTrigger = initial;
  Snap afterAck = initial;
  int triggerCount = 0;
  int ackCount = 0;
  u32 ackPayload = 0;
  const char* producer = "none";

  if(!std::strcmp(mode, "trigger")) {
    fireViCoincidence();
    triggerCount = 1;
    producer = "vi_coincidence";
    afterTrigger = snap();
  } else if(!std::strcmp(mode, "config_only")) {
    producer = "vi_config_only";
  } else if(!std::strcmp(mode, "trigger_ack0")) {
    fireViCoincidence();
    triggerCount = 1;
    producer = "vi_coincidence_then_ack";
    afterTrigger = snap();
    vi.writeWord(16, 0, cpu);
    ackCount = 1;
    afterAck = snap();
  } else if(!std::strcmp(mode, "trigger_ack_dead")) {
    fireViCoincidence();
    triggerCount = 1;
    producer = "vi_coincidence_then_ack";
    afterTrigger = snap();
    ackPayload = 0xdeadbeef;
    vi.writeWord(16, ackPayload, cpu);
    ackCount = 1;
    afterAck = snap();
  } else if(!std::strcmp(mode, "retrigger")) {
    fireViCoincidence();
    triggerCount = 1;
    afterTrigger = snap();
    vi.writeWord(16, 0, cpu);
    ackCount = 1;
    afterAck = snap();
    fireViCoincidence();
    triggerCount = 2;
    producer = "vi_coincidence_ack_retrigger";
  } else if(!std::strcmp(mode, "ack_empty")) {
    vi.writeWord(16, 0, cpu);
    ackCount = 1;
    producer = "ack_without_trigger";
    afterAck = snap();
  } else if(!std::strcmp(mode, "direct_mi_vi")) {
    // Causal decoy: bit-for-bit MI.VI/Cause state without the VI timing producer.
    mi.raise(MI::IRQ::VI);
    producer = "direct_mi_vi_decoy";
  } else if(!std::strcmp(mode, "ai_decoy")) {
    // Another RCP source reaches the same CPU IP2 gate but not the VI source bit.
    mi.writeWord(12, 1u << 5, cpu); // enable AI mask
    mi.raise(MI::IRQ::AI);
    producer = "ai_decoy";
  } else {
    return 5;
  }

  // Prevent incidental scheduler-driven VI work while testing the CPU gate. This
  // does not lower an already latched VI source; only VI_CURRENT does that.
  vi.writeWord(0, 0, cpu);
  Snap beforeCpu = snap();
  if(cpu.instruction()) cpu.synchronize();
  Snap afterCpu = snap();

  auto emitSnap = [](const char* key, const Snap& s) {
    std::printf("\"%s\":{\"vcounter\":%u,\"coincidence\":%u,\"mi_intr\":%u,\"mi_mask\":%u,\"cause_ip\":%u}",
      key, s.vcounter, s.coincidence, s.miIntr, s.miMask, s.causeIp);
  };

  std::printf("{\"name\":\"%s\",\"mode\":\"%s\",\"producer\":\"%s\",\"bev\":%d,\"vi_mask_enabled\":%d,\"cpu_im_enabled\":%d,\"ie\":%d,\"initial_exl\":%d,\"initial_erl\":%d,\"trigger_count\":%d,\"ack_count\":%d,\"ack_payload\":%u,",
    name, mode, producer, bev, viMask, cpuIm, ie, exl, erl, triggerCount, ackCount, ackPayload);
  emitSnap("initial", initial); std::printf(",");
  emitSnap("after_trigger", afterTrigger); std::printf(",");
  emitSnap("after_ack", afterAck); std::printf(",");
  emitSnap("before_cpu", beforeCpu); std::printf(",");
  emitSnap("after_cpu", afterCpu);
  std::printf(",\"pc\":%llu,\"s0\":%llu,\"cause\":%u,\"bd\":%u,\"epc\":%llu,\"final_exl\":%u,\"final_erl\":%u}\n",
    (unsigned long long)cpu.ipu.pc,
    (unsigned long long)cpu.ipu.r[16].u64,
    (u32)cpu.scc.cause.exceptionCode,
    (u32)cpu.scc.cause.branchDelay,
    (unsigned long long)cpu.scc.epc,
    (u32)cpu.scc.status.exceptionLevel,
    (u32)cpu.scc.status.errorLevel);

  ares::Nintendo64::system.unload();
  return 0;
}
