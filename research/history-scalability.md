# Strict PI-queue history scalability

Status: **VALIDATED** for the bounded synthetic source-valid cases described here.

This note measures the current strict Rust `inspect-pi-queue-boot-history` / `verify-pi-queue-boot-history` path. It does not weaken or coalesce ordered evidence and does not make a whole-ROM closure claim.

## Exact revisions

- Plaid canonical base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`
- Primary measurement head: `880b3bc64f7bffd6eafd953e92f50289a42dfee0`
- Regression/repeat head: `8dc1293dbdd5065945ef117b9382cd1e372d1980`
- Pinned ares revision from `refs.lock.toml`: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Pinned ares source inspected: `nall/nall/priority-queue.hpp`; its queue is a fixed binary min-heap. The benchmark below measures Plaid's strict history consumer, not ares queue runtime memory.

## Hypothesis

With retained causal-identity cardinality held fixed, increasing valid ordered legacy rows should cost approximately linear wall time while peak resident memory remains approximately flat because the nested v2 -> v1 -> v0 consumers reuse per-line buffers. Conversely, increasing accepted token identities should materially increase resident memory because v2 retains token/request/status identity state.

A peak RSS proportional to source bytes/legacy row count, or unexplained nonlinear verification time, would reject the streaming hypothesis.

## Source retention map

At the canonical base:

- `crates/plaid-core/src/pi_queue_history.rs` `Projection<H>` reuses `raw` and `output` vectors while reading/serializing one record at a time. It also retains a 512-slot array, a `BTreeMap` of token identities, and request/status collections.
- `crates/plaid-core/src/pi_history.rs` likewise reuses line buffers and bounded active-copy state while retaining transfer/status identity collections.
- `crates/plaid-core/src/history.rs` reads one legacy record at a time into a reused buffer and retains active/pending fetch state plus counters.
- `history::MAX_RECORDS` is 100,000,000. The v2 identity bound is separately finite; row count and retained identity count are therefore different scaling axes.

## Fixture and adversarial separation of axes

`spikes/044-history-scalability/bench.py` starts from the existing source-valid synthetic fixture in `scripts/test_pi_queue_history.py`. Stress records are inserted only after its last completed causal scope and before the footer.

Two axes deliberately differ:

1. **neutral / legacy-row axis**: source-valid base `scalar` records representing successful RDRAM writes outside a fetch context. These traverse the full v2 -> v1 -> v0 projection/inspection stack. They add ordered/hash/count evidence but no new retained queue identity.
2. **identity axis**: accepted v2 non-PI queue insertions with exact successive token IDs while reusing slot zero. This grows the token `BTreeMap` without growing the slot set or adding legacy records to the nested inspectors.

For every case the harness:

- runs release `inspect-pi-queue-boot-history` twice under `/usr/bin/time -v`;
- requires the two reports to be byte-identical;
- runs release `verify-pi-queue-boot-history` against the complete generated source;
- requires the report history digest to equal the generator's SHA-256;
- checks the exact successful-insertion count;
- for neutral rows, checks that the nested v0 event count consumed the stress `scalar` rows;
- records wall/user/system time, peak RSS, page faults, source/report digests and byte counts.

No captured ROM, firmware, game asset or large trace is committed. Generated stress histories are deleted after each case.

## Primary executable result

GitHub Actions run `37915338195`, Ubuntu 24.04 hosted runner, completed successfully at research head `880b3bc64f7bffd6eafd953e92f50289a42dfee0`.

Artifact:

- name: `history-scalability-results`
- artifact ID: `11609202441`
- artifact ZIP SHA-256: `d2bb14fcaff7ab76ed8086599963f9c75d7d0c55a492c2186345b67696b3230b`
- result JSON SHA-256: `c6facefe4b1742a0e8af6b3960bec5461f287c39f79e5e45709faf8a8e40810e`
- consumer source SHA-256: `58a5ab450faeeb8f33c64b15011c3a507d9932a1b655b46e4e3f787ee2a52ebb`
- fixture source SHA-256: `dd47ba1873a2bc0a30ab8e3d618de73506fef982f8afc1432cf5473c09d4eaed`

### Full nested legacy-row axis

| Stress rows | History bytes | Inspect 1 wall / RSS | Inspect 2 wall / RSS | Verify wall / RSS |
| ---: | ---: | ---: | ---: | ---: |
| 10,000 | 1,311,180 | 0.07 s / 4,168 KB | 0.07 s / 4,184 KB | 0.08 s / 4,280 KB |
| 100,000 | 13,101,254 | 0.69 s / 4,100 KB | 0.76 s / 4,136 KB | 0.71 s / 4,324 KB |
| 500,000 | 65,901,254 | 3.47 s / 4,272 KB | 3.48 s / 4,224 KB | 3.61 s / 4,136 KB |
| 1,000,000 | 131,901,328 | 6.93 s / 4,144 KB | 7.12 s / 4,320 KB | 7.12 s / 4,180 KB |

All measured major page faults were zero. Across a 100x increase from 10k to 1m stress rows, inspect peak RSS stayed in the same roughly 4.1-4.3 MB band while wall time scaled approximately with row count.

The 1m-row history SHA-256 was `01a8b3ac213e383727b241ab689d2647fbd3025acedb0507c3801a9baa28f691`; its report SHA-256 was `4073978ec0d15c95c653bc4bee15a66f8e52ad282b7fd9d86b5eb8bf94b3b126`.

### Retained-token identity axis

| Stress identities | History bytes | Inspect 1 wall / RSS | Inspect 2 wall / RSS | Verify wall / RSS |
| ---: | ---: | ---: | ---: | ---: |
| 10,000 | 1,600,086 | 0.02 s / 4,776 KB | 0.02 s / 4,776 KB | 0.02 s / 4,648 KB |
| 50,000 | 8,040,086 | 0.10 s / 7,152 KB | 0.10 s / 7,204 KB | 0.10 s / 7,208 KB |
| 100,000 | 16,090,164 | 0.20 s / 10,376 KB | 0.21 s / 10,276 KB | 0.20 s / 10,384 KB |
| 250,000 | 40,540,164 | 0.51 s / 20,008 KB | 0.52 s / 20,136 KB | 0.51 s / 20,008 KB |

The 10k-to-250k endpoints imply about 65 bytes of additional peak RSS per retained token on this particular optimized build/allocator. That is an empirical slope, not a Rust layout or platform invariant.

The 250k history SHA-256 was `6dac27e741001d082bd5c81cee96faf3c4736bc9fe6c45db607a38cb767d4a5a`; its report SHA-256 was `19f8d50ae99174f8ed8efb405d19e80ac61c139f6726011f5c58a22678f37b2e`.

## Regression and repeat receipt

A second successful workflow, run `37915743915` at head `8dc1293dbdd5065945ef117b9382cd1e372d1980`, first ran:

```sh
cargo test --release --locked -p plaid-core --test pi_history
```

Result: **19 passed, 0 failed**.

The workflow then repeated the complete benchmark on a different Ubuntu 24.04 hosted runner. Deterministic source and report SHA-256 values were identical to the primary run. The 1m legacy-row case measured 3.76 s / 4,236 KB on the first inspect and 3.78 s / 4,308 KB on verification. The 250k-token case measured 0.29 s / 20,200 KB on first inspect and 0.28 s / 20,200 KB on verification. Hosted CPU speed changed materially; the resident-memory shape did not.

Repeat artifact:

- artifact ID: `11608648753`
- artifact ZIP SHA-256: `e62cd43f596c499bb698d72c7227f1fb509d4be994e746734dc86361411a80d6`
- result JSON SHA-256: `a84c1324971ca70deee8c343544ecf90de56e3055f9b160b61f323f62939348f`

## Result

**VALIDATED** for these bounded cases.

The current strict nested consumer does not materialize source history merely as a function of ordered legacy-row count. Generic source-valid legacy rows stream with approximately flat resident memory and approximately linear inspection/reverification time. Retained causal identity cardinality is a separate and real memory-scaling dimension.

This matters architecturally: large ordered histories are not, by themselves, evidence that Plaid must discard or coalesce causally relevant records to fit memory. Scalability work should preserve complete ordered evidence and separately budget/index the identity-bearing state that consumers intentionally retain.

## What this does not prove

- The actual 1.57 GB / roughly 8.8 million-record bounded boot capture was not available to this Actions job and was not timed directly.
- The benchmark does not establish performance at `MAX_RECORDS` or the maximum identity bound.
- The neutral case exercises valid legacy scalar rows. Other record types can retain different bounded state or perform more expensive validation.
- Only token cardinality was isolated directly here. Request, status, PI-transfer and future executable-provenance identity structures can have different slopes.
- Hosted-runner timings and allocator overhead are not hardware/platform guarantees.
- This is an artifact-consumer scalability result, not an executable-completeness, provenance-completeness, or closed-world proof.
- The inspected pinned ares queue source is a behavioral/source reference only; this benchmark does not measure ares queue performance.

## Reproduction

From this research branch:

```sh
cargo build --release --locked -p plaid
cargo test --release --locked -p plaid-core --test pi_history
python3 spikes/044-history-scalability/bench.py
sha256sum target/history-scalability/results.json
```

The branch-only workflow `.github/workflows/research-history-scalability.yml` runs the same release build, strict PI-history regression test and benchmark and uploads only the compact result receipt.

## Recommendation

**ADOPT** the benchmark and the distinction between streamed chronology size and retained identity cardinality. Do not weaken causal evidence merely to reduce row count. Measure and bound identity-bearing indexes separately, and perform a direct measurement on the real 8.8-million-record capture when that ignored artifact is available to the integrator.
