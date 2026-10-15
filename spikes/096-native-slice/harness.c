/* Native side of spike096: runs a plaid-lower translation unit and prints the
   same state as driver.cpp. PLAID_LOWERED names the generated C file. */
#include <stdio.h>
#include PLAID_LOWERED
#include "runtime.c"

static plaid_state s;

int main(void) {
  int r;
  u32 a;
  plaid_load_images(&s);
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
           (u32)s.ram[a] << 24 | (u32)s.ram[a + 1] << 16 | (u32)s.ram[a + 2] << 8 | s.ram[a + 3]);
  printf("]}\n");
  return 0;
}
