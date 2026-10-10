# Load copy-event primitive-kind exclusivity

## Result

VALIDATED on canonical base `211176e7a489fecf8331d02915ee982cd279cb62`.

A `LoadMapping.copy_event` is not merely arbitrary Trace provenance. `merge::import_trace` constructs it from the session-qualified sequence identity of one concrete `TraceEvent::RomDmaObserved`. Current-main validation proved that the named Trace evidence exists and that some covering `ObservedDma` contains it, but did not prevent the same event identity from also being direct evidence for a mutually exclusive raw trace-event variant.

That omission lets a hand-edited or independently merged ProgramMap make one raw sequence number causally occur as both a ROM DMA and a CPU store, raw indirect observation, or entry-bytes verification. The impossible combined history validated on current main.

## Baseline reproduction

Regression: `crates/plaid-core/tests/copy_event_kind_exclusivity.rs`.

Baseline Actions run `38046249129`, job `114196275508`, on branch code before the candidate fix. Exact pinned Rabbitizer `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8` compiled.

Six focused cases ran. Two controls passed, while four desired-failing assertions demonstrated acceptance by current main:

- one DMA copy event reused as direct `ObservedWordStore` evidence;
- the same event reused as direct raw `ObservedIndirect` evidence;
- the same event reused as direct `ObservedEntryVerification` evidence;
- two maps that validate independently, one carrying the DMA/load and the other carrying the CPU-store observation under the same evidence identity, merge successfully instead of rejecting the cross-kind collision.

The store adversary writes the copied executable guest destination itself. Address plausibility therefore does not establish event identity. No payload or before/after equality is used by either the attack or the fix.

Controls show that:

- a distinct Trace event ID may legitimately identify a distinct CPU-store observation;
- the DMA copy event may remain attached to the derived `ObservedDma`, Region and Load facts that actually descend from that copy.

The merge regression also checks both merge orders after the candidate fix.

## Importer semantics

`merge::import_trace` creates one evidence ID per raw trace record:

`trace:{session}:{event.seq}`

A `RomDmaObserved` record inserts an `ObservedDma` carrying that ID. When a later compiled unit is source-matched to that transfer, `record_load` receives the same ID as `LoadObservation.copy_event`, and the resulting `LoadMapping.copy_event` names that concrete transfer event.

Other raw variants receive their own sequence IDs. In particular, `CpuWordStoreObserved`, indirect observations, and `EntryBytesVerified` cannot be the same raw record as `RomDmaObserved`. Their directly retained observation evidence therefore must not borrow an ID that is simultaneously used as a load's concrete DMA copy-event identity.

This is intentionally narrower than global EvidenceRef uniqueness. Provenance is routinely propagated into derived facts and canonical merge unions corroborating refs. The invariant applies only to IDs explicitly elevated into the causal `LoadMapping.copy_event` role and only forbids their reuse as direct evidence for incompatible primitive observation classes.

## Candidate fix

Production candidate commit: `b882ce7d44d8fcf2577076acbf9efdaba6ad34c3` (`fix: reject cross-kind load copy events`).

The validator now iterates IDs used as `LoadMapping.copy_event` and rejects a map when such an ID is also contained in direct evidence for any `ObservedWordStore`, `ObservedIndirect`, or `ObservedEntryVerification`.

Error:

`load copy event reused by incompatible primitive trace observation`

The production change is 22 added lines in `crates/plaid-core/src/program.rs`. A deterministic source transform lives at `spikes/copy-event-kind-exclusivity/apply_candidate_fix.py`.

This patch deliberately does not parse the human-readable `Evidence.detail`, infer event type from values, or impose uniqueness on arbitrary evidence references. It also does not attempt to solve exact `ObservedEntryVerification.source_unit` binding, which has separate research and stronger same-image/same-generation ambiguity.

## Falsification and validation

Candidate Actions run `38046426482`, job `114196783374`:

- focused regression: 6 passed / 0 failed;
- complete `plaid-core` test suite: 109 passed / 0 failed;
- `cargo fmt --all -- --check`: passed;
- `cargo clippy --locked -p plaid-core --all-targets -- -D warnings`: passed;
- candidate production change committed by the workflow as `b882ce7d44d8fcf2577076acbf9efdaba6ad34c3`.

An earlier candidate run `38046366681` already had focused and full-suite success but stopped at `cargo fmt --check` because the new regression file itself needed rustfmt line wrapping. No production semantic failure occurred in that run; the formatting-only test-file correction is commit `5590c27b887e1d4db6e3539eaae5b296a2804872`.

Base-to-candidate comparison is 6 commits ahead / 0 behind. Before this note, branch differences were limited to the 22-line validator guard, focused regression, deterministic patcher and branch-only workflow.

## Composition with prior research

This composes rather than duplicates `research/dma-event-uniqueness-gpt56sol`. That work established that a used copy-event ID must denote one DMA tuple `(rom_offset, physical_destination, size)` and explicitly left non-copy reuse of the same trace evidence ID unresolved. The present attack keeps the DMA identity itself singular and instead reuses it as another raw event kind.

It also composes:

- ADR-0009 deletion/fabrication resistance: rearranged or fabricated evidence must not strengthen a certificate;
- ADR-0010 actual-copy provenance: executable load provenance names the operation that actually copied the bytes;
- ADR-0018 copy identity is distinct from compilation/snapshot identity;
- ADR-0023 canonical provenance union: merging corroborating facts must not manufacture impossible causal histories.

No value equality is promoted to provenance.

## Closed-world impact

Before the candidate fix, independently plausible facts could compose into a history in which one trace sequence number was simultaneously a ROM DMA and a different primitive CPU/execution observation. Because a `LoadMapping.copy_event` is later used as executable-source provenance, this permits causal identity to be forged without breaking any local covering-DMA check.

After the fix, an ID elevated into the load copy-event role remains exclusive against the three incompatible direct primitive observation classes tested here. Merge cannot launder the collision, and merge order does not change the verdict.

This removes one internal fabrication path. It does not establish WholeRom closure by itself.

## Remaining gaps

- Trace authenticity and completeness are still separate obligations.
- The patch is scoped to the three retained primitive observation classes attacked here; it is not a general typed-event schema.
- EvidenceRefs still overload corroborating provenance and primitive event identity. A future schema should preferably represent raw event identity/type explicitly rather than recover role semantics from set membership.
- Exact entry-verification `source_unit` binding is a distinct problem and cannot be solved from equal bytes/address/generation.
- CPU/RSP transform provenance, unobserved writers, overlays/lifetimes, cache/TLB visibility, exception roots and whole-ROM mutation accounting remain independent blockers.
- This result makes no N64 hardware semantic claim. It validates an internal Plaid trace/import/ProgramMap consistency invariant.

## Integration recommendation

ADOPT the 22-line fail-closed validator guard and focused regression. It matches the importer-generated event identity contract, preserves legitimate derived propagation and distinct raw event IDs, rejects merge laundering in both orders, and requires no value-based inference.

Longer term, replace the implicit convention with an explicit typed raw-event identity carried by primitive observations and causal references. Until then, a `LoadMapping.copy_event` must not be permitted to masquerade as another primitive trace event.

## Reproduction

```sh
cargo test --locked -p plaid-core --test copy_event_kind_exclusivity -- --nocapture
cargo test --locked -p plaid-core
cargo fmt --all -- --check
cargo clippy --locked -p plaid-core --all-targets -- -D warnings
```
