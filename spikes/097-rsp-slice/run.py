"""spike097: lowered RSP microcode against the pinned ares RSP (ADR-0167).

Synthetic microcode is assembled at IMEM 0x080, lowered with `plaid lower-rsp`
and compiled with harness.c; the same IMEM/DMEM images run on ares
(driver.cpp, built in WSL like spike096). Final scalar registers, PC, the
broken flag, all of DMEM and RDRAM 0..0x2000 must match. Negative programs
must fail closed natively with their fault code.
"""
import hashlib
import importlib.util
import json
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'target/rsp-slice'
spec = importlib.util.spec_from_file_location('spike096', ROOT / 'spikes/096-native-slice/run.py')
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)
IMEM = 0x080

zero, at, v0, v1, a0, a1, a2, a3 = range(8)
t0, t1, t2, t3, t4, t5, t6, t7, s0, s1, s2, s3, s4, s5, s6, s7, t8, t9 = range(8, 26)
gp, sp, fp, ra = 28, 29, 30, 31
mfc0 = lambda rt, rd: 16 << 26 | rt << 16 | rd << 11
mtc0 = lambda rt, rd: 16 << 26 | 4 << 21 | rt << 16 | rd << 11
BREAK = A.R(13)
bltzal = lambda rs, l: A.B(1, rs, 16, l)
bgezal = lambda rs, l: A.B(1, rs, 17, l)
lwu = A.mem(39)


def li(r, v):
    return [A.lui(r, v >> 16 & 0xFFFF), A.ori(r, r, v & 0xFFFF)]


def assemble(items):
    labels, pc = {}, IMEM
    for x in items:
        if isinstance(x, str):
            labels[x] = pc
        else:
            pc += 4
    words, pc = [], IMEM
    for x in items:
        if isinstance(x, str):
            continue
        words.append(x(pc, labels) & 0xFFFFFFFF if callable(x) else x)
        pc += 4
    assert pc <= 0x1000
    image = bytearray(4096)
    for i, w in enumerate(words):
        image[IMEM + 4 * i:IMEM + 4 * i + 4] = w.to_bytes(4, 'big')
    return bytes(image), 4 * len(words)


