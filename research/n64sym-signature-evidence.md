# n64sym signature evidence is not unique executable identity

Result: **VALIDATED**

Date: 2026-10-09

Plaid base inspected: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256` (`main` at claim time)

Pinned upstream: n64sym `ccf4600f3389f1a84bde23339225cf372fdf7712`

Primary executable evidence: GitHub Actions run `37915523291`, job `113770631166`

Deterministic report SHA-256 from that run: `fb47b856cb299d801455c1c466ed626fde0c1b2c308d3b6d3ebdca54f9d2dabb`

## Question

Can a successful exact-pinned n64sym signature match be treated as a unique function/library identity fact for future Plaid static-analysis enrichment?

## Hypothesis

No. A raw n64sym match should remain candidate/provenance evidence rather than unique executable identity or closure evidence. The hypothesis is falsified if the exact pinned tool demonstrates that a signature name is uniquely determined by executable bytes plus relocation-normalized content, independent of signature-source construction order.

## Upstream contract inspected

The exact pinned signature format records:

- symbol name;
- byte size;
- `crcA`, the CRC32 of the first eight bytes (or the whole symbol if shorter);
- `crcB`, the CRC32 of the whole symbol;
- optional `.hi16`, `.lo16`, and `.targ26` relocation descriptions.

Exact pinned `n64sig` strips relocation addends before computing CRCs. For HI16/LO16 it zeros the low immediate bytes; for R_MIPS_26 it preserves only the opcode bits and zeroes the target field.

More importantly for identity, exact pinned `n64sig` stores generated symbols in `m_SymbolMap` keyed **only by `crc_b`**. If a later symbol has the same `crc_b`, it is skipped before size, `crc_a`, relocation metadata, or symbol name can distinguish it. With verbose logging the tool explicitly reports the skipped name.

Exact pinned `CSignatureFile::TestSymbol` does use `crcA` and `crcB` when scanning a signature. When relocation metadata is present, it applies the same relocation stripping to candidate bytes before those CRC checks. This distinction matters: the scanner's tuple check does not restore identities already discarded while a signature database was generated.

Upstream license is MIT. No upstream source or signature database is copied into Plaid by this experiment.

## Experiment

Durable fixture: `experiments/n64sym-signature-evidence/`

Runner: `experiments/n64sym-signature-evidence/run.py`

Branch-only workflow: `.github/workflows/research-n64sym-signature-evidence.yml`

The workflow installs only GNU MIPS binutils needed to create synthetic ELF inputs, clones n64sym, checks out the exact pin, builds the **actual pinned `n64sig`**, and compiles a tiny harness against the **actual pinned `signaturefile.cpp`/`crc32.c`**. n64sym itself is not patched. The Makefile's static-link flag is overridden only for the research executable; source behavior is unchanged.

### 1. Built-in corpus baseline

The exact pinned `src/builtin_signatures.sig` contains:

- 5,881 symbols;
- 5,881 unique `crc_b` values;
- 5,881 unique `(size, crcA, crcB)` tuples;
- 4,930 symbols with relocation metadata;
- zero duplicate `crc_b` groups in the already-generated file;
- zero duplicate full-tuple groups in the already-generated file.

This is a useful negative result. It does **not** establish uniqueness of the source libraries. The generator enforces one retained entry per `crc_b`, so duplicates/collisions can disappear before the generated corpus is inspected.

Built-in signature file SHA-256: `edb4ce7cbf5d74ea64387c11f0b7a87358ad5882b7995c97562b295c26cd54b0`.

### 2. Name-identity adversary using the real generator

The runner assembles two independent MIPS ELF objects:

- `alpha.o`: one 12-byte function named `alpha`;
- `beta.o`: the same 12 instruction bytes, but the symbol is named `beta`.

The real pinned generator is invoked twice with explicit opposite input order.

`alpha` then `beta` emits:

```text
alpha 0x000C 0x076D7C20 0x92AA615F
# warning: skipped beta (have alpha, crc: 92AA615F)
```

`beta` then `alpha` emits:

```text
beta 0x000C 0x076D7C20 0x92AA615F
# warning: skipped alpha (have beta, crc: 92AA615F)
```

Therefore the surviving symbol name is not uniquely implied by the executable bytes. It is partly a property of signature-database construction order. A later n64sym match against such a generated database can truthfully match that retained signature while still not proving that its retained source-level name/library identity was unique.

This adversary intentionally uses identical function bytes rather than manufacturing a CRC collision. That keeps the claim narrow and removes probabilistic/hash-forging arguments from the result.

### 3. Relocation-class adversary using the real matcher

The runner assembles a 16-byte `gamma` function containing an `R_MIPS_26` relocation to `external_target`. The real pinned generator emits:

```text
gamma 0x0010 0x328DCA26 0xF6C672A8
 .targ26 external_target 0x000
