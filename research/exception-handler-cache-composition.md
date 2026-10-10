# Exception-root handler provenance must compose with I-cache residency

Status: **VALIDATED for the bounded exact-pinned ares experiment**.

This result composes two previously separate Plaid evidence lanes:

1. exception entry selects a mode-sensitive executable root; and
2. a cached instruction fetch can be supplied by an older resident I-cache
   generation even after its physical backing changes.

The composition matters because a root address is not handler-byte provenance.
For the tested BEV=0 general vector, exception entry itself does not terminate or
refresh the resident executable lifetime.

## Claim tested

For exact pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`,
a real guest exception selecting `0xffffffff80000180` can execute a stale cached
handler word after an uncached guest write has changed physical RDRAM `0x180`.
Therefore `(exception class, vector PC, current backing bytes)` is insufficient to
identify the executable handler generation. The first handler fetch must be
causally joined to its actual resident/fill generation, or to the exact uncached
backing read when the fetch is uncached.

The experiment was also required to survive a same-value backing rewrite so that
value equality could not stand in for generation identity.

## Exact execution receipt

Branch: `research/exception-handler-cache-compose-gpt56sol`

Canonical branch base inspected for this lease:
`211176e7a489fecf8331d02915ee982cd279cb62`.

Successful exact-pin GitHub Actions run:
`38050813544`, job `114209395345`, tested commit
`42156c1d0eca02cc1e9078744da5ede64023a37f`.

The workflow cloned and detached exact ares pin
`9408cb43d4948fc3ea6e152a307a34348df3fe04`; the pinned checkout remained
unmodified. Source guards recorded:

- `ares/n64/cpu/exceptions.cpp` SHA-256
  `e24b2877fb5d629ca3f10f64dba9a612babb879c53ed142b42557920f216ffa7`
- `ares/n64/cpu/cpu.hpp` SHA-256
  `6f252eda8444e447031d1bdbbd094ed8286a5028e2136c9ccca911287512fc27`

Behavioral result file SHA-256:
`9715f83c898ae315ff2be8ed95c19dbf3019e6cd44953f6eec9fabe1d5577dd8`.

Adversarial model canonical payload SHA-256:
`8d0ae36f9ae213aaba8f011e9ba8d0b2088c64a074adeba73aad54aec6e67138`.
The emitted pretty-printed model report file hashes to
`52e3647ad838521dbef8da9578b83dba099fb2402d9834761bb151a653afca14`.

Uploaded evidence artifact ID `11669147754` has archive digest
`sha256:ab8a1ce08f6085740cc79194a9241e9c911738143ef59305d3ab2617af627362`.

The first workflow run, `38050763780`, failed in the adversarial model before
emulator execution because the missing-fill fixture accidentally retained its
fill event. That test bug was corrected without weakening any emulator
expectation; the next run passed source guards, model, exact-reference build,
execution, hashing, and artifact upload.

## Executed sequence and result

The fixture disables CPU/RSP recompilers and uses ordinary interpreter execution.
Observer hooks are generated only in the build output, with a plain run keeping
callbacks/tracer disabled and traced runs enabling completed fill, successful
scalar-RDRAM-write, and actual handler-fetch observations.

The instruction sequence is:

1. Place handler A, `ADDIU s0,zero,0x11` (`0x24100011`), at physical `0x180`.
2. Execute guest `SYSCALL` from uncached KSEG1. BEV=0 selects
   `0xffffffff80000180`; the first handler fetch misses and fills A.
3. Execute a real guest KSEG1 `SW` of handler B,
   `ADDIU s0,zero,0x22` (`0x24100022`), to physical `0x180`.
4. Trigger another real guest `SYSCALL` with no CACHE operation. RDRAM now holds B,
   but the handler fetch hits the resident line and executes A.
5. Execute guest CACHE hit-invalidate for the vector line. The next exception
   refills and executes B.
6. Execute another successful guest KSEG1 `SW` of B to the same backing address.
   This is a fresh storage operation with equal payload. Without invalidation the
   next handler fetch reuses the prior resident B generation.
7. Invalidate again and trigger once more. The visible bits remain B, but a new
   completed fill generation supplies the fetch.

The runner required and observed handler results
`[0x11, 0x11, 0x22, 0x22, 0x22]`, I-cache miss counts
`[1, 1, 2, 2, 3]`, hit counts `[0, 1, 1, 2, 2]`, five actual handler fetch
records, three completed vector-line fills, and two completed scalar RDRAM writes
to physical `0x180`. The completed fill payloads were `[A, B, B]`. Both traced
executions were byte-identical, and plain/traced phase plus final architectural
checkpoints agreed.

This directly falsifies current-backing attribution twice:

- after the changed-value write, current RDRAM does not even predict the executed
  instruction bits; and
- after the same-value write, current RDRAM bits match the executed instruction,
  but its fresh storage generation is still not the resident fetch's parent.

## Adversarial model

`experiments/exception-handler-cache-compose/model.py` keeps these identities
separate:

- backing storage generation;
- resident fill generation;
- resident fill's backing parent;
- resident validity/lifetime; and
- fetched value.

It rejects missing fills, fill/fetch reordering, reuse after invalidation,
wrong-parent claims, and equal-payload fill-generation decoys. A deliberately
unsound selected-root verifier that promotes current equal-valued backing to
provenance accepts the same-value forged parent.

With deterministic seed `0x504c414944`, 20,000 histories of 32 adversarial
actions produced **30,959** stale same-value fetches where latest-backing
attribution would be a false provenance claim, plus **92,859** changed-value stale
fetches. Every generated valid history passed strict replay; each tested forged
latest-backing parent failed strict replay.

## Source composition and independent comparison

At the exact ares pin, `CPU::Exception::trigger` selects the vector, updates
exception state, sets the pipeline PC, and updates CPU context. It contains no
I-cache invalidation/refill operation. The interpreter I-cache fetch separately
selects a resident line from virtual index bits, checks a physical tag, fills only
on miss, and otherwise returns the existing resident word.

Pinned Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7` independently has the
same relevant separation for this direct-mapped case: `syscall_exception()` calls
`exception_general(..., 0x180)`, which sets exception state/vector PC without an
I-cache invalidation, while `icache_fetch()` executes an already-valid matching
resident word and fills only on miss. Its I-cache line selection is based on
physical address rather than ares' virtual indexing, an already known reference
disagreement. This source comparison supports the narrow root-vs-residency
separation but is **not** promoted to physical VR4300 truth.