PROGRAMS = {
    # ADD/SUB are ADDU/SUBU on the RSP; SLTIU sign-extends its immediate;
    # writes to $zero vanish.
    'alu': [*li(t0, 0x7FFFFFFF), A.addiu(t1, zero, 1), A.add(t2, t0, t1), A.sub(t3, zero, t1),
            A.addu(t4, t2, t3), A.subu(t5, t1, t2), A.and_(t6, t0, t3), A.or_(t7, t1, t2),
            A.xor(s0, t0, t3), A.nor(s1, t0, t1), A.slt(s2, t3, t1), A.sltu(s3, t3, t1),
            A.slti(s4, t3, -2), A.sltiu(s5, t1, -1), A.andi(s6, t3, 0xF0F0), A.ori(s7, t1, 0x8000),
            A.xori(t8, t3, 0x1234), A.lui(t9, 0x8765), A.sll(gp, t3, 31), A.srl(sp, t3, 4), A.sra(fp, t2, 7),
            A.addiu(a0, zero, 35), A.sllv(a1, t1, a0), A.srlv(a2, t2, a0), A.srav(a3, t2, a0),
            A.addiu(zero, t1, 5), A.addi(v0, t0, 2), BREAK, A.nop],
    # Every width, signed and unsigned, unaligned addresses and DMEM wrap.
    'mem': [*li(t0, 0x89ABCDEF), A.addiu(s0, zero, 0x100),
            A.sw(t0, 0, s0), A.sh(t0, 5, s0), A.sb(t0, 11, s0), A.sw(t0, 0x0FFE, zero),
            A.lw(t1, 1, s0), A.lh(t2, 3, s0), A.lhu(t3, 3, s0), A.lb(t4, 2, s0), A.lbu(t5, 2, s0),
            lwu(t6, 0x0FFF, zero), A.lw(t7, -4, s0), A.lh(s1, 0x0FFF, zero), A.sh(t0, -1, zero),
            A.lw(s2, 0x0FFC, zero), BREAK, A.nop],
    # Every branch kind taken and not taken, links masked to 12 bits, J/JAL,
    # JR/JALR through computed addresses, and a counted loop.
    'branch': [A.addiu(s0, zero, 0), A.addiu(t0, zero, -1), A.addiu(t1, zero, 1),
               A.beq(t0, t1, 'x1'), A.addiu(s0, s0, 1),
               A.bne(t0, t1, 'x1'), A.addiu(s0, s0, 2), A.addiu(s0, s0, 100),
               'x1', A.blez(t0, 'x2'), A.addiu(s0, s0, 4), A.addiu(s0, s0, 100),
               'x2', A.bgtz(t1, 'x3'), A.addiu(s0, s0, 8), A.addiu(s0, s0, 100),
               'x3', A.bltz(t1, 'x4'), A.addiu(s0, s0, 16), A.bgez(t1, 'x4'), A.nop, A.addiu(s0, s0, 100),
               'x4', bltzal(t1, 'x5'), A.addiu(s0, s0, 32), A.addu(s1, ra, zero),
               bgezal(t1, 'x5'), A.nop, A.addiu(s0, s0, 100),
               'x5', A.addu(s2, ra, zero), A.jal('f'), A.addiu(s0, s0, 64), A.addu(s3, v0, zero),
               lambda pc, L: A.I(13, t2, zero, L['g']), A.jalr(t3, t2), A.addiu(s0, s0, 128), A.addu(s4, v0, zero),
               A.addiu(t4, zero, 5), A.addiu(s5, zero, 0),
               'loop', A.addiu(s5, s5, 3), A.addiu(t4, t4, -1), A.bgtz(t4, 'loop'), A.nop,
               A.j('end'), A.addiu(s0, s0, 256), A.addiu(s0, s0, 100),
               'f', A.jr(ra), A.addiu(v0, zero, 11),
               'g', A.addu(s6, t3, zero), A.jr(t3), A.addiu(v0, zero, 22),
               'end', BREAK, A.nop],
    # DMA into DMEM in rows with a skip, back out to RDRAM, the DMA registers
    # read back, polling, the semaphore, and SP_STATUS signals.
    'dma': [A.addiu(t0, zero, 0x200), mtc0(t0, 0), A.addiu(t1, zero, 0x408), mtc0(t1, 1),
            *li(t2, 0x0200100F | (0x18 << 20)), mtc0(t2, 2),
            'wait', mfc0(t3, 6), A.bne(t3, zero, 'wait'), A.nop,
            mfc0(s0, 0), mfc0(s1, 1), mfc0(s2, 2), mfc0(s3, 5),
            A.addiu(t0, zero, 0x210), mtc0(t0, 0), A.addiu(t1, zero, 0x1000), mtc0(t1, 1),
            A.addiu(t2, zero, 0x37), mtc0(t2, 3),
            'wait2', mfc0(t3, 5), A.bne(t3, zero, 'wait2'), A.nop,
            mfc0(s4, 7), mfc0(s5, 7), mtc0(zero, 7), mfc0(s6, 7),
            *li(t4, 0x01004400), mtc0(t4, 4), mfc0(s7, 4),
            A.addiu(t4, zero, 0x200), mtc0(t4, 4), mfc0(t8, 4), BREAK, A.nop],
    # DMA from RDRAM into IMEM outside the running text and back out
    # (ADR-0169); SP_MEM_ADDR reads back the IMEM bit.
    'dma_imem': [A.addiu(t0, zero, 0x1000), mtc0(t0, 0), mtc0(zero, 1), A.addiu(t1, zero, 15), mtc0(t1, 2),
                 'busy', mfc0(t3, 6), A.bne(t3, zero, 'busy'), A.nop, mfc0(s0, 0), A.addiu(t0, zero, 0x1080), mtc0(t0, 0), A.addiu(t2, zero, 0x1000), mtc0(t2, 1),
                 mtc0(t1, 3), 'idle', mfc0(t3, 6), A.bne(t3, zero, 'idle'), A.nop, mfc0(s1, 0), mfc0(s2, 1),
                 BREAK, A.nop],
    # The microcode halts itself through SP_STATUS instead of BREAK.
    'halt': [A.addiu(t0, zero, 7), A.addiu(t1, zero, 2), mtc0(t1, 4), A.addiu(t0, zero, 9), BREAK, A.nop],
    # the only RDP register the RSP may touch: DPC_STATUS of an idle RDP
    'dpc_status': [mfc0(t0, 11), BREAK, A.nop],
}
# Fail closed natively: a register jump outside the text (3), DMA over the
# program's own next words (3: IMEM no longer holds lowered code there),
# DMA beyond RDRAM (1), an RDP command register (4).
NEGATIVE = {
    'jr_out': ([A.addiu(t0, zero, 0x800), A.jr(t0), A.nop, BREAK, A.nop], 3),
    'imem_stale': ([lambda pc, L: A.I(9, t0, zero, 0x1000 | L['patched']), mtc0(t0, 0), mtc0(zero, 1),
                    A.addiu(t1, zero, 7), mtc0(t1, 2), A.nop, 'patched', A.nop, A.nop, BREAK, A.nop], 3),
    'dma_far': ([A.addiu(t0, zero, 0), mtc0(t0, 0), *li(t1, 0x00FFFFF8), mtc0(t1, 1), A.addiu(t2, zero, 15),
                 mtc0(t2, 2), BREAK, A.nop], 1),
    'dpc': ([mfc0(t0, 8), BREAK, A.nop], 4),
}


