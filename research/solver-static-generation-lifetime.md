# Static generation identity is not lifecycle evidence

Result: **REJECTED** (2026-10-10)

Canonical Plaid base: `211176e7a489fecf8331d02915ee982cd279cb62`.
Decoder contract: pinned Rabbitizer `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8` via `refs.lock.toml` / `discovery::DECODER_REV`.

## Question

Can `Scope::DeclaredStaticImages` safely re-derive an omitted executable lifetime transition merely from the fact that the retained ProgramMap contains multiple `CodeAddress.generation` values for one image identity?

The proposed attack was that generation 0 and generation 9 at the same PC might prove a reload/invalidation happened, so deleting the corresponding dynamic event could incorrectly manufacture `CLOSED`.

## Finding

No. The proposed inference is unsound in the current schema.

`generation` is an execution-identity discriminator supplied by the producer. It is not defined as a count of prior mutations, a monotonic invalidation ordinal, or a lifecycle edge. `direct_cfg` accepts an arbitrary generation on a purely static `CodeImage`, and `loads::LoadObservation` also carries generation separately from the optional `copy_event` that can actually identify a transfer.

Therefore these two causal situations can have the same retained static projection:

1. two independently declared immutable static snapshots/roots, labeled generations 0 and 9;
2. one temporal execution in which generation 0 is installed/executed, a same-value reload creates generation 9, and generation 9 executes, after the reload event is deleted.

A solver that sees only the projection cannot distinguish them. Blocking merely because multiple generations exist would reject case 1 while still inventing chronology from identity labels. Equal bytes do not repair the missing causality; the temporal adversary deliberately uses a same-value reload.

## Executable falsification

`crates/plaid-core/tests/solver_static_generation_lifetime.rs` exercises the real current solver and pinned decoder path:

- a standalone immutable self-loop at generation 7 validates and closes under `DeclaredStaticImages`;
- two same-content roots at generations 0 and 9 validate and close when supplied as independent declared static images;
- the same finite set remains OPEN under `WholeRom`, so this does not weaken whole-ROM obligations;
- adding an explicit `ExecutableWrite::OverlayReload` keeps the static scope OPEN through the existing `unresolved_executable_write` blocker;
- an otherwise inert Region carrying another generation number does not become execution/transition evidence.

These cases are intentionally same-payload. Testing changed bytes under a forged shared content identity would overlap the separate CodeImage/content-binding research and is not used to justify this result.

`experiments/solver_static_generation_lifetime.py` constructs an independent-static history and a temporal same-value-reload history. After projecting away lifecycle events, the generation-bearing images/entries/blocks are byte-identical. The canonical projection SHA-256 is:

`327d96780c7ebcd201208d25213d896b750ecd48c2963230cd3162f0a0b2c85c`

The model fails if the projections differ or if the causal histories accidentally become equal.

## Why no production patch

The hypothesized fix, such as rejecting any nonzero generation or more than one generation per image, would encode a semantic guarantee the schema does not provide. That is a false-positive closure rule, not deletion-resistant verification.

ADR-0009 deletion resistance still applies when primitive evidence survives. The missing ingredient here is exactly that primitive evidence: a retained load/reload/invalidation/write/restore/lifetime record whose causal relation to executable identities can be independently rechecked. `generation` alone cannot substitute for it.

This composes rather than weakens ADR-0018: copy identity is explicitly distinct from a compiled executable snapshot. A numeric generation likewise cannot be promoted into copy identity.

## Reproduction

```text
python3 experiments/solver_static_generation_lifetime.py
cargo test -p plaid-core --test solver_static_generation_lifetime -- --nocapture
cargo test -p plaid-core
cargo fmt --all -- --check
cargo clippy -p plaid-core --all-targets -- -D warnings
```

Branch-only Actions workflow: `.github/workflows/research-solver-static-generation-lifetime.yml`.

## Closed-world impact

This closes a tempting but unsound proof shortcut. Future executable-lifetime/whole-ROM work must preserve and verify transition evidence; it may not reconstruct causal history from generation numbers, adjacent ordinals, equal payloads, or same-PC identities.

`DeclaredStaticImages` may still close a finite union of independently declared immutable roots. That closure says nothing about how a real runtime moves between executable generations. `WholeRom` remains OPEN until load/copy/write/restore/lifetime and root completeness are independently established.

## Remaining gap

Plaid still needs a production lifecycle evidence model that can bind executable identities to actual transition operations (copy/load, successful mutation, invalidation, restore, overlay activation/retirement) and survive deletion/adversarial rechecking. Once such primitive history is retained, the solver can enforce monotonicity from that evidence. This result only says the existing `generation` label cannot provide that history by itself.
