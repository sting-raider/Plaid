# Executable Region physical-span overflow

## Result

**VALIDATED** on canonical base `211176e7a489fecf8331d02915ee982cd279cb62`.

`ProgramMap::validate()` accepted an executable `Region` whose explicit `physical_start + range.size` exceeded the 32-bit `PhysicalAddr` namespace. Because `solve()` trusts `ProgramMap::validate()` as its schema gate, an otherwise finite immutable static CFG could carry this malformed backing fact into closure reasoning. The neighboring `ObservedDma` schema already rejects the same class of physical destination overflow, so Region validation was inconsistent with the existing non-wrapping physical-span contract.

The candidate fix rejects explicit Region spans whose half-open end is greater than `2^32` while preserving a span whose end is exactly `2^32`, ordinary low mappings, and Regions with no explicit physical mapping.

## Reproduction

Branch: `research/region-physical-span-overflow-gpt56sol`

Pre-fix regression commit: `4863af2072a9f7b92a099ccee1e1dd778b82fa15`

Actions run `38002576465`, job `114063892047`, failed exactly at the new assertion:

```text
explicit 8-byte physical span starting at 0xffff_fffc must not wrap past 2^32
test result: FAILED. 0 passed; 1 failed
```

The run built the exact Rabbitizer revision pinned by `refs.lock.toml`, `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`.

The witness uses an otherwise closable two-word static image and changes only its Region to:

```text
physical_start = 0xffff_fffc
size           = 8
```

Before the fix, `map.validate()` returned `Ok(())`. The intended contract is a single non-wrapping affine physical span; the represented bytes would require addresses past `0xffff_ffff`.

## Candidate fix

Candidate production commit: `629fcb1bace38305cb678e614579a56d6c73defb`.

The smallest fix is in the Region validation loop in `crates/plaid-core/src/program.rs`:

```rust
if let Some(physical) = r.physical_start
    && u64::from(physical.0) + u64::from(r.range.size) > 1u64 << 32
{
    return Err("region physical span overflow".into());
}
```

This deliberately uses widened arithmetic and treats the Region as a half-open interval. End `== 2^32` is valid because its final represented byte is `0xffff_ffff`; only `end > 2^32` requires an unrepresentable/wrapped byte.

Candidate-fix validation run `38002731778`, job `114064398053`, passed the focused regression and the full `cargo test -p plaid-core` suite after applying and committing the candidate fix.

## Adversarial controls

`crates/plaid-core/tests/region_physical_span.rs` covers four cases:

1. `0xffff_fffc + 8`: rejected as physical-span overflow.
2. `0xffff_fff8 + 8`: accepted; half-open end is exactly `2^32` and the finite static scope remains CLOSED.
3. `0x0010_0000 + 8`: accepted and CLOSED.
4. `physical_start = None`: accepted and CLOSED; validation does not invent a physical mapping.

The executable payload is unchanged across these controls. Payload equality therefore cannot repair an invalid backing identity, and absent physical mapping is not guessed from guest address shape.

Reproduce with:

```sh
cargo test -p plaid-core --test region_physical_span -- --nocapture
cargo test -p plaid-core
```

A deterministic patcher used only to bootstrap the branch candidate is retained at `spikes/region-physical-span-overflow/apply_candidate_fix.py`. The final branch workflow validates the committed fix directly and does not self-patch.

## Composition with prior research

This result composes rather than replaces the existing physical-identity work:

- ADR-0005: physical storage identity must remain distinct from guest execution identity.
- ADR-0009: closure inputs must resist malformed/deleted/contradictory evidence rather than trusting importer convenience facts.
- ADR-0010: DMA provenance already requires exact non-wrapping physical coverage.
- ADR-0017: explicit physical mappings are candidate backing evidence, not proof by address/value equality.
- Completed solver physical-alias and conflicting-mapping attacks establish that *valid* physical spans still need uniqueness/lifetime reasoning. This finding is one layer earlier: the span itself must first be representable.

## Closed-world impact

Before physical overlap, writer coverage, copy provenance, alias equivalence, cache lineage, or executable lifetime facts can be composed, every explicit backing interval must denote a valid non-wrapping physical span. Otherwise later overlap logic can compare a malformed affine mapping as if it were a real storage identity and a finite static certificate can inherit impossible backing state.

Therefore a Region crossing `2^32` is a schema error, not an alias, not two wrapped spans, and not something that byte equality can reconcile. It must fail before CLOSED/OPEN proof evaluation.

## Remaining gap

This bounded fix does **not** prove that an accepted `physical_start` is the true N64 backing mapping. It does not establish the hardware's narrower decoded physical-address behavior, TLB context, aliases, cache residency, executable lifetime, writer completeness, DMA/copy lineage, or whole-ROM closure. It only prevents one malformed physical interval from entering those higher-order proofs.

## Integration recommendation

Adopt the Region overflow check and focused regression. Keep the validation local to the portable evidence schema so every solver/importer consumer receives the same invariant. Do not reinterpret overflowing Regions as wraparound aliases; if wrapped device semantics are ever needed, represent them explicitly as separate validated spans with their own causal/mapping evidence.
