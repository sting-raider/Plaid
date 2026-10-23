/* Plaid host runtime (ADR-0158, ADR-0159). SPDX-License-Identifier: MIT OR Apache-2.0

   Build one translation unit: this file includes the lowered program named by
   PLAID_LOWERED, which must be built with PLAID_SAFEPOINTS.

     gcc -std=gnu11 -DPLAID_SAFEPOINTS -DPLAID_LOWERED='"game.c"' -I<dir> \
         runtime/plaid_rt.c -pthread -o game
     game [--rom <rom.z64>] [--stop-at gfx|none] [--gfx-tasks N] [--seconds S]
          [--press <buttons>@<vi>:<frames>]... [--save <eeprom file>]
          [--wav <file>] [--dump <guest address> <words>]
          with -DPLAID_RSP: [--rsp-dump <dir>] [--rsp-capture <task> <dir>]

   With -DPLAID_RSP (and -I crates/plaid-lower/src), RSP tasks other than
   graphics run lowered microcode: link the texts and the registry that
   runtime/rsp_texts.py writes (ADR-0169).

   Each declared runtime function (plaid_rt_<name>) implements a libultra
   function under the o32 ABI: arguments in a0-a3 and the caller's stack at
   sp+16, results in v0 (and v1 for 64-bit values).

   Threads: every guest thread runs on its own host thread, but only the
   holder of the baton (`running`) executes guest code, as on the single
   VR4300. A handoff saves the outgoing thread's CPU registers from the shared
   plaid_state and restores the incoming thread's. Scheduling follows libultra:
   the highest-priority runnable thread runs, a thread made runnable queues
   behind threads of equal priority, and a newly runnable thread of higher
   priority preempts the sender at once.

   Events (VI retrace, timers, SP/DP task completion, SI, PI) are libultra
   messages. Host event sources only mark them pending and raise
   plaid_preempt; the baton holder delivers them at its next runtime call or
   loop-header safepoint, so guest RAM is only written by the baton holder.
   When every guest thread is blocked, the event pump delivers them itself. */
#ifndef PLAID_LOWERED
#error "define PLAID_LOWERED as the lowered program's C file"
#endif
#ifndef PLAID_SAFEPOINTS
#error "build the lowered program with PLAID_SAFEPOINTS"
#endif
#include PLAID_LOWERED
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "status.h"
#include "joybus.h"
#include "pi_bus.h"
#ifdef _WIN32
#include <windows.h>
#ifndef CREATE_WAITABLE_TIMER_HIGH_RESOLUTION
#define CREATE_WAITABLE_TIMER_HIGH_RESOLUTION 0x2
#endif
#endif

#define MAX_THREADS 64
#define MAX_TIMERS 64
#define THREAD_RETURN 0xffffffffbfc00000ull /* $ra sentinel outside guest code */
#define RT_EXIT_THREAD 100                  /* propagates out of plaid_enter */

enum { T_FREE, T_STOPPED, T_RUNNABLE, T_RUNNING, T_BLOCKED, T_DEAD };
enum { EV_SP = 4, EV_SI = 5, EV_AI = 6, EV_VI = 7, EV_PI = 8, EV_DP = 9, EV_COUNT = 15 };

typedef struct {
  int state;
  u32 guest, id, entry, arg, sp;
  s32 pri;
  u64 seq;
  u32 wait_queue; /* blocked: the queue address */
  int wait_full;  /* blocked: 1 waiting for space, 0 for a message */
  int host_started;
  pthread_t host;
  pthread_cond_t wake;
  u64 r[32], hi, lo, f[32];
  u32 fcc, fcsr, llbit;
  u32 status_global;
  int status_known, ie;
} rt_thread;

typedef struct { u32 mq, msg; int set; } rt_event;
typedef struct { int used; u32 guest, mq, msg; u64 due, interval; } rt_timer;

volatile int plaid_preempt;
static plaid_state *S;
static pthread_mutex_t big = PTHREAD_MUTEX_INITIALIZER;
static rt_thread threads[MAX_THREADS];
static rt_thread *running; /* NULL when every guest thread is blocked */
static rt_thread boot;     /* the pre-thread boot context (main_func) */
static u64 seq_counter;
static int ints_enabled = 1;
static u32 status_kernel_global; /* the SDK copy whose exception vectors are installed */
static rt_event events[EV_COUNT];
static int pending[EV_COUNT]; /* undelivered event counts */
static struct { u32 mq, msg; } pi_completions[64];
static unsigned pi_completion_count;
static u32 pi_status; /* immediate raw ROM DMA: idle plus pending interrupt */
static plaid_pi_bus pi_bus;
static u32 si_status, si_dram, si_read_address, si_write_address;
static plaid_joybus joybus;
static int si_due; /* SI DMA in flight: 1 PIF to RAM, 2 RAM to PIF */
/* After IPL3 the PIF waits for the CPU's terminate-boot bit (pinned ares
   pif/hle.cpp WaitTerminateBoot); osInitialize sends it. */
static int pif_booted;
static int si_finish(void);
static int si_access(u32 p, int write, u64 *value);
static rt_timer timers[MAX_TIMERS];
static u64 compare_due; /* COP0 Compare as a Count deadline (ADR-0199) */
static int compare_armed;
static u8 *rom;
static size_t rom_size;
static u8 eeprom[2048];
/* --sram: the cartridge's SRAM, written back after every write DMA */
#define SRAM_SIZE 0x8000
static u8 sram[SRAM_SIZE];
static const char *sram_path;
static void save_file(const char *path, const u8 *bytes, size_t size);
static int load_file(const char *path, u8 *bytes, size_t size);
static struct timespec t0;
static u64 time_base; /* osSetTime offset in count ticks */
static u32 vi_regs[14], vi_field; /* VI registers as the guest wrote them (ADR-0199) */
static u64 vi_retrace_ns;
static u32 dpc_flags; /* DPC_STATUS without --rsp-gfx: 1 source, 2 freeze, 4 flush, 0x400 start valid */
static int dp_held; /* a graphics task's DP interrupt, held while the RDP is frozen (ADR-0198) */
/* With PLAID_RT64 the runtime links plaid_rt64.dll (runtime/rt64, ADR-0163). */
#ifdef PLAID_RT64
#include "gfx.h"
static int gfx_writeback(void *context, u32 p, u32 n, const u8 *bytes);
int plaid_gfx_open(const u8 *rom_header);
void plaid_gfx_screen(const u32 *regs);
int plaid_gfx_closed(void);
u32 plaid_gfx_input(void); /* buttons << 16 | stick x << 8 | stick y */
void plaid_audio_play(const u8 *samples, u32 bytes, u32 rate); /* big-endian s16 stereo */
#endif
#ifdef PLAID_RSP
/* RSP tasks run lowered microcode (ADR-0169): the IMEM texts that
   runtime/rsp_texts.py lists, null-terminated. */
#include "rsp_state.h"
extern const plaid_rsp_text *const plaid_rsp_texts[];
#ifdef PLAID_RSP_ROM
extern const u32 plaid_rsp_boot_ucode_sizes[];
extern const u8 plaid_rsp_rom_reachable[][128];
extern const u8 plaid_rsp_rom_matchable[]; /* one per indistinguishable group (ADR-0245) */
#endif
static plaid_rsp rsp;
static const char *rsp_dump_dir, *rsp_capture_dir;
static long rsp_capture;
static int rsp_graphics;
#ifdef PLAID_RT64
#include "dpc.h"
static u8 rsp_gfx_dirty[PLAID_RAM_SIZE / 4096];
static int rsp_dpc_consume(u32 current, u32 size, int dmem) {
  if (dmem) {
    u8 commands[4096];
    u32 i;
    if (size > sizeof commands) return 1;
    for (i = 0; i < size; i++) commands[i] = rsp.dmem[(current + i) & 0xfff];
    if (plaid_gfx_rdp(S->ram, commands, size, rsp_gfx_dirty, gfx_writeback, S)) return 1;
  } else {
    if (current > PLAID_RAM_SIZE || size > PLAID_RAM_SIZE - current) return 1;
    if (plaid_gfx_rdp(S->ram, S->ram + current, size, rsp_gfx_dirty, gfx_writeback, S)) return 1;
  }
  memset(rsp_gfx_dirty, 0, sizeof rsp_gfx_dirty);
  return 0;
}
static plaid_dpc rsp_dp = {0, 0, 0, 0x80, rsp_dpc_consume};
static int rsp_dpc(u32 reg, u32 *value, int write) { return plaid_dpc_access(&rsp_dp, reg, value, write); }
#endif
#endif
/* --wav: AI buffers as 16-bit stereo PCM, the header rewritten at exit */
static FILE *wav;
static u32 wav_bytes;
/* AI DMA (ADR-0170), as ares models it: a two-entry FIFO whose head drains
   one 4-byte sample per DAC period, here on the host clock. */
static struct { u32 len[2], count, on, rate; u64 start_ns; u32 addr; } ai = {{0, 0}, 0, 0, 32000, 0, 0};
static void ai_update(void);
static u32 ai_length(void);
static void ai_submit(u32 p, u32 n);
static unsigned long vi_count, gfx_tasks, audio_tasks, dma_count;
static long stop_gfx = 1; /* stop after this many graphics tasks (0: never) */
static double run_seconds = 0;
static u32 dump_at, dump_words;

/* ---- reporting ---------------------------------------------------------- */

static void wav_header(void) {
  u8 h[44] = "RIFF\0\0\0\0WAVEfmt \x10\0\0\0\x01\0\x02\0\0\0\0\0\0\0\0\0\x04\0\x10\0data";
  u32 v[3] = {36 + wav_bytes, ai.rate, ai.rate * 4}, at[3] = {4, 24, 28}, i, k;
  for (k = 0; k < 3; k++)
    for (i = 0; i < 4; i++) h[at[k] + i] = (u8)(v[k] >> (8 * i));
  for (i = 0; i < 4; i++) h[40 + i] = (u8)(wav_bytes >> (8 * i));
  fseek(wav, 0, SEEK_SET);
  fwrite(h, 1, 44, wav);
}
static void finish(int code, const char *why) {
  u32 i, p;
  if (wav) { wav_header(); fclose(wav); wav = NULL; }
  if (dump_words) {
    printf("{\"dump\":\"%08x\",\"words\":[", dump_at);
    for (i = 0; i < dump_words; i++) {
      p = (dump_at & 0x1fffffffu) + 4 * i;
      printf("%s%u", i ? "," : "",
             p + 4 <= PLAID_RAM_SIZE ? (u32)S->ram[p] << 24 | (u32)S->ram[p + 1] << 16 | (u32)S->ram[p + 2] << 8 | S->ram[p + 3] : 0);
    }
    printf("]}\n");
  }
  printf("{\"stop\":\"%s\",\"vi\":%lu,\"gfx_tasks\":%lu,\"audio_tasks\":%lu,\"pi_dma\":%lu,"
         "\"framebuffer\":\"%08x\",\"fault\":%u,\"fault_pc\":\"%08x\",\"ra\":\"%08x\",\"a0\":\"%08x\",\"a1\":\"%08x\",\"a2\":\"%08x\",\"t9\":\"%08x\",\"fcsr\":\"%08x\"",
         why, vi_count, gfx_tasks, audio_tasks, dma_count, vi_regs[1], S->fault, S->fault_pc,
         (u32)S->r[31], (u32)S->r[4], (u32)S->r[5], (u32)S->r[6], (u32)S->r[25], S->fcsr | S->fcc << 23);
  if (S->fault == 7) /* a COP1 fault: the operands are in the FPRs */
    for (i = 0; i < 32; i++) printf("%s%016llx\"", i ? ",\"" : ",\"fpr\":[\"", (unsigned long long)S->f[i]);
  printf("%s,\"gpr\":[", S->fault == 7 ? "]" : "");
  for (i = 0; i < 32; i++) printf("%s\"%08x\"", i ? "," : "", (u32)S->r[i]);
  printf("],\"threads\":[");
  /* id, state (2 runnable, 3 running, 4 blocked), priority, wait queue */
  for (i = 0, p = 0; i < MAX_THREADS; i++)
    if (threads[i].state != T_FREE && threads[i].state != T_DEAD)
      printf("%s[%u,%d,%d,\"%08x\"]", p++ ? "," : "", threads[i].id, threads[i].state, threads[i].pri, threads[i].wait_queue);
  printf("]}\n");
  fflush(stdout);
  exit(code);
}

