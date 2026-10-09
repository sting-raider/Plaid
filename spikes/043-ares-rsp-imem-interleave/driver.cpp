/* SPDX-License-Identifier: ISC
 * Exact pinned-ares RSP IMEM DMA/direct-write interleaving fixture.
 * No reference instrumentation.
 */
#define main plaid_capability_fixture_main
#include "../003-ares-oracle/driver.cpp"
#undef main
#include <nall/hash/sha256.hpp>

using namespace ares;
using namespace ares::Nintendo64;

static auto clearDma() -> void {
  rsp.dma.pending = {};
  rsp.dma.current = {};
  rsp.dma.busy = {};
  rsp.dma.full = {};
  rsp.dma.clock = 0;
  rsp.clock = 0;
  cpu.clock = 0;
  std::memset(rsp.imem.data, 0, rsp.imem.size);
  std::memset(rsp.dmem.data, 0, rsp.dmem.size);
}

static auto put64(u32 address, u64 value) -> void {
  rdram.ram.write<Dual>(address, value, RBusDevice::ARES_DEBUGGER);
}

static auto queueRead(u32 dram, u32 imem, u32 lengthReg) -> void {
  rsp.writeWord(0x04040000, 0x1000 | (imem & 0xff8), cpu);
  rsp.writeWord(0x04040004, dram & 0xfffff8, cpu);
  rsp.writeWord(0x04040008, lengthReg, cpu);
}

static auto directImemWord(u32 offset, u32 value) -> void {
  rsp.writeWord(0x04001000 | (offset & 0xfff), value, cpu);
}

static auto word(u32 offset) -> u32 { return rsp.imem.read<Word>(offset); }

int main() {
  Headless frontend; platform = &frontend;
  frontend.cartPak->setAttribute("title", "Plaid RSP IMEM interleave fixture");
  frontend.cartPak->setAttribute("region", "NTSC");
  frontend.cartPak->setAttribute("cic", "CIC-NUS-6102");
  frontend.cartPak->append("program.rom", 8192);
  Node::System root;
  if(!load(root, "[Nintendo] Nintendo 64 (NTSC)")) return 3;
  option("Expansion Pak", "true");
  option("Deterministic Entropy", "true");
  option("Recompiler", "false");
  cartridgeSlot.port->allocate(); cartridgeSlot.port->connect();
  ares::Nintendo64::system.power(false);
  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;
  std::vector<u8> hidden(rdram.ram.size / 2); rdram.hidden.data = hidden.data();
  rdram.mapIdentity = 1;

  put64(0x1000, 0x1111111122222222ull);
  put64(0x1008, 0x3333333344444444ull);
  put64(0x2000, 0x5555555566666666ull);
  put64(0x2008, 0x7777777788888888ull);

  // Case A: direct write to the already completed first row survives transfer completion.
  clearDma();
  queueRead(0x1000, 0x200, 1u << 12); // two 8-byte rows, one dmaTransferStep per row
  rsp.dmaTransferStep();
  if(!rsp.dma.busy.any() || (u32)rsp.dma.current.count != 0 || (u32)rsp.dma.current.pbusAddress != 0x208) return 10;
  directImemWord(0x200, 0xaaaaaaaau);
  const u32 a_mid0 = word(0x200), a_mid1 = word(0x204);
  rsp.dmaTransferStep();
  if(rsp.dma.busy.any()) return 11;
  const u32 a0 = word(0x200), a1 = word(0x204), a2 = word(0x208), a3 = word(0x20c);
  if(a0 != 0xaaaaaaaau || a1 != 0x22222222u || a2 != 0x33333333u || a3 != 0x44444444u) return 12;

  // Case B: direct write to the future second-row destination is superseded by that row.
  clearDma();
  queueRead(0x1000, 0x200, 1u << 12);
  rsp.dmaTransferStep();
  directImemWord(0x208, 0xbbbbbbbbu);
  const u32 b_mid = word(0x208);
  rsp.dmaTransferStep();
  const u32 b_final = word(0x208);
  if(b_mid != 0xbbbbbbbbu || b_final != 0x33333333u) return 20;

  // Case C: same-value direct write is not discoverable by content comparison.
  clearDma();
  queueRead(0x1000, 0x200, 1u << 12);
  rsp.dmaTransferStep();
  const u32 c_before = word(0x200);
  directImemWord(0x200, c_before);
  const u32 c_after = word(0x200);
  rsp.dmaTransferStep();
  if(c_before != 0x11111111u || c_after != c_before || word(0x200) != c_before) return 30;

  // Case D: wrapping transfer. CPU overwrite of row 0 survives; CPU overwrite of
  // the wrapped future row is replaced by row 1.
  clearDma();
  queueRead(0x2000, 0xff8, 1u << 12);
  rsp.dmaTransferStep();
  if((u32)rsp.dma.current.pbusAddress != 0x000 || (u32)rsp.dma.current.count != 0) return 40;
  directImemWord(0xff8, 0xccccccccu);
  directImemWord(0x000, 0xddddddddu);
  const u32 d_mid_old = word(0xff8), d_mid_future = word(0x000);
  rsp.dmaTransferStep();
  const u32 d_old = word(0xff8), d_old_tail = word(0xffc), d_new = word(0x000), d_new_tail = word(0x004);
  if(d_mid_old != 0xccccccccu || d_mid_future != 0xddddddddu) return 41;
  if(d_old != 0xccccccccu || d_old_tail != 0x66666666u || d_new != 0x77777777u || d_new_tail != 0x88888888u) return 42;

  // Case E: unrelated direct IMEM write is not affected by completion of the transfer.
  clearDma();
  queueRead(0x1000, 0x200, 1u << 12);
  rsp.dmaTransferStep();
  directImemWord(0x300, 0xeeeeeeeeu);
  rsp.dmaTransferStep();
  const u32 e_outside = word(0x300);
  if(e_outside != 0xeeeeeeeeu) return 50;

  auto imemHash = nall::Hash::SHA256(std::span<const u8>{rsp.imem.data, rsp.imem.size}).digest();
  std::printf("{\"after_completed_row\":{\"mid\":[%u,%u],\"final\":[%u,%u,%u,%u]},"
              "\"before_later_row\":{\"mid\":%u,\"final\":%u},"
              "\"same_value\":{\"before\":%u,\"after\":%u,\"final\":%u,\"write_invoked\":true},"
              "\"wrap\":{\"mid\":[%u,%u],\"final\":[%u,%u,%u,%u]},"
              "\"non_overlap\":%u,\"final_imem_sha256\":\"%s\"}\n",
              a_mid0,a_mid1,a0,a1,a2,a3,
              b_mid,b_final,
              c_before,c_after,word(0x200),
              d_mid_old,d_mid_future,d_old,d_old_tail,d_new,d_new_tail,
              e_outside,imemHash.data());
  ares::Nintendo64::system.unload();
  return 0;
}
