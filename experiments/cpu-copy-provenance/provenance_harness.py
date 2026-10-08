from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple

# Bounded experiment: prove only direct adjacent LW/LWU -> SW copies inside one
# compiled unit. This intentionally rejects arithmetic, branches, delay slots,
# cross-unit chains, and ambiguous unit identity.

LW = 0x23
LWU = 0x27
SW = 0x2B
BNE = 0x05

@dataclass(frozen=True)
class Unit:
    unit: int
    start: int
    words: Tuple[int, ...]

@dataclass(frozen=True)
class LoadEvent:
    seq: int
    unit: int
    site: int
    dest_gpr: int
    source_addr: int
    source_kind: str
    value: int

@dataclass(frozen=True)
class StoreEvent:
    seq: int
    site: int
    destination: int
    value: int
    unit: Optional[int] = None  # None models today's cpu_word_store_observed

@dataclass(frozen=True)
class CopyWitness:
    load_seq: int
    store_seq: int
    source_kind: str
    source_addr: int
    destination: int
    value: int


def opcode(word: int) -> int:
    return (word >> 26) & 0x3F


def rt(word: int) -> int:
    return (word >> 16) & 0x1F


def word_at(unit: Unit, pc: int) -> int:
    if pc < unit.start or (pc - unit.start) % 4:
        raise ValueError("site outside/alignment")
    i = (pc - unit.start) // 4
    if i >= len(unit.words):
        raise ValueError("site outside unit")
    return unit.words[i]


def certify(units: Dict[int, Unit], loads: List[LoadEvent], stores: List[StoreEvent]) -> List[CopyWitness]:
    """Certify only an adjacent same-unit LW/LWU -> SW dynamic lineage.

    The dynamic load must identify the exact compiled unit, site, destination GPR,
    concrete source witness and value. The store must identify its executing unit.
    This deliberately refuses broader dataflow because no retirement/GPR-clobber
    trace exists yet.
    """
    out = []
    for s in stores:
        if s.unit is None or s.unit not in units:
            continue
        u = units[s.unit]
        try:
            sw = word_at(u, s.site)
        except ValueError:
            continue
        if opcode(sw) != SW:
            continue
        src_gpr = rt(sw)
        load_pc = s.site - 4
        try:
            lw = word_at(u, load_pc)
        except ValueError:
            continue
        if opcode(lw) not in (LW, LWU) or rt(lw) != src_gpr:
            continue

        prior = [
            e for e in loads
            if e.seq < s.seq
            and e.unit == s.unit
            and e.site == load_pc
            and e.dest_gpr == src_gpr
        ]
        if not prior:
            continue
        l = max(prior, key=lambda e: e.seq)
        if l.value != s.value:
            continue
        # In this bounded event model any intervening observed load means the
        # load/store pair was not the exact adjacent dynamic pair we claim.
        if any(e.seq > l.seq and e.seq < s.seq for e in loads):
            continue
        out.append(CopyWitness(l.seq, s.seq, l.source_kind, l.source_addr, s.destination, s.value))
    return out


def naive_value_join(loads: List[LoadEvent], stores: List[StoreEvent]):
    """Unsound baseline: choose the most recent prior load with equal value."""
    out = []
    for s in stores:
        candidates = [l for l in loads if l.seq < s.seq and l.value == s.value]
        if candidates:
            l = max(candidates, key=lambda x: x.seq)
            out.append((s.seq, l.source_addr))
    return out


def enc_i(op, rs_, rt_, imm):
    return (op << 26) | (rs_ << 21) | (rt_ << 16) | (imm & 0xFFFF)