/* ---- guest memory ------------------------------------------------------- */

static int phys(u32 va, u32 size, u32 *p) {
  if (va < 0x80000000u || va >= 0xc0000000u) return 1;
  *p = va & 0x1fffffffu;
  return *p > PLAID_RAM_SIZE || size > PLAID_RAM_SIZE - *p;
}
static u32 rd32(u32 va) {
  u32 p;
  if (phys(va, 4, &p)) { plaid_fault(S, va, 1); finish(1, "runtime read outside RAM"); }
  return (u32)S->ram[p] << 24 | (u32)S->ram[p + 1] << 16 | (u32)S->ram[p + 2] << 8 | S->ram[p + 3];
}
static void wr(u32 va, const u8 *bytes, u32 size) {
  u32 p;
  if (phys(va, size, &p) || plaid_runtime_write(S, p, size, va)) finish(1, "runtime write refused");
  memcpy(S->ram + p, bytes, size);
}
static void wr32(u32 va, u32 v) {
  u8 b[4] = {(u8)(v >> 24), (u8)(v >> 16), (u8)(v >> 8), (u8)v};
  wr(va, b, 4);
}
static void wr16(u32 va, u32 v) {
  u8 b[2] = {(u8)(v >> 8), (u8)v};
  wr(va, b, 2);
}
static u32 arg(int n) { return n < 4 ? (u32)S->r[4 + n] : rd32((u32)S->r[29] + 4 * n); }
static int ret(u32 v) { S->r[2] = SX32(v); return 0; }
static int ret64(u64 v) { S->r[2] = SX32((u32)(v >> 32)); S->r[3] = SX32((u32)v); return 0; }

/* ---- time --------------------------------------------------------------- */

static u64 now_ns(void) {
  struct timespec t;
  clock_gettime(CLOCK_MONOTONIC, &t);
  return (u64)(t.tv_sec - t0.tv_sec) * 1000000000ull + (u64)t.tv_nsec - (u64)t0.tv_nsec;
}
/* COUNT runs at half the 93.75 MHz CPU clock */
static u64 count_now(void) { return now_ns() * 46875ull / 1000000ull + time_base; }

/* ---- scheduling (caller holds `big`) ------------------------------------ */

static void save(rt_thread *t) {
  memcpy(t->r, S->r, sizeof t->r); memcpy(t->f, S->f, sizeof t->f);
  t->hi = S->hi; t->lo = S->lo; t->fcc = S->fcc; t->fcsr = S->fcsr; t->llbit = S->llbit;
  t->ie = ints_enabled;
  if (t->status_known) {
    u32 global = rd32(status_kernel_global ? status_kernel_global : t->status_global);
    wr32(t->guest + 0x118, status_saved(S->cp0_status, global));
    wr32(t->guest + 0x128, status_saved_mi(S->mi_mask, global, rd32(t->guest + 0x128)));
  }
}
static void restore(const rt_thread *t) {
  memcpy(S->r, t->r, sizeof t->r); memcpy(S->f, t->f, sizeof t->f);
  S->hi = t->hi; S->lo = t->lo; S->fcc = t->fcc; S->fcsr = t->fcsr; S->llbit = t->llbit;
  S->status_known = (u32)t->status_known;
  S->cp0_known &= 1u << 10; /* SDK context switches certify no staging register but EntryHi (ADR-0242). */
  S->fr_mode = 1; /* every runtime thread is a libultra thread: FR = 0 */
  S->status_thread = t->status_known ? t->guest : 0;
  ints_enabled = t->ie;
  if (t->status_known) {
    u32 saved = rd32(t->guest + 0x118), global = rd32(status_kernel_global ? status_kernel_global : t->status_global);
    if (saved & 0x040000fcu) finish(1, "unsupported saved Status mode");
    S->cp0_status = (saved & ~0xff02u) | (saved & global & 0xff00u);
    S->mi_mask = rd32(t->guest + 0x128) & (global >> 16) & 0x3fu;
    ints_enabled = S->cp0_status & 1;
    if (pi_status & 8u) { pending[EV_PI] = 1; plaid_preempt = 1; }
  }
}
static void apply_rounding(void) {
  static const int modes[4] = {FE_TONEAREST, FE_TOWARDZERO, FE_UPWARD, FE_DOWNWARD};
  fesetround(modes[S->fcsr & 3]);
}
static rt_thread *best_runnable(void) {
  rt_thread *b = NULL;
  int i;
  for (i = 0; i < MAX_THREADS; i++) {
    rt_thread *t = &threads[i];
    if (t->state == T_RUNNABLE && (!b || t->pri > b->pri || (t->pri == b->pri && t->seq < b->seq))) b = t;
  }
  return b;
}
static void make_runnable(rt_thread *t) { t->state = T_RUNNABLE; t->seq = ++seq_counter; }
static void *thread_main(void *p);

/* Hand the baton (and S) to `next`, or to nobody. S must already be saved. */
static void hand_to(rt_thread *next) {
  running = next;
  if (!next) return;
  next->state = T_RUNNING;
  restore(next);
  if (!next->host_started) {
    pthread_attr_t a;
    next->host_started = 1;
    pthread_attr_init(&a);
    pthread_attr_setstacksize(&a, 64u << 20); /* -O0 frames of large guest functions */
    if (pthread_create(&next->host, &a, thread_main, next)) finish(1, "pthread_create failed");
    pthread_attr_destroy(&a);
  } else {
    pthread_cond_signal(&next->wake);
  }
}
static void wait_for_baton(rt_thread *self) {
  while (running != self) pthread_cond_wait(&self->wake, &big);
  apply_rounding();
}
/* The running thread gives up the baton (it is runnable, blocked or dead). */
static void yield_from(rt_thread *self, int api_disabled) {
  int previous_ie = ints_enabled;
  if (api_disabled) { ints_enabled = 0; if (S->status_known) S->cp0_status &= ~1u; }
  save(self);
  hand_to(best_runnable());
  if (self->state != T_DEAD && self != &boot) wait_for_baton(self);
  if (api_disabled && self->state != T_DEAD && self != &boot) {
    ints_enabled |= previous_ie;
    if (S->status_known) S->cp0_status |= (u32)previous_ie;
  }
}
static void deliver_pending(void);
/* After making threads runnable: run a strictly higher-priority one now. */
static void maybe_preempt(int api_disabled) {
  rt_thread *b;
  deliver_pending();
  b = best_runnable();
  if (running && b && b->pri > running->pri) {
    rt_thread *self = running;
    make_runnable(self);
    yield_from(self, api_disabled);
  }
}

/* ---- message queues (OSMesgQueue in guest RAM) -------------------------- */
/* mtqueue@0 fullqueue@4 validCount@8 first@0xc msgCount@0x10 msg@0x14 */

static void wake_waiter(u32 mq, int full) {
  rt_thread *b = NULL;
  int i;
  for (i = 0; i < MAX_THREADS; i++) {
    rt_thread *t = &threads[i];
    if (t->state == T_BLOCKED && t->wait_queue == mq && t->wait_full == full &&
        (!b || t->pri > b->pri || (t->pri == b->pri && t->seq < b->seq)))
      b = t;
  }
  if (b) make_runnable(b);
}
static int block_on(u32 mq, int full) {
  rt_thread *self = running;
  if (!self || self == &boot) finish(1, "boot context blocked on a message queue");
  self->state = T_BLOCKED; self->wait_queue = mq; self->wait_full = full;
  self->seq = ++seq_counter;
  yield_from(self, 1);
  return 0;
}
/* jam: put the message at the front. Returns -1 when full and not blocking. */
static int mq_send(u32 mq, u32 msg, int block, int jam) {
  u32 count, valid, first;
  /* PLAID_TRACE_MQ set: every send on stderr, to find a stalled handshake */
  { static long t = -1; if (t < 0) t = getenv("PLAID_TRACE_MQ") ? 1 : 0; if (t) fprintf(stderr, "send %08x %08x vi=%lu ra=%08x\n", mq, msg, vi_count, (u32)S->r[31]); }
  for (;;) {
    valid = rd32(mq + 8); count = rd32(mq + 0x10);
    if (valid < count) break;
    if (!block) return -1;
    block_on(mq, 1);
  }
  first = rd32(mq + 0xc);
  if (jam) {
    first = (first + count - 1) % count;
    wr32(mq + 0xc, first);
    wr32(rd32(mq + 0x14) + 4 * first, msg);
  } else {
    wr32(rd32(mq + 0x14) + 4 * ((first + valid) % count), msg);
  }
  wr32(mq + 8, valid + 1);
  wake_waiter(mq, 0);
  return 0;
}
static int mq_recv(u32 mq, u32 msgp, int block) {
  u32 valid, first;
  for (;;) {
    valid = rd32(mq + 8);
    if (valid) break;
    if (!block) return -1;
    block_on(mq, 0);
  }
  first = rd32(mq + 0xc);
  if (msgp) wr32(msgp, rd32(rd32(mq + 0x14) + 4 * first));
  wr32(mq + 0xc, (first + 1) % rd32(mq + 0x10));
  wr32(mq + 8, valid - 1);
  wake_waiter(mq, 1);
  return 0;
}

/* ---- events ------------------------------------------------------------- */

static void post(int ev) { pending[ev]++; plaid_preempt = 1; }
static int event_eligible(int ev) {
  if (ev == 14 && pending[ev]) finish(1, "PRENMI delivery is outside the cold-start Status ABI");
  /* No running context: the HLE idle dispatcher accepts pending sources;
     a blocked caller's disabled IE does not become the idle CPU's policy. */
  if (!running) return 1;
  if (!ints_enabled) return 0;
  if (!S->status_known) return 1;
  if (S->cp0_status & 6u) return 0;
  if (ev >= EV_SP && ev <= EV_DP)
    return (S->cp0_status & 0x400u) && (S->mi_mask & (1u << (ev - EV_SP)));
  return (S->cp0_status & 0x8000u) != 0; /* Count/Compare timers */
}
static void pi_complete(u32 mq, u32 msg) {
  if (!mq) return;
  if (event_eligible(EV_PI)) { mq_send(mq, msg, 0, 0); return; }
  if (pi_completion_count == 64) finish(1, "too many pending PI completions");
  pi_completions[pi_completion_count].mq = mq;
  pi_completions[pi_completion_count++].msg = msg;
  plaid_preempt = 1;
}
static void deliver_pending(void) {
  int ev, i;
  u64 c;
  plaid_preempt = 0;
  for (ev = 0; ev < EV_COUNT; ev++)
    while (pending[ev] && event_eligible(ev)) {
      if (ev == EV_SI && si_due && si_finish()) finish(1, "SI transfer outside the declared Joybus subset");
      pending[ev]--;
      if (ev == EV_PI) pi_status &= ~8u;
      if (ev == EV_SI) si_status &= ~0x1000u;
      if (events[ev].set) {
        mq_send(events[ev].mq, events[ev].msg, 0, 0);
      }
    }
  if (event_eligible(EV_PI)) {
    unsigned n;
    for (n = 0; n < pi_completion_count; n++)
      mq_send(pi_completions[n].mq, pi_completions[n].msg, 0, 0);
    pi_completion_count = 0;
  }
  if (!event_eligible(10)) return;
  c = count_now();
  for (i = 0; i < MAX_TIMERS; i++) {
    rt_timer *t = &timers[i];
    if (t->used && c >= t->due) {
      if (t->mq) mq_send(t->mq, t->msg, 0, 0);
      if (t->interval) t->due += t->interval; else t->used = 0;
    }
  }
  if (compare_armed && c >= compare_due) { /* the timer interrupt: libultra sends OS_EVENT_COUNTER */
    compare_armed = 0;
    if (events[3].set) mq_send(events[3].mq, events[3].msg, 0, 0);
  }
}
/* Host thread: VI retrace at 60 Hz, timers, and delivery while all block. */
/* About 1 ms. Windows rounds nanosleep up to its ~15.6 ms timer tick, which
   held VI to 33 Hz (ADR-0166); a high-resolution waitable timer does not. */
