#!/usr/bin/env python3
"""Deterministic causal reducer for SP/RSP -> MI -> CPU interrupt-root provenance.

This is not an N64 emulator.  It encodes only the source-backed state transitions
needed to attack provenance shortcuts.  Operation generations advance even when a
write leaves the visible value unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Optional

EXPECTED_SHA256 = "c9c3afdc46c2e2ae0a11107b9590c8cad2896f56cebf719c29dbfcd40fb85dcc"


@dataclass(frozen=True)
class RootReceipt:
    root_gen: int
    contributors: tuple[str, ...]
    sp_assert_gen: Optional[int]
    sp_assert_source: Optional[str]
    sp_mask_gen: Optional[int]
    cpu_gate_gen: int


@dataclass
class Machine:
    seq: int = 0
    iob: bool = False
    iob_gen: int = 0
    halted: bool = False
    broken: bool = False
    sp_line: bool = False
    sp_assert_gen: Optional[int] = None
    sp_assert_source: Optional[str] = None
    sp_mask: bool = False
    sp_mask_gen: int = 0
    pi_line: bool = False
    pi_assert_gen: Optional[int] = None
    pi_mask: bool = False
    pi_mask_gen: int = 0
    ie: bool = False
    im_rcp: bool = False
    exl: bool = False
    erl: bool = False
    cpu_gate_gen: int = 0
    roots: list[RootReceipt] = field(default_factory=list)

    def tick(self) -> int:
        self.seq += 1
        return self.seq

    def set_iob(self, value: bool) -> int:
        gen = self.tick()
        self.iob = value
        self.iob_gen = gen
        return gen

    def _raise_sp(self, source: str) -> None:
        # A repeated raise is a new producer operation even when MI.SP is already 1.
        self.sp_line = True
        self.sp_assert_gen = self.seq
        self.sp_assert_source = source

    def sp_status_intr_command(self, *, clear: bool = False, set_: bool = False) -> int:
        gen = self.tick()
        # Exact pinned references and n64-systemtest agree that both bits => no change.
        if clear and not set_:
            self.sp_line = False
            self.sp_assert_gen = None
            self.sp_assert_source = None
        elif set_ and not clear:
            self._raise_sp(f"sp_status:{gen}")
        return gen

    def rsp_break(self) -> int:
        gen = self.tick()
        self.halted = True
        self.broken = True
        if self.iob:
            self._raise_sp(f"break:{gen}")
        return gen

    def set_sp_mask(self, value: bool) -> int:
        gen = self.tick()
        self.sp_mask = value
        self.sp_mask_gen = gen
        return gen

    def set_pi_line(self, value: bool) -> int:
        gen = self.tick()
        self.pi_line = value
        self.pi_assert_gen = gen if value else None
        return gen

    def set_pi_mask(self, value: bool) -> int:
        gen = self.tick()
        self.pi_mask = value
        self.pi_mask_gen = gen
        return gen

    def set_cpu_gate(
        self,
        *,
        ie: Optional[bool] = None,
        im_rcp: Optional[bool] = None,
        exl: Optional[bool] = None,
        erl: Optional[bool] = None,
    ) -> int:
        gen = self.tick()
        if ie is not None:
            self.ie = ie
        if im_rcp is not None:
            self.im_rcp = im_rcp
        if exl is not None:
            self.exl = exl
        if erl is not None:
            self.erl = erl
        self.cpu_gate_gen = gen
        return gen

    def contributors(self) -> tuple[str, ...]:
        contributors: list[str] = []
        if self.sp_line and self.sp_mask:
            contributors.append("sp")
        if self.pi_line and self.pi_mask:
            contributors.append("pi")
        return tuple(contributors)

    def cpu_gate(self) -> bool:
        return self.ie and self.im_rcp and not self.exl and not self.erl

    def cpu_boundary(self) -> Optional[RootReceipt]:
        root_gen = self.tick()
        contributors = self.contributors()
        if not contributors or not self.cpu_gate():
            return None
        receipt = RootReceipt(
            root_gen=root_gen,
            contributors=contributors,
            sp_assert_gen=self.sp_assert_gen if "sp" in contributors else None,
            sp_assert_source=self.sp_assert_source if "sp" in contributors else None,
            sp_mask_gen=self.sp_mask_gen if "sp" in contributors else None,
            cpu_gate_gen=self.cpu_gate_gen,
        )
        self.roots.append(receipt)
        return receipt

    def naive_sp_claim(self) -> bool:
        """Deliberately unsound shortcut under test."""
        return self.halted and self.broken and bool(self.contributors()) and self.cpu_gate()


def run_cases() -> dict[str, object]:
    out: dict[str, object] = {}

    m = Machine()
    m.set_sp_mask(True)
    m.set_cpu_gate(ie=True, im_rcp=True)
    m.rsp_break()
    receipt = m.cpu_boundary()
    out["break_iob_off"] = {
        "strict_sp_root": bool(receipt and "sp" in receipt.contributors),
        "naive": m.naive_sp_claim(),
    }

    m = Machine()
    m.set_sp_mask(True)
    m.set_cpu_gate(ie=True, im_rcp=True)
    raise_gen = m.sp_status_intr_command(set_=True)
    receipt = m.cpu_boundary()
    out["status_raise_without_break"] = {
        "strict_sp_root": bool(receipt and "sp" in receipt.contributors),
        "naive": m.naive_sp_claim(),
        "sp_gen": receipt.sp_assert_gen if receipt else None,
        "expected_gen": raise_gen,
    }

    m = Machine()
    m.set_cpu_gate(ie=True, im_rcp=True)
    m.set_iob(True)
    break_gen = m.rsp_break()
    before = m.cpu_boundary()
    mask_gen = m.set_sp_mask(True)
    after = m.cpu_boundary()
    out["masked_then_unmask"] = {
        "before": before is not None,
        "after_sp": bool(after and "sp" in after.contributors),
        "sp_gen": after.sp_assert_gen if after else None,
        "break_gen": break_gen,
        "mask_gen": after.sp_mask_gen if after else None,
        "expected_mask_gen": mask_gen,
    }

    m = Machine()
    m.set_iob(True)
    m.set_sp_mask(True)
    m.rsp_break()
    m.sp_status_intr_command(clear=True)
    m.set_pi_mask(True)
    m.set_pi_line(True)
    m.set_cpu_gate(ie=True, im_rcp=True)
    receipt = m.cpu_boundary()
    out["clear_then_pi_decoy"] = {
        "contributors": list(receipt.contributors) if receipt else [],
        "strict_sp_root": bool(receipt and "sp" in receipt.contributors),
        "naive": m.naive_sp_claim(),
    }

    m = Machine()
    m.set_sp_mask(True)
    m.set_cpu_gate(ie=True, im_rcp=True)
    first = m.sp_status_intr_command(set_=True)
    second = m.sp_status_intr_command(set_=True)
    receipt = m.cpu_boundary()
    out["same_value_raise_generation"] = {
        "first": first,
        "second": second,
        "receipt": receipt.sp_assert_gen if receipt else None,
        "distinct": bool(first != second and receipt and receipt.sp_assert_gen == second),
    }

    m = Machine()
    m.set_sp_mask(True)
    m.set_cpu_gate(ie=True, im_rcp=True)
    first = m.sp_status_intr_command(set_=True)
    m.sp_status_intr_command(clear=True, set_=True)
    receipt = m.cpu_boundary()
    out["set_clear_pair_noop_high"] = {
        "sp_gen": receipt.sp_assert_gen if receipt else None,
        "unchanged": bool(receipt and receipt.sp_assert_gen == first),
    }

    m = Machine()
    m.set_sp_mask(True)
    m.set_cpu_gate(ie=True, im_rcp=True)
    m.sp_status_intr_command(clear=True, set_=True)
    out["set_clear_pair_noop_low"] = {"root": m.cpu_boundary() is not None}

    m = Machine()
    m.set_sp_mask(True)
    m.sp_status_intr_command(set_=True)
    m.set_cpu_gate(ie=True, im_rcp=True, exl=True)
    blocked = m.cpu_boundary()
    m.set_cpu_gate(exl=False)
    after = m.cpu_boundary()
    out["cpu_exl_gate"] = {
        "blocked": blocked is None,
        "after_clear_sp": bool(after and "sp" in after.contributors),
    }

    m = Machine()
    m.set_iob(True)
    m.rsp_break()
    m.set_pi_mask(True)
    m.set_pi_line(True)
    m.set_cpu_gate(ie=True, im_rcp=True)
    receipt = m.cpu_boundary()
    out["sp_masked_pi_pending"] = {
        "contributors": list(receipt.contributors) if receipt else [],
        "strict_sp_root": bool(receipt and "sp" in receipt.contributors),
        "naive": m.naive_sp_claim(),
    }

    m = Machine()
    m.sp_status_intr_command(set_=True)
    first_mask = m.set_sp_mask(True)
    second_mask = m.set_sp_mask(True)
    m.set_cpu_gate(ie=True, im_rcp=True)
    receipt = m.cpu_boundary()
    out["same_value_mask_generation"] = {
        "first": first_mask,
        "second": second_mask,
        "receipt": receipt.sp_mask_gen if receipt else None,
        "distinct": bool(receipt and first_mask != second_mask and receipt.sp_mask_gen == second_mask),
    }

    m = Machine()
    m.set_sp_mask(True)
    m.sp_status_intr_command(set_=True)
    m.set_cpu_gate(ie=True, im_rcp=True, erl=True)
    out["cpu_erl_gate"] = {"blocked": m.cpu_boundary() is None}

    # Falsification assertions.  These are deliberately about causality, not payload equality.
    assert out["break_iob_off"]["strict_sp_root"] is False
    assert out["status_raise_without_break"]["strict_sp_root"] is True
    assert out["masked_then_unmask"]["before"] is False
    assert out["masked_then_unmask"]["after_sp"] is True
    assert out["clear_then_pi_decoy"]["strict_sp_root"] is False
    assert out["clear_then_pi_decoy"]["naive"] is True
    assert out["same_value_raise_generation"]["distinct"] is True
    assert out["set_clear_pair_noop_high"]["unchanged"] is True
    assert out["set_clear_pair_noop_low"]["root"] is False
    assert out["cpu_exl_gate"]["blocked"] is True
    assert out["sp_masked_pi_pending"]["strict_sp_root"] is False
    assert out["sp_masked_pi_pending"]["naive"] is True
    assert out["same_value_mask_generation"]["distinct"] is True
    assert out["cpu_erl_gate"]["blocked"] is True
    return out


def main() -> None:
    cases = run_cases()
    canonical = json.dumps(cases, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(canonical).hexdigest()
    if digest != EXPECTED_SHA256:
        raise SystemExit(f"unexpected replay digest: {digest}")
    print(json.dumps(cases, indent=2, sort_keys=True))
    print(f"sha256={digest}")


if __name__ == "__main__":
    main()
