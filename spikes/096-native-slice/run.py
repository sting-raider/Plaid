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
ra = 31
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
nop = 0
DONE = [j('exit'), nop]

def assemble(items):
    labels, pc = {'exit': EXIT}, BASE
    for x in items:
        if isinstance(x, str): labels[x] = pc
        else: pc += 4
    words, pc = [], BASE
    for x in items:
        if isinstance(x, str): continue
        words.append(x(pc, labels) & 0xFFFFFFFF if callable(x) else x); pc += 4
    assert pc < EXIT
    words += [0] * ((EXIT - pc) // 4) + [0x1000FFFF, 0]  # exit: b . ; nop
    return b''.join(w.to_bytes(4, 'big') for w in words)

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
}
# Stores into executed bytes violate the declared-immutability assumption:
# native code must fail closed (fault 2) even though the reference runs it.
SELF_MODIFYING = [lui(s0, 0x8000), sw(zero, 8, s0), *DONE]
# Cached and uncached access to one line depends on write-back D-cache state:
# native code must fail closed (fault 4) rather than guess.
CACHE_ALIAS = [lui(s0, 0x8000), sw(s0, 0x1000, s0), lui(s1, 0xA000), lw(t0, 0x1000, s1), *DONE]

def windows():
    exe = ROOT / 'target/debug/plaid.exe'
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    OUT.mkdir(parents=True, exist_ok=True)
    progs = dict(PROGRAMS, self_modifying=SELF_MODIFYING, cache_alias=CACHE_ALIAS)
    for name, items in progs.items():
        (OUT / f'{name}.bin').write_bytes(assemble(items))
        subprocess.run([str(exe), 'lower-c', str(OUT / f'{name}.bin'), hex(BASE), hex(BASE), hex(EXIT), str(OUT / f'{name}.c')], check=True)
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
    for name, fault in (('self_modifying', 2), ('cache_alias', 4)):
        bad = subprocess.run([str(OUT / f'{name}-native.exe')], capture_output=True, text=True)
        assert bad.returncode == 6 and json.loads(bad.stdout)['fault'] == fault, (name, bad.stdout)
    receipt = dict(format='plaid-native-slice-receipt-v0', ares_revision=builder().REV, compiler=Path(cc).name,
        programs=results, fail_closed_faults=dict(self_modifying=2, cache_alias=4), interpreter_linked=False, native_complete=False)
    (OUT / 'receipt.json').write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print('PASS native lowering matches pinned ares on', ', '.join(PROGRAMS), '; self-modifying and cache-alias accesses fail closed')
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
