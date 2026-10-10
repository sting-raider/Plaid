# Spike 047: cacheable pointer-table load source

Result: **VALIDATED for this bounded exact-reference fixture.** The durable
analysis and proof obligations are recorded in
`research/ares-pointer-table-dcache-load-source.md`.

This bounded experiment asks which causal generation supplies a cacheable CPU
pointer-table `LW` that immediately feeds `JR`. It is intentionally narrower than
a pointer-table closure certificate: it validates an exact load-source join on
the pinned ares interpreter and then attacks that join with forged histories.

Reference pin: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
(from `refs.lock.toml`). Both CPU and RSP recompilers are disabled.

## Cases

* `stale`: fill table pointer A through KSEG0, rewrite RDRAM backing to B through
  KSEG1, then load/dispatch A from the still-resident D-cache line.
* `same`: as above, but the backing rewrite stores A again. Content is equal;
  backing generation is not.
* `refill`: fill A, rewrite backing B, replace the clean table slot with a
  same-index line, refill the table, then load/dispatch B.
* `same_refill`: rewrite backing with A again, replace/refill, then load/dispatch
  A from a new resident generation. The conflict line also contains pointer A as
  an equal-payload provenance decoy.
* `resident`: fill backing pointer B, cached-store C into the resident line only,
  then load/dispatch C while RDRAM still contains B.

Each scenario executes an interpreted `LW -> JR` and a distinct target marker.
The instrumented build is compared with both callbacks disabled and a separately
built unmodified baseline. Traced execution is repeated byte-for-byte.

The sensor records completed identity-mapped RDRAM writes/bursts plus completed
D-cache reads/writes. `verify.py` independently replays ordered backing and
resident generations. It refuses value-equality shortcuts and rejects forged
current-RAM attribution, same-value generation collapse, equal-payload decoys,
missing/reordered events, and wrong tag/source joins.

## Reproduction

```sh
git -C .refs/ares checkout 9408cb43d4948fc3ea6e152a307a34348df3fe04
python3 spikes/047-ares-pointer-table-dcache-load-source/run_exact.py
python3 spikes/047-ares-pointer-table-dcache-load-source/verify.py \
  target/ares-pointer-table-dcache-load-source/evidence.json
```

The branch workflow performs the exact-pin checkout, repeats the strict replay,
prints hashes, runs the full `plaid-core` test suite, and uploads the evidence.

## Scope

This is behavioral evidence for one controlled identity-mapped pinned-reference
scope, not hardware truth and not a whole-ROM proof. It does not certify complete
writer coverage, TLB/mode history, D-cache restore/reset chronology, table guard
coverage, numeric target exhaustiveness, or target executable lifetime/identity.
Those obligations remain independent and must stay OPEN when absent.
