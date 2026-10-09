# Pointer-table target sets do not prove executable generations

Date: 2026-10-10

Result: **VALIDATED for the proof-obligation composition; current solver was already fail-closed**

## Question

If Plaid eventually proves that a guarded pointer table is immutable and that its
numeric guest target set is exhaustive, may it treat each numeric pointer as one
fixed `CodeAddress { image, generation }` for closure?

No. Table-content identity and target executable identity are separate facts.
The same unchanged pointer value can reach different executable generations as
backing, mapping context, cache residency, overlay lifetime, or restored state
changes. A table immutability certificate therefore cannot discharge target
image/generation/lifetime by itself.

## Exact Plaid inputs

Canonical base inspected: `211176e7a489fecf8331d02915ee982cd279cb62`.

Relevant source blobs at that base:

- `crates/plaid-core/src/tables.rs`: `8be332e607ab3b20e36704a0d8acc09812030c7d`
- `crates/plaid-core/src/indirect.rs`: `9ae89cfd553104dfff1c1a79987487e14abdd492`
- `crates/plaid-core/src/solver.rs`: `37a33656bad3cf8c2165b84836b735a1d0c7c536`
- `crates/plaid-core/tests/tables.rs`: `82f780fc7acc67d1e9ca05e786f400d7b38766eb`

The source audit found that `tables.rs` reads a numeric table word and currently
creates a candidate with `image.address(GuestAddr(target))`. That attaches the
source `CodeImage` image/generation to a value whose table bytes establish only a
numeric guest PC. This is not currently a false `CLOSED` bug because pointer-table
sites retain no `closed_proof`, retain `pointer_table_immutability_unproven`, and
the solver remains open. It is, however, a distinct proof obligation that would
be unsafe to hide inside a future immutability discharge.

## Prior research composed

This result composes two already durable findings rather than inventing another
micro-op probe:

1. `research/pointer-table-immutability-aliases.md` (blob
   `44152c37a5c0add552812ce105618802784e3c20`) established that table-content
   immutability itself needs physical alias, mapping and D-cache load-source
   provenance. Guest-virtual write exclusion and backing-write exclusion alone
   are insufficient.
2. `research/reset-cache-lifetime.md` (blob
   `4ec924688e004a7b0d1313960b4f51f7ba5cee7a`) established against pinned ares
   `9408cb43d4948fc3ea6e152a307a34348df3fe04` that backing-byte lifetime and
   resident I-cache lifetime are distinct, and restore can resurrect an older
   resident executable image.

Together they imply a stronger boundary: even a hypothetical *perfect* table
content certificate cannot select one target executable generation without a
separate target mapping/cache/lifetime proof.

## Executable adversarial model

`experiments/pointer_target_generation_lifetime.py` keeps table bytes, backing
identity, mapping generation, resident I-cache generation and payload identity
separate.

The model holds one table word and its SHA-256 constant for every dispatch while
exercising:

- initial generation G0;
- backing replacement G1 while stale resident G0 still executes;
- explicit refill to G1;
- same-payload fresh backing generation G2 while resident G1 survives;
- a dispatch with no fetch/residency witness, which stays unknown;
- a mapping-context switch to G3 at the same numeric virtual pointer; and
- restore of old resident G0 while current backing is newer.

The witnessed executable identities are `{G0, G1, G3}` despite zero table
mutations. Six deliberately forged certificates are rejected: source-generation
reuse, current-backing attribution during a stale fetch, equal-payload promotion,
missing-fetch attribution, mapping-generation erasure, and monotonic-latest
attribution across restore.

Deterministic local execution before commit produced:

```text
REPORT_SHA256=5e3958809cdab87ce67f84296c57d041151a0eec9b4cf345d8cf7e9448366c44
PASS pointer target generation/lifetime adversarial composition
```

Two executions were byte-identical.

## Candidate Plaid hardening

The isolated branch adds a second explicit unresolved fact when a complete table
snapshot yields numeric candidates:

`pointer_table_target_identity_unproven`

Its detail states that numeric table targets do not prove target image/generation,
mapping context, cache-resident generation, or executable lifetime. The existing
`pointer_table_immutability_unproven` remains unchanged. A regression verifies
that both the ProgramMap and solver report retain the new target-identity blocker.

This is intentionally a small fail-closed patch. It does **not** implement a target
lifetime certificate and does not change candidate traversal. The current solver
was already open, so the patch prevents future unsound discharge rather than
repairing an observed current `CLOSED` result.

## Closed-world impact

A future pointer-table closed-target certificate needs two independent proofs:

1. **numeric target-set proof**: guard/path completeness plus exact table
   load-source/content immutability for the declared interval; and
2. **target executable-identity proof**: for every possible dispatch, bind the
   numeric PC to the relevant mapping/backing/cache-resident executable generation
   and lifetime. If multiple generations are possible, retain the finite set with
   their lifetime predicates; if the history is incomplete or ambiguous, stay
   OPEN.

A stable pointer value, stable bytes at the table, equal code payloads, or the
current/latest backing generation cannot substitute for the second proof.

## Reproduction

```text
python3 -m py_compile experiments/pointer_target_generation_lifetime.py
python3 experiments/pointer_target_generation_lifetime.py > /tmp/ptg-a.txt
python3 experiments/pointer_target_generation_lifetime.py > /tmp/ptg-b.txt
cmp /tmp/ptg-a.txt /tmp/ptg-b.txt
cargo test --locked -p plaid-core --test tables --test solver
cargo fmt --all -- --check
```

The branch-only workflow runs the same checks and records hashes.

## Limitations

This is a proof-composition result, not a new hardware semantic claim. The
cache/restore premise comes from the existing pinned-ares research and is not
promoted to universal hardware truth. The model does not implement overlay
load/unload recognition, a complete TLB/ASID history, I-cache lineage import,
relocation provenance, exhaustive target-lifetime predicates, or whole-ROM
closure. It also does not prove that one commercial ROM uses this pattern.

## Recommendation

**ADOPT selectively.** Keep pointer-table content/immutability and pointer-target
executable identity/lifetime as separate solver obligations. The branch patch is
a small defensive representation improvement suitable for primary-integrator
review, but the research branch should not be merged wholesale. Any later
certificate that clears only table immutability while inheriting the snapshot
source image/generation for its targets must be rejected as unsound.