static void tick_sleep(void) {
  struct timespec d = {0, 1000000};
#ifdef _WIN32
  static HANDLE timer;
  LARGE_INTEGER due;
  if (!timer) timer = CreateWaitableTimerExW(NULL, NULL, CREATE_WAITABLE_TIMER_HIGH_RESOLUTION, TIMER_ALL_ACCESS);
  due.QuadPart = -10000; /* relative, in 100 ns units */
  if (timer && SetWaitableTimer(timer, &due, 0, NULL, NULL, 0) && WaitForSingleObject(timer, INFINITE) == WAIT_OBJECT_0)
    return;
#endif
  nanosleep(&d, NULL);
}
#define VI_PERIOD_NS 16683350ull /* NTSC: 60000/1001 Hz */
static void *event_pump(void *unused) {
  u64 next_vi = VI_PERIOD_NS, now; /* the first retrace is a frame after boot */
  (void)unused;
  for (;;) {
    tick_sleep();
    pthread_mutex_lock(&big);
    now = now_ns();
    if (now >= next_vi) {
      /* fixed deadlines, so sleep jitter does not stretch the period; a host
         stall longer than a frame drops the missed retraces */
      next_vi = now - next_vi < VI_PERIOD_NS ? next_vi + VI_PERIOD_NS : now + VI_PERIOD_NS;
      vi_count++;
      vi_retrace_ns = now;
      if (!(vi_regs[6] & 1)) vi_field ^= 1; /* an interlaced mode alternates fields */
      post(EV_VI);
#ifdef PLAID_RT64
      if (vi_regs[0] & 3) plaid_gfx_screen(vi_regs); /* a color depth: video on */
      if (plaid_gfx_closed()) finish(0, "window closed");
#endif
    }
    ai_update(); /* posts the AI event when the next buffer starts */
    plaid_preempt = 1; /* timers are checked at delivery */
    if (run_seconds > 0 && now_ns() > (u64)(run_seconds * 1e9)) finish(0, "time limit");
    if (!running) { /* every guest thread is blocked: deliver here */
      deliver_pending();
      hand_to(best_runnable());
    }
    pthread_mutex_unlock(&big);
  }
  return NULL;
}

/* ---- guest threads ------------------------------------------------------ */

static rt_thread *thread_of(u32 guest) {
  int i;
  if (!guest) return running;
  for (i = 0; i < MAX_THREADS; i++)
    if (threads[i].state != T_FREE && threads[i].guest == guest) return &threads[i];
  return NULL;
}
static void *thread_main(void *p) {
  rt_thread *self = p;
  int r;
  pthread_mutex_lock(&big);
  wait_for_baton(self);
  pthread_mutex_unlock(&big);
  r = plaid_enter(S, self->entry, THREAD_RETURN);
  pthread_mutex_lock(&big);
  if (r == 2) finish(0, "exit");
  if (r && r != RT_EXIT_THREAD) finish(1, "guest fault");
  self->state = T_DEAD; /* returned from its entry, or destroyed itself */
  yield_from(self, 0);
  pthread_mutex_unlock(&big);
  return NULL;
}
int plaid_rt_safepoint(plaid_state *s) {
  (void)s;
  pthread_mutex_lock(&big);
  maybe_preempt(0);
  pthread_mutex_unlock(&big);
  return 0;
}

/* Every runtime function below runs on the baton holder; LOCKED takes `big`
   so host event sources see consistent scheduler state. */
#define RT(name) static int rt_##name(void); \
  int plaid_rt_##name(plaid_state *s) { int r_; (void)s; pthread_mutex_lock(&big); r_ = rt_##name(); \
    pthread_mutex_unlock(&big); return r_; } \
  static int rt_##name(void)

/* osCreateThread(t, id, entry, arg, sp, pri) */
RT(osCreateThread) {
  int i;
  rt_thread *t = thread_of(arg(0));
  for (i = 0; !t && i < MAX_THREADS; i++)
    if (threads[i].state == T_FREE || threads[i].state == T_DEAD) t = &threads[i];
  if (!t) finish(1, "too many guest threads");
  if (t->host_started) pthread_join(t->host, NULL);
  memset(t, 0, sizeof *t);
  pthread_cond_init(&t->wake, NULL);
  t->state = T_STOPPED; t->guest = arg(0); t->id = arg(1); t->entry = arg(2);
  t->ie = 1;
  t->arg = arg(3); t->sp = arg(4); t->pri = (s32)arg(5);
  /* libultra starts a thread 16 bytes below the given top: the O32 save
     area its entry may store its argument registers into */
  t->r[4] = SX32(t->arg); t->r[29] = SX32(t->sp - 16); t->r[31] = THREAD_RETURN;
  t->fcsr = 0x01000800u; /* libultra's thread FPCSR: FS and the invalid enable */
  wr32(t->guest + 4, (u32)t->pri); wr32(t->guest + 0x14, t->id);
  wr16(t->guest + 0x10, 1); /* OS_STATE_STOPPED */
  return 0;
}
RT(osStartThread) {
  rt_thread *t = thread_of(arg(0));
  if (!t) finish(1, "osStartThread on an unknown thread");
  if (t->state == T_STOPPED) make_runnable(t);
  wr16(t->guest + 0x10, 2); /* OS_STATE_RUNNABLE */
  if (running == &boot) { /* the boot context ends here, as in libultra */
    boot.state = T_DEAD;
    yield_from(&boot, 1);
    pthread_mutex_unlock(&big);
    for (;;) { struct timespec d = {3600, 0}; nanosleep(&d, NULL); }
  }
  maybe_preempt(1);
  return 0;
}
RT(osDestroyThread) {
  rt_thread *t = thread_of(arg(0));
  if (!t) return 0;
  if (t == running) return RT_EXIT_THREAD;
  t->state = T_DEAD;
  return 0;
}
RT(osSetThreadPri) {
  rt_thread *t = thread_of(arg(0));
  if (!t) return 0;
  t->pri = (s32)arg(1);
  if (t->guest) wr32(t->guest + 4, (u32)t->pri);
  if (t == running) {
    rt_thread *b = best_runnable();
    if (b && b->pri > t->pri) { make_runnable(t); yield_from(t, 1); }
  } else {
    maybe_preempt(1);
  }
  return 0;
}
/* The caller queues behind the runnable threads of its own priority. */
RT(osYieldThread) {
  rt_thread *self = running, *b;
  deliver_pending();
  b = best_runnable();
  if (self && b && b->pri >= self->pri) { make_runnable(self); yield_from(self, 1); }
  return 0;
}
RT(osGetThreadId) { rt_thread *t = thread_of(arg(0)); return ret(t ? t->id : 0); }
RT(osStopThread) {
  rt_thread *t = thread_of(arg(0));
  if (!t) return 0;
  if (t->state == T_BLOCKED) finish(1, "osStopThread on a blocked thread is not modeled");
  if (t->guest) wr16(t->guest + 0x10, 1); /* OS_STATE_STOPPED */
  if (t == running) { t->state = T_STOPPED; yield_from(t, 1); }
  else if (t->state == T_RUNNABLE) t->state = T_STOPPED;
  return 0;
}
RT(osGetThreadPri) { rt_thread *t = thread_of(arg(0)); return ret(t ? (u32)t->pri : 0); }
RT(osCreateMesgQueue) {
  u32 mq = arg(0);
  wr32(mq, 0); wr32(mq + 4, 0); wr32(mq + 8, 0); wr32(mq + 0xc, 0);
  wr32(mq + 0x10, arg(2)); wr32(mq + 0x14, arg(1));
  return 0;
}
RT(osSendMesg) { int r = mq_send(arg(0), arg(1), arg(2) & 1, 0); maybe_preempt(1); return ret((u32)r); }
RT(osJamMesg) { int r = mq_send(arg(0), arg(1), arg(2) & 1, 1); maybe_preempt(1); return ret((u32)r); }
RT(osRecvMesg) { int r = mq_recv(arg(0), arg(1), arg(2) & 1); maybe_preempt(1); return ret((u32)r); }
RT(osSetEventMesg) {
  u32 ev = arg(0);
  if (getenv("PLAID_TRACE_MQ")) fprintf(stderr, "event %u %08x %08x\n", ev, arg(1), arg(2));
  if (ev < EV_COUNT) { events[ev].mq = arg(1); events[ev].msg = arg(2); events[ev].set = 1; }
  return 0;
}
/* Interrupt masking: while disabled, events stay pending. */
RT(__osDisableInt) { u32 was = (u32)ints_enabled; ints_enabled = 0; if (S->status_known) S->cp0_status &= ~1u; return ret(was); }
RT(__osRestoreInt) { ints_enabled |= arg(0) & 1; if (S->status_known) S->cp0_status |= arg(0) & 1; if (ints_enabled) maybe_preempt(0); return 0; }
RT(osSetIntMask) { return ret(0x003fff01u); }
RT(osGetIntMask) { return ret(0x003fff01u); } /* the same unmasked OS_IM_ALL */
/* Cause's interrupt-pending bits from undelivered events (ADR-0260): RCP
   events raise IP2, the counter IP7, pre-NMI IP4; no exception is in progress.
   shortcut: events, not raw MI_INTR state; upgrade when MI_INTR is modelled raw. */
RT(__osGetCause) {
  u32 cause = 0;
  int ev;
  for (ev = EV_SP; ev <= EV_DP; ev++) if (pending[ev]) cause |= 0x400u;
  if (pending[3]) cause |= 0x8000u;
  if (pending[14]) cause |= 0x1000u;
  return ret(cause);
}
RT(__osGetSR) {
  if (!S->status_known) return plaid_fault(S, (u32)S->r[31] - 8, 11);
  return ret(S->cp0_status);
}
int plaid_rt_osCreateThread_global(plaid_state *s, u32 global) {
  rt_thread *t;
  int result;
  (void)s;
  pthread_mutex_lock(&big);
  result = rt_osCreateThread();
  t = thread_of(arg(0));
  t->status_known = 1;
  t->status_global = global;
  wr32(t->guest + 0x118, 0xff03u); /* verified SDK create, before ERET */
  wr32(t->guest + 0x128, 0x3fu);
  wr32(t->guest + 0x18, 0);
  pthread_mutex_unlock(&big);
  return result;
}
int plaid_rt_osSetIntMask_global(plaid_state *s, u32 global_address) {
  u32 global, old;
  int result;
  (void)s;
  pthread_mutex_lock(&big);
  if (!S->status_known) {
    result = plaid_fault(S, (u32)S->r[31] - 8, 11);
  } else {
    global = rd32(global_address);
    old = status_old_mask(S->cp0_status, S->mi_mask, global);
    status_set_mask(&S->cp0_status, &S->mi_mask, arg(0), global);
    result = ret(old);
    maybe_preempt(0);
  }
  pthread_mutex_unlock(&big);
  return result;
}

/* ---- time --------------------------------------------------------------- */

RT(osGetTime) { return ret64(count_now()); }
RT(osGetCount) { return ret((u32)count_now()); }
RT(osSetTime) { time_base = ((u64)arg(0) << 32 | arg(1)) - (count_now() - time_base); return 0; }
/* __osSetCompare(value) writes COP0 Compare: the interrupt comes when Count
   next equals it, a full wrap away if it equals Count now */
RT(__osSetCompare) {
  u64 c = count_now();
  u32 left = arg(0) - (u32)c;
  compare_due = c + (left ? left : 0x100000000ull);
  compare_armed = 1;
  return 0;
}
/* osSetTimer(t, countdown (a2:a3), interval (sp+16:sp+20), mq, msg) */
RT(osSetTimer) {
  int i;
  u64 countdown = (u64)arg(2) << 32 | arg(3), interval = (u64)arg(4) << 32 | arg(5);
  for (i = 0; i < MAX_TIMERS; i++)
    if (!timers[i].used || timers[i].guest == arg(0)) break;
  if (i == MAX_TIMERS) finish(1, "too many timers");
  timers[i].used = 1; timers[i].guest = arg(0); timers[i].mq = arg(6); timers[i].msg = arg(7);
  timers[i].interval = interval;
  timers[i].due = count_now() + (countdown ? countdown : interval);
  return ret(0);
}

/* osStopTimer(t): -1 when the timer is not active, as in libultra */
RT(osStopTimer) {
  int i;
  for (i = 0; i < MAX_TIMERS; i++)
    if (timers[i].used && timers[i].guest == arg(0)) { timers[i].used = 0; return ret(0); }
  return ret((u32)-1);
}

/* ---- system ------------------------------------------------------------- */

/* Guest structures the runtime owns live above the 4 MiB osMemSize reports. */
/* Runtime-owned PI handles. Lowered code never runs libultra's exception
   preamble, so this page between the vectors and the boot globals is free;
   the top of RAM is not, since a game that sees 8 MiB puts framebuffers there. */
