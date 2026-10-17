/* Native Joybus packets, SI DMA through PIF RAM and the EEPROM busy state the
   HLE status query shares. Synthetic packets only; time is injected. */
#define main runtime_main
#include "plaid_rt.c"
#undef main
#include <assert.h>

static plaid_state state;

/* libultra's request layout: pad, tx, rx, command, then the reply bytes. */
static unsigned put(u8 *ram, unsigned at, u8 tx, u8 rx, const u8 *request) {
  unsigned i;
  ram[at++] = 0xff;
  ram[at++] = tx; ram[at++] = rx;
  for (i = 0; i < tx; i++) ram[at++] = request[i];
  for (i = 0; i < rx; i++) ram[at++] = 0xff;
  return at;
}

static void controllers(void) {
  plaid_joybus bus;
  const u8 status[] = {0}, read[] = {1};
  unsigned at = 0, ch;
  memset(&bus, 0, sizeof bus);
  for (ch = 0; ch < 4; ch++) at = put(bus.ram, at, 1, 3, status);
  bus.ram[at] = 0xfe; bus.ram[63] = 1;
  assert(plaid_joy_parse(&bus) == 0 && bus.ram[63] == 0);
  assert(plaid_joy_run(&bus, NULL, 0, 0) == 0);
  /* channel 0: gamepad, no Pak; 1-3: no device, rx length kept with 0x80 */
  assert(bus.ram[2] == 3 && bus.ram[4] == 5 && bus.ram[5] == 0 && bus.ram[6] == 2);
  for (ch = 1; ch < 4; ch++) {
    const u8 *p = bus.ram + 7 * ch;
    assert(p[2] == 0x83 && p[4] == 0xff && p[5] == 0xff && p[6] == 0xff);
  }
  memset(&bus, 0, sizeof bus);
  at = 0;
  for (ch = 0; ch < 4; ch++) at = put(bus.ram, at, 1, 4, read);
  bus.ram[at] = 0xfe; bus.ram[63] = 1;
  assert(plaid_joy_parse(&bus) == 0 && plaid_joy_run(&bus, NULL, 0, 0x12345678u) == 0);
  assert(bus.ram[4] == 0x12 && bus.ram[5] == 0x34 && bus.ram[6] == 0x56 && bus.ram[7] == 0x78);
  /* run again without a new parse: the same packets answer again */
  assert(plaid_joy_run(&bus, NULL, 0, 0x0000ffffu) == 0 && bus.ram[4] == 0 && bus.ram[7] == 0xff);
  /* a header with 0x80 or 0x40 set is skipped */
  bus.ram[1] |= 0x80; bus.ram[4] = 0xaa;
  assert(plaid_joy_run(&bus, NULL, 0, 0x12345678u) == 0 && bus.ram[4] == 0xaa);
}

/* Channel 4 after four skipped controller channels. */
static void eeprom_packet(plaid_joybus *bus, u8 tx, u8 rx, const u8 *request) {
  unsigned at;
  memset(bus->ram, 0, 64);
  at = put(bus->ram, 4, tx, rx, request);
  bus->ram[at] = 0xfe; bus->ram[63] = 1;
  assert(plaid_joy_parse(bus) == 0);
}

static void eeprom_device(void) {
  static u8 bytes[512];
  plaid_joybus bus;
  const u8 status[] = {0}, read[] = {4, 63 | 0x40};
  u8 write[10] = {5, 63, 1, 2, 3, 4, 5, 6, 7, 8};
  const u64 t = 1000, busy = 281250;
  unsigned i;
  memset(&bus, 0, sizeof bus);
  eeprom_packet(&bus, 10, 1, write);
  assert(plaid_joy_run(&bus, bytes, t, 0) == 0 && bus.ram[4 + 3 + 10] == 0);
  assert(bus.changed && bus.eeprom_busy_until == t + busy && bytes[504] == 1 && bytes[511] == 8);
  eeprom_packet(&bus, 1, 3, status);
  assert(plaid_joy_run(&bus, bytes, t + busy - 1, 0) == 0);
  assert(bus.ram[8] == 0 && bus.ram[9] == 0x80 && bus.ram[10] == 0x80);
  eeprom_packet(&bus, 2, 8, read);
  assert(plaid_joy_run(&bus, bytes, t + busy - 1, 0) == 0);
  for (i = 0; i < 8; i++) assert(bus.ram[9 + i] == 0xff);
  /* a write while busy is refused and changes nothing */
  bus.changed = 0; write[2] = 0x55;
  eeprom_packet(&bus, 10, 1, write);
  assert(plaid_joy_run(&bus, bytes, t + busy - 1, 0) == 0 && bus.ram[17] == 0x80);
  assert(!bus.changed && bytes[504] == 1);
  eeprom_packet(&bus, 1, 3, status);
  assert(plaid_joy_run(&bus, bytes, t + busy, 0) == 0 && bus.ram[10] == 0);
  /* the block number is masked to the 64 blocks of a 4 Kbit part */
  eeprom_packet(&bus, 2, 8, read);
  assert(plaid_joy_run(&bus, bytes, t + busy, 0) == 0);
  for (i = 0; i < 8; i++) assert(bus.ram[9 + i] == i + 1);
}

