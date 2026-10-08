/* SPDX-License-Identifier: GPL-2.0-or-later
 * Plaid research instrumentation, 2026. No host pointers enter this stream.
 * This header is included only by the separately built Mupen reference.
 */
#ifndef PLAID_TRACE_SINK_H
#define PLAID_TRACE_SINK_H
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>

static FILE *plaid_trace_file;
static uint64_t plaid_trace_seq, plaid_trace_unit, plaid_current_unit;
static int plaid_trace_failed;
static int plaid_trace_execution_enabled;
static int plaid_trace_writes_enabled;
static uint32_t plaid_pagespan_branch;
static uint64_t plaid_pagespan_unit;

static void plaid_trace_check(void) {
    if (plaid_trace_file && (ferror(plaid_trace_file) || fflush(plaid_trace_file))) {
        plaid_trace_failed = 1;
        fprintf(stderr, "Plaid: discovery trace write failed\n");
    }
}
static void plaid_trace_close(void) {
    if (!plaid_trace_file) return;
    if (!plaid_trace_failed)
        fprintf(plaid_trace_file, "{\"record\":\"end\",\"event_count\":%" PRIu64 "}\n", plaid_trace_seq);
    plaid_trace_check();
    if (fclose(plaid_trace_file)) fprintf(stderr, "Plaid: discovery trace close failed\n");
    plaid_trace_file = NULL;
}
static void plaid_trace_open(void) {
    const char *path = getenv("PLAID_TRACE_PATH"), *hash = getenv("PLAID_ROM_SHA256");
    const char *size_text = getenv("PLAID_ROM_SIZE");
    char *end;
    unsigned long long size;
    size_t i;
    plaid_trace_close();
    plaid_trace_seq = plaid_trace_unit = plaid_current_unit = 0;
    plaid_trace_failed = 0;
    plaid_trace_execution_enabled = 0;
    plaid_trace_writes_enabled = 0;
    plaid_pagespan_branch = 0;
    plaid_pagespan_unit = 0;
    if (!path || !*path) return;
    if (!hash || strlen(hash) != 64 || !size_text || !*size_text) goto invalid;
    for (i = 0; i < 64; ++i)
        if (!((hash[i] >= '0' && hash[i] <= '9') || (hash[i] >= 'a' && hash[i] <= 'f'))) goto invalid;
    for (i = 0; size_text[i]; ++i) if (size_text[i] < '0' || size_text[i] > '9') goto invalid;
    size = strtoull(size_text, &end, 10);
    if (*end || size < 64 || size > UINT32_MAX) goto invalid;
    plaid_trace_file = fopen(path, "wb");
    if (!plaid_trace_file) { fprintf(stderr, "Plaid: cannot open trace destination\n"); return; }
#if defined(NEW_DYNAREC) && NEW_DYNAREC == NEW_DYNAREC_X64
    {
        const char *execution = getenv("PLAID_TRACE_EXECUTION");
        plaid_trace_execution_enabled = execution && !strcmp(execution, "1");
        execution = getenv("PLAID_TRACE_WRITES");
        plaid_trace_writes_enabled = execution && !strcmp(execution, "1");
    }
#endif
    fprintf(plaid_trace_file,
        "{\"record\":\"header\",\"header\":{\"schema_version\":0,\"rom\":{\"sha256\":\"%s\",\"size\":%llu},"
        "\"engine\":\"mupen64plus-new_dynarec\",\"revision\":\"ba95bab92a76744753bfe61470823a4937850ab0\","
        "\"capabilities\":[\"compilation_units\",\"entry_installation\"%s%s,\"invalidation\",\"rom_dma\",\"target_lookup\"]}}\n", hash, size,
        plaid_trace_execution_enabled ? ",\"indirect_targets_x64\",\"verified_dirty_entries_x64\"" : "",
        plaid_trace_writes_enabled ? ",\"cpu_sw_constant_rdram_x64\"" : "");
    plaid_trace_check();
    return;
invalid:
    fprintf(stderr, "Plaid: canonical PLAID_ROM_SHA256/PLAID_ROM_SIZE required; trace disabled\n");
}
static int plaid_trace_prefix(const char *event) {
    if (!plaid_trace_file || plaid_trace_failed) return 0;
    fprintf(plaid_trace_file, "{\"record\":\"event\",\"seq\":%" PRIu64 ",\"data\":{\"event\":\"%s\"", plaid_trace_seq++, event);
    return 1;
}
static void plaid_trace_finish(void) { fputs("}}\n", plaid_trace_file); plaid_trace_check(); }
static uint64_t plaid_trace_begin(uint32_t pc, int delay_slot) {
    uint64_t unit = plaid_trace_unit++;
    plaid_current_unit = unit;
    if (!plaid_trace_prefix("compile_begin")) return unit;
    fprintf(plaid_trace_file, ",\"unit\":%" PRIu64 ",\"start\":%" PRIu32 ",\"physical_start\":", unit, pc);
    if (pc >= 0x80000000u && pc < 0xc0000000u) fprintf(plaid_trace_file, "%" PRIu32, pc & 0x1fffffffu);
    else fputs("null", plaid_trace_file);
    fprintf(plaid_trace_file, ",\"delay_slot_entry\":%s", delay_slot ? "true" : "false");
    plaid_trace_finish(); return unit;
}
static void plaid_trace_compiled(uint64_t unit, uint32_t pc, const uint32_t *words, uint32_t count) {
    uint32_t i;
    if (!plaid_trace_prefix("unit_compiled")) return;
    fprintf(plaid_trace_file, ",\"unit\":%" PRIu64 ",\"start\":%" PRIu32 ",\"words\":[", unit, pc);
    for (i = 0; i < count; ++i) fprintf(plaid_trace_file, "%s%" PRIu32, i ? "," : "", words[i]);
    fputc(']', plaid_trace_file); plaid_trace_finish();
}
static void plaid_trace_entry(uint64_t unit, uint32_t pc, uint32_t mask) {
    if (!plaid_trace_prefix("entry_installed")) return;
    fprintf(plaid_trace_file, ",\"unit\":%" PRIu64 ",\"pc\":%" PRIu32 ",\"register_mask\":%" PRIu32, unit, pc & ~3u, mask);
    plaid_trace_finish();
}
/* Called only after the reference compared this complete saved unit to memory.
 * A successful dirty lookup is a snapshot check, not proof of execution. */
