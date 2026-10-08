# Bounded CPU-copy provenance

2026-10-08. Plaid base `3cf45dc323cbcd9e6463ccc781d3de093a433097`.
Reference: Mupen64Plus Core `ba95bab92a76744753bfe61470823a4937850ab0`.

## Verdict: PARTIAL

The current limited CPU-store observation is not sufficient to prove CPU-copy
provenance. A bounded adjacent `LW/LWU -> SW` certificate is mechanically sound
under a stronger synthetic event contract, and several tempting weaker joins have
concrete counterexamples. Actual reference load instrumentation and neutrality are
not implemented in this research branch, so this does not yet promote CPU-copy
loads into production ProgramMap provenance.

## Falsifiable hypothesis

A successful source load witness carrying exact execution identity and actual
backing origin, combined with the successful store observation and a rechecked
unmodified register path, is sufficient to prove a narrow word-copy witness.
Value equality, guest address equality, or guest PC alone are insufficient.

## Existing fixture and source map

The existing full-core `cpu_copy` scenario in `scripts/test_mupen_session.py`
executes this hand-authored loop from SP memory:

```text
LUI/ORI t0, B0001000
LUI/ORI t1, 80000400
ORI     t2, zero, 64
loop:
LW      t3, 0(t0)
SW      t3, 0(t1)
ADDIU   t0, t0, 4
ADDIU   t1, t1, 4
ADDIU   t2, t2, -1
BNE     t2, zero, loop
NOP
```

The existing reference regression already establishes deterministic full-core
execution and deliberately leaves this path with no PI DMA/load mapping and an
`unknown_executable_source` blocker.

At the pinned Mupen revision:

- `new_dynarec.c::load_assemble` emits ordinary `LW`/`LWU` memory reads and sends
  constant addresses outside the direct RAM fast path through `inline_readstub`.
  The CPU-copy source `B0001000` therefore requires a post-success device-read
  witness; address generation alone is not a completed read.
- `new_dynarec.c::store_assemble` statically knows the store source guest GPR as
  `rs2[i]`. Plaid's current x64 sensor invokes its callback only after the
  successful constant aligned cached-RDRAM `SW` path and invalidation return, but
  emits only `{site,destination,value}`. It does not embed the compilation unit
  that generated the callback.
- Existing indirect-target instrumentation already embeds `plaid_current_unit`
  into generated callbacks. CPU-copy evidence needs the same generation identity;
  a guest PC is not a unique instruction identity after invalidation/recompile.
- `cart_rom.c::read_cart_rom` has three materially different backing outcomes at
  the same cartridge device: while `PI_STATUS_IO_BUSY` it returns `last_write`;
  for an in-range masked ROM offset it reads the ROM buffer; beyond ROM it returns
  zero. Therefore `B000xxxx` or even `device=cart` is not a ROM-byte-origin proof.

No upstream code was copied into Plaid by this experiment; the pinned GPL source
was inspected as a behavioral/reference boundary.

## Executable experiment

`experiments/cpu-copy-provenance/provenance_harness.py` replays the exact 16-word
CPU-copy loop and a deliberately tiny verifier. It certifies only:

1. a dynamic successful `LW` or `LWU` witness for exact `(unit, site, dest_gpr)`;
2. an immediately following `SW` in the same captured unit whose source GPR is
   that `dest_gpr`;
3. the store event identifies the exact executing unit;
4. dynamic values match; and
5. the load witness carries its backing outcome without upgrading it from address
   class (for example `pi_latch` is not `rom_bytes`).

Run:

```text
/usr/bin/python3 experiments/cpu-copy-provenance/provenance_harness.py
```

Python: 3.13.5. Harness SHA-256:
`21947d6134f6b1a46028e572a1942ff6f2426181b61b8b795b1ac33960d18ac0`.

Observed output:

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

The 64 canonical words deliberately repeat values every eight iterations. The
certificate therefore cannot accidentally depend on data uniqueness.

## Counterexamples that reject weaker joins

### Equal-value source selection is unsound

An unrelated later load with the same value makes a naive "nearest equal value"
join choose the wrong source address. Provenance is causal identity, not a content
search.

### Store PC without source-unit identity is unsound

Two compilation units can cover the same guest PC while containing different
bytes. The adversarial later unit changes the `SW` source from `t3` to `t4`; a
PC-only verifier can attach a prior `t3` load to an instruction that never stored
`t3`. The strict verifier refuses stores with no unit identity and rejects the
changed-source unit when identity is supplied.

### Clobbers/transforms destroy this narrow certificate

`LW t3; ORI t3,zero,imm; SW t3` and `LW t3; ORI t3,t3,1; SW t3` demonstrate that
equal final bits do not preserve byte origin. General copy provenance needs a real
def-use/retirement proof; this experiment intentionally refuses those chains.

### Delay-slot/control-flow crossing stays open

`LW; BNE; SW-in-delay-slot` is rejected. The tiny certificate does not infer a
register lifetime across a control-transfer boundary, exception window, or unit
transition.

### Cartridge address does not prove ROM origin

Synthetic `pi_latch` and out-of-range-zero source outcomes at cartridge addresses
remain labelled as such through the copied store. They are not promoted to ROM
origins even when the destination/value pair is otherwise a valid direct copy.

## Minimum future dynamic evidence

For the narrow direct word-copy certificate, a future reference sensor should
produce a **successful load** event after the actual read completes with at least:

```text
sequence
source_unit
site
load_opcode / width / extension semantics
destination_gpr
backing_outcome
backing_identity (for example canonical ROM offset, or verified RDRAM transaction)
value
```

The backing fields must come from the completed device/backing transaction. A
virtual/physical address before dispatch is not enough. Unsupported outcomes must
remain explicit unknown/latch/zero/device categories rather than being coerced to
ROM/RAM provenance.

The existing successful store event needs at minimum `source_unit`. `source_gpr`
may be emitted directly or deterministically re-decoded from the exact captured
unit; relying on PC against whichever current unit happens to exist is forbidden.

A first production verifier should stay deliberately small: same exact unit,
adjacent `LW/LWU rt -> SW rt`, no branch/delay-slot boundary, exact event order,
matching value, and a verified backing origin. This is enough to cover the current
synthetic CPU-copy loop without pretending to solve general MIPS dataflow.

## Remaining gaps

- No post-success Mupen load sensor was implemented or executed here.
- Instrumented/uninstrumented neutrality for that future load hook is untested.
- General register last-writer tracking across ordinary instructions, joins,
  loops, interrupts, exceptions and delay slots remains open.
- Variable/TLB/uncached, unaligned, byte/half/doubleword and load-left/right paths
  remain outside the certificate.
- RDRAM loads require transaction/backing witnesses rather than address labels.
- Cartridge reads need actual `read_cart_rom` outcome identity; IO-busy latch and
  out-of-range zero behavior must remain distinguishable.
- Destination executable lifetime/generation construction still needs integration
  with executable-write/cache/fetch chronology.

## Recommendation: INVESTIGATE

Do not infer CPU-copy source by value matching or by `site` alone. The next useful
implementation slice is a neutral post-success word-load observer plus source-unit
identity on the existing SW event, initially gated to the adjacent `LW/LWU -> SW`
certificate above. Keep all longer dataflow chains unknown until retirement/
clobber/control-flow evidence exists.
