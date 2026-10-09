/* SPDX-License-Identifier: ISC
 * Plaid research harness: VR4300 Count/Compare timer producer and interrupt-root composition.
 * The exact pinned ares implementation is built separately by spike 003's helper.
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

static auto put(u32 address, u32 word) -> void {
  rdram.ram.write<Word>(address, word, RBusDevice::ARES_DEBUGGER);
}

static auto pending7() -> u32 {
  return ((u32)cpu.scc.cause.interruptPending >> 7) & 1u;
}

static auto setGate(u32 bev, u32 ie, u32 exl, u32 erl, u32 im) -> void {
  cpu.scc.status.vectorLocation = bev;
  cpu.scc.status.interruptEnable = ie;
  cpu.scc.status.exceptionLevel = exl;
  cpu.scc.status.errorLevel = erl;
  cpu.scc.status.interruptMask = im;
  cpu.context.setMode();
}

static auto runOneInstruction() -> void {
  if(cpu.instruction()) cpu.synchronize();
}

int main(int argc, char** argv) {
  if(argc != 2) return 2;
  const char* name = argv[1];

  Headless frontend;
  platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid Count Compare fixture");
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
  constexpr u32 addiuS0 = 0x24101234; // ADDIU $s0,$zero,0x1234
  constexpr u32 mtc0T0Count = 0x40884800;   // MTC0 $t0,$9
  constexpr u32 mtc0T0Compare = 0x40885800; // MTC0 $t0,$11

  put(0, addiuS0);
  put(4, addiuS0);
  cpu.scc.cause.interruptPending = 0;
  cpu.scc.cause.exceptionCode = causeSentinel;
  cpu.scc.cause.branchDelay = 1;
  cpu.scc.epc = epcSentinel;
  cpu.pipeline.setPc(startPc);

  u32 bev = 0, ie = 0, exl = 0, erl = 0, im = 0;
  u32 pending_before_write = 0;
  u32 pending_after_write = 0;
  u32 pending_before_instruction = 0;
  u32 guest_write_executed = 0;
  u32 second_instruction_attempted = 0;

  auto setCountCompare = [&](u32 count, u32 compare) {
    cpu.setControlRegister(9, count);
    cpu.setControlRegister(11, compare);
  };

  if(!std::strcmp(name, "near_exact_bev0")) {
    bev=0; ie=1; im=0x80; setGate(bev,ie,0,0,im);
    setCountCompare(100,103); cpu.stepCount(6);
    pending_before_instruction = pending7(); runOneInstruction();
  } else if(!std::strcmp(name, "cross_bev1")) {
    bev=1; ie=1; im=0x80; setGate(bev,ie,0,0,im);
    setCountCompare(100,103); cpu.stepCount(8);
    pending_before_instruction = pending7(); runOneInstruction();
  } else if(!std::strcmp(name, "before_deadline")) {
    setGate(0,0,0,0,0); setCountCompare(100,103); cpu.stepCount(4);
  } else if(!std::strcmp(name, "masked")) {
    ie=1; im=0; setGate(0,ie,0,0,im); setCountCompare(100,103); cpu.stepCount(6);
    pending_before_instruction = pending7(); runOneInstruction();
  } else if(!std::strcmp(name, "ie0")) {
    im=0x80; setGate(0,0,0,0,im); setCountCompare(100,103); cpu.stepCount(6);
    pending_before_instruction = pending7(); runOneInstruction();
  } else if(!std::strcmp(name, "exl1")) {
    ie=1; exl=1; im=0x80; setGate(0,ie,exl,0,im); setCountCompare(100,103); cpu.stepCount(6);
    pending_before_instruction = pending7(); runOneInstruction();
  } else if(!std::strcmp(name, "erl1")) {
    ie=1; erl=1; im=0x80; setGate(0,ie,0,erl,im); setCountCompare(100,103); cpu.stepCount(6);
    pending_before_instruction = pending7(); runOneInstruction();
  } else if(!std::strcmp(name, "compare_clear_new_value")) {
    setGate(0,1,0,0,0x80); setCountCompare(100,103); cpu.stepCount(6);
    pending_before_write = pending7(); cpu.setControlRegister(11,1000); pending_after_write = pending7();
    pending_before_instruction = pending7(); runOneInstruction();
  } else if(!std::strcmp(name, "compare_clear_same_value")) {
    setGate(0,1,0,0,0x80); setCountCompare(100,103); cpu.stepCount(6);
    pending_before_write = pending7(); cpu.setControlRegister(11,103); pending_after_write = pending7();
    pending_before_instruction = pending7(); runOneInstruction();
  } else if(!std::strcmp(name, "count_write_keeps_pending")) {
    setGate(0,1,0,0,0x80); setCountCompare(100,103); cpu.stepCount(6);
    pending_before_write = pending7(); cpu.setControlRegister(9,500); pending_after_write = pending7();
    pending_before_instruction = pending7(); runOneInstruction();
  } else if(!std::strcmp(name, "count_forward_changes_deadline")) {
    setGate(0,0,0,0,0); setCountCompare(100,110); cpu.setControlRegister(9,108); cpu.stepCount(4);
  } else if(!std::strcmp(name, "count_backward_changes_deadline")) {
    setGate(0,0,0,0,0); setCountCompare(100,105); cpu.setControlRegister(9,0); cpu.stepCount(10);
  } else if(!std::strcmp(name, "wrap_cross")) {
    setGate(0,0,0,0,0); setCountCompare(0xfffffffeu,1); cpu.stepCount(6);
  } else if(!std::strcmp(name, "equal_compare_no_immediate")) {
    setGate(0,0,0,0,0); setCountCompare(100,100); cpu.stepCount(2);
  } else if(!std::strcmp(name, "guest_compare_ack")) {
    // Pending timer is masked so the guest MTC0 itself can retire. The same-value
    // Compare write must still acknowledge/clear the producer before IM7 is enabled.
    setGate(0,1,0,0,0); setCountCompare(100,103); cpu.stepCount(6);
    pending_before_write = pending7(); cpu.ipu.r[8].u64 = 103; put(0, mtc0T0Compare); put(4, addiuS0);
    runOneInstruction(); guest_write_executed = 1; pending_after_write = pending7();
    cpu.scc.status.interruptMask = 0x80; cpu.interruptPoll(); second_instruction_attempted = 1;
    pending_before_instruction = pending7(); runOneInstruction();
  } else if(!std::strcmp(name, "guest_count_not_ack")) {
    // Count write is also reachable via guest MTC0, but unlike Compare it must not
    // acknowledge an already-latched timer interrupt.
    setGate(0,1,0,0,0); setCountCompare(100,103); cpu.stepCount(6);
    pending_before_write = pending7(); cpu.ipu.r[8].u64 = 500; put(0, mtc0T0Count); put(4, addiuS0);
    runOneInstruction(); guest_write_executed = 1; pending_after_write = pending7();
    cpu.scc.status.interruptMask = 0x80; cpu.interruptPoll(); second_instruction_attempted = 1;
    pending_before_instruction = pending7(); runOneInstruction();
  } else {
    return 5;
  }

  std::printf(
    "{\"name\":\"%s\",\"bev\":%u,\"ie\":%u,\"exl\":%u,\"erl\":%u,\"im\":%u,"
    "\"pending_before_write\":%u,\"pending_after_write\":%u,\"pending_before_instruction\":%u,"
    "\"pending_final\":%u,\"count\":%llu,\"compare\":%llu,\"pc\":%llu,\"s0\":%llu,"
    "\"cause\":%u,\"bd\":%u,\"epc\":%llu,\"final_exl\":%u,\"final_erl\":%u,"
    "\"guest_write_executed\":%u,\"second_instruction_attempted\":%u}\n",
    name, bev, ie, exl, erl, im,
    pending_before_write, pending_after_write, pending_before_instruction,
    pending7(),
    (unsigned long long)(cpu.effectiveCount() >> 1),
    (unsigned long long)(cpu.scc.compare >> 1),
    (unsigned long long)cpu.ipu.pc,
    (unsigned long long)cpu.ipu.r[16].u64,
    (u32)cpu.scc.cause.exceptionCode,
    (u32)cpu.scc.cause.branchDelay,
    (unsigned long long)cpu.scc.epc,
    (u32)cpu.scc.status.exceptionLevel,
    (u32)cpu.scc.status.errorLevel,
    guest_write_executed, second_instruction_attempted);

  ares::Nintendo64::system.unload();
  return 0;
}