#define RT_RAM 0x80000200u
/* An Expansion Pak is installed: the 8 MiB the model has */
RT(osGetMemSize) { return ret(PLAID_RAM_SIZE); }

RT(osInitialize) {
  pif_booted = 1;
  if (S->status_known) S->cp0_status |= 0x20000000u;
  if (plaid_ctc1(S, 0x01000800u, (u32)S->r[31])) return 1;
  wr32(0x80000300u, 1);           /* osTvType: NTSC */
  wr32(0x80000304u, 0);           /* osRomType: cartridge */
  wr32(0x80000308u, 0xb0000000u); /* osRomBase */
  wr32(0x8000030cu, 0);           /* osResetType: cold */
  wr32(0x80000318u, PLAID_RAM_SIZE); /* osMemSize */
  return 0;
}
int plaid_rt_osInitialize_global(plaid_state *s, u32 global) {
  int result;
  (void)s;
  pthread_mutex_lock(&big);
  result = rt_osInitialize();
  status_kernel_global = global;
  pthread_mutex_unlock(&big);
  return result;
}
/* libultra 2.0K+ splits osInitialize; the common part is the whole effect here */
RT(__osInitialize_common) { return rt_osInitialize(); }
static int nop(void) { return 0; }
/* No Voice Recognition Unit is attached: every call is CONT_ERR_NO_CONTROLLER */
#define NO_VRU(name) RT(name) { return ret(1); }
NO_VRU(osVoiceInit) NO_VRU(osVoiceSetWord) NO_VRU(osVoiceCheckWord) NO_VRU(osVoiceClearDictionary)
NO_VRU(osVoiceMaskDictionary) NO_VRU(osVoiceStartReadData) NO_VRU(osVoiceStopReadData)
NO_VRU(osVoiceGetReadData) NO_VRU(osVoiceControlGain)
#define NOP(name) RT(name) { return nop(); }
NOP(osCreatePiManager) NOP(osInvalICache) NOP(osSpTaskYield)
/* The TLB as libultra's osMapTLB writes it (ADR-0162): 4 KiB-aligned even
   and odd pages, noncoherent cached, dirty and valid; -1 leaves a page invalid.
   Lowered code models global entries only, so an ASID is refused. */
static u32 tlb_lo(u32 paddr) { return paddr == 0xffffffffu ? 1 : (paddr >> 6) | 0x18 | 4 | 2 | 1; }
RT(osMapTLB) {
  u32 pm = arg(1);
  if (arg(5) != 0xffffffffu) finish(1, "osMapTLB with an ASID");
  return plaid_tlb_write(S, arg(0), (plaid_tlb_entry){pm, arg(2) & ~(pm | 0x1fffu), {tlb_lo(arg(3)), tlb_lo(arg(4))}}, S->pc);
}
RT(osUnmapTLBAll) { /* EntryHi in KSEG0 never matches a mapped address */
  return plaid_tlb_clear(S, S->pc);
}
RT(osUnmapTLB) {
  /* The SDK invalidates this indexed entry with a KSEG0 EntryHi and zero
     EntryLo values. Its PageMask cannot affect any supported mapped access. */
  return plaid_tlb_write(S, arg(0), (plaid_tlb_entry){0, 0x80000000u, {0, 0}}, S->pc);
}
RT(osSpTaskYielded) { return ret(0); }
RT(__osSpSetPc) { return ret(0); }
/* VI registers, as pinned ares vi/io.cpp (ADR-0199): libultra's own VI
   manager and osVi* functions run as guest code and program them, and the
   retrace is the VI interrupt. VI_V_CURRENT counts lines from the VI_V_INTR
   line by host time; a field has the lines ares counts for VI_V_SYNC.
   shortcut: the interrupt follows the NTSC period, not the programmed timing. */
static const u32 vi_mask[14] = {0xffffu, 0xffffffu, 0xfffu, 0x3ffu, 0, 0x3fffffffu, 0x3ffu, 0x1f0fffu,
                                0x0fff0fffu, 0x03ff03ffu, 0x03ff03ffu, 0x03ff03ffu, 0x0fff0fffu, 0x0fff0fffu};
static u32 vi_line(void) {
  u32 half = vi_regs[6], lines = half >= vi_field ? (half - vi_field) / 2 + 1 : 1;
  u64 into = vi_retrace_ns ? now_ns() - vi_retrace_ns : 0;
  u32 line = (u32)(((vi_regs[3] >> 1) + into * lines / VI_PERIOD_NS) % lines);
  return (line << 1 | vi_field) & 0x3ffu;
}
static u32 v2p(u32 a) {
  u32 p;
  u8 seg;
  if (a >= 0x80000000u && a < 0xc0000000u) return a & 0x1fffffffu;
  return plaid_tlb(S, a, 0, &p, &seg) ? 0xffffffffu : p;
}
RT(osVirtualToPhysical) { return ret(v2p(arg(0))); }

/* ---- D-cache maintenance (ADR-0183) --------------------------------------
   Lowered code never runs CACHE, so these calls are the only maintenance.
   RAM already holds every store; the tags say which lines may differ from
   hardware (see plaid_addr). */
#define DCACHE_SIZE 0x2000u
/* The slot caching va's line, or -1 (libultra's Hit operations by address) */
static int dslot(u32 va) {
  u32 i = (va >> 4) & 0x1ffu, p = v2p(va);
  return p < PLAID_RAM_SIZE && S->dtag[i] == ((p & ~0xfffu) | 1) ? (int)i : -1;
}
static void write_back_slot(int i) { if (S->dtag[i]) plaid_dwriteback(S, i); }
static void dcache_all(void) { /* Index Writeback Invalidate D over every line */
  int i;
  for (i = 0; i < 512; i++) write_back_slot(i);
  memset(S->dtag, 0, sizeof S->dtag); memset(S->dstale, 0, sizeof S->dstale);
  memset(S->ddirty, 0, sizeof S->ddirty);
}
RT(osWritebackDCache) {
  u32 va = arg(0), n = arg(1), a;
  int i;
  if ((s32)n <= 0) return 0;
  if (n >= DCACHE_SIZE) { dcache_all(); return 0; }
  for (a = va & ~15u; a < va + n; a += 16)
    if ((i = dslot(a)) >= 0) write_back_slot(i);
  return 0;
}
RT(osWritebackDCacheAll) { dcache_all(); return 0; }
/* libultra writes back and invalidates partly covered lines and discards
   whole ones; a discarded store stays in RAM here but not on hardware, so
   its line is lost until DMA rewrites all of it */
RT(osInvalDCache) {
  u32 va = arg(0), n = arg(1), a;
  int i;
  if ((s32)n <= 0) return 0;
  if (n >= DCACHE_SIZE) { dcache_all(); return 0; }
  for (a = va & ~15u; a < va + n; a += 16)
    if ((i = dslot(a)) >= 0) {
      if (a >= va && a + 16 <= va + n) { if (S->ddirty[i]) S->line_lost[v2p(a) >> 4] = 1; }
      else write_back_slot(i);
      S->dtag[i] = 0; S->ddirty[i] = 0; S->dstale[i] = 0;
    }
  return 0;
}
/* DMA bypasses the D-cache: it reads RAM, which a dirty resident line has
   not reached on hardware, and leaves a resident line older than RAM.
   dma_wrote runs before the bytes change, to keep the cached copy. */
static void dma_read(u32 p, u32 n) {
  u32 l;
  int i;
  for (l = p >> 4; n && l <= (p + n - 1) >> 4 && l < PLAID_RAM_SIZE / 16; l++)
    if (S->line_lost[l] || ((i = plaid_dresident(S, l << 4)) >= 0 && S->ddirty[i]))
      finish(1, "DMA reads RAM that differs from hardware's");
}
static void dma_wrote(u32 p, u32 n) {
  u32 l;
  int i;
  for (l = p >> 4; n && l <= (p + n - 1) >> 4 && l < PLAID_RAM_SIZE / 16; l++) {
    if (l << 4 >= p && (u64)(l << 4) + 16 <= (u64)p + n) S->line_lost[l] = 0;
    if ((i = plaid_dresident(S, l << 4)) >= 0) {
      u32 lo = l << 4 > p ? 0 : p & 15, hi = (u64)(l << 4) + 16 <= (u64)p + n ? 16 : (p + n) & 15;
      plaid_dstale(S, i, l << 4, (u16)(((1u << (hi - lo)) - 1) << lo));
    }
  }
}
/* The PI writes the physical RAM libultra names with osVirtualToPhysical, so
   a TLB-mapped destination lands on its mapped page (ADR-0224). */
static void dma_wr(u32 va, const u8 *bytes, u32 n) {
  u32 p = v2p(va);
  if (p > PLAID_RAM_SIZE || n > PLAID_RAM_SIZE - p || plaid_runtime_write(S, p, n, va)) finish(1, "runtime write refused");
  if (n) dma_wrote(p, n);
  memcpy(S->ram + p, bytes, n);
}
#ifdef PLAID_RT64
/* A completed renderer readback bypasses D-cache, just like device DMA. */
static int gfx_writeback(void *context, u32 p, u32 n, const u8 *bytes) {
  plaid_state *s = (plaid_state *)context;
  if (plaid_runtime_write(s, p, n, 0)) return 1;
  if (n) { dma_wrote(p, n); memcpy(s->ram + p, bytes, n); }
  return 0;
}
#endif
RT(__osSetFpcCsr) {
  u32 was = S->fcsr | S->fcc << 23;
  if (plaid_status_cop1(S, (u32)S->r[31] - 8)) return 1;
  if (plaid_ctc1(S, arg(0), (u32)S->r[31])) return 1;
  return ret(was);
}

/* ---- PI DMA ------------------------------------------------------------- */

/* libultra's PI DMA addresses the cartridge at K1_TO_PHYS(osRomBase | devAddr) */
static u32 pi_rom_offset(u32 dev, u32 n) {
  u32 p = (rd32(0x80000308u) | dev) & 0x1fffffffu;
  if (p < 0x10000000u || (u64)(p - 0x10000000u) + n > rom_size) finish(1, "PI DMA outside the ROM");
  return p - 0x10000000u;
}
/* osPiStartDma(mb, pri, direction, devAddr, vAddr, nbytes, mq) */
RT(osPiStartDma) {
  u32 mb = arg(0), dir = arg(2), dev = arg(3), va = arg(4), n = arg(5), mq = arg(6);
  if (dir != 0) finish(1, "PI write to cartridge");
  dma_wr(va, rom + pi_rom_offset(dev, n), n);
  dma_count++;
  pi_complete(mq, mb);
  maybe_preempt(1);
  return ret(0);
}
/* osCartRomInit(): the cartridge's OSPiHandle, with the PI domain 1 timing
   libultra reads at boot and base address 0xb0000000 */
RT(osCartRomInit) {
  u32 h = RT_RAM;
  u8 timing[6] = {0, 0x40, 0x07, 0x03, 0x12, 0}; /* type, latency, page, release, pulse, domain */
  wr32(h, 0); wr(h + 4, timing, 6); wr32(h + 0xc, 0xb0000000u); wr32(h + 0x10, 0);
  return ret(h);
}
/* ---- RCP memory and registers (ADR-0177) ------------------------------- */

/* Uncached CPU words in SP memory and the PI registers, as pinned ares
   (rsp/io.cpp, pi/io.cpp). A native build starts SP memory as the ROM's
   own IPL3 leaves it in pinned ares (PLAID_SP_BOOT, ADR-0195); otherwise
   the PIF leaves ROM 0x40-0xfff in DMEM. The header's domain 1 timing is
   in the PI. A task the runtime completes without
   running its microcode leaves SP memory unknown, and reading it then
   fails closed. PI DMA here completes before the caller resumes, so the
   status reads idle. On the PI bus the cartridge ROM reads as itself and
   the 64DD, declared absent, as open bus. Register-driven DMA, bus writes
   and other devices (SRAM, FlashRAM) fault. */
