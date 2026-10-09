# ares COP1 load-to-store byte lineage

Status: **VALIDATED** for the bounded pinned-ares interpreter scope below.

Worker: `gpt56sol-cop1-load-store-lineage-20261009`.

Plaid base: `main` at `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`.

Research branch: `research/cop1-load-store-lineage-gpt56sol`.

Pinned ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

Pinned Mupen64Plus comparison: `ba95bab92a76744753bfe61470823a4937850ab0`.

Pinned Gopher64 comparison: `e96debac941a26ba4961e5145056c0821d3a56f7`.

Experiment: `spikes/043-ares-cop1-load-store-lineage/`.

Validated Actions receipt: run `37916051023`, job `113772371785`, tested branch head `114bc1a3a4d556063ba5d60c69d1c6fd03a111d3`.

## Bounded question

Can a completed uncached identity-RDRAM `LWC1`/`LDC1` read be carried through the exact physical FPR lane(s) written by the instruction and later exported by `SWC1`/`SDC1`, without using matching payload values as provenance? In particular, do FR=0 pairing, FR=1 independent registers, FR flips, mixed 32/64-bit widths, same-value FPR overwrites, and load failures force lineage to be represented per byte rather than per FPR number or payload?

## Result

**VALIDATED.** For this decoded pinned-ares interpreter path, an ordered per-byte FPR generation model reproduced every observed successful load/store payload and rejected deliberately forged joins that a value matcher or register-number matcher would accept.

The important negative result is that equal payload values are not merely theoretically unsafe: this fixture produced **six concrete equal-value false matches**. It also produced **ten mixed-origin store payloads**, where some bytes selected by a store came from the observed RDRAM load and other bytes came from pre-existing FPR state. Therefore a single provenance token for an architectural FPR number, a whole 64-bit physical FPR, or a payload value is insufficient for this path.

A successful uncached load can mint byte origins only after the completed backing read is observed. Those origins enter the exact storage selected by ares `FT(u32/u64)` at load-time FR mode. A later store inherits only the byte generations selected by its own store-time FR mode. FR-mode changes do not themselves create ancestry; they can expose different physical lanes. Same-value `MTC1`/`DMTC1` writes replace the selected byte generations even when the numeric bits remain unchanged. CU1-disabled, alignment-faulting, and unmapped-TLB load attempts produced no completed RDRAM scalar read and changed no FPR bytes, so they minted no load origin.

## Exact pinned-ares behavior exercised

The source guard pins the exact `LWC1`, `LDC1`, `MTC1`, `DMTC1`, `SWC1`, `SDC1`, FR-sensitive `fgr_t`, and RDRAM scalar-read source shapes. The decoded fixture runs with both CPU and RSP recompilers disabled.

For the pinned ares implementation the exercised register selection is:

- FR=0 `LWC1` even `ft`: low 32-bit lane of the paired even physical FPR;
- FR=0 `LWC1` odd `ft`: high 32-bit lane of that paired even physical FPR;
- FR=0 `LDC1` even/odd: the same full paired-even physical FPR;
- FR=1 `LWC1`: low 32-bit lane of the named FPR;
- FR=1 `LDC1`: the full named FPR.

`SWC1`/`SDC1` use the corresponding store-time selection. The experiment deliberately changes FR between load and store, so this is not inferred from a static register number.

## Executed matrix

`run.py` built the existing Plaid headless oracle against exact ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, then ran **96 logical cases**:

- 64 `LWC1`/`LDC1` → `SWC1`/`SDC1` combinations across load FR=0/1, even/odd `ft`, independent store FR=0/1, and even/odd store `ft`;
- eight same-value intervening `MTC1`/`DMTC1` overwrite cases;
- 24 load failures covering CU1 disabled, misalignment, and unmapped TLB access.

Every logical case was executed once with the research callback disabled, then twice with it enabled. The two traced executions were byte-for-byte identical, and callback-disabled versus callback-enabled semantic state was identical. The callback records completed identity-RDRAM scalar effects only; it does not synthesize provenance from opcode names.

Validated output:

```text
PASS: exact pinned ares COP1/RDRAM source guards
source_pair_sha256=48c5aa9ee8fef943fccdb80bae000ace0e815ab1f51710a41694548e3044d17e
PASS: 67 COP1 lineage-model cases
model_sha256=5a771c25653c96a8f858bc35b41d2acd835dd6d5c65ac9e65f82d8ccd617cf69
PASS: 96 logical decoded pinned-ares COP1 lineage cases
false_value_matches=6 mixed_outputs=10 full_load_outputs=26
model_cases=67 model_sha256=5a771c25653c96a8f858bc35b41d2acd835dd6d5c65ac9e65f82d8ccd617cf69
results_sha256=f9c06faf9a98c48916d48f1b4409410b8dafca715074ff84585867850d6f0450
```

