# Bounded CPU-copy provenance replay

Base Plaid commit: `3cf45dc323cbcd9e6463ccc781d3de093a433097`.
Pinned Mupen64Plus Core: `ba95bab92a76744753bfe61470823a4937850ab0`.

## Hypothesis

A store's destination/value plus a preceding equal-valued load cannot establish
CPU-copy provenance. A useful bounded certificate additionally needs the exact
executing compilation unit and a successful source load witness, then must
recheck an unmodified guest-register path rather than correlate values.

This experiment intentionally proves only the smallest useful pattern:

`LW/LWU rt, ...` immediately followed by `SW rt, ...` in the same captured
compilation unit, with matching dynamic load/store values and exact unit/site
identity. Everything broader stays unresolved.

## Run

```text
/usr/bin/python3 experiments/cpu-copy-provenance/provenance_harness.py
```

Tested with Python 3.13.5. Harness SHA-256:
`21947d6134f6b1a46028e572a1942ff6f2426181b61b8b795b1ac33960d18ac0`.

Expected output:

```text
PASS canonical_witnesses=64
PASS lwu_direct_copy_accepted
PASS equal_value_decoy_rejected
PASS missing_source_unit_rejected
PASS same_pc_generation_ambiguity_rejected
PASS changed_source_register_rejected
PASS intervening_clobber_rejected
PASS delay_slot_boundary_rejected
PASS cartridge_address_not_rom_origin
PASS transformed_value_rejected
```

The canonical case uses the exact 16-word `cpu_copy` bootstrap loop in
`scripts/test_mupen_session.py`; it simulates all 64 word transfers and repeats
values every eight words so value uniqueness cannot help the proof.

## Counterexamples

- An equal-value load from another source immediately before the store causes a
  value-only join to select the wrong source.
- The current store event has no source-unit ID. The same guest PC can therefore
  refer to different compiled bytes/generations; a later unit whose SW reads a
  different GPR defeats PC-only decoding.
- An intervening GPR clobber can produce the same final bits without preserving
  their byte origin.
- A branch with SW in its delay slot is rejected rather than silently crossing a
  control-transfer boundary.
- A cartridge-space address is not a ROM-origin witness. At the pinned Mupen
  revision, `read_cart_rom` can return the PI `last_write` latch while IO is busy
  or zero when the masked ROM offset is out of bounds. The replay preserves these
  source outcomes and refuses to upgrade them to `rom_bytes`.
- A transformed value is rejected even when equality with an earlier load happens
  to hold.

## Scope

This is a project-owned replay/verifier experiment, not modified-reference
instrumentation. It proves counterexamples and the sufficiency of the declared
synthetic event contract for this tiny pattern. It does **not** prove that a new
Mupen load hook is neutral or complete, does not cover interrupts/exceptions,
TLB paths, other widths, unaligned accesses, longer copy loops, aliases, or byte
origin behind an address. See `research/cpu-copy-provenance.md` for the proposed
sensor boundary and remaining obligations.
