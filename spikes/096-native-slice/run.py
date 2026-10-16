"""Synthetic native vertical slice: ROM words -> CLOSED map -> C -> host binary,
differentially checked against the pinned ares interpreter (ADR-0126)."""
from pathlib import Path
import hashlib, importlib.util, json, os, shutil, subprocess, sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'target/native-slice'
EXIT = 0x80000F00
BASE = 0x80000000

# ---- tiny assembler: ints or callables (pc, labels) -> word; strings are labels
def R(f, rd=0, rs=0, rt=0, sa=0): return rs << 21 | rt << 16 | rd << 11 | sa << 6 | f
def I(op, rt, rs, imm): return op << 26 | rs << 21 | rt << 16 | imm & 0xFFFF
def B(op, rs, rt, label): return lambda pc, L: I(op, rt, rs, (L[label] - pc - 4) >> 2)
def J(op, label): return lambda pc, L: op << 26 | (L[label] >> 2) & 0x3FFFFFF
def LO(rt, rs, label): return lambda pc, L: I(13, rt, rs, L[label])
zero, at, v0, v1, a0, a1, a2, a3 = range(8)
t0, t1, t2, t3, t4, t5, t6, t7, s0, s1, s2, s3, s4, s5, s6, s7, t8, t9 = range(8, 26)
sp, ra = 29, 31
lui = lambda rt, imm: I(15, rt, 0, imm); ori = lambda rt, rs, imm: I(13, rt, rs, imm)
addiu = lambda rt, rs, imm: I(9, rt, rs, imm); slti = lambda rt, rs, imm: I(10, rt, rs, imm)
sltiu = lambda rt, rs, imm: I(11, rt, rs, imm); andi = lambda rt, rs, imm: I(12, rt, rs, imm)
xori = lambda rt, rs, imm: I(14, rt, rs, imm)
mem = lambda op: (lambda rt, off, base: I(op, rt, base, off))
lb, lh, lw, lbu, lhu, sb, sh, sw = map(mem, (32, 33, 35, 36, 37, 40, 41, 43))
alu = lambda f: (lambda rd, rs, rt: R(f, rd, rs, rt))
addu, subu, and_, or_, xor, nor, slt, sltu = map(alu, (33, 35, 36, 37, 38, 39, 42, 43))
shift = lambda f: (lambda rd, rt, sa: R(f, rd, 0, rt, sa))
sll, srl, sra = map(shift, (0, 2, 3))
vshift = lambda f: (lambda rd, rt, rs: R(f, rd, rs, rt))
sllv, srlv, srav = map(vshift, (4, 6, 7))
hilo = lambda f: (lambda rs, rt: R(f, 0, rs, rt))
mult, multu, div, divu = map(hilo, (24, 25, 26, 27))
mfhi = lambda rd: R(16, rd); mflo = lambda rd: R(18, rd)
mthi = lambda rs: R(17, 0, rs); mtlo = lambda rs: R(19, 0, rs)
jr = lambda rs: R(8, 0, rs); jalr = lambda rd, rs: R(9, rd, rs)
beq = lambda rs, rt, l: B(4, rs, rt, l); bne = lambda rs, rt, l: B(5, rs, rt, l)
blez = lambda rs, l: B(6, rs, 0, l); bgtz = lambda rs, l: B(7, rs, 0, l)
bltz = lambda rs, l: B(1, rs, 0, l); bgez = lambda rs, l: B(1, rs, 1, l)
j = lambda l: J(2, l); jal = lambda l: J(3, l)
gp, k0, k1, fp = 28, 26, 27, 30
ld, sd = mem(55), mem(63)
daddu, dsubu, dadd, dsub, add, sub = map(alu, (45, 47, 44, 46, 32, 34))
dsll, dsrl, dsra, dsll32, dsrl32, dsra32 = map(shift, (56, 58, 59, 60, 62, 63))
dsllv, dsrlv, dsrav = map(vshift, (20, 22, 23))
dmult, dmultu, ddiv, ddivu = map(hilo, (28, 29, 30, 31))
addi = lambda rt, rs, imm: I(8, rt, rs, imm); daddi = lambda rt, rs, imm: I(24, rt, rs, imm)
daddiu = lambda rt, rs, imm: I(25, rt, rs, imm)
cop1 = lambda sub: (lambda rt, fs: 17 << 26 | sub << 21 | rt << 16 | fs << 11)
mfc1, dmfc1, mtc1, dmtc1 = map(cop1, (0, 1, 4, 5))
lwc1, ldc1, swc1, sdc1 = map(mem, (49, 53, 57, 61))
beql = lambda rs, rt, l: B(20, rs, rt, l); bnel = lambda rs, rt, l: B(21, rs, rt, l)
blezl = lambda rs, l: B(22, rs, 0, l); bgtzl = lambda rs, l: B(23, rs, 0, l)
bltzl = lambda rs, l: B(1, rs, 2, l); bgezl = lambda rs, l: B(1, rs, 3, l)
lwl, lwr, ldl, ldr, lwu, swl, swr, sdl, sdr = map(mem, (34, 38, 26, 27, 39, 42, 46, 44, 45))
fcmp = lambda fmt, cond: (lambda fs, ft: 17 << 26 | fmt << 21 | ft << 16 | fs << 11 | 48 | cond)
bc1 = lambda nd, tf: (lambda l: B(17, 8, nd << 1 | tf, l))
bc1f, bc1t, bc1fl, bc1tl = bc1(0, 0), bc1(0, 1), bc1(1, 0), bc1(1, 1)
nop = 0
DONE = [j('exit'), nop]

def fcompare():
    # every C.cond.S/D over ordered edge cases; each condition bit is recorded
    # through BC1TL (slot runs only when taken) and BC1F (slot always runs)
    def const64(r, v):
        return [lui(r, v >> 48 & 0xFFFF), ori(r, r, v >> 32 & 0xFFFF), dsll32(r, r, 0),
                lui(at, v >> 16 & 0xFFFF), dsll32(at, at, 0), dsrl32(at, at, 0), or_(r, r, at), ori(r, r, v & 0xFFFF)]
    singles = [(0x3F800000, 0x40000000), (0x40000000, 0x3F800000), (0x3F800000, 0x3F800000),
               (0x80000000, 0x00000000), (0x00000001, 0x00000000), (0xFF800000, 0x7F800000)]
    doubles = [(0x3FF0000000000000, 0x4000000000000000), (0x4000000000000000, 0x3FF0000000000000),
               (0x8000000000000000, 0), (0x0000000000000001, 0)]
    out, n = [], 0
    regs = [s0, s1, s2, s3, s4, s5, s6, s7, t8, t9]
    for fmt, pairs in ((16, singles), (17, doubles)):
        for x, y in pairs:
            r = regs[n]; n += 1
            if fmt == 16:
                out += [lui(t0, x >> 16), ori(t0, t0, x & 0xFFFF), mtc1(t0, 1), lui(t0, y >> 16), ori(t0, t0, y & 0xFFFF), mtc1(t0, 2)]
            else:
                out += [*const64(t0, x), dmtc1(t0, 1), *const64(t0, y), dmtc1(t0, 2)]
            for cond in range(16):
                skip = f'k{n}_{cond}'
                out += [fcmp(fmt, cond)(1, 2), bc1tl(skip), ori(r, r, 1 << cond), skip]
            out += [fcmp(fmt, 2)(1, 2), bc1f(f'f{n}'), ori(v0, v0, 1 << n), ori(v1, v1, 1 << n), f'f{n}']
    return out + DONE

fop = lambda fmt, f: (lambda fd, fs, ft=0: 17 << 26 | fmt << 21 | ft << 16 | fs << 11 | fd << 6 | f)
cfc1, ctc1 = cop1(2), cop1(6)

