/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "trace_sink.h"
int main(void) {
    const uint32_t words[] = {0x3c088000u, 0x35080020u, 0x01000008u, 0};
    uint64_t unit;
    plaid_trace_open();
    unit = plaid_trace_begin(0x80000000u, 0);
    plaid_trace_entry(unit, 0x80000000u, 0);
    plaid_trace_compiled(unit, 0x80000000u, words, 4);
    /* Execution-only snapshot sensing stays disabled in the portable driver. */
    plaid_trace_verified_entry(unit, 0x80000000u, 0, words, 4);
    plaid_trace_lookup(0x80000020u, 0);
    plaid_trace_link(0x80000020u);
    plaid_trace_invalidate(0x80000000u, 16);
    /* The same address is recompiled with different bytes, never conflated. */
    unit = plaid_trace_begin(0x80000000u, 1);
    plaid_trace_entry(unit, 0x80000001u, 0x10);
    plaid_trace_compiled(unit, 0x80000000u, words + 3, 1);
    plaid_trace_invalidate(0, 0);
    plaid_trace_close();
    return plaid_trace_failed ? 1 : 0;
}
