/* RSP state shared by lowered microcode and the host runtime (ADR-0167..0169). */
#ifndef PLAID_RSP_STATE_H
#define PLAID_RSP_STATE_H
#include <stdint.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef uint64_t u64;
typedef int8_t s8; typedef int16_t s16; typedef int32_t s32; typedef int64_t s64;
typedef struct plaid_rsp {
  u32 r[32];
  u8 dmem[4096], imem[4096];
  u8 *rdram; u32 rdram_size;
  /* the host's check before an RSP DMA writes RDRAM bytes [p, p + size); nonzero refuses */
  int (*rdram_write)(u32 p, u32 size);
  u32 pc, fault, fault_pc;
  /* SP DMA: the last transfer's registers as ares reads them back (bit 12: IMEM) */
  u32 dma_mem, dma_dram, dma_length, dma_count, dma_skip;
  u32 pending_mem, pending_dram;
  u8 halted, broken, semaphore, single_step, interrupt_on_break, intr;
  u8 signal[8];
  /* vector unit: element 0 is the most significant halfword; flags are 0 or 0xffff */
  struct plaid_v { u16 e[8]; } v[32], acch, accm, accl, vcoh, vcol, vcch, vccl, vce;
  s16 divin, divout;
  u8 divdp;
  /* Lowered code runs a word only while IMEM still holds the word it was
     lowered from (ADR-0169): ok[] covers the running text, stale is set when
     any word of it differs, imem_gen counts IMEM writes. */
  u8 ok[1024], stale, imem_written;
  u32 imem_gen;
} plaid_rsp;
typedef struct plaid_v plaid_v;
/* One lowered IMEM text. run() returns 0 when the RSP halts, 1 on a fault,
   and 2 when control reaches a word this text cannot run (r->pc). */
typedef struct plaid_rsp_text {
  u32 start, size;
  const u8 *bytes;
  int (*run)(plaid_rsp *r, u32 pc);
  const char *name;
} plaid_rsp_text;
#endif
