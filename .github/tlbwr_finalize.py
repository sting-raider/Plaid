from __future__ import annotations

import os
from pathlib import Path

DECISIONS = Path("docs/DECISIONS.md")
STATUS = Path("docs/STATUS.md")
NEXT = Path("docs/NEXT.md")
RECEIPT = Path(
    "research/integration-receipts/"
    "20261011-tlbwr-generation-gpt56sol-direct-tlbwr-generation-20261011.md"
)


def append_once(path: Path, marker: str, text: str) -> None:
    current = path.read_text()
    if marker in current:
        raise SystemExit(f"refusing duplicate canonical text in {path}: {marker}")
    path.write_text(current.rstrip() + "\n\n" + text.strip() + "\n")


run_id = os.environ.get("GITHUB_RUN_ID", "UNKNOWN")
validated_sha = os.environ.get("GITHUB_SHA", "UNKNOWN")

append_once(
    DECISIONS,
    "## ADR-0104: TLBWR operation generations require observed random-selection identity",
    """
## ADR-0104: TLBWR operation generations require observed random-selection identity

Status: Accepted for bounded compiler-time observed-history replay, 2026-10-11.

Adopt a strict source-bound TLBWR begin/select/write/end replay separate from the
TLBWI protocol. Replacement-slot identity comes only from the observed random
selection boundary for that decoded TLBWR operation. CP0 Index and Wired are
retained as context and cannot select the written slot. A successful in-range
selected-slot write mints a fresh ordered operation generation even when the
before/after entry fingerprints are identical. Equal payload in another slot,
snapshot inequality, later translation behavior or CP0 Index cannot recover that
identity. A captured out-of-range selection or exception without a successful
write retains a no-write attempt but mints no mapping-operation generation.

Require exact selection/write slot agreement, contiguous source ordinals,
consistent instruction context/epoch/PC, the decoded TLBWR word, normalized
fingerprints and strict schema. Missing selection on a successful operation,
in-range success without a write, writes without selection, duplicate or
reordered boundaries, selected/write slot substitution, faulting writes and
malformed source all fail closed. Bind the complete supplied source to an
externally trusted SHA-256 and reconstruct the full report during verification.

The exact pinned ares source at
`9408cb43d4948fc3ea6e152a307a34348df3fe04` was reproduced with result SHA-256
`405def4f3c1e33c9cd0a8dd331ee1d33d0e664d1c578692989623796d986c11c`.
That evidence establishes the bounded source contract and the same-value/Index
decoy counterexamples; it does not elevate ares random-selection policy or
Wired edge behavior to hardware truth. Hardware random distribution, complete
TLB operation sensing/census, mapping semantics, PageMask/ASID/global state,
TLBP/TLBR/context chronology, backing/alias ancestry, cache residency,
save/restore/reset chronology, executable lifetime, whole-ROM closure and native
completeness remain OPEN. `plaid-tlbwi-history-v0` remains unchanged. No
reference implementation code or runtime dependency enters production and no
solver/native-complete gate is weakened.
""",
)

append_once(
    STATUS,
    "Production now exposes separate bounded source-bound `tlbwr_history` replay",
    """
- Production now exposes separate bounded source-bound `tlbwr_history` replay
  for decoded TLBWR selected-slot operation generations (ADR-0104). An observed
  random-selection boundary, not CP0 Index, snapshot diff or equal mapping
  payload, names the replacement slot. Exact selected-slot writes mint fresh
  generations even for same-content rewrites; captured out-of-range selections
  and exception/no-write attempts mint none. Complete-source SHA binding, exact
  report reconstruction and adversarial Rust regressions reject missing,
  fabricated, duplicated, reordered and mismatched selection/write boundaries.
  Exact pinned ares reproduction preserves result SHA-256
  `405def4f3c1e33c9cd0a8dd331ee1d33d0e664d1c578692989623796d986c11c`.
  Hardware random distribution, complete TLB census, mapping semantics,
  PageMask/ASID/global/context chronology, cache residency, save/restore/reset,
  executable lifetime and whole-ROM/native completeness remain OPEN.
""",
)

append_once(
    NEXT,
    "Production now also has separate source-bound TLBWR selected-slot operation replay",
    """
Production now also has separate source-bound TLBWR selected-slot operation replay
(ADR-0104). Compose TLBWI and TLBWR occurrence generations with authenticated
mapping content, legal PageMask/ASID/global state, context writers, actual
fills/residents and save/restore/reset chronology before using either in
translation or executable-lifetime certificates. TLBWR replacement identity must
come from the observed selection/write boundary; CP0 Index, equal payloads and
snapshot diffs are not substitutes. Hardware random distribution and the complete
TLB mutation/operation census remain OPEN.
""",
)

if RECEIPT.exists():
    raise SystemExit(f"refusing to overwrite existing receipt: {RECEIPT}")