The initial workflow attempt failed before building ares because Python 3.12 `dataclasses` requires a dynamically loaded module to be installed in `sys.modules`. Commit `114bc1a3a4d556063ba5d60c69d1c6fd03a111d3` fixed only that harness-loader defect; the succeeding run above then compiled and executed the exact reference fixture.

## Adversarial cases that matter

The fixture seeds equal-valued decoys into different FPR lanes. For example, the source word is `0x10213243`, while an untouched lane in another FR interpretation already contains the same numeric word. A load can therefore observe `0x10213243`, an FR flip can redirect the later `SWC1` to an unrelated lane that also contains `0x10213243`, and a value-only join would falsely claim load ancestry. The byte-generation replay rejects the edge because none of the selected store bytes carry the load event's origin token.

Likewise, an intervening decoded `MTC1` or `DMTC1` writes exactly the same bits as the preceding load. The final store payload remains numerically identical to the load payload, but all selected origins become the move instruction's generation. This demonstrates why same-value writes cannot be dropped from causal history.

Mixed-width combinations provide a second failure mode for coarse provenance. A 32-bit load can replace only one half of storage later selected by a 64-bit store. Ten tested stores contained a mixture of loaded and pre-existing byte generations. Treating the entire physical FPR as one generation would over-attribute four untouched bytes.

## Independent reference comparison

Pinned Mupen64Plus source independently supports the same broad FR selection structure: with FR=0, its single-precision pointer table maps even/odd architectural registers to halves of a paired-even backing register while its double-precision table maps both to the paired-even register; with FR=1 both tables point at the named backing register. Its `LWC1` and `LDC1` handlers read directly into those FR-selected pointers. This is corroboration, not hardware proof.

Pinned Gopher64 also routes `LWC1`/`LDC1` through FR-sensitive single/double FPR helpers and blocks CU1-disabled accesses before memory translation. However, its own source explicitly says its FR transition helper **does not account for undocumented odd-numbered-register behavior in half mode**. That caveat matters: the exact FR=0 odd-register behavior validated here is an ares behavioral fact (and is source-consistent with pinned Mupen), not an N64-wide invariant established by emulator consensus.

## Reproduction

From the repository root with exact ares checked out at `.refs/ares`:

```bash
python3 -m py_compile \
  spikes/043-ares-cop1-load-store-lineage/lineage.py \
  spikes/043-ares-cop1-load-store-lineage/source_guard.py \
  spikes/043-ares-cop1-load-store-lineage/run.py
python3 spikes/043-ares-cop1-load-store-lineage/source_guard.py
python3 spikes/043-ares-cop1-load-store-lineage/lineage.py
python3 spikes/043-ares-cop1-load-store-lineage/run.py
```

The branch workflow `.github/workflows/research-cop1-load-store-lineage.yml` checks out the exact pinned ares revision and executes the same sequence.

## Integration consequence

A trustworthy COP1 provenance subsystem should represent FPR ancestry at byte granularity (or an exactly equivalent subregister interval representation) and replay every writer that can replace those bytes. A completed memory read event can become an FPR source generation only after the architectural load succeeds. Later store provenance must be selected from the actual store-time physical byte lanes, not inferred from `ft`, current payload value, or the last load mentioning that register number.

This result is suitable evidence for adopting those requirements into the executable-mutation/provenance model. It does **not** justify hard-coding ares-specific undocumented FR=0 odd-register behavior as hardware truth.

## Limitations / explicitly not proved

This experiment does not prove:

- FPR arithmetic, conversions, comparisons, conditional moves, or every other FPR writer's lineage;
- cached-load D-cache residency/fill/writeback provenance;
- successful translated/TLB-backed load provenance;
- reverse-endian semantics;
- physical N64 bus transaction atomicity;
- hardware truth for undocumented FR=0 odd-register behavior;
- DMA/RSP producer ancestry of the source RDRAM bytes;
- whole-ROM reachability or closed-world completeness.

It proves only the bounded decoded interpreter chain above and the necessity of exact subregister/byte generation tracking for sound causal attribution across that chain.
