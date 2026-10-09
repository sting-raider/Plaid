# Declared-static guest-overlap closure attack

Status: IN PROGRESS

Branch: `research/solver-guest-overlap-closure-gpt56sol`

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62` (solver behavior is unchanged from technical base `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`).

## Question

Can `Scope::DeclaredStaticImages` report CLOSED when two distinct executable image/generation identities occupy overlapping guest virtual addresses, even though no mapping or lifetime evidence selects which identity a raw CPU guest PC denotes?

This is deliberately separate from the completed explicit-physical-alias attack. The counterexample supplies no `physical_start`; it attacks the guest-address-to-executable-identity relation itself.

## Existing invariant being composed

`loads::record_load` already treats different canonical executable sources that overlap in **guest** address space as an unresolved overlay/lifecycle candidate. The finite solver re-derives several importer consequences so deleting derived facts cannot manufacture closure (ADR-0009). The completed physical-alias solver research established the same proof-monotonicity requirement for explicit physical overlap, but did not test identical/partially overlapping guest ranges with unknown physical mappings.

## Adversarial regression

`crates/plaid-core/tests/solver_guest_overlap.rs` builds independently CLOSED `J self` images using only the declared-static integer/control-flow subset, then merges them. Cases:

- exact same guest range, distinct image IDs, conflicting delay-slot bytes;
- exact same guest range and payload, same image name but different generations;
- partial guest overlap across distinct identities;
- disjoint guest ranges (negative control);
- an extra overlapping region description for one image/generation identity (negative control).

All positive cases expect blocker `ambiguous_guest_executable_identity`. Equal payload is intentionally not an identity proof.

## Evidence

Baseline execution receipt pending branch Actions run. No semantic conclusion is claimed until unchanged-solver execution completes.