RECEIPT.parent.mkdir(parents=True, exist_ok=True)
RECEIPT.write_text(
    f"""# TLBWR selected-slot operation generation integration receipt

Date: 2026-10-11
Worker: `gpt56sol-direct-tlbwr-generation-20261011`
Cluster: source-bound TLBWR random-selected mapping-operation generations
Initial base: `bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5`
Final validated canonical parent: `24689113469e0a3325601d7b6fd41b4d06ecf761`
Validated integration head before documentation: `{validated_sha}`
Final validation Actions run: `{run_id}`

## Source research

- `research/tlbwr-mapping-generation-gpt56sol` at
  `62f722a0c4db72963f6c873ddd33b8df95ddbc7e`
- `research/ares-tlbwr-mapping-generations.md`
- `spikes/044-ares-tlbwr-mapping-generation`
- research exact-pin Actions `37917241697` and `37917473981`
- issue #4 research closeout `6079063268`
- neighboring production ADR-0102 / `plaid-tlbwi-history-v0`, reviewed but
  deliberately not widened

The research branch is behavioral evidence, not production authority. Its Python
model, ares instrumentation/build path and workflow are not production dependencies.

## Reproduced evidence

Before adopting production code, Actions `38153324068` / job `114511093924`
materialized the exact research fixture from `62f722a`, checked its Git blob IDs,
fetched exact pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`,
passed the source guard and 10,000-history adversarial model, executed the real
TLBWR matrix and required `results.json` SHA-256
`405def4f3c1e33c9cd0a8dd331ee1d33d0e664d1c578692989623796d986c11c`.
After the only initial validation failure, a rustfmt-only correction, Actions
`38153779095` repeated the exact-pin reproduction successfully. The production PR
Rust gate `38153782154` then passed the exact decoder pin, formatting, strict
locked Clippy, full locked workspace tests, retained synthetic contracts and the
independent fetch-summary oracle. Focused TLB plus exact-reference run
`38153927826` also passed. The final validation run recorded above re-ran the
current canonical Rust gate, focused TLB regressions, all retained synthetic and
oracle checks, and the exact pinned ares reproduction after reconciliation onto
canonical `24689113469e0a3325601d7b6fd41b4d06ecf761`.

The decisive reproduced counterexamples are:

- a real same-value TLBWR can perform the operation while the complete before/after
  TLB snapshot has zero changed entries;
- CP0 Index can remain on an equal-payload decoy while the actual random-selected
  replacement slot is different;
- therefore operation occurrence and selected-slot identity cannot be reconstructed
  from final state, snapshot inequality, numeric Index or equal mapping payloads.

## Adopted invariant

Production uses a separate `plaid-tlbwr-history-v0` compiler-time source protocol
with explicit begin, observed selection, actual write and end boundaries. A
successful write is accepted only when its slot exactly equals the observed
selection and that selection is in the modeled TLB-entry range. Every accepted
write mints a new operation generation, including equal before/after content.
CP0 Index and Wired remain context only. Out-of-range selections and exception
attempts with no successful write are retained without inventing generations.
Complete-source SHA binding and full report rederivation are mandatory.

UNKNOWN remains UNKNOWN. The replay never infers a selected slot from CP0 Index,
snapshot diffs, equal values, later mappings or finite trace closure.

## Rejected or superseded approaches

- No mechanical merge of `research/tlbwr-mapping-generation-gpt56sol`.
- Do not generalize ADR-0102's TLBWI `selected_slot == CP0 Index` rule to TLBWR.
- Do not use before/after inequality to decide whether TLBWR occurred.
- Do not use equal entry payloads or later translations to select a replacement slot.
- Do not treat the pinned ares random sequence/distribution as hardware truth.
- Later duplicate TLBWR direct-integration claims on issue #4 were released after
  discovering the earlier live claim for this worker; no duplicate patch was used.
- Temporary branch-only reproduction/finalization workflows are deleted before
  landing and are not production dependencies.

## Production files

- `crates/plaid-core/src/tlbwr_history.rs`
- `crates/plaid-core/src/lib.rs`
- `crates/plaid-core/tests/tlbwr_history.rs`
- `docs/STATUS.md`
- `docs/NEXT.md`
- `docs/DECISIONS.md` (ADR-0104)
- this receipt

## Tests and adversarial coverage

The final validation run recorded above executes:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`
- focused `tlb_history` and `tlbwr_history` tests
- every synthetic/oracle check retained by canonical `.github/workflows/rust.yml`
- exact pinned ares TLBWR source guard, 10,000-history adversarial model and real
  reference matrix with the expected result digest

The Rust regressions cover misleading CP0 Index, equal-value repeated writes,
identical payload in distinct selected slots, out-of-range/no-write attempts,
exception attempts, missing selection, write-without-selection, selected/write
slot substitution, duplicate selection, faulting writes, reordered ordinals and
epochs, wrong opcode, malformed fields/fingerprints/schema, complete-source
deletion, report deletion and forged closure/random-distribution flags. Existing
TLBWI tests remain a focused neighbor regression and its format/API is unchanged.

The first PR Rust run `38153582675` intentionally failed closed at formatting;
Clippy/tests were skipped and were not counted as passing. A rustfmt-only fix was
followed by fully green validation.

## Limitations and remaining proof obligations

This integration does **not** prove hardware random distribution or Wired edge
semantics, sensor completeness, a whole-machine TLB operation census, semantic
mapping validity, PageMask geometry, ASID/global behavior, TLBP/TLBR or EntryHi
writer chronology, alias/backing ancestry, D/I-cache residency or stale state,
save/restore/reset/NMI chronology, executable lifetimes, exception/root coverage,
indirect-target closure, RSP executable identity, whole-ROM closure or native
completeness. It does not clear solver blockers or enable a native-complete claim.

`progress.json` is unchanged because no whole-project milestone closed.
"""
)
