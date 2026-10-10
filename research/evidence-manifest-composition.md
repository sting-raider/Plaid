# Evidence manifest composition and complete-history deletion resistance

Result: **VALIDATED at the proof-model level**

Worker: `gpt56sol-evidence-manifest-composition-20261010`

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`

Research branch: `research/evidence-manifest-composition-gpt56sol`

## Question

What is the minimum commitment boundary that can make deletion of an entire primitive evidence family detectable after a trace/import result has been converted into a `ProgramMap` and later merged or hand edited?

This composes the explicit remaining gap from `research/solver-fetch-capture-count-laundering.md`: a surviving typed fact can force the solver OPEN, but if the entire capture and its evidence identity are removed there is no remaining in-map fact from which the solver can infer that an external source ever existed.

The target here is not a new sensor and not a claim of sensor completeness. It is a proof-boundary question: what expectation has to survive *outside the editable result* so that deleting the evidence itself cannot erase the obligation?

## Current Plaid contracts used

Current `trace.rs` gives discovery traces stronger source structure than a `ProgramMap` alone:

- event `seq` must be contiguous execution order starting at zero;
- the terminal record carries and validates an exact event count;
- trace events are typed, not human-readable prose.

Current `merge.rs::import` validates the trace, serializes the complete validated trace, hashes that full NDJSON, and uses the hash as the session component of every event evidence identity: `trace:{session}:{seq}`. It inserts a trace `Evidence` item for every event before projecting event-specific facts.

Current `merge_maps` deliberately unions semantic facts and provenance monotonically. Equivalent facts can acquire extra evidence references after merge, and derived diagnostics can be canonicalized. Therefore a hash of the entire mutable `ProgramMap` is the wrong semantic boundary for source completeness: legitimate merge changes it.

## Threat model

The experiment assumes:

1. an import source/session was accepted at some trusted pipeline boundary;
2. the resulting map can later be merged, normalized or maliciously edited;
3. an attacker may delete primitive facts, delete an entire source/session, change semantics, move equal values to fresh identities, and recompute any commitment stored only inside the edited map;
4. the attacker cannot rewrite the *externally expected source/session commitment set* supplied by the trusted build/certificate boundary.

This is intentionally narrower than authenticity of the emulator or hardware. A perfect manifest over an incomplete or lying sensor faithfully commits to incomplete or lying input.

## Model contract

`experiments/evidence-manifest-composition/model.py` defines one canonical primitive leaf as:

```text
(domain,
 session,
 source_digest,
 event_seq,
 event_kind,
 typed_semantic_tuple)
```

A session manifest contains:

```text
(session,
 source_digest,
 event_count,
 primitive_root)