#ifdef PLAID_RSP
#define DMEM rsp.dmem
#define IMEM rsp.imem
#else
static u8 DMEM[4096], IMEM[4096];
#endif
static int sp_unknown;
static u32 pi_bsd[8]; /* DOM1 LAT PWD PGS RLS, DOM2 LAT PWD PGS RLS */
static const u32 pi_bsd_mask[8] = {0xff, 0xff, 0xf, 0x3, 0xff, 0xff, 0xff, 0xff};
#ifdef PLAID_SP_BOOT
#include PLAID_SP_BOOT
#endif
#ifdef PLAID_RAM_BOOT
#include PLAID_RAM_BOOT
_Static_assert(sizeof plaid_ram_boot == 0x400, "post-IPL RDRAM prefix must contain 0x400 bytes");
#endif
static void io_boot(void) {
  u32 c = rom[0] << 24 | rom[1] << 16 | rom[2] << 8 | rom[3];
#ifdef PLAID_RAM_BOOT
  /* The IPL3 vector/boot-parameter prefix is data the game may still read.
     This does not initialize higher RDRAM or certify all post-IPL state. */
  memcpy(S->ram, plaid_ram_boot, sizeof plaid_ram_boot);
#endif
#ifdef PLAID_SP_BOOT
  memcpy(DMEM, plaid_sp_boot, 0x1000); memcpy(IMEM, plaid_sp_boot + 0x1000, 0x1000);
#else
  memcpy(DMEM + 0x40, rom + 0x40, 0xfc0);
#endif
  pi_bsd[0] = c & 0xff; pi_bsd[1] = c >> 8 & 0xff; pi_bsd[2] = c >> 16 & 0xf; pi_bsd[3] = c >> 20 & 0x3;
}
/* ---- FlashRAM (ADR-0183) -------------------------------------------------
   Domain 2 holds SRAM until a command reaches the FlashRAM register at
   0x08010000; from then on it is a 128 KiB Macronix FlashRAM as pinned ares
   models it (cartridge/flash.cpp, ares' default MX29L1101 when the model is
   unknown: byte indexed, two D2 commands to enter status mode, a stale
   first status read). Erase and program complete at once: an infinitely
   fast chip, whose busy status is never seen. */
#define FLASH_SIZE 0x20000
static u8 flash[FLASH_SIZE];
static const char *flash_path;
static struct {
  int on, mode, erase_setup, erase_sector, stale, pending_d2, cir_valid, burst;
  u32 offset;
  u16 cir_high, stale_value;
  u8 status, page[128];
} fl;
enum { FL_ARRAY, FL_STATUS, FL_ID, FL_PAGE };
static void flash_power(void) {
  memset(&fl, 0, sizeof fl);
  fl.status = 0x80 | 3 << 2; /* write state machine ready; macronix ok bits */
  memset(fl.page, 0xff, sizeof fl.page);
}
static void flash_address(u32 p) { fl.offset = p - 0x08000000u; fl.cir_valid = 0; fl.burst = 0; }
static u16 flash_read_half(void) {
  static const u16 id[4] = {0x1111, 0x8001, 0x00c2, 0x001d};
  u16 d;
  if ((fl.mode == FL_STATUS || fl.mode == FL_ID) && (fl.offset & 0x20000u)) finish(1, "FlashRAM open bus");
  if (fl.mode == FL_STATUS && fl.stale) { fl.stale = 0; d = fl.stale_value; }
  else if (fl.mode == FL_STATUS) d = fl.status;
  else if (fl.mode == FL_ID) d = id[fl.burst & 3];
  else if (fl.mode == FL_PAGE) d = (u16)(fl.page[fl.offset & 0x7e] << 8 | fl.page[(fl.offset & 0x7e) + 1]);
  else d = fl.offset + 1 < FLASH_SIZE ? (u16)(flash[fl.offset & ~1u] << 8 | flash[(fl.offset & ~1u) + 1]) : 0;
  fl.stale_value = d; fl.offset += 2; fl.burst++;
  return d;
}
static void flash_command(u32 data) {
  u32 i, base;
  u8 cmd = (u8)(data >> 24);
  if (cmd == 0xd2 && !fl.pending_d2) { fl.pending_d2 = 1; return; }
  fl.pending_d2 = 0;
  switch (cmd) {
  case 0x3c: fl.erase_setup = 1; break;
  case 0x4b: fl.erase_setup = 2; fl.erase_sector = (int)((data & 0x3ff) >> 7); break;
  case 0x78:
    if (!fl.erase_setup) break;
    base = fl.erase_setup == 1 ? 0 : (u32)fl.erase_sector << 14;
    memset(flash + base, 0xff, fl.erase_setup == 1 ? FLASH_SIZE : 0x4000);
    fl.erase_setup = 0; fl.mode = FL_STATUS; fl.stale = 1;
    save_file(flash_path, flash, FLASH_SIZE);
    break;
  case 0xa5:
    base = (data & 0x3ff) << 7;
    for (i = 0; i < 128; i++) flash[base + i] &= fl.page[i];
    memset(fl.page, 0xff, sizeof fl.page);
    fl.mode = FL_STATUS; fl.stale = 1;
    save_file(flash_path, flash, FLASH_SIZE);
    break;
  case 0xb4: fl.mode = FL_PAGE; break;
  case 0xd2: fl.mode = FL_STATUS; fl.stale = 1; break;
  case 0xe1: fl.mode = FL_ID; break;
  case 0xf0: fl.mode = FL_ARRAY; break;
  default: finish(1, "unknown FlashRAM command");
  }
}
static void flash_write_half(u16 d) {
  u32 o = fl.offset & ~1u;
  if (o == 0x10000u || o == 0x10002u) {
    fl.offset += 2;
    if (!fl.cir_valid) { fl.cir_high = d; fl.cir_valid = 1; return; }
    fl.cir_valid = 0;
    if (!fl.on) { fl.on = 1; if (flash_path && load_file(flash_path, flash, FLASH_SIZE)) finish(1, "not a 128 KiB FlashRAM save"); }
    flash_command((u32)fl.cir_high << 16 | d);
    return;
  }
  if (fl.mode == FL_STATUS && o == 0 && d == 0) fl.status |= 3 << 2;
  if (fl.mode == FL_PAGE) { fl.page[o & 0x7f] = (u8)(d >> 8); fl.page[(o & 0x7f) + 1] = (u8)d; }
  fl.offset += 2;
}

static int rt_io(plaid_state *s, u32 p, u32 size, int write, u64 *v) {
  (void)s;
  if (size != 4) return 1;
  if (!write && p >= 0x05000000u && p < 0x1fc00000u) {
    u32 value;
    u64 due = pi_bus.due;
    if (plaid_pi_bus_read_pending(&pi_bus, count_now(), &value)) {
      while (count_now() < due) {} /* ares readWord steps the remaining write clocks */
      *v = (u64)(s64)(s32)value; return 0;
    }
  }
  if ((p >= 0x04800000u && p < 0x04800020u) || (p >= 0x1fc007c0u && p < 0x1fc00800u))
    return si_access(p, write, v);
  if (p >= 0x08000000u && p < 0x10000000u && (fl.on || (write && (p & ~3u) == 0x08010000u))) {
    flash_address(p);
    if (write) { flash_write_half((u16)(*v >> 16)); flash_write_half((u16)*v); }
    else { u32 hi = flash_read_half(); *v = (u64)(s64)(s32)(hi << 16 | flash_read_half()); }
    return 0;
  }
  if (p < 0x04002000u) {
    u8 *m = (p & 0x1000u ? IMEM : DMEM) + (p & 0xfffu);
    if (!write) {
      if (sp_unknown) return 1;
      *v = (u64)(s64)(s32)(m[0] << 24 | m[1] << 16 | m[2] << 8 | m[3]);
      return 0;
    }
    m[0] = (u8)(*v >> 24); m[1] = (u8)(*v >> 16); m[2] = (u8)(*v >> 8); m[3] = (u8)*v;
#ifdef PLAID_RSP
    if (p & 0x1000u) rsp.imem_gen++;
#endif
    return 0;
  }
  if (p >= 0x04100000u && p < 0x04100020u) { /* DPC registers, as ares rdp/io.cpp; RT64 draws, so the DP is
                                                  never busy and a command list is consumed when its end is written */
    if (write && (p & 0x1fu) == 0x0cu && (*v & 4) && dp_held) { dp_held = 0; post(EV_DP); } /* the thaw */
#if defined(PLAID_RSP) && defined(PLAID_RT64)
    if (rsp_graphics) {
      u32 value = (u32)*v;
      /* CPU command submissions may follow CPU texture writes between tasks. */
      if (write) memset(rsp_gfx_dirty, 1, sizeof rsp_gfx_dirty);
      int result = rsp_dpc((p & 0x1fu) >> 2, &value, write);
      if (!write) *v = value;
      return result;
    }
#endif
    static u32 start, current;
    u32 r = (p & 0x1fu) >> 2, d = (u32)*v;
    if (!write) {
      *v = r == 0 ? start : r == 1 || r == 2 ? current : r == 3 ? dpc_flags | 0x80u : 0;
      return 0;
    }
    if (r == 0) { if (!(dpc_flags & 0x400u)) start = d & 0xfffff8u; dpc_flags |= 0x400u; }
    else if (r == 1) { current = d & 0xfffff8u; dpc_flags &= ~0x400u; }
    else if (r == 3) {
      if (d & 1) dpc_flags &= ~1u;
      if (d & 2) dpc_flags |= 1u;
      if (d & 4) dpc_flags &= ~2u;
      if (d & 8) dpc_flags |= 2u;
      if (d & 16) dpc_flags &= ~4u;
      if (d & 32) dpc_flags |= 4u;
    }
    return 0;
  }
  if (p == 0x04600010u) { /* DMA completes immediately; interrupt acknowledgment remains visible. */
    if (!write) *v = pi_status | (plaid_pi_bus_busy(&pi_bus, count_now()) ? 2u : 0u);
    else if (*v & 2) { pi_status &= ~8u; pending[EV_PI] = 0; }
    return 0;
  }
  if (p >= 0x04600014u && p <= 0x04600030u) {
    u32 k = (p - 0x04600014u) >> 2;
    if (write) pi_bsd[k] = (u32)*v & pi_bsd_mask[k];
    else *v = pi_bsd[k];
    return 0;
  }
  if (p >= 0x04400000u && p < 0x04500000u) { /* VI registers, mirrored every 0x40 bytes */
    u32 r = (p & 0x3fu) >> 2;
    if (!write) *v = r == 4 ? vi_line() : r < 14 ? vi_regs[r] : 0;
    else if (r == 4) pending[EV_VI] = 0; /* VI_V_CURRENT: acknowledges the interrupt */
    else if (r < 14) vi_regs[r] = (u32)*v & vi_mask[r];
    return 0;
  }
  if (p >= 0x04500000u && p < 0x04600000u) { /* AI registers, as ares ai/io.cpp */
    u32 r = (p & 0x1fu) >> 2;
    ai_update();
    if (!write) {
      *v = r == 3 ? (ai.count > 1 ? 0x80000001u : 0) | (ai.count ? 0x40000000u : 0) | ai.on << 25 | 1u << 24 | 1u << 20
                  : ai_length() & 0x3ffffu;
      return 0;
    }
    if (r == 0 && ai.count < 2) ai.addr = (u32)*v & 0xfffff8u;
    else if (r == 1 && ai.count < 2) ai_submit(ai.addr, (u32)*v & 0x3fff8u);
    else if (r == 2) {
      if (!ai.on && (*v & 1)) ai.start_ns = now_ns();
      ai.on = (u32)*v & 1;
    } else if (r == 4) ai.rate = 48681812u / (((u32)*v & 0x3fffu) + 1); /* NTSC VI clock / (rate + 1) */
    return 0; /* AI_STATUS write: the interrupt is an event here; AI_BITRATE: 16-bit output */
  }
  /* Read-only cartridge space still changes the PI latch and busy deadline. */
  if (write && p >= 0x10000000u && p < 0x1fc00000u) { plaid_pi_bus_write(&pi_bus, (u32)*v, count_now()); return 0; }
  if (write) return 1;
  if (p >= 0x05000000u && p < 0x08000000u) { /* no device: the address's low half twice (pi/bus.hpp) */
    *v = (u64)(s64)(s32)((p & 0xfffeu) << 16 | (p & 0xfffeu));
    return 0;
  }
  if (p >= 0x10000000u && (u64)(p - 0x10000000u) + 4 <= rom_size) {
    u8 *m = rom + (p - 0x10000000u);
    *v = (u64)(s64)(s32)(m[0] << 24 | m[1] << 16 | m[2] << 8 | m[3]);
    return 0;
  }
  return 1;
}

