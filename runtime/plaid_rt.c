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
static rt_event events[EV_COUNT];
static rt_event vi_event;
static u32 vi_retrace = 1;
static int pending[EV_COUNT]; /* undelivered event counts */
static rt_timer timers[MAX_TIMERS];
static u8 *rom;
static size_t rom_size;
static u8 eeprom[2048];
static struct timespec t0;
static u64 time_base; /* osSetTime offset in count ticks */
static u32 frame_buffer;
static u32 vi_mode, vi_black, vi_regs[14]; /* see vi_update */
/* With PLAID_RT64 the runtime links plaid_rt64.dll (runtime/rt64, ADR-0163). */
#ifdef PLAID_RT64
int plaid_gfx_open(const u8 *rom_header);
void plaid_gfx_task(const u8 *ram, u32 ucode, u32 ucode_data, u32 data_ptr);
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
static plaid_rsp rsp;
static const char *rsp_dump_dir, *rsp_capture_dir;
static long rsp_capture;
#endif
/* --wav: AI buffers as 16-bit stereo PCM, the header rewritten at exit */
static FILE *wav;
static u32 wav_bytes;
/* AI DMA (ADR-0170), as ares models it: a two-entry FIFO whose head drains
   one 4-byte sample per DAC period, here on the host clock. */
