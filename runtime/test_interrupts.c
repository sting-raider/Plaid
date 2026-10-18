/* Deterministic event arrival; no host clock or event thread is needed. */
#define main runtime_main
#include "plaid_rt.c"
#undef main
#include <assert.h>

static plaid_state state;

int main(void) {
  const u32 queue = 0x80002000u, buffer = 0x80002020u, message = 0x12345678u;
  S = &state;
  running = &boot;
  S->r[4] = queue; S->r[5] = buffer; S->r[6] = 4;
  assert(plaid_rt_osCreateMesgQueue(S) == 0);
  S->r[4] = EV_SP; S->r[5] = queue; S->r[6] = message;
  assert(plaid_rt_osSetEventMesg(S) == 0);

  post(EV_SP);
  assert(rd32(queue + 8) == 0);
  S->r[4] = 0;
  assert(plaid_rt___osRestoreInt(S) == 0);
  assert(rd32(queue + 8) == 1 && rd32(buffer) == message);

  assert(plaid_rt___osDisableInt(S) == 0 && S->r[2] == 1);
  post(EV_SP);
  S->r[4] = 0;
  assert(plaid_rt___osRestoreInt(S) == 0);
  assert(rd32(queue + 8) == 1);
  S->r[4] = 1;
  assert(plaid_rt___osRestoreInt(S) == 0);
  assert(rd32(queue + 8) == 2 && rd32(buffer + 4) == message);
  assert(S->fault == 0);
  puts("interrupt events: restore zero preserves enabled delivery; disabled arrival waits for restore one");
  return 0;
}
