#!/usr/bin/env python3
"""Bounded adversarial model for ares N64 PIF-ROM fetch provenance.

This is an independent executable model of the routing/source conditions observed
at ares revision 9408cb43d4948fc3ea6e152a307a34348df3fe04. It deliberately does not
model N64 timing or general CPU execution. It tests only whether a per-fetch
firmware-origin witness can be emitted without false positives for the declared
SI/PIF paths.
"""
from __future__ import annotations

from dataclasses import dataclass
import argparse
import hashlib
import json
import random
from pathlib import Path

ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
PIF_WINDOW_START = 0x1FC00000
PIF_WINDOW_END = 0x1FCFFFFF
PIF_ADDR_MASK = 0x7FF
PIF_ROM_END = 0x7BF
PIF_ROM_SIZE = 0x7C0
PIF_RAM_START = 0x7C0
PIF_RAM_SIZE = 0x40
KNOWN_NTSC_SHA256 = "fa7b09795ef1e54461e59f6f2d902368133e3f1cd980e34383e6a780d74beffd"


@dataclass(frozen=True)
class FirmwareRead:
    fetch_id: int
    paddr: int
    masked_offset: int
    word: int


@dataclass(frozen=True)
class FetchResult:
    fetch_id: int
    paddr: int
    cached: bool
    returned: int | None
    path: str
    witness: FirmwareRead | None


def be32(buf: bytes, offset: int) -> int:
    assert offset % 4 == 0
    assert 0 <= offset <= len(buf) - 4
    return int.from_bytes(buf[offset : offset + 4], "big")


def fetch_model(
    *,
    fetch_id: int,
    paddr: int,
    cached: bool,
    firmware: bytes,
    pif_ram: bytes,
    io_busy: bool = False,
    bus_latch: int = 0,
    rom_lockout: bool = False,
) -> FetchResult:
    """Model only the relevant pinned ares routing for a CPU instruction fetch.

    - cached non-RDRAM fetches do not reach SI/PIF because Bus::readBurst only
      accepts RDRAM for the N64 path;
    - uncached 0x1fc00000..0x1fcfffff routes through SI;
    - SI ioBusy returns busLatch before PIF access;
    - PIF masks with &0x7ff; <=0x7bf is ROM unless locked; >=0x7c0 is RAM.
    """
    assert len(firmware) == PIF_ROM_SIZE
    assert len(pif_ram) == PIF_RAM_SIZE
    paddr &= 0xFFFFFFFF

    if cached:
        return FetchResult(fetch_id, paddr, True, None, "cached_non_rdram_rejected", None)

    if not (PIF_WINDOW_START <= paddr <= PIF_WINDOW_END):
        return FetchResult(fetch_id, paddr, False, None, "not_pif_window", None)

    if io_busy:
        return FetchResult(fetch_id, paddr, False, bus_latch & 0xFFFFFFFF, "si_busy_latch", None)

    offset = paddr & PIF_ADDR_MASK
    offset &= ~3  # instruction fetch is word-aligned in this bounded model

    if offset <= PIF_ROM_END:
        if rom_lockout:
            return FetchResult(fetch_id, paddr, False, 0, "pif_rom_lockout_zero", None)
        word = be32(firmware, offset)
        witness = FirmwareRead(fetch_id, paddr, offset, word)
        return FetchResult(fetch_id, paddr, False, word, "pif_rom_read", witness)

    ram_off = offset - PIF_RAM_START
    word = be32(pif_ram, ram_off)
    return FetchResult(fetch_id, paddr, False, word, "pif_ram_read", None)


def naive_value_policy(result: FetchResult, firmware: bytes) -> int | None:
    """Intentionally unsound comparator: infer source from equal returned value."""
    if result.returned is None:
        return None
    for off in range(0, PIF_ROM_SIZE, 4):
        if be32(firmware, off) == result.returned:
            return off
    return None


def naive_physical_policy(result: FetchResult) -> int | None:
    """Intentionally incomplete comparator: physical_delta == firmware offset."""
    if result.returned is None:
        return None
    delta = result.paddr - PIF_WINDOW_START
    if 0 <= delta <= PIF_ROM_END and delta % 4 == 0:
        return delta
    return None