def run():
    # Exact current CPU-copy loop words from scripts/test_mupen_session.py.
    cpu_copy = (
        0x3c08b000, 0x35081000, 0x3c098000, 0x35290400, 0x340a0040,
        0x8d0b0000, 0xad2b0000, 0x25080004, 0x25290004, 0x254affff,
        0x1540fffa, 0, 0x3c088000, 0x35080400, 0x01000008, 0,
    )
    u1 = Unit(101, 0xA4000040, cpu_copy)
    load_pc = u1.start + 5 * 4
    store_pc = load_pc + 4

    # Canonical 64-word copy. Values repeat every eight words so no uniqueness
    # assumption can accidentally make the verifier look smarter than it is.
    loads, stores = [], []
    seq = 0
    for i in range(64):
        value = 0x10000000 | (i % 8)
        loads.append(LoadEvent(seq, u1.unit, load_pc, 11, 0xB0001000 + 4*i, "rom_bytes", value)); seq += 1
        stores.append(StoreEvent(seq, store_pc, 0x80000400 + 4*i, value, u1.unit)); seq += 1
    witnesses = certify({u1.unit: u1}, loads, stores)
    assert len(witnesses) == 64
    assert witnesses[0].source_addr == 0xB0001000
    assert witnesses[-1].destination == 0x800004FC

    # Positive boundary: LWU has the same 32-bit copied payload for SW and is
    # deliberately admitted by this certificate.
    lwu_unit = Unit(102, 0x80001000, (
        enc_i(LWU, 8, 11, 0),
        enc_i(SW, 9, 11, 0),
    ))
    lwu_load = LoadEvent(0, lwu_unit.unit, lwu_unit.start, 11, 0x80002000, "rdram", 0xF0123456)
    lwu_store = StoreEvent(1, lwu_unit.start + 4, 0x80003000, 0xF0123456, lwu_unit.unit)
    assert len(certify({lwu_unit.unit: lwu_unit}, [lwu_load], [lwu_store])) == 1

    # Adversary 1: equal-value decoy load from another site/source. Value-only
    # pairing selects the decoy. The strict verifier refuses the observed gap.
    l = LoadEvent(0, u1.unit, load_pc, 11, 0xB0002000, "rom_bytes", 0xDEADBEEF)
    decoy = LoadEvent(1, u1.unit, 0xA4000100, 12, 0xB0003000, "rom_bytes", 0xDEADBEEF)
    s = StoreEvent(2, store_pc, 0x80004000, 0xDEADBEEF, u1.unit)
    assert naive_value_join([l, decoy], [s]) == [(2, 0xB0003000)]
    assert certify({u1.unit: u1}, [l, decoy], [s]) == []

    # Adversary 2: today's store event has no executing-unit identity. A perfect
    # load event still cannot justify decoding the SW against a guessed generation.
    l2 = LoadEvent(0, u1.unit, load_pc, 11, 0xB0002100, "rom_bytes", 0x12345678)
    s_no_unit = StoreEvent(1, store_pc, 0x80004004, 0x12345678, None)
    assert certify({u1.unit: u1}, [l2], [s_no_unit]) == []

    # Adversary 3: same guest PC, later compilation changes the SW source GPR.
    # PC/value alone would fabricate lineage across generations.
    u2_words = list(cpu_copy)
    u2_words[6] = enc_i(SW, 9, 12, 0)  # SW t4,0(t1), not t3
    u2 = Unit(202, u1.start, tuple(u2_words))
    l3 = LoadEvent(0, u1.unit, load_pc, 11, 0xB0002200, "rom_bytes", 0xCAFEBABE)
    ambiguous = StoreEvent(1, store_pc, 0x80004008, 0xCAFEBABE, None)
    assert naive_value_join([l3], [ambiguous]) == [(1, 0xB0002200)]
    assert certify({u1.unit: u1, u2.unit: u2}, [l3], [ambiguous]) == []
    wrong_unit = StoreEvent(1, store_pc, 0x8000400C, 0xCAFEBABE, u2.unit)
    assert certify({u1.unit: u1, u2.unit: u2}, [l3], [wrong_unit]) == []

    # Adversary 4: intervening clobber. Equal final value does not restore source
    # provenance, because provenance is about where these bytes came from.
    clobber = Unit(303, 0x80005000, (
        enc_i(LW, 8, 11, 0),
        enc_i(0x0D, 0, 11, 0xBEEF),  # ORI t3,zero,0xBEEF
        enc_i(SW, 9, 11, 0),
    ))
    lc = LoadEvent(0, clobber.unit, clobber.start, 11, 0x80006000, "rdram", 0x0000BEEF)
    sc = StoreEvent(1, clobber.start + 8, 0x80007000, 0x0000BEEF, clobber.unit)
    assert naive_value_join([lc], [sc]) == [(1, 0x80006000)]
    assert certify({clobber.unit: clobber}, [lc], [sc]) == []

    # Adversary 5: SW is in a branch delay slot. It is dynamically adjacent to
    # the branch, not to the LW, so a two-instruction source certificate must not
    # silently cross the control-transfer boundary.
    delay = Unit(404, 0x80008000, (
        enc_i(LW, 8, 11, 0),
        enc_i(BNE, 4, 5, 1),
        enc_i(SW, 9, 11, 0),
        0,
    ))
    ld = LoadEvent(0, delay.unit, delay.start, 11, 0x80009000, "rdram", 0xABCDEF01)
    sd = StoreEvent(1, delay.start + 8, 0x8000A000, 0xABCDEF01, delay.unit)
    assert naive_value_join([ld], [sd]) == [(1, 0x80009000)]
    assert certify({delay.unit: delay}, [ld], [sd]) == []

    # Adversary 6: a cartridge-space address is not itself ROM provenance. The
    # pinned device can return its PI last-write latch while IO_BUSY, or zero for
    # an out-of-range offset. The copy witness must preserve that backing outcome
    # instead of upgrading it to canonical ROM merely because the address is B000.
    latch_load = LoadEvent(0, u1.unit, load_pc, 11, 0xB0002400, "pi_latch", 0x77777777)
    latch_store = StoreEvent(1, store_pc, 0x80004010, 0x77777777, u1.unit)
    latch_witness = certify({u1.unit: u1}, [latch_load], [latch_store])
    assert len(latch_witness) == 1 and latch_witness[0].source_kind == "pi_latch"
    assert not any(w.source_kind == "rom_bytes" for w in latch_witness)

    zero_load = LoadEvent(0, u1.unit, load_pc, 11, 0xB0FFF000, "cart_oob_zero", 0)
    zero_store = StoreEvent(1, store_pc, 0x80004014, 0, u1.unit)
    zero_witness = certify({u1.unit: u1}, [zero_load], [zero_store])
    assert len(zero_witness) == 1 and zero_witness[0].source_kind == "cart_oob_zero"
    assert not any(w.source_kind == "rom_bytes" for w in zero_witness)

    # Adversary 7: transformed value. Even if a later arithmetic operation happens
    # to produce a store value equal to some earlier load, equality is not lineage.
    transform = Unit(505, 0x8000B000, (
        enc_i(LW, 8, 11, 0),
        enc_i(0x0D, 11, 11, 1),  # ORI t3,t3,1
        enc_i(SW, 9, 11, 0),
    ))
    lt = LoadEvent(0, transform.unit, transform.start, 11, 0x8000C000, "rdram", 0x11111111)
    st = StoreEvent(1, transform.start + 8, 0x8000D000, 0x11111111, transform.unit)
    assert naive_value_join([lt], [st]) == [(1, 0x8000C000)]
    assert certify({transform.unit: transform}, [lt], [st]) == []

    print("PASS canonical_witnesses=64")
    print("PASS lwu_direct_copy_accepted")
    print("PASS equal_value_decoy_rejected")
    print("PASS missing_source_unit_rejected")
    print("PASS same_pc_generation_ambiguity_rejected")
    print("PASS changed_source_register_rejected")
    print("PASS intervening_clobber_rejected")
    print("PASS delay_slot_boundary_rejected")
    print("PASS cartridge_address_not_rom_origin")
    print("PASS transformed_value_rejected")

if __name__ == "__main__":
    run()
