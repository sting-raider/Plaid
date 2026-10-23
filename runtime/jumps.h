/* Structural word-layout nonlocal jumps. Project-owned, MIT OR Apache-2.0. */
typedef struct plaid_jump_s {
  intptr_t host[5]; /* GCC builtin jump buffer; first for stable caller address */
  struct plaid_jump_s *next, *frame_next;
  rt_context *owner;
  rt_thread *thread;
  plaid_native_frame *frame;
  const uint16_t *layout;
  u32 address, saved[23], pc;
  u64 generation;
  int armed, fr0, spawned;
} plaid_jump;
static plaid_jump *jumps;
static unsigned jump_count, context_count;
static const u8 jump_regs[11] = {29,31,16,17,18,19,20,21,22,23,30};
static plaid_jump *jump_new(u32 address, u32 pc) {
  plaid_jump *j;
  if (jump_count >= 4096) { plaid_fault(S, pc, 13); return NULL; }
  j = calloc(1, sizeof *j);
  if (!j) { plaid_fault(S, pc, 13); return NULL; }
  jump_count++; j->address = address; j->next = jumps; jumps = j;
  return j;
}

static rt_context *new_context(rt_thread *thread, int root, u32 entry) {
  rt_context *c;
  if (context_count >= 256) { plaid_fault(S, S->pc, 13); finish(1, "too many native contexts"); }
  c = calloc(1, sizeof *c);
  if (!c) { plaid_fault(S, S->pc, 13); finish(1, "coroutine allocation failed"); }
  context_count++; thread->contexts++;
  c->thread = thread; c->root = root; c->entry = entry;
  pthread_cond_init(&c->wake, NULL);
  return c;
}
static void jump_detach(plaid_jump *j) {
  if (j->frame) {
    plaid_jump **p = (plaid_jump **)&j->frame->jumps;
    while (*p && *p != j) p = &(*p)->frame_next;
    if (*p) *p = j->frame_next;
  }
  j->frame = NULL; j->frame_next = NULL; j->armed = 0;
}
static void jump_leave(plaid_state *s, plaid_native_frame *frame) {
  plaid_jump *j = frame->jumps;
  (void)s;
  while (j) {
    plaid_jump *next = j->frame_next;
    j->frame = NULL; j->owner = NULL; j->frame_next = NULL; j->armed = 0;
    j = next;
  }
  frame->jumps = NULL;
}
/* Slot reuse/destruction with suspended jump stacks is outside this model.
   Expired records never retain pointers to a context being freed. */
static int jump_thread_busy(rt_thread *t) {
  plaid_jump *j;
  if (t->contexts > 1 || (t->context && !t->context->root)) return 1;
  for (j = jumps; j; j = j->next)
    if (j->thread == t && j->generation == t->generation && j->owner) return 1;
  return 0;
}
static void jump_thread_forget(rt_thread *t) {
  plaid_jump *j;
  for (j = jumps; j; j = j->next) if (j->thread == t) {
    jump_detach(j); j->owner = NULL; j->thread = NULL; j->generation = 0;
  }
}
/* Other SDK threads/coroutines can interleave registrations in the same list. */
static int jump_unwind(rt_context *owner, plaid_native_frame *target, u32 pc) {
  plaid_native_frame *f = S->native_frames;
  while (f) {
    plaid_native_frame *next = f->next;
    if (f->owner == owner) {
      if (f == target) return 0;
      plaid_text_unpin(S, f);
    }
    f = next;
  }
  return target ? plaid_fault(S, pc, 13) : 0;
}
/* big is held. A retired parked thread releases its own registrations and
   acknowledges completion before the replacement stack may execute. */