def synthetic_firmware() -> bytes:
    data = bytearray(PIF_ROM_SIZE)
    for off in range(0, PIF_ROM_SIZE, 4):
        # unique-ish deterministic words, except explicitly adversarial duplicates/zeroes below
        word = (0xA5000000 ^ (off * 0x1021) ^ (off << 16)) & 0xFFFFFFFF
        data[off : off + 4] = word.to_bytes(4, "big")
    data[0:4] = (0x3C1ABFC0).to_bytes(4, "big")
    data[4:8] = (0).to_bytes(4, "big")  # makes lockout-zero collide with a real firmware word
    data[8:12] = data[0:4]              # duplicate word defeats value-to-offset uniqueness
    return bytes(data)


def run_cases(firmware: bytes) -> dict:
    same = firmware[0:4]
    pif_ram = bytearray(PIF_RAM_SIZE)
    pif_ram[0:4] = same  # RAM deliberately returns same value as firmware offset 0
    pif_ram = bytes(pif_ram)
    fw0 = be32(firmware, 0)

    cases = {
        "power_entry": fetch_model(fetch_id=1, paddr=0x1FC00000, cached=False, firmware=firmware, pif_ram=pif_ram),
        "last_rom_word": fetch_model(fetch_id=2, paddr=0x1FC007BC, cached=False, firmware=firmware, pif_ram=pif_ram),
        "masked_alias": fetch_model(fetch_id=3, paddr=0x1FC00800, cached=False, firmware=firmware, pif_ram=pif_ram),
        "high_masked_alias": fetch_model(fetch_id=4, paddr=0x1FCFF800, cached=False, firmware=firmware, pif_ram=pif_ram),
        "pif_ram_same_value": fetch_model(fetch_id=5, paddr=0x1FC007C0, cached=False, firmware=firmware, pif_ram=pif_ram),
        "busy_latch_same_value": fetch_model(fetch_id=6, paddr=0x1FC00000, cached=False, firmware=firmware, pif_ram=pif_ram, io_busy=True, bus_latch=fw0),
        "lockout_zero": fetch_model(fetch_id=7, paddr=0x1FC00004, cached=False, firmware=firmware, pif_ram=pif_ram, rom_lockout=True),
        "unlocked_zero": fetch_model(fetch_id=8, paddr=0x1FC00004, cached=False, firmware=firmware, pif_ram=pif_ram),
        "cached_pif": fetch_model(fetch_id=9, paddr=0x1FC00000, cached=True, firmware=firmware, pif_ram=pif_ram),
        "pi_boundary": fetch_model(fetch_id=10, paddr=0x1FBFFFFC, cached=False, firmware=firmware, pif_ram=pif_ram),
        "outside_si": fetch_model(fetch_id=11, paddr=0x1FD00000, cached=False, firmware=firmware, pif_ram=pif_ram),
    }

    # Positive witnesses are exact and bounded.
    assert cases["power_entry"].witness and cases["power_entry"].witness.masked_offset == 0
    assert cases["last_rom_word"].witness and cases["last_rom_word"].witness.masked_offset == 0x7BC
    assert cases["masked_alias"].witness and cases["masked_alias"].witness.masked_offset == 0
    assert cases["high_masked_alias"].witness and cases["high_masked_alias"].witness.masked_offset == 0
    assert cases["unlocked_zero"].witness and cases["unlocked_zero"].witness.masked_offset == 4

    # Negative paths return no firmware witness even if the value collides.
    for name in ("pif_ram_same_value", "busy_latch_same_value", "lockout_zero", "cached_pif", "pi_boundary", "outside_si"):
        assert cases[name].witness is None, name

    # Equal values cannot prove source.
    assert cases["pif_ram_same_value"].returned == fw0
    assert cases["busy_latch_same_value"].returned == fw0
    assert naive_value_policy(cases["pif_ram_same_value"], firmware) is not None
    assert naive_value_policy(cases["busy_latch_same_value"], firmware) is not None
    assert cases["lockout_zero"].returned == cases["unlocked_zero"].returned == 0
    assert naive_value_policy(cases["lockout_zero"], firmware) == 4

    # Physical-delta inference misses legitimate mirrors and cannot represent actual backing offset.
    assert naive_physical_policy(cases["masked_alias"]) is None
    assert naive_physical_policy(cases["high_masked_alias"]) is None

    # A previous genuine read cannot leak into the next same-value non-ROM fetch.
    assert cases["power_entry"].witness is not None
    assert cases["busy_latch_same_value"].witness is None
    assert cases["power_entry"].returned == cases["busy_latch_same_value"].returned
    assert cases["power_entry"].fetch_id != cases["busy_latch_same_value"].fetch_id

    return {
        name: {
            "fetch_id": c.fetch_id,
            "paddr": f"0x{c.paddr:08x}",
            "cached": c.cached,
            "returned": None if c.returned is None else f"0x{c.returned:08x}",
            "path": c.path,
            "witness_offset": None if c.witness is None else f"0x{c.witness.masked_offset:03x}",
        }
        for name, c in cases.items()
    }