RT(osPiGetStatus) {
  u64 value = 0;
  if (rt_io(S, 0x04600010u, 4, 0, &value)) return plaid_fault(S, (u32)S->r[31] - 8, 1);
  return ret((u32)value);
}
RT(osPiRawStartDma) {
  u32 direction = arg(0), offset = arg(1), destination = arg(2), size = arg(3);
  if (direction != 0) finish(1, "PI write to cartridge");
  if (!size || ((offset | destination | size) & 7u)) finish(1, "unaligned raw PI DMA is not modeled");
  dma_wr(destination, rom + pi_rom_offset(offset, size), size);
  dma_count++;
  pi_status |= 8u;
  if (S->status_known) { pending[EV_PI] = 1; plaid_preempt = 1; }
  return ret(0);
}

/* osEPiStartDma(handle, mb, direction): the OSIoMesg holds the queue at +4,
   the RAM address at +8, the device offset at +0xc and the size at +0x10 */
/* One handle DMA: direction 0 reads the device into RAM at va */
static void epi_dma(u32 h, u32 dir, u32 dev, u32 va, u32 n) {
  u32 base = rd32(h + 0xc) & 0x1fffffffu, p;
  if (base == 0x08000000u && fl.on) {
    flash_address(((base | dev) & 0x1fffffffu));
    p = v2p(va);
    if (p > PLAID_RAM_SIZE || n > PLAID_RAM_SIZE - p || (n & 1)) finish(1, "FlashRAM DMA outside RAM");
    if (dir == 0) {
      u32 i;
      dma_wrote(p, n);
      for (i = 0; i < n; i += 2) { u16 d = flash_read_half(); S->ram[p + i] = (u8)(d >> 8); S->ram[p + i + 1] = (u8)d; }
    } else {
      u32 i;
      dma_read(p, n);
      for (i = 0; i < n; i += 2) flash_write_half((u16)(S->ram[p + i] << 8 | S->ram[p + i + 1]));
    }
  } else if (base == 0x08000000u) { /* SRAM: 32 KiB, byte addressed, on PI domain 2 */
    dev = ((base | dev) & 0x1fffffffu) - 0x08000000u; /* libultra ORs the handle base in */
    if ((u64)dev + n > SRAM_SIZE) finish(1, "PI DMA outside SRAM");
    if (dir == 0) dma_wr(va, sram + dev, n);
    else {
      p = v2p(va);
      if (p > PLAID_RAM_SIZE || n > PLAID_RAM_SIZE - p) finish(1, "SRAM DMA outside RAM");
      dma_read(p, n);
      memcpy(sram + dev, S->ram + p, n);
      save_file(sram_path, sram, SRAM_SIZE);
    }
  } else {
    if (base != 0x10000000u) finish(1, "PI DMA through a non-cartridge handle");
    if (dir != 0) finish(1, "PI write to cartridge");
    dev = ((base | dev) & 0x1fffffffu) - 0x10000000u; /* libultra ORs the handle base in; a full cart address is the same */
    if ((u64)dev + n > rom_size) finish(1, "PI DMA outside the ROM");
    dma_wr(va, rom + dev, n);
  }
  dma_count++;
}
RT(osEPiStartDma) {
  u32 mb = arg(1), mq = rd32(mb + 4);
  epi_dma(arg(0), arg(2), rd32(mb + 0xc), rd32(mb + 8), rd32(mb + 0x10));
  pi_complete(mq, mb);
  maybe_preempt(1);
  return ret(0);
}
/* osEPiRawStartDma(handle, direction, devAddr, dramAddr, size): the same
   transfer, started directly; it completes at once and posts nothing */
RT(osEPiRawStartDma) {
  epi_dma(arg(0), arg(1), arg(2), arg(3), arg(4));
  return ret(0);
}

/* osEPiReadIo(handle, devAddr, data): one word from handle base | devAddr;
   only the cartridge ROM is modelled */
RT(osEPiReadIo) {
  u32 a = (rd32(arg(0) + 0xc) | arg(1)) & 0x1fffffffu;
  u64 v;
  if (a >= 0x08000000u && a < 0x10000000u && fl.on) {
    rt_io(S, a, 4, 0, &v);
    wr32(arg(2), (u32)v);
    return ret(0);
  }
  if ((a & 3) || a < 0x10000000u || (u64)(a - 0x10000000u) + 4 > rom_size) finish(1, "PI read outside the ROM");
  wr(arg(2), rom + (a - 0x10000000u), 4);
  return ret(0);
}

/* ---- SP tasks ------------------------------------------------------------ */

static void report_gfx_task(u32 task) {
  u32 dl = rd32(task + 0x30), i;
  printf("{\"gfx_task\":%lu,\"task\":\"%08x\",\"ucode\":\"%08x\",\"data_ptr\":\"%08x\",\"data_size\":%u,"
         "\"display_list\":[",
         gfx_tasks, task, rd32(task + 0x10), dl, rd32(task + 0x34));
  for (i = 0; i < 8; i++) printf("%s\"%08x%08x\"", i ? "," : "", rd32(dl + 8 * i), rd32(dl + 8 * i + 4));
  printf("]}\n");
}
#ifdef PLAID_RSP
/* RSP DMA into RDRAM obeys the same write checks as the CPU's runtime writes */
static int rsp_rdram_write(u32 p, u32 size) {
  int r = plaid_runtime_write(S, p, size, 0);
  if (!r && size) dma_wrote(p, size);
#ifdef PLAID_RT64
  if (!r && size) {
    u32 page;
    for (page = p / 4096; page <= (p + size - 1) / 4096; page++) rsp_gfx_dirty[page] = 1;
  }
#endif
  return r;
}
/* Run lowered code from pc until the RSP halts (0) or faults (1); -1 when no
   lowered text holds the word IMEM has at pc. A text that leaves at a pc
   (its copy of the word there, or of the delay slot, is stale) is not chosen
   for that pc again until IMEM changes. */
static void rsp_file(const char *dir, const char *name, const void *bytes, size_t size);
static void rsp_dump_imem(u32 pc) {
  char name[64];
  u32 h = 2166136261u, i;
  if (!rsp_dump_dir) return;
  for (i = 0; i < 4096; i++) h = (h ^ rsp.imem[i]) * 16777619u;
  snprintf(name, sizeof name, "imem-%03x-%08x.bin", pc, h);
  rsp_file(rsp_dump_dir, name, rsp.imem, 4096);
}
static int rsp_run(u32 pc) {
  u32 xpc = ~0u, xgen = 0;
  u64 xmask[4] = {0}; /* texts that left at xpc, one bit per registry entry (256 max) */
  for (;;) {
    const plaid_rsp_text *t = NULL;
    int i, rc;
    /* Oracle only: capture recognized placements too, without feeding their
       bytes back into ROM discovery or native compilation. */
    rsp_dump_imem(pc);
    for (i = 0; plaid_rsp_texts[i] && i < 256; i++) {
      const plaid_rsp_text *c = plaid_rsp_texts[i];
      if (pc == xpc && rsp.imem_gen == xgen && (xmask[i >> 6] >> (i & 63) & 1)) continue;
      if (pc < c->start || pc + 4 > c->start + c->size) continue;
      if (!memcmp(rsp.imem + pc, c->bytes + (pc - c->start), 4)) { t = c; break; }
    }
    if (!t) { rsp.pc = pc; return -1; }
    rc = t->run(&rsp, pc);
    if (rc != 2) return rc;
    if (rsp.pc != xpc || rsp.imem_gen != xgen) { xpc = rsp.pc; xgen = rsp.imem_gen; memset(xmask, 0, sizeof xmask); }
    xmask[i >> 6] |= (u64)1 << (i & 63);
    pc = rsp.pc;
  }
}
static void rsp_file(const char *dir, const char *name, const void *bytes, size_t size) {
  char path[1024];
  FILE *f;
  snprintf(path, sizeof path, "%s/%s", dir, name);
  f = fopen(path, "wb");
  if (!f || fwrite(bytes, 1, size, f) != size || fclose(f)) finish(1, "cannot write an RSP file");
}
/* --rsp-capture: the whole RSP-visible state, as spike098 loads it into ares */
static void rsp_save(const char *tag) {
  char name[64], json[16384];
  int n = 0, i, k;
  snprintf(name, sizeof name, "%s-rdram.bin", tag); rsp_file(rsp_capture_dir, name, S->ram, PLAID_RAM_SIZE);
  snprintf(name, sizeof name, "%s-imem.bin", tag); rsp_file(rsp_capture_dir, name, rsp.imem, 4096);
  snprintf(name, sizeof name, "%s-dmem.bin", tag); rsp_file(rsp_capture_dir, name, rsp.dmem, 4096);
  n += snprintf(json + n, sizeof json - n, "{\"pc\":%u,\"halted\":%u,\"broken\":%u,\"regs\":[", rsp.pc, rsp.halted,
                rsp.broken);
  for (i = 0; i < 32; i++) n += snprintf(json + n, sizeof json - n, "%s%u", i ? "," : "", rsp.r[i]);
  n += snprintf(json + n, sizeof json - n, "],\"vu\":\"");
  for (i = 0; i < 35; i++) {
    const plaid_v *v = i < 32 ? &rsp.v[i] : i == 32 ? &rsp.acch : i == 33 ? &rsp.accm : &rsp.accl;
    for (k = 0; k < 8; k++) n += snprintf(json + n, sizeof json - n, "%04x", v->e[k]);
  }
  {
    u32 f[3] = {0, 0, 0};
    for (k = 0; k < 8; k++) {
      f[0] |= (u32)(rsp.vcol.e[k] != 0) << k | (u32)(rsp.vcoh.e[k] != 0) << (8 + k);
      f[1] |= (u32)(rsp.vccl.e[k] != 0) << k | (u32)(rsp.vcch.e[k] != 0) << (8 + k);
      f[2] |= (u32)(rsp.vce.e[k] != 0) << k;
    }
    n += snprintf(json + n, sizeof json - n, "\",\"vflags\":[%u,%u,%u,%u,%u,%u],\"signals\":[", f[0], f[1], f[2],
                  (u32)(u16)rsp.divin, (u32)(u16)rsp.divout, (u32)rsp.divdp);
  }
  for (i = 0; i < 8; i++) n += snprintf(json + n, sizeof json - n, "%s%u", i ? "," : "", rsp.signal[i]);
  n += snprintf(json + n, sizeof json - n, "],\"semaphore\":%u,\"interrupt_on_break\":%u}\n", rsp.semaphore,
                rsp.interrupt_on_break);
  snprintf(name, sizeof name, "%s-state.json", tag); rsp_file(rsp_capture_dir, name, json, (size_t)n);
}
#ifdef PLAID_RSP_ROM
/* Startup selects direct-reachable entry words. Every executed word, including
   indirect targets and subsequent fallthrough, still passes its fetch guard. */
