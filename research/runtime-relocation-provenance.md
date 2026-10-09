# Runtime relocation provenance: erased immediates still require causal generations

Worker: `gpt56sol-runtime-relocation-provenance-20261010`

Base: Plaid `211176e7a489fecf8331d02915ee982cd279cb62`

Reference source: N64Recomp `ffb39cdad1da5de07eaaa48bd1db4a89a7986771`, exactly as pinned by `refs.lock.toml`.

## Question

What evidence is minimally sufficient to certify a runtime MIPS HI16/LO16 relocation mutation when executable storage can be loaded/reloaded in different generations?

This experiment deliberately does **not** claim that N64Recomp's static relocation implementation is hardware truth or that all commercial N64 overlays use these exact relocation records. The pinned code is used only as an exact, reproducible relocation-transform oracle for the two common MIPS immediate forms. The proof question is causal: can `(site, kind, target)` plus the final patched word identify the source executable generation and mutation?

## Current Plaid posture

`program::Relocation` currently retains `site`, `kind`, `target`, and evidence. `solver.rs` emits `unverified_relocation` for every retained relocation, so current `DeclaredStaticImages` behavior is already fail-closed. This research therefore does **not** report a current false-CLOSED bug. It establishes the evidence contract a future relocation verifier must satisfy before that blocker can ever be discharged.

## Exact pinned source facts

Source guards used by the experiment:

- `RecompModTool/main.cpp` Git blob `0768f16bf58ce09824cfe6ddec9eb5fcf9251ed7`
- `include/recomp.h` Git blob `73f3e73d7fc6cd6ccf37637f579fc389b554d8c3`

In the pinned mod tool, both `R_MIPS_HI16` and `R_MIPS_LO16` retain `reloc_word & 0xffff0000` and replace the entire immediate field. HI16 uses the sign-adjusted high half of the relocation target; LO16 uses the target low half. The runtime macro's HI16 carry expression is algebraically equivalent. The experiment checks that equivalence for 250,000 deterministic random 32-bit targets.

Pinned `R_MIPS_26` is intentionally not generalized into this result: that path is emitted as a relocation rather than patched by the inspected mod-tool code.

## Counterexample

Take two distinct storage/load generations at one relocation site with the same opcode/register upper half but different old immediates, for example:

- generation A: `0x3c081111`
- generation B: `0x3c082222`
- target: `0x80408000`

Both HI16 relocations produce `0x3c088041`. The relocation transform has erased the distinguishing old immediate. A verifier keyed by site/kind/target/post-word therefore cannot tell which storage generation was consumed. Payload equality after the mutation is not provenance.

The same problem appears even without differing payloads: reapplying a relocation to a word that is already patched can leave before/after bytes equal while still constituting a new mutation operation and postimage generation. An overlay reload can also reinstall byte-identical input at the same virtual site under a different load generation.

For paired HI16/LO16 reasoning, equal target values are likewise insufficient to prove that both halves came from the same overlay/load generation. A cross-generation pair is a possible numeric pair but not a causal relocation certificate.

## Executable adversarial reducer

`experiments/runtime_relocation_provenance.py` models ordered storage generations, relocation events, and actual write events. It compares a deliberately naive tuple/post-byte identity with a strict receipt that requires:

1. exact input storage generation;
2. exact input load/overlay generation;
3. preimage word for that generation;
4. relocation event identity, kind, target, and order;
5. exact mutation/write event identity;
6. a distinct postimage storage generation, including same-value writes;
7. same load/overlay generation when a paired HI16/LO16 semantic claim is made.

Cache-visible executable lifetime, relocation discovery completeness, and target reachability are intentionally separate obligations.

Deterministic attacks include distinct preimages collapsing to one postimage, generation swaps, same-value repeated relocations, byte-identical overlay reload generations, cross-generation HI16/LO16 pairs, missing writes, reordered writes, non-advancing generations, and equal-payload decoy events.

The fixed-seed fuzz axis exercises 100,000 cases per class. Exact-pin CI produced:

- naive generation-swap false accepts: 100,000 / 100,000;
- strict generation-swap rejects: 100,000 / 100,000;
- naive same-value generation collapses: 100,000 / 100,000;
- strict same-value generation advances: 100,000 / 100,000;
- naive cross-load HI16/LO16 accepts: 100,000 / 100,000;
- strict cross-load HI16/LO16 rejects: 100,000 / 100,000.

## Reproduction and receipts

Branch workflow: `.github/workflows/research-runtime-relocation-provenance.yml`.

Reproduce locally with an exact N64Recomp checkout:

```sh
python3 -m py_compile experiments/runtime_relocation_provenance.py
python3 experiments/runtime_relocation_provenance.py --source-root /path/to/N64Recomp
```

Authoritative GitHub Actions run `38004080089` at branch head `4e397992c473c398e1d9e44823a0c3b8b28afeb7` succeeded. It cloned the exact N64Recomp pin, verified both source blobs, ran the reducer twice and required `cmp` equality before uploading receipts.

- semantic report digest embedded in both outputs: `78ad10aa9533dca441c81b4063bff87fd98da3d00ef933d7d883f46488deb87f`
- committed experiment SHA-256: `78d133c07b85fc352c1659190e5ac7eb0c6cff977a6ae36e52a011dedf269615`
- emitted JSON file SHA-256: `585f33160ed068c5cac7541017e592c0b5924f5289e2f78b82e5dbb01ce97836`
- artifact ID: `11650735657`
- artifact ZIP SHA-256: `68b34f33d20fd5c4b5c3117e70d493da4ca6bfe8ca77b99bec4e575682e30ffc`

## Interpretation

A future relocation certificate should be a transformation edge between concrete storage generations, not a descriptive annotation attached to a site. The target and resulting bits establish what transform could have happened. The source generation plus exact mutation event establish which transform did happen.

This composes existing Plaid findings rather than replacing them:

- exact CPU copy/transform work already requires def-use generations rather than value matching;
- same-value writes already advance storage provenance;
- overlay reloads already require generation separation;
- cached-code work already shows that backing/postimage mutation is not equivalent to fetch-visible executable identity.

Thus a relocation proof may establish a backing/storage postimage generation and still leave closure OPEN until cache visibility/lifetime and reachability are independently discharged.

## Integration recommendation

Do not clear `unverified_relocation` from a fact shaped only like the current `Relocation` tuple. If/when a production verifier is added, represent relocation as a provenance-bearing mutation receipt with explicit input/load generation, preimage, event/write identity, output generation, and pair identity where applicable. Equal bytes, equal targets, and equal sites must not merge generations.

No production Plaid file is changed by this branch. The result is a bounded evidence-contract validation, not a whole-ROM relocation census and not a hardware-universal relocation semantics claim.
