#!/usr/bin/env python3
"""Build exact pinned ares and verify integer SD effects in CPU-visible SP memory."""
from __future__ import annotations
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "target/ares-cpu-sd-sp-sink-gpt56sol"
DATA = 0x1122334455667788
HIGH = DATA >> 32

bspec = importlib.util.spec_from_file_location("ares_build", ROOT / "spikes/003-ares-oracle/run.py")
build = importlib.util.module_from_spec(bspec)
assert bspec.loader is not None
bspec.loader.exec_module(build)


def source_guards() -> None:
    ref = ROOT / ".refs/ares"
    ipu = (ref / "ares/n64/cpu/interpreter-ipu.cpp").read_text()
    sd = """auto CPU::SD(cr64& rt, cr64& rs, s16 imm) -> void {\n  if(!context.kernelMode() && context.bits == 32) return exception.reservedInstruction();\n  write<Dual>(rs.u64 + imm, rt.u64);\n}"""
    assert ipu.count(sd) == 1
    io = (ref / "ares/n64/memory/io.hpp").read_text()
    dual = """    if constexpr(Size == Dual) {\n      ((T*)this)->writeWord(address, data >> 32, thread);\n    }"""
    assert io.count(dual) == 1
    rsp = (ref / "ares/n64/rsp/io.cpp").read_text()
    assert "if(address & 0x1000) return recompiler.invalidate(address & 0xfff), imem.write<Word>(address, data);" in rsp
    assert "else                 return dmem.write<Word>(address, data);" in rsp


def invoke(exe: Path, bank: str, mode: str, offset: int, observer: str) -> dict:
    args = [str(exe), bank, mode, str(offset), observer]
    a = subprocess.check_output(args, text=True, timeout=20)
    b = subprocess.check_output(args, text=True, timeout=20)
    assert a == b, (bank, mode, offset, observer)
    return json.loads(a)


def neutral_pair(exe: Path, bank: str, mode: str, offset: int) -> tuple[dict, dict]:
    on = invoke(exe, bank, mode, offset, "on")
    off = invoke(exe, bank, mode, offset, "off")
    a = {k: v for k, v in on.items() if k not in ("observer", "sinks")}
    b = {k: v for k, v in off.items() if k not in ("observer", "sinks")}
    assert a == b, (on, off)
    assert off["sinks"] == [], off
    return on, off


def changed_indices(before: list[int], after: list[int]) -> list[int]:
    return [i for i, (a, b) in enumerate(zip(before, after)) if a != b]


def expected_address(result: dict) -> int:
    base = 0x04001000 if result["bank"] == "imem" else 0x04000000
    return base + result["offset"]


def certify_completed_sd(result: dict) -> bool:
    """Bounded sink certificate. It intentionally ignores before/after inequality."""
    if result["mode"] not in ("ok", "same") or result["exception"] != 0:
        return False
    if len(result["sinks"]) != 1:
        return False
    sink = result["sinks"][0]
    return sink == {
        "address": expected_address(result),
        "bank": 1 if result["bank"] == "imem" else 0,
        "offset": result["offset"],
        "value": HIGH,
        "cpu": True,
    }