```

The exact pinned matcher implementation is then run against three buffers:

1. original first word `0x0c000000` -> `MATCH`;
2. byte-distinct relocation target `0x0c123456` -> `MATCH`;
3. mutation to a non-relocation byte -> `NO_MATCH`.

Hashes:

- original bytes: `0a182d4da2341f510213a00ae11f3398f138c25985f28c503f649c33ef3d9430`;
- relocated-target bytes: `2c6e76c91ca259a01fb8e65b89c27947b50671aefb77534d30479d9de430a693`;
- unrelated-byte mutation: `7cc45ddef238e46881f628b48c1371691ca954fda682218a8639cc82e12d9242`.

This is intentional n64sym behavior, not a bug: relocation-normalized byte variants are designed to inhabit the same signature class. It nevertheless proves that a signature class is not an exact executable-byte identity.

## Source guards

The passing run recorded these exact upstream SHA-256 values:

- `LICENSE.md`: `5a060e234d7d92edf81387957dc8baf1e67e6790db9954206e02560bc9676834`
- `src/n64sig.cpp`: `2cef1a51b1c3d44b29880c832f00c1e623bfe80ac2a09a8421bb2f300bfb6b98`
- `src/signaturefile.cpp`: `e0156bef06163dc45916134bc77385246a08544956495fe8f1c8c74de5bc3249`
- `src/builtin_signatures.sig`: `edb4ce7cbf5d74ea64387c11f0b7a87358ad5882b7995c97562b295c26cd54b0`

The runner also asserts the exact source constructs for `crc_b`-only generator deduplication and relocation stripping before executing the fixtures.

## Reproduction

On Ubuntu with Python 3, Git, GNU make/g++, and `binutils-mips-linux-gnu`:

```sh
python3 -m py_compile experiments/n64sym-signature-evidence/run.py
python3 experiments/n64sym-signature-evidence/run.py \
  --report experiments/n64sym-signature-evidence/report.json
```

The default runner clones n64sym and checks out the exact pinned revision. `--n64sym <path>` may instead point at an existing checkout; the revision assertion remains mandatory.

The branch workflow is the canonical executable reproduction for this research result.

## Result

**VALIDATED.** A successful n64sym match is useful static evidence, but it is not a unique function/library identity fact and is not exact executable-byte identity.

A future Plaid adapter should preserve at least:

- exact n64sym/signature-source revision;
- signature key (`size`, `crcA`, `crcB`);
- relocation normalization metadata/assumptions;
- matched image and executable generation;
- the reported name as a **candidate label**, not canonical identity;
- ambiguity/source-library context where available.

Signature evidence may enrich traversal, naming, ABI hypotheses, known-library hints, or comparison tooling. It must not silently establish reachability, byte origin, table immutability, executable lifetime, exhaustive indirect targets, or closed-world status.

## Limitations

- This experiment does not claim that any particular commercial-ROM n64sym match is false.
- It does not recover symbols discarded when the shipped built-in signature file was originally generated because the original `oslibs` inputs are not part of this experiment.
- It does not construct a distinct-byte CRC32 collision. The order-dependent identity counterexample needs no collision, and relocation normalization separately supplies a byte-distinct same-signature-class case.
- It does not compare n64sym against spimdisasm or another signature system.
- It does not implement a Plaid production adapter.
- It does not prove the correctness of n64sym's ROM segment-address heuristics.

## What this explicitly does not prove

A matching symbol name does **not** prove:

- execution or reachability;
- the physical origin of fetched bytes;
- that the bytes remain immutable;
- that two aliases/generations are the same executable lifetime;
- that an indirect target set is finite or exhaustive;
- whole-ROM closure.

## Integration recommendation

**ADOPT** the evidence contract, not the research branch wholesale: n64sym may be added later as optional static candidate evidence, but symbol names must retain signature provenance and ambiguity and must never become closure proof by themselves.