# ---- vector unit (ADR-0168) ----
vu = lambda f, vd, vs, vt, e: 18 << 26 | 1 << 25 | e << 21 | vt << 16 | vs << 11 | vd << 6 | f
cop2 = lambda sub: (lambda rt, rd, e=0: 18 << 26 | sub << 21 | rt << 16 | rd << 11 | e << 7)
mfc2, cfc2, mtc2, ctc2 = map(cop2, (0, 2, 4, 6))
lwc2 = lambda op, vt, base, imm, e: 50 << 26 | base << 21 | vt << 16 | op << 11 | e << 7 | imm & 0x7F
swc2 = lambda op, vt, base, imm, e: 58 << 26 | base << 21 | vt << 16 | op << 11 | e << 7 | imm & 0x7F
lqv = lambda vt, imm, base=zero, e=0: lwc2(4, vt, base, imm, e)
sqv = lambda vt, imm, base, e=0: swc2(4, vt, base, imm, e)
VSAR = 0x1D
# Every computational op; VRCPH/VRSQH come right before their L forms so the
# double-precision input is exercised.
VOPS = [*range(0x12), 0x13, 0x14, 0x15, VSAR, *range(0x20, 0x2E), 0x30, 0x32, 0x31, 0x33, 0x34, 0x36, 0x35, 0x37]
EDGES = [0x8000, 0x7FFF, 0xFFFF, 0, 1, 0x8001, 0x4000, 0xC000, 0x8000, 0xFFFF, 0x7FFF, 0, 0xFFFF, 0x8000, 0x4000,
         0x4000, 1, 0xFFFE, 0x7FFE, 0x8002, 0x00FF, 0xFF00, 0x1234, 0xEDCB, 0, 0, 0x8000, 0x8000, 0x7FFF, 0x7FFF, 1,
         0xFFFF]
SMALL = [0, 1, 2, 3, 0xFFFF, 0xFFFE, 0xFFFD, 0x7FFF, 0x7FFE, 0x8000, 0x8001]


def vec_program(k, count=48):
    """Each op on edge and chained inputs; after each, vd, the accumulator
    and the flags are stored to DMEM from 0x100 on."""
    rng = random.Random(1000 + k)
    out = [lqv(v, v - 1) for v in range(1, 9)]
    for rd in range(3):
        out += [*li(t0, rng.getrandbits(16)), ctc2(t0, rd)]
    out.append(A.addiu(s0, zero, 0x100))
    for i in range(count):
        f = VOPS[(k * count + i) % len(VOPS)]
        vd = rng.randrange(9, 29)
        out += [vu(f, vd, rng.randrange(1, 29), rng.randrange(1, 29), rng.randrange(16)), sqv(vd, 0, s0)]
        for n, e in enumerate((8, 9, 10)):
            out += [vu(VSAR, 29 + n, 0, 0, e), sqv(29 + n, 1 + n, s0)]
        for n in range(3):
            out += [cfc2(t0 + n, n), A.sh(t0 + n, 64 + 2 * n, s0)]
        out.append(A.addiu(s0, s0, 80))
    return out + [BREAK, A.nop]


def vload_program(k):
    """Every LWC2 form at elements 8k..8k+7, random offsets and addresses (DMEM wraps)."""
    rng = random.Random(2000 + k)
    out, dump = [lqv(v, v - 1) for v in range(1, 29)], 0
    out.append(A.addiu(s0, zero, 0x200))
    for op in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11):
        for e in range(8 * k, 8 * k + 8):
            vt, imm = rng.randrange(1, 29), rng.randrange(-64, 64)
            out += [A.addiu(t0, zero, rng.randrange(0x1000)), lwc2(op, vt, t0, imm, e)]
            for v in (range(vt & ~7, (vt & ~7) + 8) if op == 11 else [vt]):
                if dump == 64:
                    out, dump = out + [A.addiu(s0, s0, 0x400)], 0
                out.append(sqv(v, dump, s0))
                dump += 1
    return out + [BREAK, A.nop]