static struct { u32 len[2], count, on, rate; u64 start_ns; } ai = {{0, 0}, 0, 0, 32000, 0};
static void ai_update(void);
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
         "\"framebuffer\":\"%08x\",\"fault\":%u,\"fault_pc\":\"%08x\",\"ra\":\"%08x\",\"a0\":\"%08x\",\"a1\":\"%08x\"}\n",
         why, vi_count, gfx_tasks, audio_tasks, dma_count, frame_buffer, S->fault, S->fault_pc,
         (u32)S->r[31], (u32)S->r[4], (u32)S->r[5]);
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
}
static void restore(const rt_thread *t) {
  memcpy(S->r, t->r, sizeof t->r); memcpy(S->f, t->f, sizeof t->f);
  S->hi = t->hi; S->lo = t->lo; S->fcc = t->fcc; S->fcsr = t->fcsr; S->llbit = t->llbit;
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
static void yield_from(rt_thread *self) {
  save(self);
  hand_to(best_runnable());
  if (self->state != T_DEAD && self != &boot) wait_for_baton(self);
}
static void deliver_pending(void);
/* After making threads runnable: run a strictly higher-priority one now. */
static void maybe_preempt(void) {
  rt_thread *b;
  deliver_pending();
  b = best_runnable();
  if (running && b && b->pri > running->pri) {
    rt_thread *self = running;
    make_runnable(self);
    yield_from(self);
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
  yield_from(self);
  return 0;
}
/* jam: put the message at the front. Returns -1 when full and not blocking. */
static int mq_send(u32 mq, u32 msg, int block, int jam) {
  u32 count, valid, first;
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
static void deliver_pending(void) {
  int ev, i;
  u64 c;
  if (!ints_enabled) return;
  plaid_preempt = 0;
  for (ev = 0; ev < EV_COUNT; ev++)
    while (pending[ev]) {
      pending[ev]--;
      if (ev == EV_VI) {
        if (vi_event.set && vi_count % vi_retrace == 0) mq_send(vi_event.mq, vi_event.msg, 0, 0);
      } else if (events[ev].set) {
        mq_send(events[ev].mq, events[ev].msg, 0, 0);
      }
    }
  c = count_now();
  for (i = 0; i < MAX_TIMERS; i++) {
    rt_timer *t = &timers[i];
    if (t->used && c >= t->due) {
      if (t->mq) mq_send(t->mq, t->msg, 0, 0);
      if (t->interval) t->due += t->interval; else t->used = 0;
    }
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
  u64 next_vi = 0, now;
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
      post(EV_VI);
#ifdef PLAID_RT64
      if (vi_mode) plaid_gfx_screen(vi_regs);
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
  yield_from(self);
  pthread_mutex_unlock(&big);
  return NULL;
}
int plaid_rt_safepoint(plaid_state *s) {
  (void)s;
  pthread_mutex_lock(&big);
  maybe_preempt();
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
  t->arg = arg(3); t->sp = arg(4); t->pri = (s32)arg(5);
  t->r[4] = SX32(t->arg); t->r[29] = SX32(t->sp); t->r[31] = THREAD_RETURN;
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
    yield_from(&boot);
    pthread_mutex_unlock(&big);
    for (;;) { struct timespec d = {3600, 0}; nanosleep(&d, NULL); }
  }
  maybe_preempt();
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
    if (b && b->pri > t->pri) { make_runnable(t); yield_from(t); }
  } else {
    maybe_preempt();
  }
  return 0;
}
/* The caller queues behind the runnable threads of its own priority. */
RT(osYieldThread) {
  rt_thread *self = running, *b;
  deliver_pending();
  b = best_runnable();
  if (self && b && b->pri >= self->pri) { make_runnable(self); yield_from(self); }
  return 0;
}
RT(osGetThreadPri) { rt_thread *t = thread_of(arg(0)); return ret(t ? (u32)t->pri : 0); }
RT(osCreateMesgQueue) {
  u32 mq = arg(0);
  wr32(mq, 0); wr32(mq + 4, 0); wr32(mq + 8, 0); wr32(mq + 0xc, 0);
  wr32(mq + 0x10, arg(2)); wr32(mq + 0x14, arg(1));
  return 0;
}
RT(osSendMesg) { int r = mq_send(arg(0), arg(1), arg(2) & 1, 0); maybe_preempt(); return ret((u32)r); }
RT(osJamMesg) { int r = mq_send(arg(0), arg(1), arg(2) & 1, 1); maybe_preempt(); return ret((u32)r); }
RT(osRecvMesg) { int r = mq_recv(arg(0), arg(1), arg(2) & 1); maybe_preempt(); return ret((u32)r); }
RT(osSetEventMesg) {
  u32 ev = arg(0);
  if (ev < EV_COUNT) { events[ev].mq = arg(1); events[ev].msg = arg(2); events[ev].set = 1; }
  return 0;
}
RT(osViSetEvent) {
  vi_event.mq = arg(0); vi_event.msg = arg(1); vi_event.set = 1;
  vi_retrace = arg(2) ? arg(2) : 1;
  return 0;
}
/* Interrupt masking: while disabled, events stay pending. */
RT(__osDisableInt) { u32 was = (u32)ints_enabled; ints_enabled = 0; return ret(was); }
RT(__osRestoreInt) { ints_enabled = arg(0) & 1; if (ints_enabled) maybe_preempt(); return 0; }
RT(osSetIntMask) { return ret(0x003fff01u); }

/* ---- time --------------------------------------------------------------- */

RT(osGetTime) { return ret64(count_now()); }
RT(osGetCount) { return ret((u32)count_now()); }
RT(osSetTime) { time_base = ((u64)arg(0) << 32 | arg(1)) - (count_now() - time_base); return 0; }
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

/* ---- system ------------------------------------------------------------- */

RT(osInitialize) {
  wr32(0x80000300u, 1);           /* osTvType: NTSC */
  wr32(0x80000304u, 0);           /* osRomType: cartridge */
  wr32(0x80000308u, 0xb0000000u); /* osRomBase */
  wr32(0x8000030cu, 0);           /* osResetType: cold */
  wr32(0x80000318u, 0x00400000u); /* osMemSize: 4 MiB */
  return 0;
}
static int nop(void) { return 0; }
#define NOP(name) RT(name) { return nop(); }
NOP(osCreateViManager) NOP(osViSetSpecialFeatures)
NOP(osCreatePiManager) NOP(osInvalDCache) NOP(osInvalICache) NOP(osWritebackDCache)
NOP(osWritebackDCacheAll) NOP(osSpTaskYield)
/* The TLB as libultra's osMapTLB writes it (ADR-0162): 4 KiB-aligned even
   and odd pages, noncoherent cached, dirty and valid; -1 leaves a page invalid.
   Lowered code models global entries only, so an ASID is refused. */
static u32 tlb_lo(u32 paddr) { return paddr == 0xffffffffu ? 1 : (paddr >> 6) | 0x18 | 4 | 2 | 1; }
RT(osMapTLB) {
  u32 pm = arg(1);
  if (arg(5) != 0xffffffffu) finish(1, "osMapTLB with an ASID");
  S->tlb[arg(0) & 31] = (plaid_tlb_entry){pm, arg(2) & ~(pm | 0x1fffu), {tlb_lo(arg(3)), tlb_lo(arg(4))}};
  return 0;
}
RT(osUnmapTLBAll) { /* EntryHi in KSEG0 never matches a mapped address */
  int i;
  for (i = 0; i < 32; i++) S->tlb[i] = (plaid_tlb_entry){0, 0x80000000u, {0, 0}};
  return 0;
}
RT(osSpTaskYielded) { return ret(0); }
RT(__osSpSetPc) { return ret(0); }
/* VI registers as libultra's retrace handler writes them from the OSViMode
   (comRegs at +4, fldRegs[0] at +0x28), the next framebuffer and the black
   flag. shortcut: field 0 only and no special features (gamma, dither), which
   SM64's non-interlaced LAN1 mode does not need; interlaced modes would
   alternate fields. */
static void vi_update(void) {
  u32 m = vi_mode, f = m + 0x28;
  if (!m) return;
  vi_regs[0] = rd32(m + 0x04);
  vi_regs[1] = (frame_buffer & 0x1fffffffu) + rd32(f);
  vi_regs[2] = rd32(m + 0x08);
  vi_regs[3] = rd32(f + 0x10);
  vi_regs[4] = 0;
  vi_regs[5] = rd32(m + 0x0c);
  vi_regs[6] = rd32(m + 0x10);
  vi_regs[7] = rd32(m + 0x14);
  vi_regs[8] = rd32(m + 0x18);
  vi_regs[9] = vi_black ? 0 : rd32(m + 0x1c);
  vi_regs[10] = rd32(f + 0x08);
  vi_regs[11] = rd32(f + 0x0c);
  vi_regs[12] = rd32(m + 0x20);
  vi_regs[13] = rd32(f + 0x04);
}
RT(osViSetMode) { vi_mode = arg(0); vi_update(); return 0; }
RT(osViBlack) { vi_black = arg(0) & 0xff; vi_update(); return 0; }
RT(osViSwapBuffer) { frame_buffer = arg(0); vi_update(); return 0; }
static u32 v2p(u32 a) {
  u32 p;
  u8 seg;
  if (a >= 0x80000000u && a < 0xc0000000u) return a & 0x1fffffffu;
  return plaid_tlb(S, a, 0, &p, &seg) ? 0xffffffffu : p;
}
RT(osVirtualToPhysical) { return ret(v2p(arg(0))); }
RT(__osSetFpcCsr) {
  u32 was = S->fcsr | S->fcc << 23;
  if (plaid_ctc1(S, arg(0), (u32)S->r[31])) return 1;
  return ret(was);
}

/* ---- PI DMA ------------------------------------------------------------- */

/* osPiStartDma(mb, pri, direction, devAddr, vAddr, nbytes, mq) */
RT(osPiStartDma) {
  u32 mb = arg(0), dir = arg(2), dev = arg(3), va = arg(4), n = arg(5), mq = arg(6);
  if (dir != 0) finish(1, "PI write to cartridge");
  if ((u64)dev + n > rom_size) finish(1, "PI DMA outside the ROM");
  wr(va, rom + dev, n);
  dma_count++;
  if (mq) mq_send(mq, mb, 0, 0);
  maybe_preempt();
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
static int rsp_rdram_write(u32 p, u32 size) { return plaid_runtime_write(S, p, size, 0); }
/* Run lowered code from pc until the RSP halts (0) or faults (1); -1 when no
   lowered text holds the word IMEM has at pc. A text that leaves at a pc
   (its copy of the word there, or of the delay slot, is stale) is not chosen
   for that pc again until IMEM changes. */
static int rsp_run(u32 pc) {
  u32 xpc = ~0u, xgen = 0;
  u64 xmask = 0;
  for (;;) {
    const plaid_rsp_text *t = NULL;
    int i, rc;
    for (i = 0; plaid_rsp_texts[i] && i < 64; i++) {
      const plaid_rsp_text *c = plaid_rsp_texts[i];
      if (pc == xpc && rsp.imem_gen == xgen && (xmask >> i & 1)) continue;
      if (pc < c->start || pc + 4 > c->start + c->size) continue;
      if (!memcmp(rsp.imem + pc, c->bytes + (pc - c->start), 4)) { t = c; break; }
    }
    if (!t) { rsp.pc = pc; return -1; }
    rc = t->run(&rsp, pc);
    if (rc != 2) return rc;
    if (rsp.pc != xpc || rsp.imem_gen != xgen) { xpc = rsp.pc; xgen = rsp.imem_gen; xmask = 0; }
    xmask |= (u64)1 << i;
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
static void rsp_task(void) {
  int rc, capture = rsp_capture_dir && (long)audio_tasks == rsp_capture;
  /* osSpTaskStartGo: SET_INTR_ON_BREAK | CLEAR_SSTEP | CLEAR_BROKE | CLEAR_HALT */
  rsp.interrupt_on_break = 1; rsp.single_step = 0; rsp.broken = 0; rsp.halted = 0;
  if (capture) rsp_save("before");
  rc = rsp_run(rsp.pc);
  if (capture) { rsp_save("after"); finish(0, "RSP task captured"); }
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
  if (t[0] == 1) return 0;
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
/* Graphics tasks go to the renderer (RT64); with PLAID_RSP other tasks run
   their lowered microcode, otherwise they complete at once. */
RT(osSpTaskStartGo) {
  u32 task = arg(0), type = rd32(task);
  if (type == 1) {
    gfx_tasks++;
    report_gfx_task(task);
    if (stop_gfx && (long)gfx_tasks >= stop_gfx) finish(0, "graphics task");
#ifdef PLAID_RT64
    plaid_gfx_task(S->ram, rd32(task + 0x10), rd32(task + 0x18), rd32(task + 0x30));
#endif
    post(EV_SP);
    post(EV_DP);
  } else {
    audio_tasks++;
#ifdef PLAID_RSP
    rsp_task();
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
  u32 p = v2p(arg(0)), n = arg(1) & 0x3fff8u, i;
  ai_update();
  if (ai.count == 2) return ret(0xffffffffu);
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
  return ret(0);
}

/* ---- SI: controllers and EEPROM ------------------------------------------ */

/* osContInit(mq, &bitpattern, status[4]): one standard controller */
RT(osContInit) {
  u8 bits = 1;
  int i;
  wr(arg(1), &bits, 1);
  for (i = 0; i < 4; i++) {
    u8 st[4] = {0, i == 0 ? 5 : 0, 0, i == 0 ? 0 : 8};
    wr(arg(2) + 4 * i, st, 4);
  }
  return ret(0);
}
RT(osContStartReadData) { post(EV_SI); return ret(0); }
/* Controller 1: scripted presses (--press, by VI frame) OR the renderer
   window's keyboard. shortcut: scripts set buttons only, not the stick. */
#define MAX_PRESSES 32
static struct { u32 buttons, at, frames; } presses[MAX_PRESSES];
static int n_presses;
RT(osContGetReadData) {
  u32 b = 0, stick = 0;
  int i;
  for (i = 0; i < n_presses; i++)
    if (vi_count >= presses[i].at && vi_count - presses[i].at < presses[i].frames) b |= presses[i].buttons;
#ifdef PLAID_RT64
  stick = plaid_gfx_input();
  b |= stick >> 16;
#endif
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
static void save_eeprom(void) {
  char tmp[1024];
  FILE *f;
  if (!save_path) return;
  snprintf(tmp, sizeof tmp, "%s.tmp", save_path);
  f = fopen(tmp, "wb");
  if (!f || fwrite(eeprom, 1, EEPROM_SIZE, f) != EEPROM_SIZE || fclose(f)) finish(1, "cannot write the save file");
  remove(save_path);
  if (rename(tmp, save_path)) finish(1, "cannot replace the save file");
}
static int load_eeprom(void) {
  char tmp[1024];
  FILE *f = fopen(save_path, "rb");
  size_t n;
  snprintf(tmp, sizeof tmp, "%s.tmp", save_path);
  if (!f) f = fopen(tmp, "rb"); /* a write interrupted after the remove */
  if (!f) return 0;             /* no save yet */
  n = fread(eeprom, 1, EEPROM_SIZE + 1, f);
  fclose(f);
  return n == EEPROM_SIZE ? 0 : -1;
}
RT(osEepromProbe) { return ret(1); } /* EEPROM_TYPE_4K */
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
    else if (!strcmp(argv[i], "--save") && i + 1 < argc) save_path = argv[++i];
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
      fprintf(stderr, "usage: %s [--rom <rom.z64>] [--stop-at gfx|none] [--gfx-tasks N] [--seconds S] [--press <buttons>@<vi>:<frames>] [--save <eeprom file>] [--wav <file>] [--rsp-dump <dir>] [--rsp-capture <task> <dir>] [--dump <addr> <words>]\n", argv[0]);
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
  if (save_path && load_eeprom()) { fprintf(stderr, "%s is not a %d-byte EEPROM save\n", save_path, EEPROM_SIZE); return 2; }
  S = calloc(1, sizeof *S);
  if (!S) return 2;
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
