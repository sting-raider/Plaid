from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
from itertools import permutations
import json

ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
PLAID_BASE = "3cf45dc323cbcd9e6463ccc781d3de093a433097"

# Exact pinned-source blobs inspected for the synchronous call-order constraints.
SOURCE_BLOBS = {
    "ares/n64/cpu/cpu.cpp": "41964d49c8983ae9a97b25625174cd4c4316c4a8",
    "ares/n64/cpu/memory.cpp": "f362ef67ab41ccf57330bbedd6f614e07a61dd17",
    "ares/n64/cpu/interpreter-ipu.cpp": "938ccbd0af1f127439d9859c1fd6be2bbd5222a3",
    "ares/n64/memory/bus.hpp": "367308207719c1048daa1bbf7ffca635ca0c97d5",
    "ares/n64/mi/bus.hpp": "2d61fa47b6ae568390df421036df4ffefd23b4e5",
    "ares/n64/rdram/rdram.hpp": "c718ec2e9b2a78610353562cbc81dd973b278ee2",
}

@dataclass(frozen=True)
class Event:
    family: str
    kind: str
    address: int
    token: str
    sequence: int | None = None


def all_family_interleavings(events: tuple[Event, ...]) -> list[tuple[Event, ...]]:
    """All total orders preserving only each sensor family's internal order."""
    valid = []
    for candidate in permutations(events):
        ok = True
        for family in {e.family for e in events}:
            original = [e.token for e in events if e.family == family]
            merged = [e.token for e in candidate if e.family == family]
            if original != merged:
                ok = False
                break
        if ok:
            valid.append(candidate)
    return valid


def source_valid(order: tuple[Event, ...], constraints: tuple[tuple[str, str], ...]) -> bool:
    pos = {event.token: index for index, event in enumerate(order)}
    return all(pos[a] < pos[b] for a, b in constraints)


class TinyState:
    """State-only model used solely to check observer side-effect neutrality."""
    def __init__(self, observe: bool):
        self.observe = observe
        self.sequence = 0
        self.events: list[Event] = []
        self.ram = {0x0000: 1, 0x4000: 9}
        self.cache_valid = False
        self.cache_address = 0
        self.cache_word = 0

    def emit(self, family: str, kind: str, address: int, token: str) -> None:
        if not self.observe:
            return
        self.sequence += 1
        self.events.append(Event(family, kind, address, token, self.sequence))

    def cached_miss_fetch(self, address: int) -> int:
        # Pinned path: RDRAM burst returns -> fill callback -> CPU::fetch returns
        # -> instructionPrologue/debugger fetch observation.
        value = self.ram[address]
        self.emit("ram", "burst_read", address, "r")
        self.cache_valid = True
        self.cache_address = address
        self.cache_word = value
        self.emit("fill", "fill_complete", address, "f")
        self.emit("fetch", "instruction_fetch", address, "x")
        return value

    def cache_writeback_hit(self) -> None:
        # Pinned path: writeBurst stores + hidden update -> RAM callback ->
        # Line::writeBack returns -> CACHE handler returns -> op callback.
        assert self.cache_valid
        self.ram[self.cache_address] = self.cache_word
        self.emit("ram", "burst_write", self.cache_address, "w")
        self.emit("cache_op", "operation_complete", self.cache_address, "c")

    def uncached_fetch_current_sensors(self, address: int) -> int:
        # Ground truth performs an ordinary RDRAM word read, but spike 016's
        # current RAM sensor only observes readBurst/writeBurst, so no RAM event.
        value = self.ram[address]
        self.emit("fetch", "instruction_fetch", address, "u")
        return value

    def snapshot(self):
        return (tuple(sorted(self.ram.items())), self.cache_valid, self.cache_address, self.cache_word)


def main() -> None:
    # A cached miss has three independently ordered sensor families today. Without
    # a shared sequence, the raw arrays alone admit all six cross-family orders.
    cached = (
        Event("ram", "burst_read", 0, "r"),
        Event("fill", "fill_complete", 0, "f"),
        Event("fetch", "instruction_fetch", 0, "x"),
    )
    cached_orders = all_family_interleavings(cached)
    cached_source_valid = [o for o in cached_orders if source_valid(o, (("r", "f"), ("f", "x")))]
    assert len(cached_orders) == 6
    assert len(cached_source_valid) == 1

    # A writeback has the same problem across RAM and CACHE-op vectors.
    writeback = (
        Event("ram", "burst_write", 0x4000, "w"),
        Event("cache_op", "operation_complete", 0x4000, "c"),
    )
    write_orders = all_family_interleavings(writeback)
    assert len(write_orders) == 2
    assert len([o for o in write_orders if source_valid(o, (("w", "c"),))]) == 1

    # Repeated equal-address/equal-payload fills are intentionally adversarial:
    # values cannot serve as identity. Per-family order exists, but no cross-family
    # ordinal is serialized, so source-specific nesting knowledge is still needed.
    equal_payload = (
        Event("ram", "burst_read", 0, "r1"),
        Event("ram", "burst_read", 0, "r2"),
        Event("fill", "fill_complete", 0, "f1"),
        Event("fill", "fill_complete", 0, "f2"),
    )
    equal_orders = all_family_interleavings(equal_payload)
    assert len(equal_orders) == 6
    causal = (("r1", "f1"), ("f1", "r2"), ("r2", "f2"))
    assert len([o for o in equal_orders if source_valid(o, causal)]) == 1

    # Executable side-effect check on the tiny synchronous model: adding a shared
    # sequence changes only evidence, not RAM/cache state or returned values.
    plain = TinyState(False)
    traced = TinyState(True)
    assert plain.cached_miss_fetch(0) == traced.cached_miss_fetch(0) == 1
    plain.cache_address = traced.cache_address = 0x4000
    plain.cache_word = traced.cache_word = 9
    plain.cache_valid = traced.cache_valid = True
    plain.ram[0x4000] = traced.ram[0x4000] = 8
    plain.cache_writeback_hit(); traced.cache_writeback_hit()
    assert plain.uncached_fetch_current_sensors(0x4000) == traced.uncached_fetch_current_sensors(0x4000) == 9
    assert plain.snapshot() == traced.snapshot()

    kinds = [e.kind for e in traced.events]
    assert kinds == ["burst_read", "fill_complete", "instruction_fetch", "burst_write", "operation_complete", "instruction_fetch"]
    # The final uncached fetch has no observed RAM word-read predecessor. A global
    # sequence cannot repair an event that was never sensed.
    final = traced.events[-1]
    assert final.token == "u"
    assert not any(e.kind == "word_read" and e.sequence < final.sequence for e in traced.events)

    payload = {
        "plaid_base": PLAID_BASE,
        "ares_rev": ARES_REV,
        "source_blobs": SOURCE_BLOBS,
        "separate_array_cached_orders": len(cached_orders),
        "separate_array_writeback_orders": len(write_orders),
        "equal_payload_cross_family_orders": len(equal_orders),
        "unique_source_valid_cached_orders": len(cached_source_valid),
        "ordered_events": [asdict(e) for e in traced.events],
        "uncached_fetch_has_backing_event": False,
        "state": traced.snapshot(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    digest = sha256(encoded).hexdigest()
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"PASS sha256={digest}")


if __name__ == "__main__":
    main()
