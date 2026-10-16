/* Native side of spike096: runs a plaid-lower translation unit and prints the
   same state as driver.cpp. PLAID_LOWERED names the generated C file. */
#include <stdio.h>
#include PLAID_LOWERED
#include "runtime.c"

static plaid_state s;

/* RAM as a cached read sees it, as driver.cpp dumps through ares' D-cache:
   a resident line's stale bytes read its older copy (ADR-0183) */
static u32 cached_byte(u32 a) {
  u32 i = (a >> 4) & 0x1ffu;
  if (s.dtag[i] == ((a & ~0xfffu) | 1) && (s.dstale[i] >> (a & 15) & 1)) return s.dold[i][a & 15];
  return s.ram[a];
}

int main(void) {
  int r;
  u32 a;
  plaid_load_images(&s);
  s.r[31] = (u64)(s64)(s32)PLAID_EXIT; /* as driver.cpp: the host entry returns to the exit */
  if (plaid_run(&s)) {
    printf("{\"fault\":%u,\"fault_pc\":%u}\n", s.fault, s.fault_pc);
    return 6;
  }
  printf("{\"pc\":%u,\"regs\":[", s.pc);
  for (r = 0; r < 32; r++) printf("%s%llu", r ? "," : "", (unsigned long long)s.r[r]);
  printf("],\"hi\":%llu,\"lo\":%llu,\"fpr\":[", (unsigned long long)s.hi, (unsigned long long)s.lo);
  for (r = 0; r < 32; r++) printf("%s%llu", r ? "," : "", (unsigned long long)s.f[r]);
  printf("],\"fcc\":%u,\"fcsr\":%u,\"ram\":[", s.fcc, s.fcsr | s.fcc << 23);
  for (a = 0x1000; a < 0x1100; a += 4)
    printf("%s%u", a != 0x1000 ? "," : "",
           cached_byte(a) << 24 | cached_byte(a + 1) << 16 | cached_byte(a + 2) << 8 | cached_byte(a + 3));
  printf("]}\n");
  return 0;
}