static void retire_context(rt_context *c) {
  jump_unwind(c, NULL, S->pc);
  if (c->retire_waiter) {
    c->retire_waiter->retire_pending--;
    pthread_cond_signal(&c->retire_waiter->wake);
  }
  pthread_cond_destroy(&c->wake); c->thread->contexts--; context_count--;
  free(c); host_context = NULL;
  pthread_mutex_unlock(&big);
  pthread_exit(NULL);
}
static int jump_read(u32 address, const uint16_t *layout, u32 *words, u32 pc) {
  unsigned i;
  for (i = 0; i < 23; i++) {
    u64 w;
    if (plaid_load(S, SX32(address) + layout[i], 4, pc, &w)) return 1;
    words[i] = (u32)w;
  }
  return 0;
}
intptr_t *plaid_jump_begin(plaid_state *s, plaid_native_frame *frame,
                       const uint16_t *layout, int fr0, u32 pc) {
  plaid_jump *j;
  u32 address = (u32)s->r[4], physical;
  if (!frame || frame->owner != host_context || phys(address, 4, &physical) || (address & 3)) {
    plaid_fault(s, pc, 13); return NULL;
  }
  for (j = jumps; j; j = j->next) if ((j->address & 0x1fffffffu) == physical) break;
  if (!j) {
    j = jump_new(address, pc);
    if (!j) return NULL;
  }
  if (j->owner && j->owner != host_context) { plaid_fault(s, pc, 13); return NULL; }
  jump_detach(j);
  j->address = address; j->layout = layout; j->fr0 = fr0; j->pc = pc;
  j->owner = host_context; j->thread = host_context->thread; j->generation = j->thread->generation; j->frame = frame; j->spawned = 0;
  j->frame_next = frame->jumps; frame->jumps = j;
  s->frame_leave = jump_leave;
  return j->host;
}
int plaid_jump_save(plaid_state *s, intptr_t *host) {
  plaid_jump *j = (plaid_jump *)host;
  unsigned i;
  for (i = 0; i < 23; i++) {
    u32 w;
    if (i < 11) w = (u32)s->r[jump_regs[i]];
    else {
      unsigned reg = i + 9, pair = j->fr0 ? reg & ~1u : reg;
      if (plaid_status_fp(s, j->pc, j->fr0)) return 1;
      w = (u32)(s->f[pair] >> (j->fr0 && (reg & 1) ? 32 : 0));
    }
    if (plaid_store(s, SX32(j->address) + j->layout[i], 4, w, j->pc)) return 1;
    j->saved[i] = w;
  }
  j->armed = 0; s->r[2] = 0;
  return 0;
}
int plaid_jump_resume(plaid_state *s, intptr_t *host) {
  plaid_jump *j = (plaid_jump *)host;
  if (j->owner != host_context || !j->armed || host_context->resume != j)
    return plaid_fault(s, j->pc, 13);
  j->armed = 0; host_context->resume = NULL;
  return 0;
}
static void jump_host(rt_context *self) {
  plaid_jump *j = self->resume;
  if (!j || !j->armed || jump_unwind(self, j->frame, j->pc)) finish(1, "invalid coroutine continuation");
  /* No runtime mutex or another host context's frames survive this jump. */
  pthread_mutex_unlock(&big);
  __builtin_longjmp(j->host, 1);
}
static void *coroutine_main(void *p) {
  rt_context *self = p;
  int r;
  host_context = self;
  pthread_mutex_lock(&big);
  wait_for_baton(self->thread);
  pthread_mutex_unlock(&big);
  r = plaid_coroutine_enter(S, self->entry, S->r[31]);
  pthread_mutex_lock(&big);
  if (r == 2) finish(0, "exit");
  if (!r) plaid_fault(S, self->entry, 13);
  finish(1, "coroutine entry returned or faulted");
  return NULL;
}
int plaid_jump_to(plaid_state *s, const uint16_t *layout, int fr0, int nonzero, u32 pc) {
  rt_context *self = host_context, *next;
  plaid_jump *j, *p;
  u32 words[23], address = (u32)s->r[4], physical, value = (u32)s->r[5];
  unsigned i;
  int edited = 0, keep = 0, fresh = 0;
  pthread_mutex_lock(&big);
  if (!self || running != self->thread || self->thread->context != self ||
      phys(address, 4, &physical) || (address & 3)) goto refused;
  for (j = jumps; j; j = j->next) if ((j->address & 0x1fffffffu) == physical) break;
  if (!j) {
    /* A directly authored initial context has no host continuation. It may
       start only at a compiled function entry, never an arbitrary block. */
    if (jump_read(address, layout, words, pc)) goto fault;
    if ((words[0] & 7) || (words[1] & 3) || !plaid_coroutine_target(s, words[1])) goto refused;
    j = jump_new(address, pc);
    if (!j) goto fault;
    j->layout = layout; j->fr0 = fr0; j->pc = pc;
    j->thread = self->thread; j->generation = self->thread->generation;
    memcpy(j->saved, words, sizeof words);
    fresh = edited = 1;
  }
  if (j->fr0 != fr0 || memcmp(layout, j->layout, sizeof(uint16_t) * 23)) goto refused;
  if (j->thread != self->thread || j->generation != self->thread->generation) goto refused;
  if (!fresh && jump_read(address, layout, words, pc)) goto fault;
  for (i = 0; i < 23; i++) if (words[i] != j->saved[i]) {
    if (i > 1) goto refused; /* only a new entry and stack may be authored */
    edited = 1;
  }
  if (!edited && (!j->owner || !j->frame)) goto refused;
  if (edited) {
    rt_context *old = j->owner;
    if (j->spawned) goto refused;
    if ((words[0] & 7) || (words[1] & 3)) goto refused;
    if (old && old != self && !plaid_coroutine_target(s, words[1])) goto refused;
    j->spawned = 1;
    jump_detach(j);
    j->owner = NULL;
    if (old && old != self) {
      int live = 0;
      for (p = jumps; p; p = p->next) if (p->owner == old && p->frame) live = 1;
      if (!live) {
        /* Retargeting its last saved continuation makes this parked stack
           unreachable in the modeled buffer system. It can only exit. */
        old->retired = 1; old->retire_waiter = self; self->retire_pending++;
        pthread_cond_signal(&old->wake);
        while (self->retire_pending) pthread_cond_wait(&self->wake, &big);
      }
    }
    next = new_context(self->thread, 0, words[1]);
  } else {
    next = j->owner;
    j->armed = 1; next->resume = j;
  }
  for (i = 0; i < 23; i++) {
    if (i < 11) s->r[jump_regs[i]] = SX32(words[i]);
    else {
      unsigned reg = i + 9, pair = fr0 ? reg & ~1u : reg, shift = fr0 && (reg & 1) ? 32 : 0;
      if (plaid_status_fp(s, pc, fr0)) goto fault;
      s->f[pair] = (s->f[pair] & ~(0xffffffffull << shift)) | (u64)words[i] << shift;
    }
  }
  s->r[2] = SX32(nonzero && !value ? 1 : value);
  if (next == self) { jump_host(self); return 1; }
  for (p = jumps; p; p = p->next) if (p->frame && p->owner == self) keep = 1;
  if (!keep && jump_unwind(self, NULL, pc)) goto fault;
  self->thread->context = next; s->native_context = next;
  if (edited) {
    pthread_t host;
    pthread_attr_t attr;
    pthread_attr_init(&attr);
    pthread_attr_setstacksize(&attr, 64u << 20);
    if (pthread_create(&host, &attr, coroutine_main, next)) finish(1, "coroutine pthread_create failed");
    pthread_attr_destroy(&attr);
    pthread_detach(host);
  } else pthread_cond_signal(&next->wake);
  if (!keep) {
    retire_context(self);
  }
  wait_for_baton(self->thread);
  jump_host(self);
  return 1;
refused:
  plaid_fault(s, pc, 13);
fault:
  pthread_mutex_unlock(&big);
  return 1;
}
