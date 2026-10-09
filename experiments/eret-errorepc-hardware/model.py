#!/usr/bin/env python3
"""Adversarial ErrorEPC/ERL ERET provenance model for Plaid research."""
from __future__ import annotations
import hashlib, json, random
from dataclasses import dataclass

UNKNOWN = object()

@dataclass
class Reg:
    value: object = UNKNOWN
    generation: int = 0
    writer: str = "unknown"

    def write(self, value: object, writer: str) -> None:
        self.generation += 1
        self.value = value
        self.writer = writer

@dataclass
class State:
    epc: Reg
    errorepc: Reg
    erl: bool
    exl: bool


def eret(state: State):
    reg = state.errorepc if state.erl else state.epc
    selected = "ErrorEPC" if state.erl else "EPC"
    out = {
        "selected": selected,
        "known": reg.value is not UNKNOWN,
        "target": None if reg.value is UNKNOWN else reg.value,
        "generation": reg.generation,
        "writer": reg.writer,
        "erl_before": state.erl,
        "exl_before": state.exl,
    }
    if state.erl:
        state.erl = False
    else:
        state.exl = False
    out["erl_after"] = state.erl
    out["exl_after"] = state.exl
    return out


def capture_only_target(state: State, last_epc_capture, last_error_capture):
    return last_error_capture if state.erl else last_epc_capture


def fixed_cases():
    cases = []

    s = State(Reg(0x1110, 1, "exception_capture"), Reg(0x2220, 1, "nmi_capture"), True, True)
    r = eret(s)
    assert r["target"] == 0x2220 and r["selected"] == "ErrorEPC"
    assert not s.erl and s.exl
    cases.append(("erl_selects_errorepc_preserves_exl", r))

    s = State(Reg(0x1110, 1, "exception_capture"), Reg(0x2220, 1, "nmi_capture"), False, True)
    r = eret(s)
    assert r["target"] == 0x1110 and r["selected"] == "EPC"
    assert not s.exl and not s.erl
    cases.append(("erl0_selects_epc", r))

    s = State(Reg(0x1110, 1, "exception_capture"), Reg(0x2220, 1, "nmi_capture"), True, False)
    s.errorepc.write(0x3330, "guest_dmtc0")
    r = eret(s)
    assert r["target"] == 0x3330 and r["generation"] == 2
    cases.append(("guest_overwrites_nmi_capture", r))

    s = State(Reg(0x1110, 1, "exception_capture"), Reg(0x2220, 7, "nmi_capture"), True, False)
    old_generation = s.errorepc.generation
    s.errorepc.write(0x2220, "guest_dmtc0_same_value")
    r = eret(s)
    assert r["target"] == 0x2220 and r["generation"] == old_generation + 1
    assert r["writer"] == "guest_dmtc0_same_value"
    cases.append(("same_value_write_is_new_generation", r))

    s = State(Reg(0x1110, 1, "exception_capture"), Reg(0x2220, 1, "nmi_capture"), True, True)
    s.errorepc.write(UNKNOWN, "restore_unknown")
    r = eret(s)
    assert not r["known"] and r["target"] is None
    cases.append(("unknown_errorepc_fails_closed", r))

    s = State(Reg(0x1110, 1, "exception_capture"), Reg(0x2220, 1, "nmi_capture"), True, False)
    last_error_capture = 0x2220
    s.errorepc.write(0x4440, "guest_dmtc0")
    guessed = capture_only_target(s, 0x1110, last_error_capture)
    actual = eret(s)["target"]
    assert guessed == 0x2220 and actual == 0x4440 and guessed != actual
    cases.append(("capture_only_policy_rejected", {"guessed": guessed, "actual": actual}))

    return cases


def fuzz(seed=0x4300, histories=100_000):
    rng = random.Random(seed)
    wrong_capture = 0
    missing_capture = 0
    same_value_substitution = 0
    known = 0
    unresolved = 0
    erets = 0
    same_value_writes = 0

    for _ in range(histories):
        epc = Reg()
        err = Reg()
        state = State(epc, err, bool(rng.getrandbits(1)), bool(rng.getrandbits(1)))
        last_epc_capture = None
        last_error_capture = None
        for _step in range(rng.randint(6, 24)):
            op = rng.randrange(10)
            if op == 0:
                v = rng.randrange(0, 64) * 4
                epc.write(v, "exception_capture")
                last_epc_capture = v
            elif op == 1:
                v = rng.randrange(0, 64) * 4
                err.write(v, "nmi_capture")
                last_error_capture = v
            elif op == 2:
                v = rng.randrange(0, 64) * 4
                if epc.value is not UNKNOWN and v == epc.value:
                    same_value_writes += 1
                epc.write(v, "guest_mtc0")
            elif op == 3:
                v = rng.randrange(0, 64) * 4
                if err.value is not UNKNOWN and v == err.value:
                    same_value_writes += 1
                err.write(v, "guest_dmtc0")
            elif op == 4:
                epc.write(UNKNOWN, "unknown_restore")
            elif op == 5:
                err.write(UNKNOWN, "unknown_restore")
            elif op == 6:
                state.erl = bool(rng.getrandbits(1))
            elif op == 7:
                state.exl = bool(rng.getrandbits(1))
            else:
                before_erl = state.erl
                selected = err if before_erl else epc
                guessed = last_error_capture if before_erl else last_epc_capture
                selected_generation = selected.generation
                selected_writer = selected.writer
                selected_value = selected.value
                result = eret(state)
                erets += 1
                if result["known"]:
                    known += 1
                    if guessed is None:
                        missing_capture += 1
                    elif guessed != result["target"]:
                        wrong_capture += 1
                    elif selected_writer.startswith("guest_"):
                        same_value_substitution += 1
                    assert result["generation"] == selected_generation
                    assert result["target"] == selected_value
                else:
                    unresolved += 1
                    assert result["target"] is None

    return {
        "seed": seed,
        "histories": histories,
        "eret_events": erets,
        "generation_aware_known": known,
        "generation_aware_unresolved": unresolved,
        "capture_only_wrong_target": wrong_capture,
        "capture_only_missing_target": missing_capture,
        "capture_only_same_value_provenance_substitution": same_value_substitution,
        "same_value_register_writes": same_value_writes,
    }


def main():
    fixed = fixed_cases()
    fuzzed = fuzz()
    assert fuzzed["eret_events"] > 100_000
    assert fuzzed["capture_only_wrong_target"] > 0
    assert fuzzed["capture_only_missing_target"] > 0
    assert fuzzed["capture_only_same_value_provenance_substitution"] > 0
    assert fuzzed["same_value_register_writes"] > 0
    report = {
        "contract": "VR4300 ERET selects current ErrorEPC generation iff ERL=1, else current EPC generation",
        "fixed_cases": [{"name": n, "result": r} for n, r in fixed],
        "fuzz": fuzzed,
        "forged_policies_rejected": [
            "ERL ignored and EPC always selected",
            "ErrorEPC inferred only from last NMI/reset capture",
            "same-value ErrorEPC write coalesced away",
            "unknown restore treated as prior known ErrorEPC",
            "ERL=1 ERET clears EXL instead of ERL",
        ],
    }
    payload = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    print(json.dumps(report, indent=2, sort_keys=True))
    print("REPORT_SHA256", hashlib.sha256(payload).hexdigest())
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
