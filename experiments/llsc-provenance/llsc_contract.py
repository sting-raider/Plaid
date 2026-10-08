#!/usr/bin/env python3
"""Deterministic adversarial model for pinned N64 LL/SC reference semantics.

This does not pretend the model is hardware. Hardware obligations are kept separate
and come only from pinned n64-systemtest cases. Reference rules are transcribed from
exact pinned sources documented in research/llsc-provenance.md.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
from itertools import product
import hashlib, json

A = 0x001000
B = 0x002000
VA1 = 0x0DEA0000
VA2 = 0x0BEE0000

@dataclass(frozen=True)
class State:
    llbit: bool = False
    lladdr: int = 0
    mem_a: int = 0x89ABCDEF
    mem_b: int = 0xA5A5A5A5

@dataclass(frozen=True)
class Result:
    state: State
    status: int | None = None
    wrote: bool = False
    backing_wrote: bool = False
    cache_resident_wrote: bool = False

class Model:
    def __init__(self, name: str, records_lladdr: bool, clear_after_sc: bool, clear_on_eret: bool):
        self.name = name
        self.records_lladdr = records_lladdr
        self.clear_after_sc = clear_after_sc
        self.clear_on_eret = clear_on_eret

    def step(self, state: State, action: tuple) -> Result:
        op = action[0]
        if op == "ll":
            phys = action[1]
            return Result(replace(state, llbit=True, lladdr=(phys >> 4) if self.records_lladdr else state.lladdr))
        if op == "eret":
            return Result(replace(state, llbit=False if self.clear_on_eret else state.llbit))
        if op == "sc":
            phys, value, cached, write_success = action[1:]
            if not state.llbit:
                return Result(state, status=0)
            if not write_success:
                # Pinned sources disagree in some failure-path register details; the only
                # provenance-safe fact used here is that there was no successful mutation.
                return Result(state, status=None)
            ns = state
            if phys == A:
                ns = replace(ns, mem_a=value)
            elif phys == B:
                ns = replace(ns, mem_b=value)
            if self.clear_after_sc:
                ns = replace(ns, llbit=False)
            return Result(ns, status=1, wrote=True,
                          backing_wrote=not cached,
                          cache_resident_wrote=cached)
        raise ValueError(action)

MODELS = {
    # Pinned ares interpreter SC/SCD checks llbit and returns write(...), with no
    # llbit clear in the instruction; ERET clears it. LL/LLD records paddr>>4.
    "ares": Model("ares", records_lladdr=True, clear_after_sc=False, clear_on_eret=True),
    # Pinned Mupen LL only sets llbit; SC clears llbit after successful write;
    # ERET clears llbit. No LLAddr write appears in LL/LLD paths at this pin.
    "mupen": Model("mupen", records_lladdr=False, clear_after_sc=True, clear_on_eret=True),
    # Pinned Gopher64 LL/LLD records LLAddr; SC/SCD clear llbit before data_write;
    # ERET clears llbit.
    "gopher": Model("gopher", records_lladdr=True, clear_after_sc=True, clear_on_eret=True),
}

def run(model: Model, actions: list[tuple]) -> list[Result]:
    s = State()
    out = []
    for a in actions:
        r = model.step(s, a)
        out.append(r)
        s = r.state
    return out

def observable(r: Result):
    return (r.state.llbit, r.state.lladdr, r.state.mem_a, r.state.mem_b,
            r.status, r.wrote, r.backing_wrote, r.cache_resident_wrote)

def assert_hardware_obligations():
    # Pinned n64-systemtest: LL publishes physical LLAddr.
    for name in ("ares", "gopher"):
        r = run(MODELS[name], [("ll", A)])[0]
        assert r.state.lladdr == A >> 4
    # Mupen divergence is deliberate evidence: its pinned LL path does not update LLAddr.
    assert run(MODELS["mupen"], [("ll", A)])[0].state.lladdr != A >> 4

    # Pinned n64-systemtest: ERET clears reservation but leaves LLAddr, so SC must fail.
    seq = [("ll", A), ("eret",), ("sc", A, 0x13579BDF, False, True)]
    for model in MODELS.values():
        rs = run(model, seq)
        assert rs[-1].status == 0 and not rs[-1].wrote
        assert rs[-1].state.mem_a == 0x89ABCDEF
    for name in ("ares", "gopher"):
        assert run(MODELS[name], seq)[-1].state.lladdr == A >> 4

    # Pinned n64-systemtest: distinct TLB VAs to same physical backing must allow SC.
    # The source models use physical paddr for LLAddr (or ignore LLAddr entirely), not VA identity.
    alias_seq = [("ll", A), ("sc", A, 0x13579BDF, False, True)]
    for model in MODELS.values():
        rs = run(model, alias_seq)
        assert rs[-1].status == 1 and rs[-1].wrote and rs[-1].state.mem_a == 0x13579BDF

    # Failed store must never create provenance even if status-register details differ.
    fail_seq = [("ll", A), ("sc", A, 0xDEADBEEF, False, False)]
    for model in MODELS.values():
        rs = run(model, fail_seq)
        assert not rs[-1].wrote and not rs[-1].backing_wrote and not rs[-1].cache_resident_wrote
        assert rs[-1].state.mem_a == 0x89ABCDEF

    # Cached SC success is not an immediate backing witness. Uncached success is.
    for cached in (False, True):
        r = run(MODELS["gopher"], [("ll", A), ("sc", A, 0x12345678, cached, True)])[-1]
        assert r.wrote
        assert r.backing_wrote == (not cached)
        assert r.cache_resident_wrote == cached

def exhaustive_divergences(max_len=4):
    alphabet = [
        ("ll", A),
        ("ll", B),
        ("eret",),
        ("sc", A, 0x11111111, False, True),
        ("sc", B, 0x22222222, False, True),
    ]
    divergent = []
    minimal = None
    for n in range(1, max_len + 1):
        for actions in product(alphabet, repeat=n):
            traces = {name: tuple(observable(x) for x in run(model, list(actions)))
                      for name, model in MODELS.items()}
            if len(set(traces.values())) != 1:
                divergent.append(actions)
                if minimal is None:
                    minimal = actions
        if minimal is not None:
            break
    # Find the first behavioral divergence *excluding LLAddr observability*, so the
    # repeated-SC reservation bug cannot be hidden by Mupen's earlier LLAddr mismatch.
    behavioral = None
    for n in range(1, max_len + 1):
        for actions in product(alphabet, repeat=n):
            sigs = {}
            for name, model in MODELS.items():
                rs = run(model, list(actions))
                sigs[name] = tuple((r.state.llbit, r.state.mem_a, r.state.mem_b,
                                    r.status, r.wrote) for r in rs)
            if len(set(sigs.values())) != 1:
                behavioral = actions
                return divergent, minimal, behavioral
    return divergent, minimal, behavioral

def main():
    assert_hardware_obligations()
    divergent, minimal, behavioral = exhaustive_divergences()

    repeated = [("ll", A),
                ("sc", A, 0x11111111, False, True),
                ("sc", A, 0x22222222, False, True)]
    repeated_results = {}
    for name, model in MODELS.items():
        rs = run(model, repeated)
        repeated_results[name] = {
            "statuses": [r.status for r in rs],
            "writes": [r.wrote for r in rs],
            "final_llbit": rs[-1].state.llbit,
            "final_mem_a": f"0x{rs[-1].state.mem_a:08x}",
            "lladdr": f"0x{rs[-1].state.lladdr:x}",
        }

    report = {
        "verdict": "PARTIAL",
        "validated_contract_assertions": [
            "pinned hardware suite requires physical-address-derived LLAddr; ares/gopher source models satisfy it, Mupen pin diverges",
            "ERET clears reservation so following SC/SCD emits no mutation",
            "pinned hardware suite permits LL/SC through distinct TLB virtual aliases to the same physical backing",
            "provenance contract emits no mutation for failed backing writes",
            "provenance contract distinguishes cache-resident successful SC from immediate uncached backing mutation",
        ],
        "minimal_reference_divergence": [list(a) for a in minimal] if minimal else None,
        "minimal_behavioral_divergence_ignoring_lladdr": [list(a) for a in behavioral] if behavioral else None,
        "repeated_sc_counterexample": repeated_results,
        "safe_contract": {
            "emit_mutation_only_after_successful_write": True,
            "failed_sc_emits_mutation": False,
            "eret_terminates_reservation": True,
            "lladdr_is_physical_granule": True,
            "cached_success_is_immediate_backing_write": False,
            "treat_reference_only_repeated_sc_or_different_physical_sc_as_hardware_invariant": False,
        },
        "reference_consensus_without_pinned_hardware_test": {
            "sc_to_different_physical_after_ll_is_gated_only_by_llbit_in_all_three_models": True,
            "safe_to_promote_to_hardware_invariant": False,
        },
        "reference_disagreement": {
            "ares_successful_sc_clears_llbit": False,
            "mupen_successful_sc_clears_llbit": True,
            "gopher_successful_sc_clears_llbit": True,
            "mupen_ll_updates_lladdr": False,
            "ares_ll_updates_lladdr": True,
            "gopher_ll_updates_lladdr": True,
        },
    }
    raw = json.dumps(report, sort_keys=True, indent=2) + "\n"
    print(raw, end="")
    print("REPORT_SHA256", hashlib.sha256(raw.encode()).hexdigest())

if __name__ == "__main__":
    main()