def adversarial_replay(actual: list[dict]) -> dict:
    successes = [r for r in actual if r["observer"] == "on" and r["mode"] in ("ok", "same")]
    assert successes and all(certify_completed_sd(r) for r in successes)

    same = next(r for r in successes if r["mode"] == "same")
    assert changed_indices(same["before_target_bytes"], same["after_target_bytes"]) == []
    naive_same_value_accepts = bool(changed_indices(same["before_target_bytes"], same["after_target_bytes"]))
    assert not naive_same_value_accepts and certify_completed_sd(same)

    base = next(r for r in successes if r["mode"] == "ok" and r["bank"] == "dmem" and r["offset"] == 0)
    forged = []
    no_sink = copy.deepcopy(base); no_sink["sinks"] = []
    forged.append(("opcode_without_sink", no_sink))
    low_half = copy.deepcopy(base); low_half["sinks"][0]["value"] = DATA & 0xFFFFFFFF
    forged.append(("wrong_low_half_payload", low_half))
    two_words = copy.deepcopy(base)
    second = copy.deepcopy(two_words["sinks"][0]); second["address"] += 4; second["offset"] += 4; second["value"] = DATA & 0xFFFFFFFF
    two_words["sinks"].append(second)
    forged.append(("invented_architectural_eight_bytes", two_words))
    wrong_bank = copy.deepcopy(base); wrong_bank["sinks"][0]["bank"] = 1
    forged.append(("equal_payload_wrong_bank", wrong_bank))
    fault_with_sink = copy.deepcopy(base); fault_with_sink["mode"] = "misalign"; fault_with_sink["exception"] = 5
    forged.append(("fault_with_fabricated_sink", fault_with_sink))
    for name, history in forged:
        assert not certify_completed_sd(history), name
    return {
        "same_value_diff_rule_accepts": naive_same_value_accepts,
        "same_value_sink_rule_accepts": certify_completed_sd(same),
        "forged_histories_rejected": [name for name, _ in forged],
    }


def main() -> None:
    source_guards()
    exe = build.build(HERE / "driver.cpp", OUT, raw_fetch_access=True, physical_fetch_access=True, sp_backing_access=True)
    results: list[dict] = []
    for bank in ("dmem", "imem"):
        for mode in ("ok", "same"):
            for offset in (0, 8):
                r, disabled = neutral_pair(exe, bank, mode, offset)
                results += [r, disabled]
                assert (r["exception"], r["coprocessor_error"]) == (0, 0), r
                assert r["after_other_words"] == r["before_other_words"], r
                index = offset // 4
                expected_changed_words = [] if mode == "same" else [index]
                assert changed_indices(r["before_target_words"], r["after_target_words"]) == expected_changed_words, r
                # Numeric helper readback is endian/presentation-sensitive. The completed
                # device observer is the payload oracle; helper views establish footprint only.
                assert r["after_target_words"][index + 1] == r["before_target_words"][index + 1], r
                assert r["sinks"] == [{
                    "address": (0x04001000 if bank == "imem" else 0x04000000) + offset,
                    "bank": 1 if bank == "imem" else 0,
                    "offset": offset,
                    "value": HIGH,
                    "cpu": True,
                }], r
                changed = changed_indices(r["before_target_bytes"], r["after_target_bytes"])
                if mode == "same":
                    assert changed == [], r
                else:
                    assert changed and all(offset <= i < offset + 4 for i in changed), r
                    assert r["after_target_bytes"][:offset] == r["before_target_bytes"][:offset], r
                    assert r["after_target_bytes"][offset + 4:] == r["before_target_bytes"][offset + 4:], r

        for mode, expected_exception in (("misalign", 5), ("reserved", 10)):
            r, disabled = neutral_pair(exe, bank, mode, 0)
            results += [r, disabled]
            assert r["exception"] == expected_exception, r
            assert r["after_target_words"] == r["before_target_words"], r
            assert r["after_other_words"] == r["before_other_words"], r
            assert r["after_target_bytes"] == r["before_target_bytes"], r
            assert r["sinks"] == [], r

    replay = adversarial_replay(results)
    encoded = (json.dumps({"results": results, "replay": replay}, sort_keys=True, separators=(",", ":")) + "\n").encode()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_bytes(encoded)
    digest = hashlib.sha256(encoded).hexdigest()
    print(f"PASS: {len(results)} enabled/disabled exact-pin integer SD-to-SP observations; every process repeated")
    print("same_value_diff_rule_accepts=false")
    print("same_value_sink_rule_accepts=true")
    print("forged_histories_rejected=" + str(len(replay["forged_histories_rejected"])))
    print("results_sha256=" + digest)


if __name__ == "__main__":
    main()
