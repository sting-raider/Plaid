#!/usr/bin/env python3
"""Standalone adversarial model for one completed integer SD -> SP Word sink."""
from dataclasses import dataclass

HIGH = 0x11223344
LOW = 0x55667788

@dataclass(frozen=True)
class Sink:
    address: int
    bank: int
    offset: int
    value: int
    cpu: bool = True


def certify(mode: str, exception: int, bank: int, offset: int, sinks: list[Sink]) -> bool:
    if mode not in ("ok", "same") or exception != 0 or len(sinks) != 1:
        return False
    base = 0x04001000 if bank else 0x04000000
    return sinks[0] == Sink(base + offset, bank, offset, HIGH, True)


def main() -> None:
    good = Sink(0x04000000, 0, 0, HIGH)
    assert certify("ok", 0, 0, 0, [good])
    assert certify("same", 0, 0, 0, [good])
    assert not certify("ok", 0, 0, 0, [])
    assert not certify("ok", 0, 0, 0, [Sink(0x04000000, 0, 0, LOW)])
    assert not certify("ok", 0, 0, 0, [good, Sink(0x04000004, 0, 4, LOW)])
    assert not certify("ok", 0, 0, 0, [Sink(0x04000000, 1, 0, HIGH)])
    assert not certify("misalign", 5, 0, 0, [good])
    print("PASS: same-value sink retained; five forged histories rejected")


if __name__ == "__main__":
    main()
