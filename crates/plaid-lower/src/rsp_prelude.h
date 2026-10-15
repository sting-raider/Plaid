/* RSP model for lowered microcode (ADR-0167). Semantics follow pinned ares
   (ares/n64/rsp: interpreter-ipu.cpp, interpreter-scc.cpp, io.cpp, dma.cpp;
   ISC license, Copyright (c) 2004-2021 ares team, Near et al).

   DMEM and RDRAM are big-endian byte arrays. DMA completes when it is
   started, so SP_DMA_BUSY and SP_DMA_FULL read 0: the result equals ares for
   microcode that waits for its DMA before using the bytes. Faults:
   1 DMA outside RDRAM, 2 DMA into IMEM (lowered code is fixed),
   3 transfer outside the lowered text or misaligned, 4 RDP command register. */
#include <stdint.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef uint64_t u64;
typedef int8_t s8; typedef int16_t s16; typedef int32_t s32; typedef int64_t s64;
typedef struct {
  u32 r[32];
  u8 dmem[4096];
  u8 *rdram; u32 rdram_size;
  u32 pc, fault, fault_pc;
  /* SP DMA: the last started transfer's registers, as ares reads them back */
  u32 dma_mem, dma_dram, dma_length, dma_count, dma_skip;
  u32 pending_mem, pending_dram;
  u8 halted, broken, semaphore, single_step, interrupt_on_break, intr;
  u8 signal[8];
} plaid_rsp;

static int plaid_rsp_fault(plaid_rsp *r, u32 pc, u32 code) {
  r->fault = code; r->fault_pc = pc; r->halted = 1;
  return 1;
}
/* scalar DMEM access: byte-wise, each byte address wrapped to 12 bits */
static inline u32 plaid_rsp_ld(plaid_rsp *r, u32 a, u32 size) {
  u32 v = 0, i;
  for (i = 0; i < size; i++) v = v << 8 | r->dmem[(a + i) & 0xfff];
  return v;
}
static inline void plaid_rsp_st(plaid_rsp *r, u32 a, u32 size, u32 v) {
  u32 i;
  for (i = 0; i < size; i++) r->dmem[(a + i) & 0xfff] = (u8)(v >> (8 * (size - 1 - i)));
}
/* SP_RD_LEN / SP_WR_LEN: length rows of (length | 7) + 1 bytes, count + 1
   rows, skip bytes between rows in RDRAM. */
static int plaid_rsp_dma(plaid_rsp *r, u32 value, int to_rdram, u32 pc) {
  u32 length = value & 0xff8, count = (value >> 12) & 0xff, skip = (value >> 20) & 0xff8;
  u32 mem = r->pending_mem & 0xff8, dram = r->pending_dram & 0xfffff8, row, i;
  if (r->pending_mem & 0x1000) return plaid_rsp_fault(r, pc, 2);
  for (row = 0; row <= count; row++) {
    for (i = 0; i <= length; i += 8) {
      if (dram + 8 > r->rdram_size) return plaid_rsp_fault(r, pc, 1);
      if (to_rdram) {
        u32 j;
        for (j = 0; j < 8; j++) r->rdram[dram + j] = r->dmem[(mem + j) & 0xfff];
      } else {
        u32 j;
        for (j = 0; j < 8; j++) r->dmem[(mem + j) & 0xfff] = r->rdram[dram + j];
      }
      dram = (dram + 8) & 0xffffff;
      mem = (mem + 8) & 0xfff;
    }
    if (row < count) dram = (dram + skip) & 0xffffff;
  }
  r->dma_mem = mem; r->dma_dram = dram; r->dma_length = 0xff8; r->dma_count = 0; r->dma_skip = skip;
  return 0;
}
static inline int plaid_rsp_mfc0(plaid_rsp *r, u32 rd, u32 *out, u32 pc) {
  u32 i, v = 0;
  if (rd & 8) return plaid_rsp_fault(r, pc, 4);
  switch (rd & 7) {
  case 0: v = r->dma_mem & 0xfff; break; /* SP_MEM_ADDR: DMEM region */
  case 1: v = r->dma_dram & 0xffffff; break;
  case 2: case 3: v = r->dma_length | r->dma_count << 12 | r->dma_skip << 20; break;
  case 4:
    v = r->halted | r->broken << 1 | r->single_step << 5 | r->interrupt_on_break << 6;
    for (i = 0; i < 8; i++) v |= (u32)r->signal[i] << (7 + i);
    break;
  case 5: case 6: v = 0; break; /* DMA full / busy: transfers complete at once */
  case 7: v = r->semaphore; r->semaphore = 1; break;
  }
  *out = v;
  return 0;
}
static inline int plaid_rsp_mtc0(plaid_rsp *r, u32 rd, u32 v, u32 pc) {
  u32 i;
  if (rd & 8) return plaid_rsp_fault(r, pc, 4);
  switch (rd & 7) {
  case 0: r->pending_mem = v & 0x1ff8; break;
  case 1: r->pending_dram = v & 0xfffff8; break;
  case 2: return plaid_rsp_dma(r, v, 0, pc);
  case 3: return plaid_rsp_dma(r, v, 1, pc);
  case 4:
    if ((v & 1) && !(v & 2)) r->halted = 0;
    if ((v & 2) && !(v & 1)) r->halted = 1;
    if (v & 4) r->broken = 0;
    if ((v & 8) && !(v & 16)) r->intr = 0;
    if ((v & 16) && !(v & 8)) r->intr = 1;
    if ((v & 32) && !(v & 64)) r->single_step = 0;
    if ((v & 64) && !(v & 32)) r->single_step = 1;
    if ((v & 128) && !(v & 256)) r->interrupt_on_break = 0;
    if ((v & 256) && !(v & 128)) r->interrupt_on_break = 1;
    for (i = 0; i < 8; i++) {
      u32 clr = 1u << (9 + 2 * i), set = clr << 1;
      if ((v & clr) && !(v & set)) r->signal[i] = 0;
      if ((v & set) && !(v & clr)) r->signal[i] = 1;
    }
    break;
  case 5: case 6: break; /* read-only */
  case 7: r->semaphore = 0; break;
  }
  return 0;
}