## Closed-world impact

A whole-ROM certificate cannot discharge an exception/interrupt root merely by
proving the vector address and identifying the bytes currently stored beneath it.
For a cacheable handler fetch, the proof chain must preserve enough chronology to
join:

`root-entry event -> selected virtual root -> actual first fetch -> translated physical access -> resident cache generation -> fill/backing generation -> producer provenance`.

For an uncached handler fetch, the analogous chain should terminate at the exact
successful backing-read/transform witness rather than a resident generation.

A backing mutation does not itself end a resident executable lifetime. Exception
entry does not do so in this tested path either. An observed successful cache
operation/refill/replacement/reset or other independently validated lifecycle
boundary must justify changing resident identity. Equal payloads cannot collapse
those generations.

If the first handler fetch cannot be causally assigned to one executable source
generation, the root obligation remains UNKNOWN and native completeness remains
OPEN. Seeding the vector from a final memory snapshot would be unsound.

## Remaining gap

This is bounded emulator evidence, not hardware truth and not whole-ROM closure.
It covers one BEV=0 KSEG0 general-vector line, guest SYSCALL entry, identity RDRAM,
interpreter execution, guest uncached SW mutations, and guest I-cache
hit-invalidate controls. It does not establish:

- physical VR4300/N64 cache truth;
- BEV=1 boot-ROM handler residency/provenance;
- TLB refill/XTLB vector cache interactions;
- maskable-interrupt producer timing;
- reset/NMI handler provenance;
- large pages, synonyms, or arbitrary aliases;
- save/restore/reset cache generations;
- every executable mutation source; or
- arbitrary-ROM reachability and executable-lifetime closure.

## Integration recommendation

**ADOPT the semantic proof obligation, not the research instrumentation wholesale.**

Exception-root discovery should produce a root-entry fact, not a synthetic byte
origin. The first executable fetch servicing that root must go through the same
backing/mapping/cache/lifetime provenance machinery as any other fetch. Current
memory snapshots, vector addresses, or equal instruction values must never be
used to manufacture handler provenance. Missing cache/fill ancestry must fail
closed.
