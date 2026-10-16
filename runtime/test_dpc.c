/* Synthetic register/command-boundary regression, without a ROM or GPU. */
#include "rsp_state.h"
#include "rsp_prelude.h"
#include "dpc.h"
#include <stdio.h>

static u32 calls, last_address, last_size, last_source;
static int consume(u32 address, u32 size, int dmem) {
  if (address >= 0x10000) return 1;
  calls++; last_address = address; last_size = size; last_source = dmem;
  return 0;
}
static plaid_dpc dp = {0, 0, 0, 0x80, consume};
static int bus(u32 reg, u32 *v, int write) { return plaid_dpc_access(&dp, reg, v, write); }
#define CHECK(test) do { if (!(test)) { fprintf(stderr, "DPC check failed at line %d\n", __LINE__); return 1; } } while (0)
#define WRITE(reg, value) CHECK(!plaid_rsp_mtc0(&rsp, reg, value, 0x100))
#define READ(reg, expected) do { u32 got; CHECK(!plaid_rsp_mfc0(&rsp, reg, &got, 0x104)); CHECK(got == (expected)); } while (0)

int main(void) {
  plaid_rsp rsp = {0};
  rsp.dpc = bus;
  WRITE(11, 8); /* freeze */
  WRITE(8, 0xff001017); /* mask to 24 bits and align */
  WRITE(8, 0x2000); /* first pending START wins */
  WRITE(9, 0x1027);
  READ(8, 0x1010); READ(9, 0x1020); READ(10, 0x1010);
  CHECK(calls == 0);
  WRITE(11, 4); /* unfreeze drains the pending range */
  CHECK(calls == 1 && last_address == 0x1010 && last_size == 16 && !last_source);
  READ(10, 0x1020); READ(11, 0x88);
  WRITE(9, 0x1028); /* append: START is no longer pending */
  CHECK(calls == 2 && last_address == 0x1020 && last_size == 8);
  WRITE(11, 2); /* XBUS DMEM source */
  WRITE(8, 0xff8); WRITE(9, 0x1008);
  CHECK(calls == 3 && last_address == 0xff8 && last_size == 16 && last_source == 1);
  WRITE(11, 8); WRITE(9, 0x1010);
  WRITE(11, 12); /* clear-freeze flushes before set-freeze, as ares does */
  CHECK(calls == 4 && last_address == 0x1008 && last_size == 8);
  READ(11, 0x8b);
  WRITE(11, 5); /* RDRAM source, unfreeze */
  WRITE(8, 0x10000);
  CHECK(plaid_rsp_mtc0(&rsp, 9, 0x10008, 0x222) == 1);
  CHECK(rsp.fault == 4 && rsp.fault_pc == 0x222 && calls == 4 && dp.current == 0x10000);
  rsp = (plaid_rsp){0}; /* no bus: existing fail-closed behavior */
  READ(11, 0x80);
  CHECK(plaid_rsp_mtc0(&rsp, 9, 0x1008, 0x224) == 1 && rsp.fault == 4);
  CHECK(plaid_rsp_mfc0(&rsp, 8, &last_address, 0x228) == 1 && rsp.fault_pc == 0x228);
  puts("PASS RSP DPC delegation: freeze, first START, append, XBUS, alignment, refused ranges and missing bus");
  return 0;
}
