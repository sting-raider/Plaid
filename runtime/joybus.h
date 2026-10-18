/* SPDX-License-Identifier: MIT OR Apache-2.0
   Native Joybus packets for the declared one-gamepad / 4 Kbit EEPROM platform.
   This does not execute PIF firmware or guest instructions. */
#ifndef PLAID_JOYBUS_H
#define PLAID_JOYBUS_H
typedef struct { u8 header, input, output, send, receive, action; } plaid_joy_packet;
typedef struct {
  u8 ram[64];
  plaid_joy_packet packet[5];
  u64 eeprom_busy_until;
  int changed;
} plaid_joybus;

static int plaid_joy_parse(plaid_joybus *bus) {
  unsigned channel = 0, cursor = 0;
  if (bus->ram[63] & ~1u) return 1;
  if (!(bus->ram[63] & 1)) return 0;
  memset(bus->packet, 0, sizeof bus->packet);
  bus->ram[63] = 0;
  while (channel < 5 && cursor < 63) {
    unsigned start = cursor++, tx = bus->ram[start], rx;
    plaid_joy_packet *packet;
    if (tx == 0xfe) break;
    if (tx == 0xff) continue;
    if (!tx) { channel++; continue; }
    packet = &bus->packet[channel++];
    if (tx == 0xfd) { packet->action = 2; continue; }
    if (cursor >= 63) return 1;
    rx = bus->ram[cursor++] & 63u;
    tx &= 63u;
    if (!tx || cursor + tx + rx > 63) return 1;
    packet->header = (u8)start;
    packet->input = (u8)cursor;
    packet->output = (u8)(cursor + tx);
    packet->send = (u8)tx;
    packet->receive = (u8)rx;
    packet->action = 1;
    cursor += tx + rx;
  }
  return 0;
}

static int plaid_joy_run(plaid_joybus *bus, u8 *eeprom_bytes, u64 ticks, u32 controller) {
  int channel;
  for (channel = 4; channel >= 0; channel--) {
    const plaid_joy_packet *p = &bus->packet[channel];
    const u8 *request = bus->ram + p->input;
    u8 *reply = bus->ram + p->output;
    unsigned command;
    if (p->action != 1 || (bus->ram[p->header] & 0xc0)) continue;
    bus->ram[p->header + 1] = p->receive;
    if (channel > 0 && channel < 4) {
      bus->ram[p->header + 1] |= 0x80;
      continue;
    }
    command = request[0];
    if ((command == 0 || command == 0xff) && p->send == 1 && p->receive == 3) {
      reply[0] = channel == 0 ? 5 : 0;
      reply[1] = channel == 0 ? 0 : 0x80;
      reply[2] = channel == 0 ? 2 : ticks < bus->eeprom_busy_until ? 0x80 : 0;
    } else if (channel == 0 && command == 1 && p->send == 1 && p->receive == 4) {
      unsigned byte;
      for (byte = 0; byte < 4; byte++) reply[byte] = (u8)(controller >> (24 - 8 * byte));
    } else if (channel == 4 && command == 4 && p->send == 2 && p->receive == 8) {
      unsigned byte, block = request[1] & 63u;
      for (byte = 0; byte < 8; byte++)
        reply[byte] = ticks < bus->eeprom_busy_until ? 0xff : eeprom_bytes[block * 8 + byte];
    } else if (channel == 4 && command == 5 && p->send == 10 && p->receive == 1) {
      reply[0] = ticks < bus->eeprom_busy_until ? 0x80 : 0;
      if (!reply[0]) {
        memcpy(eeprom_bytes + (request[1] & 63u) * 8, request + 2, 8);
        bus->eeprom_busy_until = ticks + 281250; /* 6 ms at COUNT's 46.875 MHz */
        bus->changed = 1;
      }
    } else {
      return 1; /* outside the declared packet subset */
    }
  }
  return 0;
}
#endif
