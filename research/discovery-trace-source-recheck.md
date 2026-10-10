# DiscoveryTrace source-bound ProgramMap projection recheck

Status: **VALIDATED** for the bounded source-projection contract below.

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`

Branch: `research/discovery-trace-source-recheck-gpt56sol`

## Question

Can a complete immutable `DiscoveryTrace` authenticate the raw ProgramMap primitive facts that claim provenance from that trace without trusting editable `Evidence.detail`, value equality, or a generic `EvidenceKind::Trace` label?

Yes, for the raw fields actually retained in ProgramMap. This is deliberately narrower than proving that the trace sensors are complete or hardware-accurate. The source trace is treated as the finite captured source whose own structural completeness is already enforced by contiguous sequence numbers plus the mandatory End record.

## Why the existing structure is insufficient by itself

`merge::import` assigns each event the identity `trace:<sha256(complete NDJSON)>:<seq>` and attaches that ID to raw DMA, CPU-word-store, indirect-target and entry-verification facts. `ProgramMap::validate()` can check that a referenced Evidence row exists and has Trace kind, and the completed generic cross-kind-exclusivity work rejects incompatible event-role reuse inside an already materialized map. Neither operation has the immutable `DiscoveryTrace`, so neither can prove that a Trace ID used as a store really names a `CpuWordStoreObserved` source event or that a source primitive was not simply deleted from the raw projection. That generic worker's closeout explicitly leaves this exact typed/source-bound authenticity gap open.

The focused regression keeps a valid complete trace beside its imported ProgramMap, then demonstrates that ordinary ProgramMap validation still accepts a store row whose only source-session evidence ID actually names a `TargetLookup`. This is not a request to parse `Evidence.detail`; the missing input is the source trace itself.

## Validated verifier

`trace_projection::verify_discovery_trace_projection(map, trace)`:

1. validates both inputs and requires the same canonical ROM identity;
2. recomputes the source session hash from the complete canonical NDJSON;
3. replays invalidation epochs and compile-begin source-unit identities directly from ordered source events;
4. derives the exact retained raw semantics for each primitive source event:
   - ROM DMA tuple;
   - successful aligned CPU word-store tuple plus import generation;
   - indirect observation tuple plus source-unit CompileBegin identity;
   - entry verification PC/mask, compile generation, verification generation and source-unit CompileBegin identity;
5. checks only raw ProgramMap primitive collections for source-session IDs, so generic derived Region/CFG provenance can legitimately reuse a primitive event ID;
6. requires each primitive source event to appear exactly once after canonicalization and rejects wrong-role IDs, changed tuples, deleted events and multiple raw uses;
7. verifies Trace evidence kind/producer/revision but intentionally does **not** trust `Evidence.detail` as the event oracle.

Facts from other trace sessions may coexist in a merged ProgramMap. They are outside this invocation's source session and are not guessed to be equivalent.

## Adversarial matrix

The focused tests cover:

- exact imported projection: accept;
- a store fact relabeled with a source `TargetLookup` event ID: generic ProgramMap validation accepts, source recheck rejects;
- equal-value store-event transplant across different destinations: reject;
- deletion of a source DMA primitive while leaving its source evidence available: reject;
- map imported from a different complete trace session: reject;
- generation tampering across an `Invalidate`: reject;
- loss of an indirect observation's explicit CompileBegin source-unit identity: reject;
- entry-verification context rebound to an unrelated valid Trace event ID: reject;
- derived Region provenance reusing a valid primitive event ID: accept, proving the verifier is not a global one-use rule.

No adversary is reconciled by payload equality.

## Executable evidence

Actions run `38074159944`, job `114277513069`, on branch head `2e71d1da50b10ab6662aefbaaf3e9d69df0c88e4`:

- exact pinned Rabbitizer `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`: verified;
- focused `trace_projection` matrix: **9/9 PASS**;
- full `cargo test --locked -p plaid-core`: PASS;
- `cargo fmt --all -- --check`: PASS;
- `cargo clippy --locked -p plaid-core --all-targets -- -D warnings`: PASS.

An earlier run `38074014112` already had focused 9/9 and full plaid-core green, then failed only on two rustfmt line wraps; no semantic change was required.

## Closed-world impact

This closes a source-authenticity gap only when the complete DiscoveryTrace is available at verification time. It lets later provenance/lifetime composition distinguish “this ProgramMap row structurally references some Trace evidence” from “this raw fact is the exact typed projection of event N in this complete trace source.” That matters before using raw writers, indirect executions or entry checks as causal proof inputs.

It composes rather than replaces the structural within-kind and generic cross-kind event-role guards: those remain useful when the source trace is unavailable or before source recheck.

It does not establish sensor completeness, emulator correctness, hardware truth, byte provenance beyond what the raw event records, cache/TLB lifetime, overlay lifetime, transforms/relocations, exception-root completeness, RSP executable identity or whole-ROM closure. A trace can be perfectly rechecked and still be an incomplete observation of the machine.

## Reproduction

```sh
cargo test --locked -p plaid-core --test trace_projection -- --nocapture
cargo test --locked -p plaid-core
cargo fmt --all -- --check
cargo clippy --locked -p plaid-core --all-targets -- -D warnings
```