def vstore_program(k):
    """Every SWC2 form at elements 8k..8k+7, each into its own 32-byte slot; the last slots wrap."""
    rng = random.Random(3000 + k)
    out, i = [lqv(v, v - 1) for v in range(1, 29)], 0
    for op, scale in enumerate((1, 2, 4, 8, 16, 16, 8, 8, 16, 16, 16, 16)):
        for e in range(8 * k, 8 * k + 8):
            address, imm = 0x200 + 32 * (i + 16) + rng.randrange(16), rng.randrange(-64, 64)
            # pattern vectors: the edge vectors repeat bytes that SFV/SHV/SUV would hide
            out += [A.addiu(t0, zero, (address - imm * scale) & 0x7FFF), swc2(op, rng.randrange(5, 29), t0, imm, e)]
            i += 1
    return out + [BREAK, A.nop]


FLAG_OPS = [0x10, 0x11, 0x14, 0x15, 0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x25, 0x24, 0x25, 0x24]


def vflag_program(k, count=48):
    """Compare, clip, merge and carry ops chained on small-range values, so
    equal, sum -1 and carry cases are common; flags dumped after each."""
    rng = random.Random(5000 + k)
    out = [lqv(v, 4 + v - 1) for v in range(1, 9)] + [A.addiu(s0, zero, 0x100)]
    for i in range(count):
        # every fourth op is VCH then VCL on small values: VCL reads VCH's VCE
        f, vd = (0x25, 0x24, *FLAG_OPS)[i % 4 if i % 4 < 2 else 2 + rng.randrange(len(FLAG_OPS))], rng.randrange(9, 29)
        pool = 9 if i < 8 or i % 4 < 2 else 29
        vs, vt = rng.randrange(1, pool), rng.randrange(1, pool)
        out += [vu(f, vd, vs, vt, rng.choice((0, 0, 0, 2, 3, 5, 8, 15))), sqv(vd, 0, s0)]
        for n in range(3):
            out += [cfc2(t0 + n, n), A.sh(t0 + n, 16 + 2 * n, s0)]
        out.append(A.addiu(s0, s0, 32))
    return out + [BREAK, A.nop]


MAC_OPS = [0x08, 0x09, 0x0C, 0x0D, 0x0E, 0x0F, 0x0B, 0x02, 0x0A]


def vacc_program(k):
    """Multiply-accumulate chains that carry the 48-bit accumulator past 32
    bits both ways: a seeding multiply, then ten accumulations of edge values."""
    rng = random.Random(6000 + k)
    out = [lqv(v, v - 1) for v in range(1, 9)] + [A.addiu(s0, zero, 0x100)]
    for f in MAC_OPS[3 * k:3 * k + 3]:
        for step in range(11):
            op = rng.choice((0x00, 0x07, 0x05)) if step == 0 else f
            vs = rng.choice((1, 2, 3)) if step < 6 else rng.randrange(1, 9)
            vd = 9 + step
            out += [vu(op, vd, vs, rng.choice((1, 2, 3, vs)), rng.choice((0, 0, 8, 9))), sqv(vd, 0, s0)]
            for n, e in enumerate((8, 9, 10)):
                out += [vu(VSAR, 29 + n, 0, 0, e), sqv(29 + n, 1 + n, s0)]
            out.append(A.addiu(s0, s0, 64))
    return out + [BREAK, A.nop]


def vmove_program():
    """MTC2/MFC2 at every element (15 wraps), CTC2/CFC2 on every register."""
    rng = random.Random(4000)
    out = [lqv(v, v - 1) for v in range(1, 9)] + [A.addiu(s0, zero, 0x400)]
    for i in range(48):
        out += [*li(t0, rng.getrandbits(32)), mtc2(t0, rng.randrange(1, 9), i % 16),
                mfc2(t1, rng.randrange(1, 9), rng.randrange(16)), A.sw(t1, 4 * i, s0)]
    for i in range(16):
        out += [*li(t0, rng.getrandbits(32)), ctc2(t0, i % 8), cfc2(t1, rng.randrange(8)), A.sw(t1, 0x100 + 4 * i, s0)]
    return out + [mfc2(zero, 1, 0), cfc2(zero, 0), BREAK, A.nop]


