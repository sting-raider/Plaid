/* Native side of spike097 (ADR-0167): runs microcode lowered by
   `plaid lower-rsp` (PLAID_RSP_LOWERED, function plaid_rsp_prog) on the same
   IMEM-start, DMEM image and RDRAM pattern as driver.cpp, then prints the
   same state.   harness <dmem.bin> <pc> */
#include <stdio.h>
#include <stdlib.h>
#include PLAID_RSP_LOWERED

static plaid_rsp r;

int main(int argc, char **argv) {
  FILE *f;
  u32 a;
  int i;
  if (argc != 3) return 2;
  f = fopen(argv[1], "rb");
  if (!f || fread(r.dmem, 1, 4096, f) != 4096) return 5;
  fclose(f);
  r.rdram_size = 0x800000;
  r.rdram = calloc(1, r.rdram_size);
  if (!r.rdram) return 5;
  for (a = 0; a < 0x10000; a++) r.rdram[a] = (u8)(a * 7 + 3);
  if (plaid_rsp_prog(&r, (u32)strtoul(argv[2], NULL, 0))) {
    printf("{\"fault\":%u,\"fault_pc\":%u}\n", r.fault, r.fault_pc);
    return 6;
  }
  printf("{\"pc\":%u,\"broken\":%u,\"regs\":[", r.pc, r.broken);
  for (i = 0; i < 32; i++) printf("%s%u", i ? "," : "", r.r[i]);
  printf("],\"dmem\":\"");
  for (a = 0; a < 4096; a++) printf("%02x", r.dmem[a]);
  printf("\",\"rdram\":\"");
  for (a = 0; a < 0x2000; a++) printf("%02x", r.rdram[a]);
  printf("\",\"vu\":\"");
  for (i = 0; i < 35; i++) {
    const plaid_v *v = i < 32 ? &r.v[i] : i == 32 ? &r.acch : i == 33 ? &r.accm : &r.accl;
    int n;
    for (n = 0; n < 8; n++) printf("%04x", v->e[n]);
  }
  {
    u32 f[3] = {0, 0, 0};
    int n;
    for (n = 0; n < 8; n++) {
      f[0] |= (u32)(r.vcol.e[n] != 0) << n | (u32)(r.vcoh.e[n] != 0) << (8 + n);
      f[1] |= (u32)(r.vccl.e[n] != 0) << n | (u32)(r.vcch.e[n] != 0) << (8 + n);
      f[2] |= (u32)(r.vce.e[n] != 0) << n;
    }
    printf("\",\"vflags\":[%u,%u,%u,%u,%u,%u]}\n", f[0], f[1], f[2], (u32)(u16)r.divin, (u32)(u16)r.divout,
           (u32)r.divdp);
  }
  return 0;
}