def fuzz(firmware: bytes, iterations: int = 100_000) -> dict:
    rng = random.Random(0x504946)  # "PIF"
    pif_ram = bytes(rng.getrandbits(8) for _ in range(PIF_RAM_SIZE))
    positives = negatives = 0
    mirrored_positives = 0

    interesting = [
        0x1FBFFFFC, 0x1FC00000, 0x1FC00004, 0x1FC007BC, 0x1FC007C0,
        0x1FC007FC, 0x1FC00800, 0x1FC01000, 0x1FCFF800, 0x1FCFFFFC, 0x1FD00000,
    ]

    for i in range(iterations):
        if i < len(interesting):
            paddr = interesting[i]
        else:
            # Concentrate around SI/PIF boundaries but include arbitrary 32-bit addresses.
            if rng.randrange(4):
                paddr = (0x1FB00000 + rng.randrange(0x300000)) & ~3
            else:
                paddr = rng.getrandbits(32) & ~3
        cached = bool(rng.getrandbits(1))
        io_busy = bool(rng.randrange(8) == 0)
        rom_lockout = bool(rng.randrange(8) == 0)
        latch = rng.getrandbits(32)
        r = fetch_model(
            fetch_id=1000 + i,
            paddr=paddr,
            cached=cached,
            firmware=firmware,
            pif_ram=pif_ram,
            io_busy=io_busy,
            bus_latch=latch,
            rom_lockout=rom_lockout,
        )

        offset = paddr & PIF_ADDR_MASK & ~3
        oracle_positive = (
            not cached
            and PIF_WINDOW_START <= paddr <= PIF_WINDOW_END
            and not io_busy
            and offset <= PIF_ROM_END
            and not rom_lockout
        )
        assert (r.witness is not None) == oracle_positive
        if r.witness:
            positives += 1
            assert r.path == "pif_rom_read"
            assert r.witness.fetch_id == r.fetch_id
            assert r.witness.paddr == paddr
            assert r.witness.masked_offset == offset
            assert r.witness.word == r.returned == be32(firmware, offset)
            if paddr - PIF_WINDOW_START > PIF_ROM_END:
                mirrored_positives += 1
        else:
            negatives += 1
            assert r.path != "pif_rom_read"

    return {
        "iterations": iterations,
        "positives": positives,
        "negatives": negatives,
        "mirrored_positives": mirrored_positives,
        "seed": "0x504946",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--firmware", type=Path, help="Optional local 1,984-byte NTSC PIF ROM; never written to output")
    ap.add_argument("--fuzz", type=int, default=100_000)
    args = ap.parse_args()

    if args.firmware:
        firmware = args.firmware.read_bytes()
        assert len(firmware) == PIF_ROM_SIZE
        digest = hashlib.sha256(firmware).hexdigest()
        assert digest == KNOWN_NTSC_SHA256, digest
        fixture = "local_ntsc_pif"
    else:
        firmware = synthetic_firmware()
        digest = hashlib.sha256(firmware).hexdigest()
        fixture = "synthetic"

    cases = run_cases(firmware)
    fuzz_result = fuzz(firmware, args.fuzz)
    output = {
        "ares_revision": ARES_REV,
        "fixture": fixture,
        "firmware_size": len(firmware),
        "firmware_sha256": digest,
        "cases": cases,
        "fuzz": fuzz_result,
        "result": "MODEL_VALIDATED",
        "claim": "Firmware provenance is sound only when tied to the actual unlocked PIF ROM backing read within the same fetch context; address/value inference alone is unsound.",
    }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