static int rsp_rom_matches(u32 index, const u8 *bytes, u32 start, u32 size) {
  const plaid_rsp_text *t = plaid_rsp_texts[index];
  u32 pc;
  /* A DMA longer than the text is fine: words outside it fail their fetch guard. */
  if (t->start != start || !size) return 0;
  for (pc = start; pc < t->start + t->size; pc += 4) {
    if (!(plaid_rsp_rom_reachable[index][pc / 32] >> (pc / 4 % 8) & 1)) continue;
    if (pc - start + 4 > size || memcmp(bytes + pc - start, t->bytes + pc - start, 4)) return 0;
  }
  return 1;
}
#endif
static void rsp_task(void) {
  int rc, capture = rsp_capture_dir && (long)audio_tasks == rsp_capture;
#ifdef PLAID_RSP_ROM
  /* Check the submitted bytes before any RSP side effects. The recognized
     boot DMA length takes precedence over the SDK's often ignored ucode_size. */
  u32 boot_size, ucode, size = 0, i;
  u32 boot_matches = 0, text_matches = 0;
  boot_size = (u32)rsp.dmem[0xfcc] << 24 | (u32)rsp.dmem[0xfcd] << 16 |
              (u32)rsp.dmem[0xfce] << 8 | rsp.dmem[0xfcf];
  if (boot_size && boot_size <= 0x1000) boot_size = ((boot_size - 1) | 7) + 1;
  ucode = (u32)rsp.dmem[0xfd0] << 24 | (u32)rsp.dmem[0xfd1] << 16 |
          (u32)rsp.dmem[0xfd2] << 8 | rsp.dmem[0xfd3];
  for (i = 0; plaid_rsp_texts[i]; i++) {
    if (plaid_rsp_rom_matchable[i] && boot_size <= 0x1000 && rsp_rom_matches(i, rsp.imem, 0, boot_size)) {
      boot_matches++;
      size = plaid_rsp_boot_ucode_sizes[i];
    }
  }
  if (boot_matches != 1) {
    fprintf(stderr, "RSP task boot: %u matches for %u bytes at IMEM 0\n", boot_matches, boot_size);
    finish(1, "unknown or ambiguous ROM-derived RSP microcode");
  }
  /* A recognized boot loads text at 0x80. Otherwise this is direct-loaded text.
     The DMA size, rather than advertised ucode_size, bounds the comparison. */
  if (size) {
    if (ucode <= PLAID_RAM_SIZE && size <= PLAID_RAM_SIZE - ucode) {
      for (i = 0; plaid_rsp_texts[i]; i++) {
        if (plaid_rsp_rom_matchable[i] && rsp_rom_matches(i, S->ram + ucode, 0x80, size)) text_matches++;
      }
    }
    if (text_matches != 1) {
      fprintf(stderr, "RSP task text: %u matches for %u bytes from RDRAM %08x\n", text_matches, size, ucode);
      finish(1, "unknown or ambiguous ROM-derived RSP microcode");
    }
  }
#endif
  /* osSpTaskStartGo: SET_INTR_ON_BREAK | CLEAR_SSTEP | CLEAR_BROKE | CLEAR_HALT */
  rsp.interrupt_on_break = 1; rsp.single_step = 0; rsp.broken = 0; rsp.halted = 0;
  if (capture) rsp_save("before");
  rc = rsp_run(rsp.pc);
  if (rc < 0) {
    char name[64];
    u32 h = 2166136261u, i;
    for (i = 0; i < 4096; i++) h = (h ^ rsp.imem[i]) * 16777619u;
    snprintf(name, sizeof name, "imem-%03x-%08x.bin", rsp.pc, h);
    if (rsp_dump_dir) rsp_file(rsp_dump_dir, name, rsp.imem, 4096);
    fprintf(stderr, "no lowered RSP code for IMEM %03x; %s %s (runtime/rsp_texts.py lowers it)\n", rsp.pc,
            rsp_dump_dir ? "saved" : "--rsp-dump <dir> would save", name);
    finish(1, "unlowered RSP code");
  }
  if (rc) {
    fprintf(stderr, "RSP fault %u at IMEM %03x\n", rsp.fault, rsp.fault_pc);
    finish(1, "RSP fault");
  }
  if (!rsp.halted) finish(1, "RSP task returned without halting");
  if (capture) { rsp_save("after"); finish(0, "RSP task captured"); }
}
#endif
/* osSpTaskLoad as libultra does it for the RSP: the task, with its pointers
   made physical, at DMEM 0xfc0; the boot microcode at IMEM 0; signals 0-2
   cleared; PC 0. Graphics tasks go to the renderer instead. */
RT(osSpTaskLoad) {
#ifdef PLAID_RSP
  static const int pointers[] = {4, 6, 8, 10, 11, 12, 14}; /* ucode .. yield_data_ptr */
  u32 task = arg(0), t[16], boot, n, i;
  for (i = 0; i < 16; i++) t[i] = rd32(task + 4 * i);
  if (t[0] == 1 && !rsp_graphics) return 0;
  if (t[1] & 1) finish(1, "yielded RSP task"); /* OS_TASK_YIELDED: only graphics tasks yield */
  for (i = 0; i < 7; i++)
    if (t[pointers[i]]) t[pointers[i]] = v2p(t[pointers[i]]);
  for (i = 0; i < 64; i++) rsp.dmem[0xfc0 + i] = (u8)(t[i / 4] >> (24 - 8 * (i % 4)));
  boot = v2p(t[2]);
  n = t[3] ? ((t[3] - 1) | 7) + 1 : 0; /* the DMA moves whole doublewords */
  if (n > 0x1000 || boot > PLAID_RAM_SIZE || n > PLAID_RAM_SIZE - boot) finish(1, "RSP boot microcode outside RAM");
  memcpy(rsp.imem, S->ram + boot, n);
  rsp.imem_gen++;
  rsp.signal[0] = rsp.signal[1] = rsp.signal[2] = 0;
  rsp.interrupt_on_break = 1;
  rsp.pc = 0;
  rsp.rdram = S->ram; rsp.rdram_size = PLAID_RAM_SIZE; rsp.rdram_write = rsp_rdram_write;
#endif
  return 0;
}
static int dp_frozen(void) {
#if defined(PLAID_RSP) && defined(PLAID_RT64)
  if (rsp_graphics) return rsp_dp.status & 2;
#endif
  return dpc_flags & 2;
}
/* Graphics tasks go to the renderer (RT64); with PLAID_RSP other tasks run
   their lowered microcode, otherwise they complete at once. */
RT(osSpTaskStartGo) {
  u32 task = arg(0), type = rd32(task);
  if (type == 1) {
    gfx_tasks++;
    sp_unknown = 1;
    report_gfx_task(task);
    if (stop_gfx && (long)gfx_tasks >= stop_gfx) finish(0, "graphics task");
#ifdef PLAID_RT64
#ifdef PLAID_RSP
    if (rsp_graphics) { sp_unknown = 0; memset(rsp_gfx_dirty, 1, sizeof rsp_gfx_dirty); rsp_task(); }
    else
#endif
      if (plaid_gfx_task(S->ram, rd32(task + 0x10), rd32(task + 0x18), rd32(task + 0x30), gfx_writeback, S)) return 1;
#endif
    post(EV_SP);
    /* a frozen RDP consumes nothing, so the DP interrupt waits for the thaw
       (ares rdp/io.cpp) */
    if (dp_frozen()) dp_held = 1; else post(EV_DP);
  } else {
    audio_tasks++;
#ifdef PLAID_RSP
    rsp_task();
#else
    sp_unknown = 1;
#endif
    post(EV_SP);
  }
  return 0;
}

/* ---- audio --------------------------------------------------------------- */

/* Retires the buffers the DAC has finished by now. The next buffer starts
   where the last ended, and its start raises the AI interrupt. */
static void ai_update(void) {
  u64 now = now_ns(), end;
  while (ai.on && ai.count) {
    end = ai.start_ns + (u64)(ai.len[0] / 4) * 1000000000ull / ai.rate;
    if (now < end) break;
    ai.start_ns = end;
    ai.len[0] = ai.len[1];
    if (--ai.count) post(EV_AI);
  }
}
/* bytes left in the playing buffer, in whole samples */
static u32 ai_length(void) {
  u64 played;
  if (!ai.count) return 0;
  if (!ai.on) return ai.len[0];
  played = (now_ns() - ai.start_ns) * ai.rate / 1000000000ull * 4;
  return played < ai.len[0] ? ai.len[0] - (u32)played : 0;
}
/* libultra's rate from the NTSC VI clock: the DAC divides 48681812 Hz. It
   also turns AI DMA on. */
RT(osAiSetFrequency) {
  u32 dac = (u32)((float)48681812u / (float)arg(0) + .5f);
  if (dac < 132) return ret(0xffffffffu);
  ai_update();
  ai.rate = 48681812u / dac;
  if (!ai.on) { ai.on = 1; ai.start_ns = now_ns(); }
  return ret(ai.rate);
}
RT(osAiGetLength) { ai_update(); return ret(ai_length()); }
/* full (bit 31 and bit 0), busy (bit 30), DMA on (bit 25); bits 24 and 20
   read as set (ares) */
RT(osAiGetStatus) {
  ai_update();
  return ret((ai.count > 1 ? 0x80000001u : 0) | (ai.count ? 0x40000000u : 0) | ai.on << 25 | 1u << 24 | 1u << 20);
}
/* -1 while the FIFO is full, as libultra's __osAiDeviceBusy check */
RT(osAiSetNextBuffer) {
  ai_update();
  if (ai.count == 2) return ret(0xffffffffu);
  ai_submit(v2p(arg(0)), arg(1) & 0x3fff8u);
  return ret(0);
}
/* one buffer into a FIFO with room: the first raises the AI interrupt */
static void ai_submit(u32 p, u32 n) {
  u32 i;
  if (p > PLAID_RAM_SIZE || n > PLAID_RAM_SIZE - p) finish(1, "AI buffer outside RAM");
  if (!ai.count) { ai.start_ns = now_ns(); post(EV_AI); }
  ai.len[ai.count++] = n;
  if (wav) {
    for (i = 0; i < n; i += 2) { fputc(S->ram[p + i + 1], wav); fputc(S->ram[p + i], wav); }
    wav_bytes += n;
  }
#ifdef PLAID_RT64
  plaid_audio_play(S->ram + p, n, ai.rate);
#endif
}

/* ---- SI: controllers and EEPROM ------------------------------------------ */

/* osContInit(mq, &bitpattern, status[4]): one standard controller */
static void cont_status(u32 status) {
  int i;
  for (i = 0; i < 4; i++) {
    u8 st[4] = {0, i == 0 ? 5 : 0, i == 0 ? 2 : 0, i == 0 ? 0 : 8};
    wr(status + 4 * i, st, 4);
  }
}
RT(osContInit) {
  u8 bits = 1;
  wr(arg(1), &bits, 1);
  cont_status(arg(2));
  return ret(0);
}
/* libultra's osContInit also creates __osEepromTimerQ with one message,
   __osEepromTimerMsg, on which osEepromLongWrite waits out each write
   (ADR-0196); like __osContinitialized, only on the first call */
int plaid_rt_osContInit_eeprom(plaid_state *s, u32 queue, u32 message) {
  static u32 created;
  int result;
  (void)s;
  pthread_mutex_lock(&big);
  result = rt_osContInit();
  if (queue != created) {
    wr32(queue, 0); wr32(queue + 4, 0); wr32(queue + 8, 0); wr32(queue + 0xc, 0);
    wr32(queue + 0x10, 1); wr32(queue + 0x14, message);
    created = queue;
  }
  pthread_mutex_unlock(&big);
  return result;
}
RT(osContStartReadData) { post(EV_SI); return ret(0); }
RT(osContStartQuery) { post(EV_SI); return ret(0); }
RT(osContGetQuery) { cont_status(arg(0)); return 0; }
RT(osContSetCh) { return ret(0); }
/* No Rumble Pak: PFS_ERR_NOPACK */
RT(osMotorInit) { return ret(1); }
RT(__osPfsGetStatus) { return ret(1); } /* every channel has no Controller Pak */
/* The same policy for every libultra pak operation: PFS_ERR_NOPACK. */
#define PFS_NOPACK(name) RT(name) { return ret(1); }
PFS_NOPACK(osPfsInitPak) PFS_NOPACK(osPfsFreeBlocks) PFS_NOPACK(osPfsAllocateFile)
PFS_NOPACK(osPfsDeleteFile) PFS_NOPACK(osPfsFileState) PFS_NOPACK(osPfsFindFile)
PFS_NOPACK(osPfsReadWriteFile)
RT(__osMotorAccess) { return ret(1); }
/* Both SDK wrappers use the same no-accessory policy as __osMotorAccess. */
RT(osMotorStart) { return rt___osMotorAccess(); }
RT(osMotorStop) { return rt___osMotorAccess(); }
/* Controller 1: scripted presses (--press, by VI frame) OR the renderer
   window's keyboard. shortcut: scripts set buttons only, not the stick. */
#define MAX_PRESSES 32
static struct { u32 buttons, at, frames; } presses[MAX_PRESSES];
static int n_presses;
static u32 controller_input(void) {
  u32 b = 0, stick = 0;
  int i;
  for (i = 0; i < n_presses; i++)
    if (vi_count >= presses[i].at && vi_count - presses[i].at < presses[i].frames) b |= presses[i].buttons;
#ifdef PLAID_RT64
  stick = plaid_gfx_input();
  b |= stick >> 16;
#endif
  return (b << 16) | (stick & 0xffffu);
}
RT(osContGetReadData) {
  u32 input = controller_input(), b = input >> 16, stick = input;
  int i;
  for (i = 0; i < 4; i++) { /* OSContPad: button, stick_x, stick_y, errno */
    u8 pad[6] = {0, 0, 0, 0, i == 0 ? 0 : 8, 0};
    if (i == 0) { pad[0] = (u8)(b >> 8); pad[1] = (u8)b; pad[2] = (u8)(stick >> 8); pad[3] = (u8)stick; }
    wr(arg(0) + 6 * i, pad, 6);
  }
  return 0;
}
/* 4 Kbit EEPROM (512 bytes). With --save, it is loaded at start and written
   back after every write (ADR-0165): to <path>.tmp first, then renamed, so an
   interrupted write leaves the previous save or the complete new one. */