```

`primitive_root` is SHA-256 over the canonical sequence-ordered primitive leaves. Sequence is inside each leaf, so row reordering does not change the commitment while chronology changes do.

Crucially, these are **not** leaf fields:

- derived `Region`/block/CFG facts;
- mutable evidence-reference unions;
- human-readable evidence detail;
- merge order.

A merged result retains the union of the original per-session manifests. It never creates a fresh global root over the merged map.

The strict verifier receives the expected per-session manifest set from outside the editable map, recomputes each session's primitive projection from retained primitive receipts, and requires exact session-set and root agreement.

## Deterministic adversarial matrix

The fixed two-session fixture covers ROM DMA, CPU word store, indirect transfer and entry verification primitives. It deliberately contains two equal-value word-store events at different causal identities.

The model proves all of the following:

- baseline strict verification passes;
- deleting one primitive and recomputing the local manifest passes a naive local verifier but fails the external expectation;
- deleting an entire session plus its local manifest passes the naive local verifier but fails the external expectation;
- replacing a deleted event with an equal-value event at a fresh identity fails;
- transplanting identical semantics into a different session fails;
- reusing one event identity with incompatible semantics fails;
- event-row reordering passes;
- adding or deleting derived facts does not change the primitive commitment;
- provenance-reference expansion does not change the primitive commitment;
- two independent sessions merge successfully in either order and produce the same canonical merged projection;
- forging a fresh local manifest after editing passes the local self-check but still fails the original external expectation.

Stable semantic result SHA-256, excluding timing:

`519772b1ad3bdaa555a30c49fd92b65c14e3be9b6aff5d2c5b58434467e13fec`

## Fuzzing

Deterministic seed: `0x504c414944`.

Corpus: 4,000 randomly generated multi-session histories, 2-4 sessions each, 2-12 events per session, with deliberate equal-value decoys.

For every case:

- naive local self-rehash falsely accepted the partial-deletion attack: **4,000 / 4,000**;
- strict external root rejected the same attack: **4,000 / 4,000**;
- naive local self-rehash falsely accepted whole-session deletion: **4,000 / 4,000**;
- strict external session/root expectation rejected whole-session deletion: **4,000 / 4,000**;
- strict verification rejected same-value fresh-event replacement: **4,000 / 4,000**;
- strict verification rejected cross-session transplant: **4,000 / 4,000**;
- strict verification accepted harmless row reordering: **4,000 / 4,000**;
- strict verification accepted derived/provenance expansion: **4,000 / 4,000**;
- strict verification accepted independently committed session merges in both merge orders: **4,000 / 4,000**.

This does not prove SHA-256 collision resistance or an implementation theorem. It does falsify the relevant weaker constructions under the modeled edit/merge semantics.

## Trust-field ablation

`experiments/evidence-manifest-composition/ablations.py` separates presence, count and semantic binding.

### Source/session identity only

An externally expected source/session set detects deletion of an entire session, but it **accepts partial event deletion** if at least one event from that session survives. Without re-reading the raw source, a source hash does not tell the verifier which projected events are absent.

### Source/session identity + expected count

Adding an externally expected event count detects deletion when the count changes, but it still **accepts same-count semantic substitution** and an equal-value replacement moved to a fresh event identity. Count proves cardinality, not causality or semantics.

### Externally expected primitive root

An external root whose leaves bind session/source identity, event identity, kind and typed semantics rejects partial deletion, whole-session deletion (through exact expected session-set matching), semantic mutation, same-value fresh-event replacement and cross-session substitution.

Under this model, `event_count` is therefore useful explicit metadata and a cheap structural check, but it is not cryptographically necessary once the external root commits to the full canonical leaf list. For current discovery traces, the session identifier is itself the SHA-256 of the complete NDJSON source, so a separately repeated `source_digest` is also redundant for integrity. Keeping both fields can still be useful for generic non-trace sources and diagnostics.

Most importantly, the ablation confirms that if the attacker is allowed to rewrite the *expected* root after editing, the forged result verifies. The root is not magic. The trust boundary is the externally preserved expectation.

A 40-session ablation-size probe produced:

- root-only external map: **5,601 bytes**;
- full `(session, source_digest, count, root)` manifest map: **15,601 bytes**.

Stable ablation semantic SHA-256:

`8cc5a6caa077d6bf9a1115fc5b92b43994be5b96d52044efafbaca2afb2acac4`

## Bounded scaling measurement

The main model builds 40 sessions with 1,000 primitive events each, 40,000 events total.

Canonical sizes on the deterministic corpus:

- primitive leaves: **12,398,469 bytes**;
- full session manifests: **15,601 bytes**;
- manifest/leaf ratio: **0.001258**.

Build and verification time are reported by the script but intentionally excluded from the semantic hash because runner timing is not reproducible evidence. The algorithm still hashes every primitive event and is O(number of primitive events). The size result is a commitment-storage result, not a claim of sublinear verification.

## What the experiment falsified

### `hash(current_program_map)`

Unsound for complete-history authenticity. The editor can delete the history and recompute the hash. Legitimate merge also changes the map, forcing a new hash and destroying the identity of the original source commitments.

### mutable global `expected_fact_root`

Same problem if it lives under the same edit authority as the map. A forged root after edit is internally consistent and externally meaningless.

### source hash without source replay

Enough to name an expected source and detect complete disappearance, not enough to derive or check its typed projected event set after the source bytes are gone.

### source hash + count without source replay

Enough to catch missing cardinality, not semantic substitution, causal-identity replacement or equal-value decoys.

## Minimum contract under the modeled boundary

When the raw source will **not** be available to the verifier, the cryptographic minimum demonstrated here is:

1. an externally expected exact set of source/session identities; and
2. for each source/session, an externally expected root over domain-separated canonical primitive leaves that include event identity/order, kind and typed semantics.

The current model stores count/source digest alongside the root because they are cheap, useful and correspond to Plaid's existing source contracts, but the ablation shows they are not substitutes for the semantic root.

When the complete raw source **is** available at verification time, a different minimum is possible: preserve only a trusted expected source digest/profile, re-read and completely re-import that source, and compare the resulting typed projection against the map. Existing `verify_fetch_capture` work is already a local example of this stronger complete-source style. In that mode a separately stored primitive root can be derived rather than trusted.

## Production integration shape

This branch deliberately does not patch `ProgramMap`.

A production design should choose one of two explicit trust models rather than quietly blending them:

### A. Source unavailable at solve/package time

- introduce a versioned, typed source/session manifest or certificate input outside editable `ProgramMap` facts;
- retain enough typed primitive event receipts (or per-event semantic leaf digests bound to event identity) to recompute the expected primitive root;
- require exact expected-session-set coverage before any positive CLOSED/native-complete certificate;
- merge source manifests by keyed union; same session + different manifest is a hard conflict;
- never re-root the merged `ProgramMap` as a replacement for the original session commitments.

### B. Source available for complete re-verification

- treat a trusted expected source digest/profile as the source identity;
- completely re-read/re-import the source at the certificate boundary;
- compare the independently rederived primitive projection against the retained map/obligations;
- preserve the verified-source receipt as a typed proof object, not evidence prose.

For current discovery traces, option B can exploit the already canonical, contiguous, end-counted NDJSON format and session hash. Other source types need their own exact canonicalization and complete-source verifier.

Digital signatures are not inherently required if the expected manifest is supplied by a trusted build/package input that the map editor cannot rewrite. Signing becomes relevant when commitments cross an untrusted storage or distribution boundary. A signature over a bad/incomplete sensor stream still does not prove coverage.

## Closed-world impact

This result closes one design uncertainty: **complete-history deletion resistance cannot be obtained from an editable ProgramMap alone**. A positive closure pipeline needs an expected-source boundary that survives deletion of all corresponding map facts.

Per-source/session commitments are compatible with Plaid's monotone merge model because they commit to primitive source events, not to mutable derived facts or evidence-reference unions. Same payloads remain distinct when event identities differ. Reordering storage does not erase chronology because sequence belongs to the committed leaf.

This does not make `WholeRom` CLOSED. It gives a defensible way for future whole-ROM certificates to state which evidence sources were expected and to detect that one disappeared or was semantically rewritten.

## Remaining gaps

- The experiment models four representative primitive event classes, not every current/future trace, fetch, cache, PI/SP, TLB, RSP, transform or hardware-test source.
- Current `ProgramMap` has no generic typed raw event collection from which a complete discovery-trace primitive root could be recomputed. Human-readable `Evidence.detail` must not become that interface.
- A production projection must decide which source events are primitive obligations and how every primitive event maps to typed downstream obligations without allowing an unmodeled event to vanish merely because no current `ProgramMap` field represents it.
- Partial-map workflows from one source/session need explicit semantics. This model treats a session manifest as a commitment to a complete source projection, not as a freely splittable shard.
- The 40,000-event benchmark is bounded. Million-event traces need streaming root construction and memory/RSS measurement.
- This work does not authenticate emulator instrumentation, prove hardware truth, prove sensor completeness, establish executable lifetimes, solve aliases/caches/TLB, or establish roots/control-flow closure.
- Key management/signing policy, if artifacts cross a hostile boundary, is a separate security design decision.

## Integration recommendation

**ADOPT the invariant and trust-boundary design, not this research model verbatim.**

The primary integrator should not add a self-hash field to `ProgramMap` and call the problem solved. Instead, define the certificate/build input's expected evidence-source set first. For each complete source, either re-verify that source at certificate time or retain an externally expected semantic primitive root plus typed receipts capable of recomputing it. Keep per-source commitments independent through merge.

This should precede any whole-ROM CLOSED claim because otherwise deleting the evidence that would have kept the result OPEN can remain indistinguishable from never having collected that evidence.

## Reproduction

```sh
python3 experiments/evidence-manifest-composition/model.py
python3 experiments/evidence-manifest-composition/ablations.py
cargo test --locked -p plaid-core
cargo fmt --all -- --check
cargo clippy --locked -p plaid-core --all-targets -- -D warnings
```