static void refusals(void) {
  plaid_joybus bus;
  const u8 unknown[] = {2}, status[] = {0};
  memset(&bus, 0, sizeof bus);
  bus.ram[63] = 2;
  assert(plaid_joy_parse(&bus) == 1);            /* control bits outside the subset */
  memset(&bus, 0, sizeof bus);
  bus.ram[0] = 0x40; bus.ram[1] = 1; bus.ram[63] = 1;
  assert(plaid_joy_parse(&bus) == 1);            /* zero transmit length */
  memset(&bus, 0, sizeof bus);
  memset(bus.ram, 0xff, 60);
  bus.ram[60] = 1; bus.ram[61] = 3; bus.ram[63] = 1;
  assert(plaid_joy_parse(&bus) == 1);            /* packet past byte 62 */
  memset(&bus, 0, sizeof bus);
  put(bus.ram, 0, 1, 3, unknown); bus.ram[7] = 0xfe; bus.ram[63] = 1;
  assert(plaid_joy_parse(&bus) == 0 && plaid_joy_run(&bus, NULL, 0, 0) == 1);
  memset(&bus, 0, sizeof bus);
  put(bus.ram, 0, 1, 2, status); bus.ram[6] = 0xfe; bus.ram[63] = 1;
  assert(plaid_joy_parse(&bus) == 0 && plaid_joy_run(&bus, NULL, 0, 0) == 1);  /* wrong length */
}

/* SI DMA into PIF RAM, the packet run, DMA back, and the shared busy state. */
static void si_and_status(void) {
  const u32 dram = 0x00010000u, block = 0xa0010000u, out = 0xa0020000u;
  u64 v;
  unsigned i;
  for (i = 0; i < 64; i += 4) wr32(block + i, 0);
  wr32(block + 4, 0xff010300u); wr32(block + 8, 0xffffffffu);   /* ch4 status */
  wr32(block + 12, 0xfe000000u); wr32(block + 60, 1);
  v = dram; assert(si_access(0x04800000u, 1, &v) == 0);
  v = 0x1fc007c0u; assert(si_access(0x04800010u, 1, &v) == 0);
  assert(si_status == 0x1000 && pending[EV_SI]);
  v = 0; assert(si_access(0x04800018u, 1, &v) == 0 && si_status == 0 && !pending[EV_SI]);
  joybus.eeprom_busy_until = count_now() + 1000000000ull;
  v = 0x1fc007c0u; assert(si_access(0x04800004u, 1, &v) == 0 && pending[EV_SI]);
  assert(rd32(block + 4) == 0xff010300u && rd32(block + 8) == 0x008080ffu);
  v = 0; assert(si_access(0x1fc007c0u + 8, 0, &v) == 0 && (u32)v == 0x008080ffu);
  v = 0x1fc007c1u; assert(si_access(0x04800004u, 1, &v) == 0);  /* low bit ignored */
  v = 0x1fc00000u; assert(si_access(0x04800004u, 1, &v) == 1);  /* not PIF RAM */
  /* the HLE status query reports the same busy device, then idle */
  S->r[4] = 0; S->r[5] = out;
  assert(plaid_rt___osEepStatus(S) == 0 && rd32(out) == 0x80008000u);
  joybus.eeprom_busy_until = 0;
  assert(plaid_rt___osEepStatus(S) == 0 && rd32(out) == 0x80000000u);
}

int main(void) {
  S = &state; running = &boot;
  controllers();
  eeprom_device();
  refusals();
  si_and_status();
  assert(S->fault == 0);
  puts("{\"joybus\":\"ok\"}");
  return 0;
}