PROGRAMS.update({f'vec{k}': vec_program(k) for k in range(8)})
PROGRAMS.update({f'vload{k}': vload_program(k) for k in range(2)})
PROGRAMS.update({f'vstore{k}': vstore_program(k) for k in range(2)})
PROGRAMS.update({f'vflag{k}': vflag_program(k) for k in range(4)})
PROGRAMS.update({f'vacc{k}': vacc_program(k) for k in range(3)})
PROGRAMS['vmove'] = vmove_program()


def dmem_image():
    image = bytearray((i * 13 + 7) & 0xFF for i in range(4096))
    image[:64] = b''.join(h.to_bytes(2, 'big') for h in EDGES)
    rng = random.Random(7)  # 0x40..0xbf: small-range halfwords for the flag programs
    image[64:192] = b''.join(rng.choice(SMALL).to_bytes(2, 'big') for _ in range(64))
    return bytes(image)


def windows():
    exe = ROOT / 'target/debug/plaid.exe'
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'dmem.bin').write_bytes(dmem_image())
    native = {}
    for name, items in {**PROGRAMS, **{k: v[0] for k, v in NEGATIVE.items()}}.items():
        imem, size = assemble(items)
        (OUT / f'{name}.imem').write_bytes(imem)
        subprocess.run([str(exe), 'lower-rsp', str(OUT / f'{name}.imem'), hex(IMEM), hex(size), hex(IMEM), 'prog',
                        str(OUT / f'{name}.c'), '--raw'], check=True)
        out = OUT / f'{name}-native.exe'
        subprocess.run([cc, '-O2', '-std=c99', '-Wall', '-Werror', '-Wno-unused-label', '-Wno-unused-function',
                        f'-DPLAID_RSP_LOWERED="{name}.c"', '-I', str(OUT), str(HERE / 'harness.c'), '-o', str(out)],
                       check=True)
        native[name] = subprocess.run([str(out), str(OUT / f'{name}.imem'), str(OUT / 'dmem.bin'), hex(IMEM)],
                                      capture_output=True, text=True)
    script = subprocess.check_output(['wsl', '-d', 'Ubuntu', '--exec', 'wslpath', '-a', str(HERE / 'run.py')],
                                     text=True).strip()
    subprocess.run(['wsl', '-d', 'Ubuntu', '--exec', 'python3', script, '--oracle', *sys.argv[1:]], check=True)
    results = {}
    for name in PROGRAMS:
        run = native[name]
        assert run.returncode == 0, (name, run.stdout)
        oracle = json.loads((OUT / f'{name}-oracle.json').read_text())
        mine = json.loads(run.stdout)
        for key in oracle:
            if mine[key] != oracle[key]:
                at = next(i for i, (x, y) in enumerate(zip(mine[key], oracle[key])) if x != y)
                raise AssertionError((name, key, at, mine[key][at:at + 32], oracle[key][at:at + 32]))
        results[name] = hashlib.sha256(json.dumps(oracle, sort_keys=True).encode()).hexdigest()
    for name, (_, fault) in NEGATIVE.items():
        run = native[name]
        assert run.returncode == 6 and json.loads(run.stdout)['fault'] == fault, (name, run.stdout)
    receipt = dict(format='plaid-rsp-slice-receipt-v0', ares_revision=builder().REV, programs=results,
                   fail_closed_faults={k: v[1] for k, v in NEGATIVE.items()}, interpreter_linked=False)
    (OUT / 'receipt.json').write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print('PASS lowered RSP microcode matches pinned ares on', ', '.join(PROGRAMS), '; out-of-text jump, '
          'self-overwritten code, far DMA and RDP-register programs fail closed')
    print(json.dumps(receipt, sort_keys=True))


def builder():
    s = importlib.util.spec_from_file_location('builder', ROOT / 'spikes/003-ares-oracle/run.py')
    module = importlib.util.module_from_spec(s)
    s.loader.exec_module(module)
    return module


def oracle():
    oracle_exe = OUT / 'oracle/oracle'
    if '--rebuild' in sys.argv or not oracle_exe.exists():
        oracle_exe = builder().build(HERE / 'driver.cpp', OUT / 'oracle')
    for name in PROGRAMS:
        out = subprocess.run([str(oracle_exe), str(OUT / f'{name}.imem'), str(OUT / 'dmem.bin'), hex(IMEM)],
                             capture_output=True, text=True, timeout=120)
        assert out.returncode == 0, (name, out.returncode, out.stderr)
        (OUT / f'{name}-oracle.json').write_text(out.stdout)


if __name__ == '__main__':
    oracle() if '--oracle' in sys.argv else windows()
