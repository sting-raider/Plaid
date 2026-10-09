# n64sym signature evidence experiment

Verdict is determined by `run.py`; this directory contains no upstream code or game assets.

## Question

Can an exact pinned n64sym signature match be treated as unique function/library identity evidence for Plaid?

## Falsifiable hypothesis

No. The experiment tries two concrete attacks against that assumption:

1. Build two MIPS ELF objects whose functions have identical bytes but different names. Run the real pinned `n64sig` with the objects in opposite orders. If the emitted identity changes with input order, the name is signature-database provenance rather than unique executable identity.
2. Generate a function containing an `R_MIPS_26` relocation, then invoke the exact pinned `CSignatureFile::TestSymbol` implementation on the original bytes, a byte-distinct JAL target, and a non-relocation byte mutation. The relocated target should remain in the same signature class while the unrelated mutation must fail.

The run also audits `src/builtin_signatures.sig` for duplicate key statistics and guards the exact upstream revision/source behavior.

## Reproduce

Requirements: Python 3, Git, GNU make/g++, and `binutils-mips-linux-gnu`.

```sh
python3 experiments/n64sym-signature-evidence/run.py \
  --report experiments/n64sym-signature-evidence/report.json
```

The default path clones and checks out n64sym revision `ccf4600f3389f1a84bde23339225cf372fdf7712`, as pinned by Plaid `refs.lock.toml`. An existing exact-pin checkout may be passed with `--n64sym`.

## Scope

A validated result would justify only candidate/provenance semantics for future signature evidence. It would not show that n64sym matches are generally inaccurate, would not establish reachable code, executable-byte provenance, table immutability, or closed-world control flow, and would not add n64sym as a runtime dependency.