static void plaid_trace_verified_entry(uint64_t unit, uint32_t pc, uint32_t mask, const uint32_t *words, uint32_t count) {
    uint32_t i;
    if (!plaid_trace_execution_enabled || !plaid_trace_prefix("entry_bytes_verified")) return;
    fprintf(plaid_trace_file, ",\"unit\":%" PRIu64 ",\"pc\":%" PRIu32 ",\"register_mask\":%" PRIu32 ",\"words\":[", unit, pc, mask);
    for (i = 0; i < count; ++i) fprintf(plaid_trace_file, "%s%" PRIu32, i ? "," : "", words[i]);
    fputc(']', plaid_trace_file); plaid_trace_finish();
}
static void plaid_trace_lookup(uint32_t target, int delay_slot) {
    if (!plaid_trace_prefix("target_lookup")) return;
    fprintf(plaid_trace_file, ",\"target\":%" PRIu32 ",\"delay_slot_entry\":%s", target & ~3u, delay_slot ? "true" : "false");
    plaid_trace_finish();
}
static void plaid_trace_link(uint32_t target) {
    if (!plaid_trace_prefix("runtime_link")) return;
    fprintf(plaid_trace_file, ",\"target\":%" PRIu32, target & ~3u); plaid_trace_finish();
}
/* Called by generated reference code after the delay slot, before lookup/cache
 * dispatch. The target argument is the saved pre-delay-slot branch operand. */
void plaid_trace_indirect(uint32_t site, uint32_t target, uint64_t source_unit) {
    if (!plaid_trace_prefix("indirect_target_observed")) return;
    fprintf(plaid_trace_file, ",\"site\":%" PRIu32 ",\"target\":%" PRIu32 ",\"delay_slot_pc\":%" PRIu32 ",\"source_unit\":%" PRIu64,
        site, target, site + 4u, source_unit);
    plaid_trace_finish();
}
/* The predecessor records site|1 only for JR/JALR. Direct pagespan branches
 * clear it, preventing a shared delay-slot entry from inventing an observation. */
void plaid_trace_pagespan(uint32_t site, uint32_t target) {
    if (plaid_pagespan_branch == (site | 1u)) plaid_trace_indirect(site, target, plaid_pagespan_unit);
}
void plaid_trace_pagespan_context(uint32_t branch, uint64_t source_unit) {
    plaid_pagespan_branch = branch;
    plaid_pagespan_unit = source_unit;
}
static void plaid_trace_invalidate(uint32_t address, size_t size) {
    if (!plaid_trace_prefix("invalidate")) return;
    if (!size || size > UINT32_MAX || (uint64_t)address + size > UINT64_C(0x100000000))
        fputs(",\"range\":null", plaid_trace_file);
    else fprintf(plaid_trace_file, ",\"range\":{\"start\":%" PRIu32 ",\"size\":%" PRIu32 "}", address, (uint32_t)size);
    plaid_trace_finish();
}
/* Exported only by the research reference's new_dynarec translation unit. */
void plaid_trace_rom_dma(uint32_t offset, uint32_t destination, uint32_t size) {
    if (!size || !plaid_trace_prefix("rom_dma_observed")) return;
    fprintf(plaid_trace_file, ",\"rom_offset\":%" PRIu32 ",\"physical_destination\":%" PRIu32 ",\"size\":%" PRIu32, offset,destination,size);
    plaid_trace_finish();
}
void plaid_trace_word_store(uint32_t site, uint32_t destination, uint32_t value) {
    if (!plaid_trace_writes_enabled || !plaid_trace_prefix("cpu_word_store_observed")) return;
    fprintf(plaid_trace_file, ",\"site\":%" PRIu32 ",\"destination\":%" PRIu32 ",\"value\":%" PRIu32, site,destination,value);
    plaid_trace_finish();
}
#endif
