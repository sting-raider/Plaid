# Exception roots require executable-generation identity

Status: **VALIDATED** for the bounded exact-pinned-ares BEV=0 general-exception case.

## Question

Can a whole-ROM certificate identify an exception root only by its architectural
vector virtual address plus the bytes currently present in backing storage?

No, not for a cached root. Existing exception-vector research proves where the
architectural transfer goes. Separately, cached-code visibility research proves
that valid I-cache residency can outlive a backing mutation. This experiment
composes those facts and executes the composition through the pinned reference.

## Result

For BEV=0, the general exception root is `0xffffffff80000180`, a cached direct
segment address. The fixture first executed an old handler at physical `0x180`,
creating resident generation A (`ADDIU v0,zero,1`). It then replaced backing RDRAM
with generation B (`ADDIU v0,zero,2`) while preserving the valid I-cache line.

A real guest `SYSCALL` executed from KSEG1 transferred to exactly
`0xffffffff80000180`, but the next handler instruction still came from resident
generation A and produced `v0 == 1` even though backing already contained B. After
a guest I-cache hit-invalidate, a second `SYSCALL` transferred to the **same**
vector address and the handler miss/refill executed generation B (`v0 == 2`).

Therefore `(exception kind, vector PC, current backing bytes)` is not a sound
executable-root identity. For a cached root, the certificate must bind the transfer
to the actual resident/fetch generation, or to a causally verified miss/refill
whose backing source generation is known.

## Exact executable evidence

Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`.
Exact ares pin: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

Initial successful Actions run: `37933901521`, job `113831050291`.
Both recompilers were disabled. The runner source-guarded the exact revision and
relevant exception/cache/memory Git blobs before building.

Dynamic evidence SHA-256:

`f794aabf9f70f9755e719138ed13d70d0a26334dab01d5a5702ca6ebbb2710cb`

Canonical dynamic evidence:

```json
{"backing_word":604110850,"icache_hits":1,"icache_misses":2,"refilled_handler":2,"refilled_resident_word":604110850,"refilled_root_pc":18446744071562068352,"stale_handler":1,"stale_resident_word":604110849,"stale_root_pc":18446744071562068352,"vector_va":18446744071562068352,"warm_handler":1}
```

`604110849 == 0x24020001`; `604110850 == 0x24020002`. Both stale and refilled
root PCs are decimal `18446744071562068352 == 0xffffffff80000180`.

The exact executable fixture was run twice by its runner and required byte-identical
stdout. CI also performed a fresh checkout of the exact ares pin.

## Adversarial replay

`experiments/exception_root_generation.py` ran twice byte-identically in the same
job. Report SHA-256:

`fb73e817fb097ca91caa100d5d5e179ec3b736df3785776f86618e6aa2000c8e`

Six histories were exercised:

- changed backing after a cached fill: strict root remains generation 1 while a
  current-backing policy incorrectly substitutes generation 2;
- invalidate/refill after the write: strict root correctly moves to generation 2;
- invalidate/refill **before** the write: the newer resident ID still contains
  backing generation 1 and remains stale after generation 2 is written;
- same-value replacement: payloads compare equal but resident generation 1 and
  current backing generation 2 remain different provenance;
- BEV=1 general-vector address as an uncached policy control: current backing is
  the fetch source in this abstract control, not a fabricated resident line;
- cached root with known backing but no resident/fill witness: strict identity is
  UNKNOWN while the naive vector/current-backing policy invents one.

Four deliberate vector/current-backing forgeries were rejected.

## Source composition

Pinned ares `exceptions.cpp` Git blob
`870e7d420f38fbda862cb4c7cb88481155b19251` computes the normal exception base as
`0x80000000` when BEV is clear and uses general offset `0x0180`, then calls
`pipeline.setPc(vectorBase + vectorOffset)`. It does not bypass the ordinary
instruction-fetch/cache machinery for the handler.

The dynamic cache behavior is consistent with the previously validated
`research/cached-code-patch-visibility` result: backing mutation and executable
I-cache visibility are separate transitions. This experiment adds the missing
composition with an actual exception-root transfer.

## Closed-world impact

A whole-ROM root verifier must keep separate:

1. architectural root transfer identity: exception/interrupt kind, vector and
   relevant execution context;
2. virtual/physical mapping identity;
3. backing byte generation;
4. resident instruction-cache generation and its source fill; and
5. the executable bytes actually fetched at the root.

Proving item 1 does not prove item 5. Current RAM at a cached vector is not a
substitute for resident-cache history. If Plaid lacks a unique resident/fill chain,
the handler executable generation must remain UNKNOWN/OPEN even when the vector
address itself is fully proven.

This matters for exception and maskable-interrupt handlers sharing cached vector
space, handler self-modification, overlays/aliases at handler backing, and
compiler-time exploration that forks or restores states. Equal bytes across two
backing writes must not collapse their generations.

## Artifacts

- `spikes/044-ares-exception-root-generation/driver.cpp`
- `spikes/044-ares-exception-root-generation/run.py`
- `spikes/044-ares-exception-root-generation/results.json`
- `spikes/044-ares-exception-root-generation/README.md`
- `experiments/exception_root_generation.py`
- `.github/workflows/research-exception-root-generation.yml`

Reproduce with `.refs/ares` at the exact pin:

```sh
python3 experiments/exception_root_generation.py
python3 spikes/044-ares-exception-root-generation/run.py
```

## Remaining gap

This is not a physical-hardware timing proof and not a complete N64 root model.
It covers exact pinned ares, BEV=0 general exception entry, identity RDRAM and
interpreter execution. It does not establish all CACHE variants, TLB-mapped
aliases, reset/NMI roots, complete handler mutation census, save/restore semantics,
or whole-ROM lifetime closure. BEV=1 is only an uncached adversarial-model control
here. The result is a proof-composition constraint, not permission to mark any
whole-ROM scope CLOSED by itself.

## Integration recommendation

**ADOPT the invariant, not the branch wholesale.** Root certificates should name
the architectural transfer separately from executable-generation evidence. For a
cached root, require a unique resident/fetch generation or a verified miss/refill
chain to a backing generation. Never resolve the handler generation by vector
address, current RAM contents, or payload equality alone. Missing cache provenance
must keep the executable root identity OPEN.
