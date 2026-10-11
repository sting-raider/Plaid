/* SPDX-License-Identifier: ISC
 * Plaid research harness: SI/PIF producer -> MI.SI -> CPU interrupt root.
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
  u32 dmaBusy;
  u32 ioBusy;
  u32 siInterrupt;
  u32 miIntr;
  u32 miMask;
  u32 causeIp;
};

static auto snap() -> Snap {
  return {
    (u32)si.io.dmaBusy,
    (u32)si.io.ioBusy,
    (u32)si.io.interrupt,
    (u32)mi.readWord(8, cpu),
    (u32)mi.readWord(12, cpu),
    (u32)cpu.scc.cause.interruptPending,
  };
}

static auto put(u32 address, u32 word) -> void {
  rdram.ram.write<Word>(address, word, RBusDevice::ARES_DEBUGGER);
}

int main(int argc, char** argv) {
  if(argc != 9) return 2;
  const char* name = argv[1];
  const char* mode = argv[2];
  int bev = std::atoi(argv[3]);
  int miMask = std::atoi(argv[4]);
  int cpuIm = std::atoi(argv[5]);
  int ie = std::atoi(argv[6]);
  int exl = std::atoi(argv[7]);
  int erl = std::atoi(argv[8]);
  if((bev & ~1) || (miMask & ~1) || (cpuIm & ~1) || (ie & ~1) || (exl & ~1) || (erl & ~1)) return 2;

  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid SI interrupt root fixture");
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
  constexpr u32 addiuS0 = 0x24101234;  // ADDIU $s0,$zero,0x1234
  constexpr u32 pifRam = 0x1fc007c0;
  constexpr u32 dmaBuffer = 0x1000;    // deliberately disjoint from planted code

  put(0, addiuS0);
  put(4, 0);

  // Normalize every RCP source before enabling the SI mask. This avoids relying on
  // reset snapshots as evidence that a particular producer is inactive.
  mi.lower(MI::IRQ::SP);
  mi.lower(MI::IRQ::SI);
  mi.lower(MI::IRQ::AI);
  mi.lower(MI::IRQ::VI);
  mi.lower(MI::IRQ::PI);
  mi.lower(MI::IRQ::DP);
  si.io.interrupt = 0;
  si.io.dmaBusy = 0;
  si.io.ioBusy = 0;

  // MI_INTR_MASK writes use clear/set pairs; SI set is bit 3, clear is bit 2.
  mi.writeWord(12, miMask ? (1u << 3) : (1u << 2), cpu);

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

  Snap initial = snap();
  Snap afterRequest = initial;
  Snap afterComplete = initial;
  Snap afterAck = initial;
  int didRequest = 0;
  int didComplete = 0;
  int didAck = 0;
  const char* producer = "none";

  si.ioWrite(0, dmaBuffer);  // SI_DRAM_ADDRESS; never overwrite the CPU sentinel

  if(!std::strcmp(mode, "request_read")) {
    si.ioWrite(4, pifRam);
    didRequest = 1;
    producer = "dma_read_request_only";
    afterRequest = snap();
  } else if(!std::strcmp(mode, "complete_read")) {
    si.ioWrite(4, pifRam);
    didRequest = 1;
    afterRequest = snap();
    si.dmaRead();
    didComplete = 1;
    producer = "dma_read_completion";
    afterComplete = snap();
  } else if(!std::strcmp(mode, "complete_write")) {
    si.ioWrite(16, pifRam);
    didRequest = 1;
    afterRequest = snap();
    si.dmaWrite();
    didComplete = 1;
    producer = "dma_write_completion";
    afterComplete = snap();
  } else if(!std::strcmp(mode, "complete_ack")) {
    si.ioWrite(4, pifRam);
    didRequest = 1;
    afterRequest = snap();
    si.dmaRead();
    didComplete = 1;
    afterComplete = snap();
    si.ioWrite(24, 0);  // SI_STATUS acknowledgement
    didAck = 1;
    producer = "dma_read_completion_then_ack";
    afterAck = snap();
  } else if(!std::strcmp(mode, "double_complete")) {
    si.ioWrite(4, pifRam);
    didRequest = 1;
    afterRequest = snap();
    si.dmaRead();
    didComplete = 1;
    afterComplete = snap();
    si.ioWrite(24, 0);
    didAck = 1;
    afterAck = snap();
    si.ioWrite(16, pifRam);
    si.dmaWrite();
    producer = "dma_read_ack_dma_write_completion";
  } else if(!std::strcmp(mode, "ack_empty")) {
    si.ioWrite(24, 0);
    didAck = 1;
    producer = "ack_without_completion";
    afterAck = snap();
  } else if(!std::strcmp(mode, "bus_complete")) {
    // Distinct SI producer path: direct PIF bus write completion, not SI DMA.
    si.writeWord(pifRam, 0, cpu);
    didRequest = 1;
    afterRequest = snap();
    si.writeFinished();
    didComplete = 1;
    producer = "direct_pif_bus_write_completion";
    afterComplete = snap();
  } else {
    return 5;
  }

  Snap beforeCpu = snap();
  if(cpu.instruction()) cpu.synchronize();
  Snap afterCpu = snap();

  auto emitSnap = [](const char* key, const Snap& s) {
    std::printf("\"%s\":{\"dma_busy\":%u,\"io_busy\":%u,\"si_interrupt\":%u,\"mi_intr\":%u,\"mi_mask\":%u,\"cause_ip\":%u}",
      key, s.dmaBusy, s.ioBusy, s.siInterrupt, s.miIntr, s.miMask, s.causeIp);
  };

  std::printf("{\"name\":\"%s\",\"mode\":\"%s\",\"producer\":\"%s\",\"bev\":%d,\"mi_mask_enabled\":%d,\"cpu_im_enabled\":%d,\"ie\":%d,\"initial_exl\":%d,\"initial_erl\":%d,\"did_request\":%d,\"did_complete\":%d,\"did_ack\":%d,",
    name, mode, producer, bev, miMask, cpuIm, ie, exl, erl, didRequest, didComplete, didAck);
  emitSnap("initial", initial); std::printf(",");
  emitSnap("after_request", afterRequest); std::printf(",");
  emitSnap("after_complete", afterComplete); std::printf(",");
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
