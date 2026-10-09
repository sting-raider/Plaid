# Bounded two-path cross-block indirect join

2026-10-10. Result: VALIDATED for the bounded static case described below.

Base: `main` at `211176e7a489fecf8331d02915ee982cd279cb62`.
Research branch: `research/cross-block-join-gpt56sol`.
Pinned decoder: Rabbitizer `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`.

## Question

The existing `plaid-cross-block-constant/v0` prover intentionally stops at a CFG
join. Can Plaid soundly prove one useful join shape without turning that bounded
certificate into a general dataflow solver?

The tested shape is exactly two acyclic root-to-site paths. Each path must be
reconstructed from current bytes and roots, contain only already-supported scalar
operations and non-linking direct control, and independently derive the same
canonical aligned JR/JALR source-register target from an otherwise unknown
incoming GPR state (`$zero` remains known zero).

## Baseline

On unmodified current `main`, the equal-target diamond remained uncertified while
the divergent-target diamond also remained uncertified. GitHub Actions run
`38003715192` passed the focused baseline and the full `plaid-core` suite. Thus
the lane starts from a conservative completeness gap rather than a reproduced
unsound CLOSED result.

## Prototype

The branch adds `plaid-cross-block-join/v0` as a fallback after the existing local
and single-predecessor certificates. The prototype:

- rebuilds the direct CFG from current image bytes and current root boundaries;
- treats declared entries, same-image indirect candidates/observations, and
  cross-image direct entries as path roots;
- enumerates exactly two root-to-site paths, bounded by the existing 128-block
  chain and 65,536-word image limits;
- rejects cycles, calls/linking control, unsupported effects, missing incoming
  paths, and path counts other than two;
- simulates each path independently from unknown incoming GPR state except
  `$zero`;
- requires both paths to derive the same aligned, canonical 32-bit-compatible
  JR/JALR target;
- records both path block/edge identities plus a traversed-word digest; and
- makes `verify_constant` recompute the exact join certificate from current map
  facts and bytes rather than trusting the evidence producer label.

Equal target values are used only to prove the finite target set. They do not
collapse path identity, writer provenance, executable lifetime, or any other
causal identity.

## Adversarial evidence

Final focused run `38004562128` / job `114070257563` passed 11/11 cases plus the
entire `cargo test -p plaid-core` suite. The focused matrix established:

- equal two-arm target: certified and independently rechecked;
- divergent targets: no certificate and no synthetic candidate;
- one arm changed after certification: stale proof rejected;
- required direct edge deleted: proof rejected;
- new alternate entry into one arm: proof rejected;
- new indirect candidate into one arm: proof rejected;
- linking/call edge on one arm: proof rejected;
- loop on the path: proof rejected;
- distinct supported scalar computations yielding the same target: accepted as
  target-set equality while retaining separate path identities;
- equal-target diamond whose target is already-discovered image entry: removes the
  indirect blocker and permits `Scope::DeclaredStaticImages` to report CLOSED;
- `syscall` in the final JR delay slot: target certificate remains valid but the
  closure solver remains OPEN, preserving delay-slot safety as a separate proof
  obligation.

Reproduction:

```text
cargo test -p plaid-core --test cross_block_join -- --nocapture
cargo test -p plaid-core
```

The branch workflow also checks that `refs.lock.toml` and `plaid-core` both name
Rabbitizer revision `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8` before running.

## Side finding kept out of scope

Pinned Rabbitizer enables CPU pseudos by default. In particular, a canonical
`bne rs,$zero,target` can surface through `opcode_name()` as `bnez`; zero-word
NOP is likewise a pseudo form not named by Plaid's current scalar whitelist.
The existing restricted cross-block prover therefore has completeness gaps around
those pseudo names. This experiment deliberately used canonical `bne rs,rt` and
`ori $zero,$zero,0` fixtures instead of widening instruction admissibility at the
same time. No hardware-semantics claim follows from that decoder naming detail.

## Closed-world impact

This removes one false-negative indirect-target obligation for a narrowly bounded
static diamond. It can change a declared immutable static-image scope from OPEN
to CLOSED when that join was the only remaining indirect-target blocker.

It does **not** close whole-ROM execution. The prototype supplies no proof for
more-than-two-way joins, loops, calls, memory/COP effects, mutable code,
dynamically produced generations, mapping/cache/lifetime provenance, exception or
interrupt root completeness, RSP executable identity, or whole-ROM coverage.
Those obligations remain OPEN exactly as before.

## Integration recommendation

Adopt the bounded rule only with its adversarial regression matrix and exact
recheck contract. The prototype is intentionally conservative but adds noticeable
code to `indirect_chain.rs`; the primary integrator may prefer to refactor common
path simulation shared with the single-predecessor certificate before canonical
integration. Keep Rabbitizer pseudo-name completeness as a separate change so the
semantic review surface stays auditable.
