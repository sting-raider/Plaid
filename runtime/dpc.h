/* Synchronous, idle DPC boundary for lowered RSP code. Register semantics:
   pinned ares n64/rdp/io.cpp. The consumer must refuse unsupported ranges. */
#ifndef PLAID_DPC_H
#define PLAID_DPC_H
typedef struct {
  u32 start, end, current, status;
  int (*consume)(u32 address, u32 size, int dmem);
} plaid_dpc;

static int plaid_dpc_flush(plaid_dpc *d) {
  if (d->status & 2) return 0;
  if (d->end < d->current) return 1;
  if (d->end > d->current) {
    if (!d->consume || d->consume(d->current, d->end - d->current, d->status & 1)) return 1;
    d->current = d->end;
  }
  d->status |= 0x88; /* ready, start_gclk: all submitted commands consumed */
  return 0;
}

static int plaid_dpc_access(plaid_dpc *d, u32 reg, u32 *value, int write) {
  u32 v = write ? *value : 0;
  if (reg > 7) return 1;
  if (!write) {
    *value = reg == 0 ? d->start : reg == 1 ? d->end : reg == 2 ? d->current : reg == 3 ? d->status : 0;
    return 0;
  }
  if (reg == 0) {
    if (!(d->status & 0x400)) d->start = v & 0xfffff8;
    d->status |= 0x400;
  } else if (reg == 1) {
    d->end = v & 0xfffff8;
    if (d->status & 0x400) { d->current = d->start; d->status &= ~0x400u; }
    return plaid_dpc_flush(d);
  } else if (reg == 3) {
    if (v & 1) d->status &= ~1u;
    if (v & 2) d->status |= 1;
    if (v & 4) { d->status &= ~2u; if (plaid_dpc_flush(d)) return 1; }
    if (v & 8) d->status |= 2;
    if (v & 16) d->status &= ~4u;
    if (v & 32) d->status |= 4;
  }
  return 0;
}
#endif
