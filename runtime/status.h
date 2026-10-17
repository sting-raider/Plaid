/* SPDX-License-Identifier: MIT OR Apache-2.0
   Project-owned SDK mask algebra. Values are guest words, never host pointers. */
#ifndef PLAID_STATUS_H
#define PLAID_STATUS_H
static u32 status_old_mask(u32 status, u32 mi, u32 global) {
  u32 old = (status & 0xff01u) | (~global & 0xff00u);
  if (mi) old |= ((mi | (~(global >> 16) & 0x3fu)) & 0x3fu) << 16;
  return old;
}
static void status_set_mask(u32 *status, u32 *mi, u32 requested, u32 global) {
  *status = (*status & ~0xff00u) | (requested & global & 0xff00u);
  *mi = (requested & global) >> 16 & 0x3fu;
}
static u32 status_saved(u32 status, u32 global) {
  if (status & 0xff00u) status |= ~global & 0xff00u;
  return status | 2u;
}
static u32 status_saved_mi(u32 mi, u32 global, u32 previous) {
  return mi ? (mi | (~(global >> 16) & previous & 0x3fu)) & 0x3fu : 0;
}
#endif