def farith():
    # COP1 arithmetic, conversions and FCSR (ADR-0139): results and FCSR
    # snapshots go to RAM; each rounding mode drives CVT.W and a division.
    import struct
    S = lambda x: struct.unpack('>I', struct.pack('>f', x))[0]
    D = lambda x: struct.unpack('>Q', struct.pack('>d', x))[0]
    def c32(f, v): return [lui(t0, v >> 16), ori(t0, t0, v & 0xFFFF), mtc1(t0, f)]
    def c64(f, v):
        return [lui(t0, v >> 48 & 0xFFFF), ori(t0, t0, v >> 32 & 0xFFFF), dsll32(t0, t0, 0),
                lui(at, v >> 16 & 0xFFFF), dsll32(at, at, 0), dsrl32(at, at, 0), or_(t0, t0, at),
                ori(t0, t0, v & 0xFFFF), dmtc1(t0, f)]
    out, off = [lui(gp, 0x8000), ori(gp, gp, 0x1000)], [0]
    def keep(f, wide=False):
        o = off[0] = (off[0] + 7) & ~7 if wide else off[0]
        off[0] += 8 if wide else 4
        return [(sdc1 if wide else swc1)(f, o, gp)]
    def fcsr():
        o = off[0]; off[0] += 4
        return [cfc1(t1, 31), sw(t1, o, gp)]
    s_, d_ = (lambda f: fop(16, f)), (lambda f: fop(17, f))
    out += c32(1, S(1.0)) + c32(2, S(3.0)) + [mtc1(zero, 4)] + c32(6, S(1e30)) + c32(8, S(-1.0))
    out += [s_(3)(3, 1, 2), *keep(3), *fcsr(), s_(0)(3, 1, 2), *keep(3), *fcsr(),
            s_(1)(3, 1, 2), *keep(3), s_(2)(3, 2, 2), *keep(3),
            s_(3)(5, 1, 4), *keep(5), *fcsr(), s_(4)(5, 2), *keep(5), *fcsr(),
            s_(4)(5, 8), *keep(5), *fcsr(), s_(2)(7, 6, 6), *keep(7), *fcsr(),
            s_(7)(9, 2), s_(5)(10, 8), s_(6)(11, 6),
            # ADD.S into $f0 has all-zero low bits, like a COP1 move
            s_(0)(0, 1, 2), *keep(0)]
    out += c64(12, D(1.0)) + c64(14, D(3.0))
    out += [d_(3)(16, 12, 14), *keep(16, True), d_(0)(18, 12, 14), d_(1)(20, 12, 14),
            d_(2)(22, 14, 14), d_(4)(24, 14), *keep(24, True), d_(7)(26, 14), d_(5)(26, 26), *fcsr()]
    # conversions
    out += [s_(3)(3, 1, 2), s_(33)(13, 3), d_(32)(15, 16), *fcsr(), addiu(t2, zero, 7), mtc1(t2, 17),
            fop(20, 32)(17, 17), addiu(t2, zero, -5), mtc1(t2, 19), fop(20, 33)(19, 19)]
    out += c64(21, 0x0000123456789ABC) + [fop(21, 32)(23, 21), fop(21, 33)(25, 21), *fcsr()]
    out += c32(27, S(2.5)) + c32(28, S(-2.5)) + c64(29, D(-2.7))
    regs = [s0, s1, s2, s3, s4, s5, s6, s7]
    for rm in range(4):
        out += [addiu(t1, zero, rm), ctc1(t1, 31), s_(36)(30, 27), mfc1(regs[2 * rm], 30),
                s_(36)(30, 28), mfc1(regs[2 * rm + 1], 30), s_(3)(31, 1, 2), *keep(31), *fcsr()]
    out += [s_(13)(30, 28), mfc1(t8, 30), d_(13)(30, 29), mfc1(t9, 30), d_(36)(30, 29), mfc1(v0, 30), *fcsr()]
    # FS flushes an underflowing result per rounding mode
    out += c32(0, S(1e-30)) + c32(30, S(1e-10))
    for rm in (0, 2):
        out += [lui(t1, 0x0100), ori(t1, t1, rm), ctc1(t1, 31), s_(2)(31, 0, 30), *keep(31), *fcsr()]
    out += [cfc1(v1, 0), ctc1(zero, 31), *fcsr()]
    assert off[0] <= 0x100
    return out + DONE

def fround():
    # ROUND/TRUNC/CEIL/FLOOR to W and L, and CVT.L (ADR-0143): ties, signs,
    # fractions and a 2^40 + 0.5 double; results and the final FCSR to RAM.
    import struct
    S = lambda x: struct.unpack('>I', struct.pack('>f', x))[0]
    D = lambda x: struct.unpack('>Q', struct.pack('>d', x))[0]
    def c32(f, v): return [lui(t0, v >> 16), ori(t0, t0, v & 0xFFFF), mtc1(t0, f)]
    def c64(f, v):
        return [lui(t0, v >> 48 & 0xFFFF), ori(t0, t0, v >> 32 & 0xFFFF), dsll32(t0, t0, 0),
                lui(at, v >> 16 & 0xFFFF), dsll32(at, at, 0), dsrl32(at, at, 0), or_(t0, t0, at),
                ori(t0, t0, v & 0xFFFF), dmtc1(t0, f)]
    out, off = [lui(gp, 0x8000), ori(gp, gp, 0x1000)], [0]
    def keep(f, wide=False):
        o = off[0] = (off[0] + 7) & ~7 if wide else off[0]
        off[0] += 8 if wide else 4
        return [(sdc1 if wide else swc1)(f, o, gp)]
    for fmt, value, const, ops in [(16, x, c32, range(8, 16)) for x in (2.5, -2.5, -0.5, 1.75)] +             [(17, -3.5, c64, range(8, 16)), (17, 2.0 ** 40 + 0.5, c64, range(8, 12))]:
        out += const(1, S(value) if fmt == 16 else D(value))
        for f in ops:
            out += [fop(fmt, f)(2, 1), *keep(2, f < 12 and value > 2 ** 31)]
    out += c32(1, S(2.5)) + [addiu(t1, zero, 2), ctc1(t1, 31), fop(16, 37)(2, 1), *keep(2, True)]
    out += c64(1, D(-(2.0 ** 40) - 0.5)) + [addiu(t1, zero, 3), ctc1(t1, 31), fop(17, 37)(2, 1), *keep(2, True)]
    o = off[0]; off[0] += 4
    out += [cfc1(t1, 31), sw(t1, o, gp), ctc1(zero, 31)]
    assert off[0] <= 0x100
    return out + DONE

ll, lld, sc, scd = map(mem, (48, 52, 56, 60))

def system():
    # LL/SC, SYNC, untaken conditional traps and REGIMM branch-and-link (ADR-0145).
    rt_trap = lambda f: (lambda rs, rt: R(f, 0, rs, rt))
    tge, tgeu, tlt, tltu, teq, tne = map(rt_trap, (48, 49, 50, 51, 52, 54))
    im_trap = lambda k: (lambda rs, imm: I(1, k, rs, imm))
    tgei, tgeiu, tlti, tltiu, teqi, tnei = map(im_trap, (8, 9, 10, 11, 12, 14))
    link = lambda k: (lambda rs, l: B(1, rs, k, l))
    bltzal, bgezal, bltzall, bgezall = map(link, (16, 17, 18, 19))
    return [lui(gp, 0x8000), ori(gp, gp, 0x1000), addiu(t0, zero, 7), sw(t0, 0, gp),
        addiu(t2, zero, 99), sc(t2, 0, gp),
        ll(t3, 0, gp), addiu(t3, t3, 1), sc(t3, 0, gp),
        addiu(t4, zero, -3), sd(t4, 8, gp), lld(t5, 8, gp), daddiu(t5, t5, 10), scd(t5, 8, gp), R(15),
        addiu(s0, zero, 1), addiu(s1, zero, 2), addiu(s2, zero, -1),
        tge(s0, s1), tgeu(s0, s1), tlt(s1, s0), tltu(s1, s0), teq(s0, s1), tne(s0, s0),
        lui(s3, 1), tgei(s0, 5), tgeiu(s0, -1), tgeiu(s3, -1), tlti(s0, -4), tltiu(s0, 0), tltiu(s2, -1), teqi(s0, 3), tnei(s0, 1),
        bgezal(zero, 'f'), nop, mfhi(t6), bltzal(s0, 'f'), addiu(t7, t7, 1), addu(t8, ra, zero),
        bgezall(s2, 'f'), addiu(v1, v1, 100), bltzall(s2, 'f'), addiu(v1, v1, 1),
        bgezal(s0, 'f'), addiu(v1, v1, 10), *DONE,
        'f', addiu(v0, v0, 1), jr(ra), nop]

