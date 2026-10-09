#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json, random

PINS = {
    "plaid": "ae41bdba82993ec8e77f47e5f9d3bb9af06f9256",
    "ares": "9408cb43d4948fc3ea6e152a307a34348df3fe04",
    "gopher64": "e96debac941a26ba4961e5145056c0821d3a56f7",
    "mupen64plus-core": "ba95bab92a76744753bfe61470823a4937850ab0",
    "n64-systemtest": "196f5421173220eb2f63a7a99c64795dc0ea0698",
}

@dataclass(frozen=True)
class RegValue:
    value: int | None
    generation: int
    source: str

class Replay:
    def __init__(self):
        self.epc = RegValue(None, 0, "unknown")
        self.error_epc = RegValue(None, 0, "unknown")
        self.erl = False
        self._gen = 0
        self.latest_capture = {"epc": None, "error_epc": None}

    def _write(self, which: str, value: int | None, source: str):
        self._gen += 1
        rv = RegValue(value, self._gen, source)
        if which == "epc": self.epc = rv
        else: self.error_epc = rv
        return rv

    def capture_epc(self, value: int):
        rv = self._write("epc", value, "exception_capture")
        self.latest_capture["epc"] = rv

    def capture_error_epc(self, value: int):
        rv = self._write("error_epc", value, "error_capture")
        self.latest_capture["error_epc"] = rv

    def mtc0_epc(self, value: int): self._write("epc", value, "guest_mtc0")
    def mtc0_error_epc(self, value: int): self._write("error_epc", value, "guest_mtc0")
    def unknown_epc_write(self): self._write("epc", None, "unknown_write")
    def unknown_error_epc_write(self): self._write("error_epc", None, "unknown_write")
    def set_erl(self, value: bool): self.erl = bool(value)

    def current(self, which: str) -> RegValue:
        return self.error_epc if which == "error_epc" else self.epc

    def eret(self, profile: str):
        if self.erl:
            if profile == "mupen64plus-core":
                # Exact pinned pure-interpreter behavior: log error and stop.
                return {"outcome": "stop", "register": None, "target": None, "sound": None, "naive": None}
            which = "error_epc"
        else:
            which = "epc"
        rv = self.current(which)
        actual = rv.value
        sound = None if actual is None else {
            "register": which, "target": actual, "generation": rv.generation, "source": rv.source
        }
        cap = self.latest_capture[which]
        naive = None if cap is None else {
            "register": which, "target": cap.value, "generation": cap.generation, "source": cap.source
        }
        return {"outcome": "jump", "register": which, "target": actual, "sound": sound, "naive": naive}


def common_epc_cases():
    out = []
    for profile in ("ares", "gopher64", "mupen64plus-core"):
        r = Replay(); r.capture_epc(0x80001000); r.mtc0_epc(0x80002000)
        e = r.eret(profile)
        assert e["outcome"] == "jump" and e["target"] == 0x80002000
        assert e["sound"]["source"] == "guest_mtc0" and e["naive"]["target"] == 0x80001000

        r = Replay(); r.mtc0_epc(0x80003000)
        e = r.eret(profile)
        assert e["target"] == 0x80003000 and e["sound"]["source"] == "guest_mtc0" and e["naive"] is None

        r = Replay(); r.capture_epc(0x80006000); captured_gen = r.epc.generation; r.mtc0_epc(0x80006000)
        e = r.eret(profile)
        assert e["target"] == e["naive"]["target"] == e["sound"]["target"]
        assert e["sound"]["generation"] != captured_gen and e["sound"]["source"] == "guest_mtc0"
        assert e["naive"]["source"] == "exception_capture"

        r = Replay(); r.capture_epc(0x80008000); r.unknown_epc_write()
        e = r.eret(profile)
        assert e["outcome"] == "jump" and e["target"] is None and e["sound"] is None
        assert e["naive"]["target"] == 0x80008000
    out.extend([
        "captured_epc_overwritten_to_different_guest_target_all_refs",
        "guest_only_epc_target_all_refs",
        "same_value_epc_overwrite_changes_generation_all_refs",
        "unknown_epc_write_fails_closed_all_refs",
    ])
    return out


def disputed_erl_cases():
    results = {}
    for profile in ("ares", "gopher64", "mupen64plus-core"):
        r = Replay(); r.capture_error_epc(0x80004000); r.mtc0_error_epc(0x80005000); r.set_erl(True)
        e = r.eret(profile)
        results[profile] = {"outcome": e["outcome"], "target": e["target"]}
    assert results["ares"] == {"outcome": "jump", "target": 0x80005000}
    assert results["gopher64"] == {"outcome": "jump", "target": 0x80005000}
    assert results["mupen64plus-core"] == {"outcome": "stop", "target": None}
    return results


def fuzz_common_epc(seed=0x45524554, histories=100_000, max_actions=24):
    rng = random.Random(seed)
    stats = {
        "histories": histories, "eret_events": 0, "guest_selected": 0, "unknown_selected": 0,
        "naive_wrong_target": 0, "naive_missing": 0, "naive_same_value_provenance_steal": 0,
        "sound_known": 0, "sound_unknown": 0,
    }
    for _ in range(histories):
        r = Replay()
        r.set_erl(False)
        for _ in range(rng.randint(1, max_actions)):
            op = rng.randrange(8)
            v = 0x80000000 | (rng.randrange(0, 0x10000) & ~3)
            if op == 0: r.capture_epc(v)
            elif op == 1: r.mtc0_epc(v)
            elif op == 2: r.unknown_epc_write()
            elif op == 3:
                cap = r.latest_capture["epc"]
                r.mtc0_epc(cap.value if cap is not None else v)
            elif op in (4, 5, 6, 7):
                e = r.eret("ares")
                stats["eret_events"] += 1
                before = r.epc
                if before.source == "guest_mtc0": stats["guest_selected"] += 1
                if before.source == "unknown_write" or before.value is None: stats["unknown_selected"] += 1
                sound, naive, actual = e["sound"], e["naive"], e["target"]
                if sound is None:
                    stats["sound_unknown"] += 1
                    assert actual is None
                else:
                    stats["sound_known"] += 1
                    assert sound["target"] == actual and sound["generation"] == before.generation
                if naive is None:
                    if actual is not None: stats["naive_missing"] += 1
                elif naive["target"] != actual:
                    stats["naive_wrong_target"] += 1
                elif sound is not None and naive["generation"] != sound["generation"]:
                    stats["naive_same_value_provenance_steal"] += 1
    assert all(stats[k] > 0 for k in (
        "guest_selected", "naive_wrong_target", "naive_missing", "naive_same_value_provenance_steal"
    ))
    return stats


def main():
    report = {
        "schema": "plaid.eret-target-provenance-model.v2",
        "pins": PINS,
        "hypothesis_common_epc": "capture-only ERET target provenance is unsound because EPC is guest-writable",
        "common_epc_cases": common_epc_cases(),
        "disputed_erl_case": disputed_erl_cases(),
        "fuzz_common_epc": fuzz_common_epc(),
        "result": "PASS_WITH_REFERENCE_DISAGREEMENT",
    }
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    digest = sha256(canonical).hexdigest()
    print(json.dumps(report, sort_keys=True, indent=2))
    print("REPORT_SHA256", digest)

if __name__ == "__main__":
    main()
