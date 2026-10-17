"""Independently assembled Status save/dispatch boundaries for the test oracle."""

def context_program(T):
    A = T.A
    code, offset = [], 0
    mfc0 = lambda r: 0x40006000 | r << 16
    mtc0 = lambda r: 0x40806000 | r << 16
    def emit(*words): code.extend(words)
    def log(a, b):
        nonlocal offset
        emit(A.sw(a, offset, A.gp), A.sw(b, offset + 4, A.gp))
        offset += 8
    def read_log(mi=True, context=None):
        if context is None: emit(mfc0(A.t0))
        else: emit(*T.li(A.t3, context), A.lw(A.t0, 0x118, A.t3))
        if mi: emit(*T.li(A.t3, 0xa430000c), A.lw(A.t1, 0, A.t3))
        else: emit(A.lw(A.t1, 0x128, A.t3))
        log(A.t0, A.t1)
    def dispatch(context, global_mask, mi, label):
        emit(*T.li(A.t3, context), A.lw(A.t0, 0x118, A.t3),
             *T.li(A.t1, 0xffff00ff), A.and_(A.t2, A.t0, A.t1),
             *T.li(A.t1, global_mask & 0xff00), A.and_(A.t0, A.t0, A.t1),
             A.or_(A.t0, A.t0, A.t2), mtc0(A.t0), A.nop, A.nop,
             A.lui(A.t1, 0x8000), A.LO(A.t1, A.t1, label), 0x40807000 | A.t1 << 16,
             *T.poke(0xa430000c, sum((2 if mi >> bit & 1 else 1) << (2 * bit) for bit in range(6))),
             0x42000018, A.nop, label)
    one, two = 0x80006000, 0x80006200
    emit(*T.li(A.gp, 0x80001000))
    for context in (one, two):
        emit(*T.poke(context + 0x118, 0xff03), *T.poke(context + 0x128, 0x3f))
    read_log(False, one)
    dispatch(one, 0x3fff01, 0x3f, 'first'); read_log()
    emit(mfc0(A.t0), *T.li(A.t1, 0xfffffffe), A.and_(A.t0, A.t0, A.t1), mtc0(A.t0),
         A.nop, A.nop, A.ori(A.t0, A.t0, 2), *T.li(A.t3, one), A.sw(A.t0, 0x118, A.t3))
    read_log(False, one)
    dispatch(two, 0x1ff01, 1, 'second'); read_log()
    emit(*T.li(A.t3, two), *T.li(A.t1, 2), A.sw(A.t1, 0x128, A.t3),
         *T.li(A.t4, 0xa430000c), A.lw(A.t0, 0, A.t4),
         A.lw(A.t1, 0x128, A.t3), *T.li(A.t2, 0x3e), A.and_(A.t1, A.t1, A.t2),
         A.or_(A.t0, A.t0, A.t1), A.sw(A.t0, 0x128, A.t3),
         mfc0(A.t0), A.ori(A.t0, A.t0, 2), A.sw(A.t0, 0x118, A.t3))
    read_log(False, two)
    emit(mfc0(A.t0), *T.li(A.t1, 0xffff00ff), A.and_(A.t0, A.t0, A.t1),
         A.ori(A.t0, A.t0, 0x5500), mtc0(A.t0), A.nop, A.nop, *T.poke(0xa430000c, 0x555))
    read_log()
    emit(mfc0(A.t0), A.ori(A.t0, A.t0, 2), *T.li(A.t3, two), A.sw(A.t0, 0x118, A.t3), A.sw(A.zero, 0x128, A.t3))
    read_log(False, two)
    dispatch(one, 0x3fff01, 0x3f, 'third'); read_log()
    emit(mfc0(A.t0), A.ori(A.t0, A.t0, 1), mtc0(A.t0), A.nop, A.nop); read_log()
    emit(*T.li(A.t3, two), A.lw(A.t0, 0x118, A.t3), *T.li(A.t1, 0xffffefff),
         A.and_(A.t0, A.t0, A.t1), A.sw(A.t0, 0x118, A.t3))
    dispatch(two, 0x1ff01, 0, 'fourth'); read_log()
    emit(mfc0(A.t0), *T.li(A.t1, 0x20000000), A.or_(A.t0, A.t0, A.t1), mtc0(A.t0),
         A.nop, A.nop, *T.poke(two + 0x18, 1), mfc0(A.t0), *T.li(A.t3, two), A.lw(A.t1, 0x18, A.t3))
    log(A.t0, A.t1)
    dispatch(one, 0x1ff01, 1, 'fifth'); read_log()
    dispatch(one, 0x3fff01, 0x3f, 'sixth'); read_log()
    emit(mfc0(A.t0), *T.li(A.t1, 0x20000000), A.or_(A.t0, A.t0, A.t1), mtc0(A.t0),
         A.nop, A.nop, *T.li(A.t1, 0x01000800), 0x44c0f800 | A.t1 << 16,
         mfc0(A.t0), 0x4440f800 | A.t1 << 16)
    log(A.t0,A.t1)
    emit(mfc0(A.t0),A.ori(A.t0,A.t0,2),*T.li(A.t3,one),A.sw(A.t0,0x118,A.t3),A.lw(A.t1,0x18,A.t3))
    log(A.t1,A.t0)
    return code + list(A.DONE)