def label_pcs(items):
    labels, pc = {'exit': EXIT}, BASE
    for x in items:
        if isinstance(x, str): labels[x] = pc
        else: pc += 4
    return labels

def assemble(items):
    labels = label_pcs(items)
    words, pc = [], BASE
    for x in items:
        if isinstance(x, str): continue
        words.append(x(pc, labels) & 0xFFFFFFFF if callable(x) else x); pc += 4
    assert pc < EXIT
    words += [0] * ((EXIT - pc) // 4) + [0x1000FFFF, 0]  # exit: b . ; nop
    return b''.join(w.to_bytes(4, 'big') for w in words)

LOAD_AT = EXIT + 8
# A position-independent routine stored as data, copied to LOAD_AT through
# KSEG1 (no D-cache write-back needed) and called there (ADR-0136).
PAYLOAD = ['payload', addiu(v0, zero, 0), addiu(t0, zero, 4),
    'pl', addu(v0, v0, t0), addiu(t0, t0, -1), bgtz(t0, 'pl'), nop, jr(ra), nop]
# A load placed away from the image leaves a hole in the composite (ADR-0150).
LOAD_DEST = {'load_gap': LOAD_AT + 0x100}

def load_program(early=False, patch=False, at=LOAD_AT, reload=False, payload=None):
    def copy(label):
        return [lui(s0, 0xA000), LO(s0, s0, 'payload'), lui(s1, 0xA000), ori(s1, s1, at & 0xFFFF),
            addiu(s2, zero, 8),
            label, lw(t1, 0, s0), sw(t1, 0, s1), addiu(s0, s0, 4), addiu(s1, s1, 4), addiu(s2, s2, -1), bgtz(s2, label), nop]
    call = [lambda pc, L: 3 << 26 | (at >> 2) & 0x3FFFFFF, nop, addu(s3, v0, zero)]
    body = call + copy('cp') if early else copy('cp') + call
    # A write into the verified load revokes it (ADR-0161): entering it again
    # compares its bytes, so a changed word faults 8 and a reloaded copy runs.
    if patch or reload:
        body += [sw(s1, -4, s1)]
    if reload:
        body += copy('cp2')
    if patch or reload:
        body += call
    return [*body, *DONE, *(payload or PAYLOAD)]

# The load's own code writing its bytes: fault 2 (ADR-0161).
SELF_PAYLOAD = ['payload', lui(t0, 0xA000), ori(t0, t0, LOAD_AT & 0xFFFF), sw(t0, 0, t0), jr(ra), nop, nop, nop, nop]

# A relocatable overlay (ADR-0181) in the Zelda64 trailer format, linked at
# OVL_LINK and declared there; the program copies loader-relocated images to
# real bases and calls a function pointer read from the overlay's data.
OVL_LINK, OVL_B1, OVL_B2 = 0x80600000, 0x80003000, 0x80007FC0  # B2: LO16 carry

def overlay_file(extra=()):
    # (word, relocation kind or None, label); HI16/LO16 name 'ovar' or 'ovh'
    hi = lambda rt, sym: ('hi', I(15, rt, 0, 0), sym)
    lo = lambda op, rt, rs, sym: ('lo', I(op, rt, rs, 0), sym)
    text = [(addiu(sp, sp, -16),), (sw(ra, 12, sp),), hi(t0, 'ovar'), lo(35, t1, t0, 'ovar'),
        (addiu(t1, t1, 7),), lo(43, t1, t0, 'ovar'), ('jal', 3 << 26, 'ovh'), (nop,),
        hi(t2, 'ovar'), lo(9, s4, t2, 'ovar'), *extra, (lw(ra, 12, sp),), (jr(ra),), (addiu(sp, sp, 16),),
        ('ovh',), (addu(v1, ra, zero),), (jr(ra),), (addiu(v0, zero, 42),)]
    syms, at = {}, 0
    for x in text:
        if x[0] == 'ovh': syms['ovh'] = at
        else: at += 4
    syms['ovar'] = at  # data: ovar, then fptr -> ovf (offset 0)
    words, relocs = [], []
    for x in text:
        if x[0] == 'ovh': continue
        off = len(words) * 4
        if x[0] == 'hi':
            v = OVL_LINK + syms[x[2]]
            words.append(x[1] | ((v + 0x8000) >> 16)); relocs.append((1, 5, off))
        elif x[0] == 'lo':
            words.append(x[1] | ((OVL_LINK + syms[x[2]]) & 0xFFFF)); relocs.append((1, 6, off))
        elif x[0] == 'jal':
            words.append(x[1] | ((OVL_LINK + syms['ovh']) & 0x0FFFFFFF) >> 2); relocs.append((1, 4, off))
        else:
            words.append(x[0])
    text_size = len(words) * 4
    words += [100, OVL_LINK]; relocs.append((2, 2, 4))
    start = len(words)
    words += [text_size, 8, 0, 8, len(relocs)] + [sec << 30 | kind << 24 | off for sec, kind, off in relocs]
    while (len(words) + 1) % 4: words.append(0)
    words.append((len(words) + 1 - start) * 4)
    return words, relocs, text_size

def relocate(words, relocs, text_size, base):
    out, delta, highs = list(words), base - OVL_LINK, {}
    for sec, kind, off in relocs:
        at = (off + (text_size if sec == 2 else 0)) // 4
        w = out[at]
        if kind == 2: out[at] = (w + delta) & 0xFFFFFFFF
        elif kind == 4: out[at] = w & 0xFC000000 | ((((w & 0x3FFFFFF) << 2 | 0x80000000) + delta) & 0x0FFFFFFF) >> 2
        elif kind == 5: highs[(w >> 16) & 31] = (at, words[at])
        else:
            h, orig = highs[(w >> 21) & 31]
            v = ((orig << 16) + (w & 0xFFFF ^ 0x8000) - 0x8000 + delta) & 0xFFFFFFFF
            out[h] = out[h] & 0xFFFF0000 | ((v + 0x8000) >> 16) & 0xFFFF
            out[at] = w & 0xFFFF0000 | v & 0xFFFF
    return out

def overlay_program(extra=(), tamper=False, revoke=True):
    words, relocs, text_size = overlay_file(extra)
    fptr = text_size + 4
    def copy(label, dst, n):
        return [lui(s6, 0xA000), LO(s6, s6, label), lui(s7, dst >> 16 | 0x2000), ori(s7, s7, dst & 0xFFFF),
            addiu(t8, zero, n), label + '_cp', lw(t1, 0, s6), sw(t1, 0, s7), addiu(s6, s6, 4), addiu(s7, s7, 4),
            addiu(t8, t8, -1), bgtz(t8, label + '_cp'), nop]
    def call(base):
        a = base + fptr
        return [lui(t0, (a + 0x8000) >> 16), lw(t9, a & 0xFFFF, t0), lui(a0, 0x8000), LO(a0, a0, 'clobber'),
            jalr(ra, t9), nop]
    poke = [lui(t0, 0xA000), sw(zero, (OVL_B1 + 0x10) & 0xFFFF, t0)]  # a non-relocated text word of B1
    body = [lui(sp, 0x8000), ori(sp, sp, 0x1100), *copy('ovl_b1', OVL_B1, len(words)), *(poke if tamper else []),
        *call(OVL_B1), addu(s0, v1, zero), addu(s1, s4, zero), addu(s2, v0, zero)]
    if revoke:
        # a write into B1's text revokes its binding, so the copy at B2 binds
        body += [*poke, *copy('ovl_b2', OVL_B2, len(words)), *call(OVL_B2), addu(s3, v1, zero),
            lui(t0, (OVL_B1 + text_size + 0x8000) >> 16), lw(s5, (OVL_B1 + text_size) & 0xFFFF, t0)]
    return [*body, *DONE, 'pad', jr(ra), nop, 'clobber', *poke, jr(ra), nop,
        'ovl_link', *words, 'ovl_b1', *relocate(words, relocs, text_size, OVL_B1),
        'ovl_b2', *relocate(words, relocs, text_size, OVL_B2)]

OVERLAYS = {'overlay': overlay_program(),
    # tampered bytes match no overlay at any base: unknown target, fault 3
    'ovl_tamper': overlay_program(tamper=True, revoke=False),
    # overlay code writing its own text: fault 2
    'ovl_self': overlay_program(extra=[('hi', I(15, t3, 0, 0), 'ovh'), ('lo', I(43, zero, t3, 0), 'ovh')], revoke=False),
    # a callee revokes the binding; returning into the overlay: fault 8
    'ovl_callback': overlay_program(extra=[(jalr(ra, a0),), (nop,)], revoke=False)}

def tlb_program(body, odd_valid=True, dirty=True, even0=0x2000):
    # TLB-mapped data (ADR-0162). On ares `map` runs MTC0 and TLBWI; natively
    # runtime.c writes the same entry. Pages are global and cached.
    mtc0 = lambda rt, rd: 0x40800000 | rt << 16 | rd << 11
    lo = lambda pa, v=1, d=1: (pa >> 6) | 3 << 3 | d << 2 | v << 1 | 1
    const = lambda r, v: [lui(r, v >> 16), ori(r, r, v & 0xFFFF)]
    def entry(i, mask, hi, lo0, lo1):
        return [addiu(a0, zero, i), *const(a1, mask), *const(a2, hi), *const(a3, lo0), *const(t0, lo1),
            sw(t0, 16, sp), jal('map'), nop]
    return [lui(sp, 0x8000), ori(sp, sp, 0x2000),
        *entry(0, 0, 0x00100000, lo(even0, d=int(dirty)), lo(0x1000)),
        *entry(1, 0x1E000, 0x04000000, lo(0), lo(0x10000, v=int(odd_valid))),
        *entry(2, 0, 0xC0000000, lo(0x2000), lo(0x1000)),
        *body, or_(t0, zero, zero), *DONE,
        'map', mtc0(a0, 0), mtc0(a1, 5), mtc0(a2, 10), mtc0(a3, 2), lw(t0, 16, sp), mtc0(t0, 3), nop,
        0x42000002, nop, jr(ra), nop]

def jump_table(prefix):
    # GCC shape: the index scale SLL sits in the bound check's delay slot.
    return [*prefix, addiu(s1, zero, 0), addiu(t0, zero, 0),
        'loop', sltiu(at, t0, 3), beq(at, zero, 'dflt'), sll(t1, t0, 2),
        lui(at, 0x8000), addu(at, at, t1), lambda pc, L: I(35, t1, at, L['tbl']), jr(t1), nop,
        'c0', addiu(s1, s1, 1), j('next'), nop,
        'c1', addiu(s1, s1, 10), j('next'), nop,
        'c2', addiu(s1, s1, 100), j('next'), nop,
        'dflt', addiu(s1, s1, 1000),
        'next', addiu(t0, t0, 1), slti(t2, t0, 4), bne(t2, zero, 'loop'), nop, *DONE,
        'tbl', lambda pc, L: L['c0'], lambda pc, L: L['c1'], lambda pc, L: L['c2']]

def scheduled_table():
    # GCC's scheduled shape (ADR-0140): work between the bound and its branch,
    # the base LUI between scale and add, and a branch-likely loop back into
    # the guard carrying the bound in its slot.
    return [addiu(s1, zero, 0), addiu(t0, zero, 0), addiu(t3, zero, 0), sltiu(at, t0, 3), addiu(t3, t3, 1),
        'guard', beq(at, zero, 'dflt'), nop,
        sll(t1, t0, 2), lui(at, 0x8000), addu(at, at, t1), lambda pc, L: I(35, t1, at, L['tbl']), jr(t1), nop,
        'c0', addiu(s1, s1, 1), j('next'), nop,
        'c1', addiu(s1, s1, 10), j('next'), nop,
        'c2', addiu(s1, s1, 100), j('next'), nop,
        'dflt', addiu(s1, s1, 1000),
        'next', addiu(t0, t0, 1), slti(t2, t0, 5), bnel(t2, zero, 'guard'), sltiu(at, t0, 3), *DONE,
        'tbl', lambda pc, L: L['c0'], lambda pc, L: L['c1'], lambda pc, L: L['c2']]

PROGRAMS = {
    'alu': [lui(t0, 0x8000), ori(t0, t0, 0x1234), addiu(t1, zero, -5),
        addu(t2, t0, t1), subu(t3, t1, t0), and_(t4, t0, t1), or_(t5, t0, t1), xor(t6, t0, t1), nor(t7, t0, t1),
        slt(s0, t1, t0), sltu(s1, t1, t0), slti(s2, t1, -4), sltiu(s3, t1, -4), andi(s4, t1, 0xFF0F), xori(s5, t0, 0xFFFF),
        sll(s6, t1, 4), srl(s7, t1, 4), sra(t8, t1, 4), addiu(a0, zero, 35), sllv(t9, t0, a0), srlv(v0, t1, a0), srav(v1, t1, a0),
        lui(a1, 0x7FFF), ori(a1, a1, 0xFFFF), addiu(a1, a1, 1), *DONE],
    'muldiv': [addiu(t0, zero, -7), addiu(t1, zero, 3), mult(t0, t1), mfhi(s0), mflo(s1), multu(t0, t1), mfhi(s2), mflo(s3),
        div(t0, t1), mfhi(s4), mflo(s5), divu(t0, t1), mfhi(s6), mflo(s7),
        div(t0, zero), mfhi(a0), mflo(a1), divu(t1, zero), mfhi(a2), mflo(a3),
        lui(t2, 0x8000), addiu(t3, zero, -1), div(t2, t3), mfhi(t4), mflo(t5),
        lui(t6, 0x1234), ori(t6, t6, 0x5678), mthi(t6), mtlo(t1), mfhi(t7), mflo(t8), *DONE],
    'loops': [addiu(t0, zero, 0), addiu(t1, zero, 1), addiu(t2, zero, 101),
        'l1', addu(t0, t0, t1), addiu(t1, t1, 1), bne(t1, t2, 'l1'), nop,
        addiu(t3, zero, 10), addiu(t4, zero, 0),
        'l2', addiu(t4, t4, 3), addiu(t3, t3, -1), bgtz(t3, 'l2'), nop,
        addiu(t5, zero, -1), bltz(t5, 'l3'), addiu(t6, zero, 1), addiu(t6, t6, 100),
        'l3', bgez(t5, 'l4'), addiu(t7, zero, 2), addiu(t7, t7, 50),
        'l4', blez(zero, 'l5'), addiu(s0, zero, 9), addiu(s0, s0, 9),
        'l5', *DONE],
    'memory': [lui(s0, 0x8000), ori(s0, s0, 0x1000), lui(s1, 0xA000), ori(s1, s1, 0x1080),
        lui(t0, 0x89AB), ori(t0, t0, 0xCDEF), sw(t0, 0, s0), sh(t0, 4, s0), sb(t0, 7, s0), sb(t0, 8, s0),
        lw(t1, 0, s0), lh(t2, 0, s0), lhu(t3, 0, s0), lb(t4, 0, s0), lbu(t5, 0, s0), lh(t6, 2, s0), lb(t7, 3, s0),
        addiu(t8, zero, -2), sw(t8, 12, s1), lw(t9, 12, s1), sh(t8, 16, s1), lw(a0, 16, s1), lbu(a1, 17, s1),
        sw(t0, 0x20, s0), lb(a2, 0x21, s0), *DONE],
    # A line used only uncached so far is not cached: its first cached access
    # is coherent (ADR-0176); the reverse order still faults (cache_alias).
    'uncached_first': [lui(s1, 0xA000), ori(s1, s1, 0x1040), addiu(t0, zero, 0x55), sw(t0, 0, s1), lw(t1, 4, s1),
        lui(s0, 0x8000), ori(s0, s0, 0x1040), lw(t2, 0, s0), addiu(t3, zero, 0x66), sw(t3, 4, s0), lw(t4, 4, s0), *DONE],
    # LWL/LWR/LDL/LDR/LWU and SWL/SWR/SDL/SDR at every misalignment; v0 has a
    # non-sign-extended upper word to expose LWR's upper-word rule.
    'unaligned': [lui(s0, 0x8000), ori(s0, s0, 0x1000), lui(t0, 0x89AB), ori(t0, t0, 0xCDEF),
        lui(t1, 0x0123), ori(t1, t1, 0x4567), sw(t0, 0, s0), sw(t1, 4, s0), sw(t1, 8, s0), sw(t0, 12, s0),
        *[sw(t0, o, s0) for o in (0x40, 0x44, 0x48, 0x4C, 0x60, 0x64, 0x68, 0x6C)], sw(t1, 0x50, s0), sw(t1, 0x54, s0),
        lui(v0, 0x1234), ori(v0, v0, 0x5678), dsll32(v0, v0, 0), ori(v0, v0, 0x5678),
        lwl(t2, 1, s0), lwr(t2, 4, s0),
        *[x for r, o in ((t3, 0), (t4, 1), (t5, 2), (t6, 3)) for x in (daddu(r, v0, zero), lwl(r, o, s0))],
        *[x for r, o in ((t7, 0), (t8, 1), (t9, 2), (s1, 3)) for x in (daddu(r, v0, zero), lwr(r, o, s0))],
        *[x for r, op, o in ((s2, ldl, 3), (s3, ldl, 10), (s4, ldr, 3), (s5, ldr, 10)) for x in (daddu(r, v0, zero), op(r, o, s0))],
        lwu(s6, 0, s0),
        swl(t1, 0x41, s0), swr(t1, 0x46, s0), swl(t1, 0x48, s0), swr(t1, 0x4F, s0), swl(t1, 0x4F, s0), swr(t1, 0x4C, s0),
        swl(t0, 0x51, s0), swr(t0, 0x54, s0), sdl(v0, 0x63, s0), sdr(v0, 0x6D, s0), *DONE],
    'fcompare': fcompare(),
    'farith': farith(),
    'fround': fround(),
    'system': system(),
    # A non-leaf host entry returns to the host's $ra (ADR-0146).
    'hostreturn': [lui(sp, 0x8000), ori(sp, sp, 0x1100), addiu(sp, sp, -8), sw(ra, 4, sp), jal('f'), nop,
        addu(s0, v0, zero), lw(ra, 4, sp), jr(ra), addiu(sp, sp, 8),
        'f', addiu(v0, zero, 42), jr(ra), nop],
    'load': load_program(),
    'load_gap': load_program(at=LOAD_DEST['load_gap']),
    'load_reload': load_program(reload=True),
    # GCC's divide check: BREAK 7 guarded by a divisor test that is not taken.
    'divcheck': [addiu(t0, zero, 21), addiu(t1, zero, 4), div(t0, t1), bne(t1, zero, 'ok'), nop,
        R(13, 0, 0, 7 >> 5, 7 & 31), 'ok', mflo(t2), mfhi(t3), *DONE],
    'transfers': [addiu(t0, zero, 1), beq(t0, t0, 'a'), addiu(t0, zero, 5), addiu(t1, zero, 99),
        'a', bne(t0, zero, 'b'), addiu(t2, t0, 1),
        'b', jal('c'), addu(t3, ra, zero), addiu(t4, zero, 7), *DONE,
        'c', lui(t5, 0x8000), LO(t5, t5, 'd'), jr(t5), addiu(t6, zero, 3),
        'd', addiu(t7, zero, 4), lui(a0, 0x8000), LO(a0, a0, 'e'), jalr(a1, a0), nop,
        'e', addu(a2, a1, zero), *DONE],
    # 64-bit ALU, shifts, 128-bit HI/LO, LD/SD, trapping adds that do not trap,
    # and branch-likely slots (taken and nullified).
    'wide': [lui(gp, 0x8000), ori(gp, gp, 0x1000), lui(t0, 0x8000), ori(t0, t0, 0x1234),
        dsll32(t1, t0, 0), dsrl32(t2, t1, 4), dsra32(t3, t1, 4), dsll(t4, t0, 12), dsrl(t5, t1, 8), dsra(t6, t1, 8),
        addiu(a0, zero, 40), dsllv(t7, t0, a0), dsrlv(s0, t1, a0), dsrav(s1, t1, a0),
        daddu(s2, t1, t0), dsubu(s3, t0, t1), daddiu(s4, t1, -1), dadd(s5, t0, t0), dsub(s6, t1, t0), daddi(s7, t1, -1),
        add(t8, a0, a0), sub(t9, a0, t0), addi(v0, a0, -50),
        dmult(t1, t0), mfhi(a1), mflo(a2), sd(a1, 0, gp), sd(a2, 8, gp),
        dmultu(t1, t0), mfhi(a1), mflo(a2), sd(a1, 16, gp), sd(a2, 24, gp),
        ddiv(t1, t0), mfhi(a1), mflo(a2), sd(a1, 32, gp), sd(a2, 40, gp),
        ddivu(t1, t0), mfhi(a1), mflo(a2), sd(a1, 48, gp), sd(a2, 56, gp),
        ddiv(t1, zero), mfhi(a1), mflo(a2), sd(a1, 64, gp), sd(a2, 72, gp),
        ddivu(t0, zero), mfhi(a1), mflo(a2), sd(a1, 80, gp), sd(a2, 88, gp),
        lui(a3, 0x8000), dsll32(a3, a3, 0), daddiu(v1, zero, -1),
        ddiv(a3, v1), mfhi(a1), mflo(a2), sd(a1, 96, gp), sd(a2, 104, gp), ld(k0, 8, gp),
        addiu(k1, zero, 0), beql(zero, zero, 'l1'), addiu(k1, k1, 1), addiu(k1, k1, 100),
        'l1', bnel(zero, zero, 'l2'), addiu(k1, k1, 10), addiu(k1, k1, 1000),
        'l2', blezl(zero, 'l3'), addiu(fp, zero, 7), addiu(fp, fp, 1),
        'l3', bgtzl(zero, 'l4'), addiu(fp, fp, 20),
        'l4', bltzl(t1, 'l5'), addiu(fp, fp, 300), addiu(fp, fp, 4000),
        'l5', bgezl(t1, 'l6'), addiu(fp, fp, 5000),
        'l6', *DONE],
    # Calls and a tail call into a declared runtime function (ADR-0129). The
    # guest body runs on ares; natively it is never decoded (its SYNC is outside
    # the scope) and runtime.c provides it. Caller-saved registers the ABI
    # leaves unspecified are cleared after each call.
    'boundary': [lui(s0, 0x8000), ori(s0, s0, 0x1000),
        lui(t0, 0x0102), ori(t0, t0, 0x0304), sw(t0, 0, s0), lui(t0, 0x05FE), ori(t0, t0, 0x0780), sw(t0, 4, s0),
        addu(a0, s0, zero), addiu(a1, zero, 8), jal('sum'), nop, addu(s1, v0, zero),
        addu(a0, s0, zero), addiu(a1, zero, 4), jal('wrap'), nop, addu(s2, v0, zero),
        or_(a0, zero, zero), or_(a1, zero, zero), or_(t0, zero, zero), *DONE,
        'wrap', addiu(a1, a1, 1), j('sum'), nop,
        'sum', addu(v0, zero, zero),
        'sl', lbu(t0, 0, a0), addu(v0, v0, t0), addiu(a0, a0, 1), addiu(a1, a1, -1), bgtz(a1, 'sl'), nop,
        R(15), jr(ra), nop],
    # A runtime function entering guest code it is passed (ADR-0130). Only the
    # proven callback reaches plaid_enter natively.
    'callback': [lui(sp, 0x8000), ori(sp, sp, 0x2000),
        lui(a0, 0x8000), LO(a0, a0, 'cb'), addiu(a1, zero, 21), jal('spawn'), nop, addu(s1, v0, zero),
        or_(a0, zero, zero), or_(t9, zero, zero), *DONE,
        'cb', addu(v0, a0, a0), jr(ra), nop,
        'spawn', addiu(sp, sp, -8), sw(ra, 4, sp), addu(t9, a0, zero), addu(a0, a1, zero), jalr(ra, t9), nop,
        addiu(v0, v0, 1), lw(ra, 4, sp), R(15), jr(ra), addiu(sp, sp, 8)],
    # A wrapper spills its callback argument IDO-style and forwards it to the
    # runtime (ADR-0149); both callers' constants are entered natively.
    'forwarded': [lui(sp, 0x8000), ori(sp, sp, 0x2000), lui(gp, 0x8000), ori(gp, gp, 0x1000),
        lui(a0, 0x8000), LO(a0, a0, 'cb1'), addiu(a1, zero, 21), jal('go'), nop, addu(s1, v0, zero),
        lui(a0, 0x8000), LO(a0, a0, 'cb2'), addiu(a1, zero, 5), jal('go'), nop, addu(s2, v0, zero),
        or_(a0, zero, zero), or_(a1, zero, zero), or_(t9, zero, zero), *DONE,
        'cb1', addu(v0, a0, a0), jr(ra), nop,
        'cb2', addiu(v0, a0, 100), jr(ra), nop,
        'go', addiu(sp, sp, -24), sw(ra, 20, sp), sw(a0, 24, sp), sw(a1, 28, sp), sw(zero, 0, gp),
        lw(a0, 24, sp), lw(a1, 28, sp), jal('spawn'), nop, lw(ra, 20, sp), jr(ra), addiu(sp, sp, 24),
        'spawn', addiu(sp, sp, -8), sw(ra, 4, sp), addu(t9, a0, zero), addu(a0, a1, zero), jalr(ra, t9), nop,
        addiu(v0, v0, 1), lw(ra, 4, sp), R(15), jr(ra), addiu(sp, sp, 8)],
    # COP1 data moves with 64-bit FPRs: 32-bit forms keep the high word (ADR-0131).
    'fpu': [lui(gp, 0x8000), ori(gp, gp, 0x1000), lui(t0, 0x3F80), mtc1(t0, 0), swc1(0, 0, gp),
        lui(t1, 0x1234), ori(t1, t1, 0x5678), dsll32(t1, t1, 0), ori(t1, t1, 0x9ABC),
        dmtc1(t1, 2), sdc1(2, 8, gp), dmfc1(t2, 2), mfc1(t3, 2), mtc1(t0, 2), dmfc1(t4, 2),
        lui(t5, 0x8765), ori(t5, t5, 0x4321), sw(t5, 16, gp), lwc1(4, 16, gp), mfc1(t6, 4),
        ldc1(6, 8, gp), dmfc1(t7, 6), mtc1(t5, 1), dmfc1(s0, 1), sdc1(2, 24, gp), *DONE],
    # A bounded jump table, closed under the guarded scope (ADR-0132).
    'table': jump_table([]),
    'scheduled_table': scheduled_table(),
    # Register calls through memory dispatch over the address-taken
    # functions (ADR-0153): f1 is taken by a code constant, f2 only by a
    # data word.
    'addrtaken': [lui(sp, 0x8000), ori(sp, sp, 0x2000), lui(gp, 0x8000), ori(gp, gp, 0x1000),
        lui(t0, 0x8000), LO(t0, t0, 'f1'), sw(t0, 0, gp), lw(t9, 0, gp), addiu(a0, zero, 7), jalr(ra, t9), nop,
        addu(s1, v0, zero),
        lui(t1, 0x8000), LO(t1, t1, 'ptr'), lw(t9, 0, t1), addiu(a0, zero, 5), jalr(ra, t9), nop, addu(s2, v0, zero),
        or_(a0, zero, zero), or_(t9, zero, zero), or_(t0, zero, zero), or_(t1, zero, zero), *DONE,
        'ptr', lambda pc, L: L['f2'],
        'pad', jr(ra), nop,
        'f1', addu(v0, a0, a0), jr(ra), nop,
        'f2', addiu(v0, a0, 100), jr(ra), nop],
    # IDO's shape (ADR-0151): the bound in the slot of a previous branch.
    'ido_table': [addiu(s1, zero, 0), addiu(t0, zero, 0),
        'loop', slti(at, t0, 0), bne(at, zero, 'dflt'), sltiu(at, t0, 3), beq(at, zero, 'dflt'), sll(t1, t0, 2),
        lui(at, 0x8000), addu(at, at, t1), lambda pc, L: I(35, t1, at, L['tbl']), jr(t1), nop,
        'c0', addiu(s1, s1, 1), j('next'), nop,
        'c1', addiu(s1, s1, 10), j('next'), nop,
        'c2', addiu(s1, s1, 100), j('next'), nop,
        'dflt', addiu(s1, s1, 1000),
        'next', addiu(t0, t0, 1), slti(t2, t0, 4), bne(t2, zero, 'loop'), nop, *DONE,
        'tbl', lambda pc, L: L['c0'], lambda pc, L: L['c1'], lambda pc, L: L['c2']],
    # IDO's unscheduled shape (ADR-0154): a load-delay nop before the jump.
    'delay_table': [addiu(s1, zero, 0), addiu(t0, zero, 0),
        'loop', sltiu(at, t0, 3), beq(at, zero, 'dflt'), nop, sll(t1, t0, 2),
        lui(at, 0x8000), addu(at, at, t1), lambda pc, L: I(35, t1, at, L['tbl']), nop, jr(t1), nop,
        'c0', addiu(s1, s1, 1), j('next'), nop,
        'c1', addiu(s1, s1, 10), j('next'), nop,
        'c2', addiu(s1, s1, 100), j('next'), nop,
        'dflt', addiu(s1, s1, 1000),
        'next', addiu(t0, t0, 1), slti(t2, t0, 4), bne(t2, zero, 'loop'), nop, *DONE,
        'tbl', lambda pc, L: L['c0'], lambda pc, L: L['c1'], lambda pc, L: L['c2']],
    # IDO's audio shape (ADR-0156): the bound, then a taken branch that is
    # the guard's only way in.
    'hop_table': [addiu(s1, zero, 0), addiu(t0, zero, 0), addiu(t4, zero, 1),
        'loop', sltiu(at, t0, 3), bne(t4, zero, 'guard'), nop, j('dflt'), nop,
        'guard', beq(at, zero, 'dflt'), sll(t1, t0, 2),
        lui(at, 0x8000), addu(at, at, t1), lambda pc, L: I(35, t1, at, L['tbl']), jr(t1), nop,
        'c0', addiu(s1, s1, 1), j('next'), nop,
        'c1', addiu(s1, s1, 10), j('next'), nop,
        'c2', addiu(s1, s1, 100), j('next'), nop,
        'dflt', addiu(s1, s1, 1000),
        'next', addiu(t0, t0, 1), slti(t2, t0, 4), bne(t2, zero, 'loop'), nop, *DONE,
        'tbl', lambda pc, L: L['c0'], lambda pc, L: L['c1'], lambda pc, L: L['c2']],
    # Status.FR = 0 (ADR-0160), as libultra threads run: doubles in even/odd
    # pairs built by 32-bit moves, odd 32-bit transfers, masked sources.
    # Stores through a 4 KiB even page, its odd page and a 64 KiB page, read
    # back through KSEG2, KSEG0 and a second mapping at the same cache index
    # (ADR-0162).
    'tlb': tlb_program([lui(t1, 0x1122), ori(t1, t1, 0x3344), lui(t2, 0x5566), ori(t2, t2, 0x7788),
        lui(s0, 0x0010), sw(t1, 0x10, s0), lui(s4, 0x0010), ori(s4, s4, 0x1000), sw(t2, 0x20, s4),
        lui(s5, 0x0400), addiu(t3, zero, 0x5A), sb(t3, 0x1033, s5), lhu(v1, 0x1032, s5),
        lui(s6, 0xC000), lw(s1, 0x10, s6), lui(s7, 0x8000), lw(s2, 0x1020, s7), lw(t5, 0x2010, s7),
        dsll32(t4, t1, 0), or_(t4, t4, t2), sd(t4, 0x40, s4), ld(s3, 0x1040, s6)]),
    'fpu_fr0': [lui(gp, 0x8000), ori(gp, gp, 0x1000),
        lui(at, 0x3FF0), mtc1(at, 11), mtc1(zero, 10), lui(t0, 0x4000), mtc1(t0, 13), mtc1(zero, 12),
        fop(17, 0)(14, 10, 12), fop(17, 3)(16, 10, 12), sdc1(14, 0, gp), mfc1(t1, 15), mfc1(t2, 14),
        lui(t3, 0x4040), mtc1(t3, 4), fop(16, 33)(6, 4), fcmp(17, 2)(6, 14), cfc1(t5, 31),
        fop(17, 32)(8, 16), swc1(8, 8, gp), ldc1(18, 0, gp), lwc1(21, 8, gp), swc1(21, 12, gp),
        dmfc1(t4, 17), fop(16, 0)(22, 5, 4), swc1(22, 16, gp), *DONE],
    # Nested, recursive, pointer and tail calls; frames live in the RAM window.
    'calls': [lui(sp, 0x8000), ori(sp, sp, 0x1100),
        addiu(a0, zero, 5), jal('fact'), nop, addu(s0, v0, zero),
        addiu(a0, zero, 3), jal('twice'), nop, addu(s1, v0, zero),
        lui(t0, 0x8000), LO(t0, t0, 'inc'), addiu(a0, zero, 40), jalr(ra, t0), nop, addu(s2, v0, zero),
        addiu(a0, zero, 7), jal('tail'), nop, addu(s3, v0, zero), *DONE,
        'inc', addiu(v0, a0, 1), jr(ra), nop,
        'twice', addiu(sp, sp, -8), sw(ra, 4, sp), jal('inc'), nop, addu(a0, v0, zero), jal('inc'), nop,
        lw(ra, 4, sp), jr(ra), addiu(sp, sp, 8),
        'tail', addiu(a0, a0, 100), j('inc'), nop,
        'fact', addiu(sp, sp, -16), sw(ra, 12, sp), sw(a0, 8, sp), slti(t0, a0, 2), beq(t0, zero, 'rec'), nop,
        addiu(v0, zero, 1), j('out'), nop,
        'rec', addiu(a0, a0, -1), jal('fact'), nop, lw(a0, 8, sp), mult(v0, a0), mflo(v0),
        'out', lw(ra, 12, sp), jr(ra), addiu(sp, sp, 16)],
}
# Stores into executed bytes violate the declared-immutability assumption:
# native code must fail closed (fault 2) even though the reference runs it.
SELF_MODIFYING = [lui(s0, 0x8000), sw(zero, 8, s0), *DONE]
# Cached and uncached access to one line depends on write-back D-cache state:
# native code must fail closed (fault 4) rather than guess.
# A return whose $ra is not its call's continuation must fault 5 natively.
BAD_RETURN = [jal('f'), nop, *DONE, 'f', addiu(ra, ra, 8), jr(ra), nop]
# A trapping add that overflows raises on hardware; native code must fault 6.
OVERFLOW = [lui(t0, 0x7FFF), ori(t0, t0, 0xFFFF), addi(t1, t0, 1), *DONE]
RUNTIME = {'boundary': [('sum', [])], 'callback': [('spawn', ['a0'])], 'forwarded': [('spawn', ['a0'])],
    'tlb': [('map', [])], 'tlb_invalid': [('map', [])], 'tlb_clean': [('map', [])],
    'tlb_alias': [('map', [])]}
# A load from an invalid page and a store to a clean one: fault 1 (ADR-0162).
TLB_INVALID = tlb_program([lui(s5, 0x0401), lw(s1, 0, s5)], odd_valid=False)
TLB_CLEAN = tlb_program([lui(s0, 0x0010), sw(t1, 0, s0)], dirty=False)
# A 4 KiB page caching physical 0x1000 at virtual index bit 12 = 0, then a
# KSEG0 read of the same line at the other index: fault 4 (ADR-0162).
TLB_ALIAS = tlb_program([lui(s0, 0x0010), sw(t1, 0x10, s0), lui(s7, 0x8000), lw(s2, 0x1010, s7)], even0=0x1000)
LOADS = {'load': load_program(), 'load_gap': load_program(at=LOAD_DEST['load_gap']), 'load_reload': load_program(reload=True),
    'load_early': load_program(early=True), 'load_patch': load_program(patch=True), 'load_self': load_program(payload=SELF_PAYLOAD)}
# Jump-table bytes are store-protected like code: a write must fault 2.
TABLE_WRITE = jump_table([lui(s2, 0x8000), lambda pc, L: I(43, zero, s2, L['tbl'])])
# A host entry returning anywhere but the host's $ra: fault 5 (ADR-0146).
HOST_BAD_RETURN = [addiu(ra, ra, 4), jr(ra), nop]
# A register call to an address no one takes (4 bytes into f1): fault 3.
AT_BAD = [lui(gp, 0x8000), ori(gp, gp, 0x1000), lui(t0, 0x8000), LO(t0, t0, 'f1'), addiu(t9, t0, 4),
    sw(t9, 0, gp), lw(t9, 0, gp), jalr(ra, t9), nop, *DONE,
    'pad', jr(ra), nop,
    'f1', addu(v0, a0, a0), jr(ra), nop]
ADDRESS_TAKEN = {'addrtaken', 'at_bad', *OVERLAYS}
PROGRAMS['overlay'] = OVERLAYS['overlay']
FR0 = {'fpu_fr0'}
# A taken conditional trap raises an unmodeled exception: fault 10.
TRAP = [addiu(t0, zero, 0), R(52, 0, t0, zero), *DONE]
# A reached BREAK raises an unmodeled exception: fault 9.
BREAK = [addiu(t1, zero, 0), bne(t1, zero, 'ok'), nop, R(13, 0, 0, 0, 7), 'ok', *DONE]
# An enabled FPU exception (inexact on 1/3) and an out-of-range CVT.W: fault 7.
FPU_ENABLED = [lui(t0, 0x3F80), mtc1(t0, 1), lui(t0, 0x4040), mtc1(t0, 2), addiu(t1, zero, 0x80),
    ctc1(t1, 31), fop(16, 3)(3, 1, 2), *DONE]
FPU_RANGE = [lui(t0, 0x4F00), mtc1(t0, 1), fop(16, 36)(2, 1), *DONE]
# CEIL.W of 2^31 - 0.5 rounds out of the W range: fault 7.
FPU_ROUND_RANGE = [lui(t0, 0x41DF), ori(t0, t0, 0xFFFF), dsll32(t0, t0, 0), lui(at, 0xFFE0), dsll32(at, at, 0),
    dsrl32(at, at, 0), or_(t0, t0, at), dmtc1(t0, 1), fop(17, 14)(2, 1), *DONE]
# A compare with a NaN operand is outside the modeled COP1 subset: fault 7.
FPU_NAN = [lui(t0, 0x7FC0), mtc1(t0, 1), fcmp(16, 2)(1, 1), *DONE]
CACHE_ALIAS = [lui(s0, 0x8000), sw(s0, 0x1000, s0), lui(s1, 0xA000), lw(t0, 0x1000, s1), *DONE]

def windows():
    exe = ROOT / 'target/debug/plaid.exe'
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    OUT.mkdir(parents=True, exist_ok=True)
    progs = dict(PROGRAMS, self_modifying=SELF_MODIFYING, cache_alias=CACHE_ALIAS, bad_return=BAD_RETURN, overflow=OVERFLOW, table_write=TABLE_WRITE, fpu_nan=FPU_NAN,
        fpu_enabled=FPU_ENABLED, fpu_range=FPU_RANGE, fpu_round_range=FPU_ROUND_RANGE, load_early=LOADS['load_early'], load_patch=LOADS['load_patch'], load_self=LOADS['load_self'], break_reached=BREAK, trap_taken=TRAP, host_bad_return=HOST_BAD_RETURN, at_bad=AT_BAD, tlb_invalid=TLB_INVALID, tlb_clean=TLB_CLEAN, tlb_alias=TLB_ALIAS, **OVERLAYS)
    for name, items in progs.items():
        (OUT / f'{name}.bin').write_bytes(assemble(items))
        extra = []
        if name in RUNTIME:
            labels = label_pcs(items)
            decl = dict(format='plaid-runtime-functions-v0', source='spike096 synthetic declaration',
                functions=[dict(entry=hex(labels[f]), name=f, callbacks=cb) for f, cb in RUNTIME[name]])
            (OUT / f'{name}.runtime.json').write_text(json.dumps(decl))
            extra = [str(OUT / f'{name}.runtime.json')]
        if name in LOADS:
            labels = label_pcs(items)
            decl = dict(format='plaid-loads-v0', source='spike096 synthetic load',
                loads=[dict(destination=hex(LOAD_DEST.get(name, LOAD_AT)), size=hex(32), rom=hex(labels['payload'] - BASE), encoding='raw')])
            (OUT / f'{name}.loads.json').write_text(json.dumps(decl))
            extra += ['--loads', str(OUT / f'{name}.loads.json')]
        if name in OVERLAYS:
            labels = label_pcs(items)
            decl = dict(format='plaid-loads-v0', source='spike096 synthetic relocatable overlay',
                loads=[dict(destination=hex(OVL_LINK), size=hex(labels['ovl_b1'] - labels['ovl_link']),
                    rom=hex(labels['ovl_link'] - BASE), encoding='raw', relocatable=True)])
            (OUT / f'{name}.loads.json').write_text(json.dumps(decl))
            extra += ['--loads', str(OUT / f'{name}.loads.json')]
        if name in ADDRESS_TAKEN:
            extra += ['--address-taken']
        if name in FR0:
            extra += ['--fr0']
        subprocess.run([str(exe), 'lower-c', str(OUT / f'{name}.bin'), hex(BASE), hex(BASE), hex(EXIT), str(OUT / f'{name}.c'), *extra], check=True)
        subprocess.run([cc, '-O2', '-std=c99', '-Wall', '-Werror', '-Wno-unused-label', '-DPLAID_SAFEPOINTS', f'-DPLAID_LOWERED="{name}.c"', f'-DPLAID_EXIT=0x{EXIT:x}u',
            '-I', str(OUT), str(HERE / 'harness.c'), '-o', str(OUT / f'{name}-native.exe')], check=True)
    script = subprocess.check_output(['wsl', '-d', 'Ubuntu', '--exec', 'wslpath', '-a', str(HERE / 'run.py')], text=True).strip()
    subprocess.run(['wsl', '-d', 'Ubuntu', '--exec', 'python3', script, '--oracle', *sys.argv[1:]], check=True)
    results = {}
    for name in PROGRAMS:
        native = subprocess.run([str(OUT / f'{name}-native.exe')], capture_output=True, text=True)
        assert native.returncode == 0, (name, native.stdout)
        oracle = json.loads((OUT / f'{name}-oracle.json').read_text())
        assert json.loads(native.stdout) == oracle, (name, native.stdout, oracle)
        results[name] = hashlib.sha256(json.dumps(oracle, sort_keys=True).encode()).hexdigest()
    for name, fault in (('self_modifying', 2), ('cache_alias', 4), ('bad_return', 5), ('overflow', 6), ('table_write', 2), ('fpu_nan', 7), ('fpu_enabled', 7), ('fpu_range', 7), ('fpu_round_range', 7), ('load_early', 8), ('load_patch', 8), ('load_self', 2), ('break_reached', 9), ('trap_taken', 10), ('host_bad_return', 5), ('at_bad', 3), ('tlb_invalid', 1), ('tlb_clean', 1), ('tlb_alias', 4), ('ovl_tamper', 3), ('ovl_self', 2), ('ovl_callback', 8)):
        bad = subprocess.run([str(OUT / f'{name}-native.exe')], capture_output=True, text=True)
        assert bad.returncode == 6 and json.loads(bad.stdout)['fault'] == fault, (name, bad.stdout)
    receipt = dict(format='plaid-native-slice-receipt-v0', ares_revision=builder().REV, compiler=Path(cc).name,
        programs=results, fail_closed_faults=dict(self_modifying=2, cache_alias=4, bad_return=5, overflow=6, table_write=2, fpu_nan=7, fpu_enabled=7, fpu_range=7, fpu_round_range=7, load_early=8, load_patch=8, load_self=2, break_reached=9, trap_taken=10, host_bad_return=5, at_bad=3, tlb_invalid=1, tlb_clean=1, tlb_alias=4, ovl_tamper=3, ovl_self=2, ovl_callback=8), interpreter_linked=False, native_complete=False)
    (OUT / 'receipt.json').write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print('PASS native lowering matches pinned ares on', ', '.join(PROGRAMS), '; self-modifying, cache-alias, bad-return, overflow, table-write, NaN-compare, enabled-FPU-exception, out-of-range-conversion, out-of-range-rounding, early-load, patched-load re-entry, load self-write, BREAK, trap, host-return, unknown-target, invalid-page, clean-page, cache-index-alias, tampered-overlay, overlay self-write and revoked-overlay-return programs fail closed')
    print(json.dumps(receipt, sort_keys=True))

def builder():
    spec = importlib.util.spec_from_file_location('builder', ROOT / 'spikes/003-ares-oracle/run.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

def oracle():
    oracle_exe = OUT / 'oracle/oracle'
    if '--rebuild' in sys.argv or not oracle_exe.exists():
        oracle_exe = builder().build(HERE / 'driver.cpp', OUT / 'oracle')
    for name in PROGRAMS:
        out = subprocess.run([str(oracle_exe), str(OUT / f'{name}.bin'), hex(EXIT), *(['fr0'] if name in FR0 else [])],
            capture_output=True, text=True, timeout=120)
        assert out.returncode == 0, (name, out.returncode, out.stderr)
        (OUT / f'{name}-oracle.json').write_text(out.stdout)

if __name__ == '__main__':
    oracle() if '--oracle' in sys.argv else windows()
