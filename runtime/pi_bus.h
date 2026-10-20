/* Read-only PI bus writes, matching pinned ares pi/bus.hpp. SPDX-License-Identifier: MIT OR Apache-2.0 */
#ifndef PLAID_PI_BUS_H
#define PLAID_PI_BUS_H
typedef struct { u32 latch; u64 due; } plaid_pi_bus;
/* COUNT ticks are half the CPU clocks; PI_BUS_Write completes after 400. */
static inline int plaid_pi_bus_busy(const plaid_pi_bus *bus, u64 count) { return count < bus->due; }
static inline void plaid_pi_bus_write(plaid_pi_bus *bus, u32 value, u64 count) {
  if (plaid_pi_bus_busy(bus, count)) return;
  bus->latch = value;
  bus->due = count + 200;
}
static inline int plaid_pi_bus_read_pending(plaid_pi_bus *bus, u64 count, u32 *value) {
  if (!plaid_pi_bus_busy(bus, count)) return 0;
  *value = bus->latch;
  bus->due = 0; /* readWord forces the pending write to finish, returning its latch */
  return 1;
}
#endif
