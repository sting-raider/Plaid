# Spike 036: ares TLB-mapped uncached fetch provenance

This spike extends the validated direct-KSEG1 ordinary-RDRAM fetch witness into the VR4300 mapped segment at exact pinned ares revision `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

## Question

When `TLB::load` succeeds and the selected EntryLo cache algorithm is 2, can Plaid safely compose that translation with the existing uncached `CPU::fetch` / ordinary identity-RDRAM backing-read witness without losing virtual executable identity?

## What runs

`run.py` reuses the instrumentation/build machinery from `spikes/025-ares-rdram-uncached-fetch/` and executes an exact-reference matrix covering:

- valid non-global CCA=2 mapping;
- two distinct virtual aliases to the same physical instruction word;
- a real `TLBWI` remap of one virtual address to a different physical page with identical instruction bytes;
- cacheable CCA=3 mapping;
- reverse-endian Word lane rewriting after translation;
- an equal-valued TLB-mapped data-read decoy between two fetches;
- a global entry across an ASID mismatch;
- non-global ASID mismatch;
- invalid selected EntryLo half;
- true TLB miss.

The verifier requires one capture-wide ordinal and only accepts an ordinary-RDRAM witness when exactly one four-byte `VR4300_UNCACHED` scalar read occurs strictly inside an uncached fetch interval and its address/value match the post-endian bus paddr/fetched word. It also mutates the captured trace to force ambiguity and verifies fail-closed behavior.

`source_guard.py` checks the exact pinned TLB, fetch, TLBWI and RDRAM source contracts before compiling.

`source_model.py` is a deterministic supporting stress model of the exact `Entry::synchronize` / `TLB::load` equations. It exercises 100,000 generated ASID/global/valid/CCA cases. It is not a replacement for exact-reference execution.

## Reproduce

Prepare `.refs/ares` at the exact pinned commit, then run:

```bash
python3 spikes/036-ares-tlb-uncached-fetch/source_guard.py
python3 spikes/036-ares-tlb-uncached-fetch/source_model.py
python3 spikes/036-ares-tlb-uncached-fetch/run.py
```

The research branch also carries `.github/workflows/research-tlb-uncached-fetch.yml`, which fetches the exact pin and runs the fixture on Ubuntu.

## Recorded checkpoint

GitHub Actions run `37849934100` on branch commit `81eb12332403e889dd55f452e7617d30fd7b51f3` completed successfully. `results.json` SHA-256:

`e72d4332f3112bea8b1130183d93c7791e688edca7340903ed6a5e5bd58cd851`

Uploaded artifact digest:

`sha256:48cf5b441b10a4d60f7ea678a5eb7b8fb99ac75e53aa9d1cf60cc08174bf2156`

The deterministic source model digest is:

`e9890debc340c0ef26016f757cf2e50ff8fd26344ef2a4342bceb597d02976af`

## Scope limit

The dynamic matrix uses 4 KiB TLB halves and ordinary identity-mapped RDRAM. It does not establish a complete N64 TLB model, all page sizes/regions/address modes, or cached-I-cache provenance. A successful mapped access to a physical address above RDRAM is structurally routed by pinned `Bus::read` away from `MI::readRdram`; that non-RDRAM exclusion was source-checked rather than given its own dynamic phase in this fixture.