#define EEPROM_SIZE 512
static const char *save_path;
static void save_file(const char *path, const u8 *bytes, size_t size) {
  char tmp[1024];
  FILE *f;
  if (!path) return;
  snprintf(tmp, sizeof tmp, "%s.tmp", path);
  f = fopen(tmp, "wb");
  if (!f || fwrite(bytes, 1, size, f) != size || fclose(f)) finish(1, "cannot write the save file");
  remove(path);
  if (rename(tmp, path)) finish(1, "cannot replace the save file");
}
static void save_eeprom(void) { save_file(save_path, eeprom, EEPROM_SIZE); }
static int load_file(const char *path, u8 *bytes, size_t size) {
  char tmp[1024];
  FILE *f = fopen(path, "rb");
  size_t n;
  snprintf(tmp, sizeof tmp, "%s.tmp", path);
  if (!f) f = fopen(tmp, "rb"); /* a write interrupted after the remove */
  if (!f) return 0;             /* no save yet */
  n = fread(bytes, 1, size + 1, f);
  fclose(f);
  return n == size ? 0 : -1;
}
RT(osEepromProbe) { return ret(1); } /* EEPROM_TYPE_4K */
RT(__osEepStatus) {
  wr16(arg(1), 0x8000); /* 4 Kbit device, no response error */
  wr16(arg(1) + 2, count_now() < joybus.eeprom_busy_until ? 0x8000 : 0); /* busy as the SI path */
  return ret(0);
}
RT(osEepromRead) { wr(arg(2), eeprom + 8 * (arg(1) & 63), 8); return ret(0); }
RT(osEepromWrite) {
  u32 i;
  for (i = 0; i < 8; i++) eeprom[8 * (arg(1) & 63) + i] = (u8)(rd32((arg(2) + i) & ~3u) >> (24 - 8 * ((arg(2) + i) & 3)));
  save_eeprom();
  return ret(0);
}
RT(osEepromLongRead) {
  u32 a = 8 * (arg(1) & 63), n = arg(3);
  if (a + n > 512) return ret((u32)-1);
  wr(arg(2), eeprom + a, n);
  return ret(0);
}
RT(osEepromLongWrite) {
  u32 a = 8 * (arg(1) & 63), n = arg(3), i, b = arg(2);
  if (a + n > 512) return ret((u32)-1);
  for (i = 0; i < n; i++) eeprom[a + i] = (u8)(rd32((b + i) & ~3u) >> (24 - 8 * ((b + i) & 3)));
  save_eeprom();
  return ret(0);
}

/* Native SI transfers preserve the SDK's guest packet construction and cache
   operations. As pinned ares orders them, the address write starts the DMA
   (busy) and the bytes move with the interrupt: here at SI delivery or the
   guest's next SI/PIF access, so the SDK's cache operations after the start
   precede the transfer. */
static int si_finish(void) {
  int due = si_due;
  si_due = 0;
  if (due == 2) {
    dma_read(si_dram, 64);
    memcpy(joybus.ram, S->ram + si_dram, 64);
    if (plaid_joy_parse(&joybus)) return 1;
  } else {
    if (plaid_joy_run(&joybus, eeprom, count_now(), controller_input())) return 1;
    dma_wr(0xa0000000u | si_dram, joybus.ram, 64);
    if (joybus.changed) { save_eeprom(); joybus.changed = 0; }
  }
  si_status = 0x1000;
  return 0;
}
static int si_access(u32 p, int write, u64 *value) {
  u32 offset;
  if (si_due && si_finish()) return 1;
  if (p >= 0x1fc007c0u) {
    offset = p - 0x1fc007c0u;
    if (write) {
      unsigned byte;
      for (byte = 0; byte < 4; byte++) joybus.ram[offset + byte] = (u8)(*value >> (24 - byte * 8));
      /* ares clears the command byte and enters Run on its next PIF step;
         here that happens at once. A second terminate is not modeled. */
      if (offset == 60 && !pif_booted && (joybus.ram[63] & 0x08)) { joybus.ram[63] = 0; pif_booted = 1; return 0; }
      if (offset == 60 && plaid_joy_parse(&joybus)) return 1;
    } else {
      *value = (u32)joybus.ram[offset] << 24 | (u32)joybus.ram[offset + 1] << 16
        | (u32)joybus.ram[offset + 2] << 8 | joybus.ram[offset + 3];
    }
    return 0;
  }
  offset = p - 0x04800000u;
  if (!write) {
    *value = offset == 0 ? si_dram : offset == 4 ? si_read_address
      : offset == 16 ? si_write_address : offset == 24 ? si_status : 0;
    return 0;
  }
  if (offset == 0) { si_dram = (u32)*value & 0xfffff8u; return 0; }
  if (offset == 24) { si_status = 0; pending[EV_SI] = 0; return 0; }
  if (offset != 4 && offset != 16) return 1;
  if (((u32)*value & ~1u) != 0x1fc007c0u || si_dram > PLAID_RAM_SIZE - 64) return 1;
  if (offset == 16) { si_write_address = (u32)*value & ~1u; si_due = 2; }
  else { si_read_address = (u32)*value & ~1u; si_due = 1; }
  si_status = 1; /* DMA busy */
  pending[EV_SI] = 1; plaid_preempt = 1;
  return 0;
}

/* ---- 64-bit helpers: o32 pairs, high word first ------------------------- */

static u64 pair(int n) { return (u64)arg(n) << 32 | arg(n + 1); }
RT(__ull_div) { u64 b = pair(2); return ret64(b ? pair(0) / b : 0); }
RT(__ull_rem) { u64 b = pair(2); return ret64(b ? pair(0) % b : pair(0)); }
RT(__ll_div) { s64 b = (s64)pair(2); return ret64(b ? (u64)((s64)pair(0) / b) : 0); }
RT(__ll_mul) { return ret64(pair(0) * pair(2)); }
RT(__ull_to_d) { double d = (double)pair(0); memcpy(&S->f[0], &d, 8); return 0; }
RT(__ull_to_f) {
  float f = (float)pair(0);
  u32 bits;
  memcpy(&bits, &f, 4);
  S->f[0] = (S->f[0] & 0xffffffff00000000ull) | bits;
  return 0;
}

/* ---- development-board debug output: no board is attached --------------- */

RT(__osRdbSend) { return ret(arg(1)); } /* (buf, size, type): every byte "sent" */
RT(is_proutSyncPrintf) { return ret(1); }
RT(__checkHardware_msp) { return ret(0); }
RT(__checkHardware_kmc) { return ret(0); }
RT(__checkHardware_isv) { return ret(0); }
RT(__osInitialize_msp) { return 0; }
RT(__osInitialize_kmc) { return 0; }
RT(__osInitialize_isv) { return 0; }

/* ---- entry -------------------------------------------------------------- */

int main(int argc, char **argv) {
  FILE *f;
  pthread_t pump;
  int i, r;
  const char *rom_path = NULL;
  for (i = 1; i < argc; i++) {
    if (!strcmp(argv[i], "--rom") && i + 1 < argc) rom_path = argv[++i];
    else if (!strcmp(argv[i], "--dump") && i + 2 < argc) {
      dump_at = (u32)strtoul(argv[i + 1], NULL, 0);
      dump_words = (u32)strtoul(argv[i + 2], NULL, 0);
      i += 2;
    } else if (!strcmp(argv[i], "--stop-at") && i + 1 < argc) stop_gfx = strcmp(argv[++i], "none") ? 1 : 0;
    else if (!strcmp(argv[i], "--gfx-tasks") && i + 1 < argc) stop_gfx = atol(argv[++i]);
    else if (!strcmp(argv[i], "--seconds") && i + 1 < argc) run_seconds = atof(argv[++i]);
#if defined(PLAID_RT64) && defined(PLAID_RSP)
    else if (!strcmp(argv[i], "--rsp-gfx")) { rsp_graphics = 1; rsp.dpc = rsp_dpc; }
#endif
    else if (!strcmp(argv[i], "--save") && i + 1 < argc) save_path = argv[++i];
    else if (!strcmp(argv[i], "--sram") && i + 1 < argc) sram_path = argv[++i];
    else if (!strcmp(argv[i], "--flash") && i + 1 < argc) flash_path = argv[++i];
    else if (!strcmp(argv[i], "--wav") && i + 1 < argc) {
      if (!(wav = fopen(argv[++i], "wb"))) { perror(argv[i]); return 2; }
      wav_header();
    }
#ifdef PLAID_RSP
    else if (!strcmp(argv[i], "--rsp-dump") && i + 1 < argc) rsp_dump_dir = argv[++i];
    else if (!strcmp(argv[i], "--rsp-capture") && i + 2 < argc) {
      rsp_capture = atol(argv[++i]);
      rsp_capture_dir = argv[++i];
    }
#endif
    else if (!strcmp(argv[i], "--press") && i + 1 < argc && n_presses < MAX_PRESSES &&
             sscanf(argv[++i], "%i@%u:%u", (int *)&presses[n_presses].buttons, &presses[n_presses].at,
                    &presses[n_presses].frames) == 3) n_presses++;
    else {
      fprintf(stderr, "usage: %s [--rom <rom.z64>] [--stop-at gfx|none] [--gfx-tasks N] [--seconds S] [--press <buttons>@<vi>:<frames>] [--save <eeprom file>] [--sram <sram file>] [--wav <file>] [--rsp-dump <dir>] [--rsp-capture <task> <dir>] [--rsp-gfx] [--dump <addr> <words>]\n", argv[0]);
      return 2;
    }
  }
  if (rom_path) { /* the PI DMA source; without one, any DMA stops the run */
    f = fopen(rom_path, "rb");
    if (!f) { perror(rom_path); return 2; }
    fseek(f, 0, SEEK_END); rom_size = (size_t)ftell(f); fseek(f, 0, SEEK_SET);
    rom = malloc(rom_size);
    if (!rom || fread(rom, 1, rom_size, f) != rom_size) { fprintf(stderr, "cannot read ROM\n"); return 2; }
    fclose(f);
    if (rom_size < 0x1000 || rom[0] != 0x80 || rom[1] != 0x37) { fprintf(stderr, "expected a big-endian .z64 ROM\n"); return 2; }
  }
  if (sram_path && load_file(sram_path, sram, SRAM_SIZE)) { fprintf(stderr, "%s is not a %d-byte SRAM save\n", sram_path, SRAM_SIZE); return 2; }
  memset(flash, 0xff, FLASH_SIZE); /* an erased chip until its save is loaded */
  flash_power();
  if (save_path && load_file(save_path, eeprom, EEPROM_SIZE)) { fprintf(stderr, "%s is not a %d-byte EEPROM save\n", save_path, EEPROM_SIZE); return 2; }
  S = calloc(1, sizeof *S);
  if (!S) return 2;
  S->fr_mode = 2; /* IPL3 hands over with Status.CU1 = 1, Status.FR = 1 */
#ifdef PLAID_BOOT_STATUS
  S->cp0_status = PLAID_BOOT_STATUS; S->status_known = 1;
  S->cp0_entryhi = PLAID_BOOT_ENTRYHI & 0xc00000ffffffe0ffull; S->cp0_known = 1u << 10;
  ints_enabled = S->cp0_status & 1u;
  S->fr_mode = (S->cp0_status & 0x04000000u) ? 2 : 1;
#endif
  S->io = rt_io;
  if (rom) io_boot();
#ifdef PLAID_RT64
  if (!rom || plaid_gfx_open(rom)) { fprintf(stderr, "the renderer needs --rom and a working GPU\n"); return 2; }
#endif
  clock_gettime(CLOCK_MONOTONIC, &t0);
  plaid_load_images(S);
  pthread_mutex_lock(&big);
  pthread_cond_init(&boot.wake, NULL);
  boot.pri = -1; boot.state = T_RUNNING; running = &boot;
  pthread_mutex_unlock(&big);
  pthread_create(&pump, NULL, event_pump, NULL);
  S->r[31] = THREAD_RETURN;
  r = plaid_run(S);
  pthread_mutex_lock(&big);
  finish(r ? 1 : 0, r ? "guest fault" : "exit");
  return 0;
}
