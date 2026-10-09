# Declared-static solver ROM-source boundary

Status: PARTIAL

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`.

Branch: `research/solver-rom-source-binding-gpt56sol`.

## Question

Can `solver::solve(map, images, Scope::DeclaredStaticImages)` authenticate an
executable `Region`'s claimed `rom_offset` against the canonical ROM named by
`ProgramMap::rom`?

A stronger initial hypothesis treated a `CLOSED` result with a false claimed ROM
offset as a proof bug. The experiment validated the observable behavior but
rejected that interpretation: declared-static closure is intentionally relative
to supplied immutable image facts. It is not a canonical-ROM-source or causal
load-provenance certificate.

## Current-main counterexample

The focused fixture constructs a valid canonical big-endian N64 ROM and a
self-authenticating two-word `CodeImage` at guest `0x80000000`:

```text
canonical ROM @ 64: NOP ; NOP
supplied CodeImage: J 0x80000000 ; NOP
CodeImage.rom_offset: 64
Region.rom_offset:    64
```

The CodeImage's image identity is the SHA-256 of its own supplied bytes. The map
is built by `direct_cfg`, so Region and CodeImage image/generation/offset metadata
agree and `ProgramMap::validate()` succeeds. The only independent contradiction
is that the canonical ROM bytes at offset 64 differ from the supplied image.

On unmodified base behavior, `solve(... DeclaredStaticImages)` returns `CLOSED`.
The initial red test encoded the stronger expected contract (`OPEN` with a
canonical-source blocker), so Actions run `38002940750`, job `114065077208`,
failed exactly `left: Closed / right: Open`. Its no-ROM-offset control remained
`CLOSED`. Exact pinned Rabbitizer
`724a49a5b4dbfb99f1a9e6992e63964fd29c90c8` compiled in the run.

This establishes a real API boundary: the public finite solver receives a
`RomIdentity`, not canonical ROM bytes, and therefore cannot itself authenticate
that a declared ROM offset contains the supplied executable bytes.

## Adversarial same-value decoy

A second fixture places the supplied `J self ; NOP` payload at canonical ROM
offset 72 while the CodeImage and Region still claim offset 64, whose bytes are
`NOP ; NOP`.

The equal payload elsewhere does not make the offset-64 claim true. The final
research regression checks both facts explicitly and then records that the
finite declared-static solver still closes relative to the declared immutable
image. This is deliberate: content equality at some other location is not used
to infer provenance.

## Falsified strict prototype

Commit `068629b325ea2b833e4f2e84299397541f5992a2` prototyped a stronger solver
contract:

- witness-less `solve` emitted `canonical_rom_source_unverified` whenever a
  covering Region carried `rom_offset`;
- `solve_with_rom(..., &CanonicalRom)` checked that the ProgramMap identity
  matched the supplied canonical ROM and compared executable bytes against the
  Region's affine ROM location;
- mismatches emitted `canonical_rom_source_mismatch`;
- exact byte matches passed the check.

Expanded adversaries covered no witness, wrong bytes at the claimed location,
an equal-payload decoy at another location, exact `CodeImage::from_rom` content,
and a no-ROM-metadata control. At head `64b9faea710923119082e7aa46456cd6928b1241`,
Actions run `38003463814`, job `114066750989`, passed:

```sh
cargo fmt --all -- --check
cargo test -p plaid-core --test solver_rom_source_binding -- --nocapture
# 5 passed; 0 failed
cargo clippy -p plaid-core --all-targets -- -D warnings
```

The complete `cargo test -p plaid-core` then failed exactly one existing test:
`fetch.rs::distinct_captures_merge_without_summing_or_collapsing_observations`.
That test deliberately constructs a canonical `CodeImage::from_rom` plus a static
CFG and expects witness-less `DeclaredStaticImages` solving to be `CLOSED`.
The other 12 tests in that fetch test binary passed before Cargo stopped.

This failure falsifies the proposed compatibility assumption that every explicit
`Region::rom_offset` must be independently authenticated by the finite solver.
The strict production change was therefore reverted in commit
`0bbaa494390ed2dc0d7b69e045c7c0558082fb9a`; it remains in branch history only as
a rejected experiment.

## Why byte equality is still not causal provenance

Even the stronger `solve_with_rom` prototype was too easy to over-interpret.
Exact equality between supplied executable bytes and canonical bytes at a named
ROM offset proves only **content/location consistency** for that snapshot. It does
not prove that runtime execution causally descended from that ROM location.

Plaid already has the stronger pattern in `loads::record_load` and ADR-0010:
canonical source bytes are checked together with explicit copy evidence, and when
a copy event is asserted it must be backed by trace evidence and a covering
observed DMA. Requested length, destination equality, or equal payloads are not
promoted into source provenance.

Keep these distinct:

- executable content identity;
- declared Region ROM location;
- canonical byte equality at that location;
- physical backing identity;
- observed copy/DMA event identity;
- executable generation/lifetime;
- causal source provenance.

The experiment does not justify collapsing any of them.

## Composition with prior research

This result composes rather than duplicates two completed solver attacks:

- `solver-codeimage-content-binding` authenticates content-derived image IDs
  against supplied bytes. The adversary here is self-authenticating, so that
  invariant can pass.
- `solver-supplied-image-provenance` rejects explicit CodeImage-vs-covering-Region
  ROM/physical metadata contradictions. The adversary here gives both objects the
  same ROM offset, so that invariant can also pass.

The remaining independent question was whether matching metadata is itself bound
to canonical ROM content. It is not at the `solve` API boundary, and that is
consistent with ADR-0009's declared finite-image scope. ADR-0010 supplies the
separate causal-copy standard when actual ROM provenance is claimed.

The CLI also has a stronger input boundary than the library solver: `plaid solve`
reads the canonical ROM, checks `map.rom`, reconstructs candidate CodeImages from
Region ROM offsets, and retains only hash-matching images before invoking the
solver. That behavior must not be generalized into an assumption about arbitrary
library callers.

## Closed-world impact

The useful closure result is negative but important: **do not compose
`DeclaredStaticImages == CLOSED` into a proof that executable bytes came from a
Region's claimed canonical ROM offset.** The status proves closure only for the
declared finite immutable-image scope and its explicit exclusions. It remains
`native_complete=false`, and whole-ROM closure remains independently OPEN.

A future whole-ROM certificate must carry an independently verified source/copy
chain if canonical ROM origin matters. Neither self-authenticating content nor
matching `rom_offset` metadata can substitute for that chain.

## Remaining gap

Plaid has no single solver-level certificate that says, with explicit semantics,
"these declared executable bytes are byte-consistent with canonical ROM range X"
while keeping that fact distinct from causal copy provenance. The CLI partially
reconstructs this relation operationally, and load evidence carries stronger
copy semantics, but the library solver report does not expose the distinction.

If such a certificate is useful for later composition, it should be a separate
verified fact or stronger solver input, not an inference from equality and not a
silent upgrade of `DeclaredStaticImages` semantics.

## Integration recommendation

Do **not** adopt the strict `canonical_rom_source_unverified` blocker prototype or
its `solve_with_rom` byte-equality result as a causal provenance proof.

Retain the final adversarial regression/research note as a scope-boundary guard,
or translate the result into documentation/report wording that makes the finite
solver's relative semantics unmistakable. If a canonical byte-consistency
certificate is added later, name it narrowly and require separate DMA/copy/history
evidence before promoting it to causal ROM provenance.
