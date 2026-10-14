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
nop = 0
DONE = [j('exit'), nop]

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
    # COP1 data moves with 64-bit FPRs: 32-bit forms keep the high word (ADR-0131).
    'fpu': [lui(gp, 0x8000), ori(gp, gp, 0x1000), lui(t0, 0x3F80), mtc1(t0, 0), swc1(0, 0, gp),
        lui(t1, 0x1234), ori(t1, t1, 0x5678), dsll32(t1, t1, 0), ori(t1, t1, 0x9ABC),
        dmtc1(t1, 2), sdc1(2, 8, gp), dmfc1(t2, 2), mfc1(t3, 2), mtc1(t0, 2), dmfc1(t4, 2),
        lui(t5, 0x8765), ori(t5, t5, 0x4321), sw(t5, 16, gp), lwc1(4, 16, gp), mfc1(t6, 4),
        ldc1(6, 8, gp), dmfc1(t7, 6), mtc1(t5, 1), dmfc1(s0, 1), sdc1(2, 24, gp), *DONE],
    # A bounded jump table, closed under the guarded scope (ADR-0132).
    'table': jump_table([]),
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
RUNTIME = {'boundary': [('sum', [])], 'callback': [('spawn', ['a0'])]}
# Jump-table bytes are store-protected like code: a write must fault 2.
TABLE_WRITE = jump_table([lui(s2, 0x8000), lambda pc, L: I(43, zero, s2, L['tbl'])])
CACHE_ALIAS = [lui(s0, 0x8000), sw(s0, 0x1000, s0), lui(s1, 0xA000), lw(t0, 0x1000, s1), *DONE]

def windows():
    exe = ROOT / 'target/debug/plaid.exe'
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    OUT.mkdir(parents=True, exist_ok=True)
    progs = dict(PROGRAMS, self_modifying=SELF_MODIFYING, cache_alias=CACHE_ALIAS, bad_return=BAD_RETURN, overflow=OVERFLOW, table_write=TABLE_WRITE)
    for name, items in progs.items():
        (OUT / f'{name}.bin').write_bytes(assemble(items))
        extra = []
        if name in RUNTIME:
            labels = label_pcs(items)
            decl = dict(format='plaid-runtime-functions-v0', source='spike096 synthetic declaration',
                functions=[dict(entry=hex(labels[f]), name=f, callbacks=cb) for f, cb in RUNTIME[name]])
            (OUT / f'{name}.runtime.json').write_text(json.dumps(decl))
            extra = [str(OUT / f'{name}.runtime.json')]
        subprocess.run([str(exe), 'lower-c', str(OUT / f'{name}.bin'), hex(BASE), hex(BASE), hex(EXIT), str(OUT / f'{name}.c'), *extra], check=True)
        subprocess.run([cc, '-O2', '-std=c99', '-Wall', '-Werror', '-Wno-unused-label', f'-DPLAID_LOWERED="{name}.c"',
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
    for name, fault in (('self_modifying', 2), ('cache_alias', 4), ('bad_return', 5), ('overflow', 6), ('table_write', 2)):
        bad = subprocess.run([str(OUT / f'{name}-native.exe')], capture_output=True, text=True)
        assert bad.returncode == 6 and json.loads(bad.stdout)['fault'] == fault, (name, bad.stdout)
    receipt = dict(format='plaid-native-slice-receipt-v0', ares_revision=builder().REV, compiler=Path(cc).name,
        programs=results, fail_closed_faults=dict(self_modifying=2, cache_alias=4, bad_return=5, overflow=6, table_write=2), interpreter_linked=False, native_complete=False)
    (OUT / 'receipt.json').write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print('PASS native lowering matches pinned ares on', ', '.join(PROGRAMS), '; self-modifying, cache-alias, bad-return, overflow and table-write programs fail closed')
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
        out = subprocess.run([str(oracle_exe), str(OUT / f'{name}.bin'), hex(EXIT)], capture_output=True, text=True, timeout=120)
        assert out.returncode == 0, (name, out.returncode, out.stderr)
        (OUT / f'{name}-oracle.json').write_text(out.stdout)

if __name__ == '__main__':
    oracle() if '--oracle' in sys.argv else windows()
