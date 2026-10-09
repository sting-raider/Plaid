# RSP vector load/store byte-lane lineage

**Result: PARTIAL**

Canonical Plaid base inspected before the experiment:
`ae41bdba82993ec8e77f47e5f9d3bb9af06f9256` (`main`).
Tested research head before this note: `abed01fdaa124815d6418298254649f58845195e`.
Exact upstream pins: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`;
Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`.

## Question and hypothesis

Question: after RSP vector DMEM loads, can provenance be represented as one origin
for a whole 128-bit vector register, or must producer identity be retained at
byte-lane granularity through later vector stores?

Hypothesis: for the bounded `LQV`/`LRV` -> vector register -> `SQV`/`SRV` path,
exact per-byte lineage requires the ordered source reads and the vector register's
per-byte generations. Numeric equality is insufficient. Partial loads must retain
old origins in untouched lanes, equal-valued later loads must replace the origin of
lanes they actually write, and intervening `MTC2` writes must cut only their two
written lanes.

## Baseline

Main already has actual RSP DMEM sink sensing (ADR-0077): completed scalar/vector
stores can be associated with decoded RSP instruction contexts, including
same-value stores. That work explicitly does not establish ultimate source
producer identity. The missing link here is the vector-register dataflow between
a DMEM read and a later DMEM store.

At the exact ares pin, guarded source shows:

- `LQV` writes only `element .. min(16 + element - (address & 15), 16)`;
- `LRV` aligns the source address down to 16 bytes and writes only its derived
  trailing vector lanes;
- `SQV` emits the selected vector lanes until the next 16-byte memory boundary;
- `SRV` aligns the destination down and remaps the selected vector lanes;
- `MTC2` writes two adjacent vector bytes except at element 15.

The exact Gopher64 pin independently implements the same bounded lane formulas in
`src/device/rsp_su_instructions.rs` (blob
`4afc4c9886bf85759e12f61769acbe84a7e33898`). This is independent source
corroboration only, not an independently executed oracle or hardware truth.

## Experiment

No reference instrumentation was required. The fixture executes actual decoded RSP
instructions under exact pinned ares with the RSP recompiler disabled and compares
the resulting vector register and DMEM bytes against a project-owned byte-lane
replay model. The reference is run twice and stdout must be identical.

Six deterministic fixtures attack the model:

| case | adversary | required lane result |
| --- | --- | --- |
| `aligned_lqv_sqv` | ordinary full load/store | all 16 lanes come from the load |
| `partial_lqv_sqv` | `LQV 0x205,e=3` | lanes 0..2 and 14..15 retain pre-load origins; 3..13 come from DMEM |
| `equal_decoy_latest_load` | equal bytes at 0x400 and 0x500; load A then B | stored bytes equal A and B, but all lane generations are B |
| `lrv_srv_effective_span` | nominal bases `0x60b` / `0x70b` | reads `0x600..0x60a`, writes `0x700..0x70a`, lanes 5..15 |
| `mixed_same_value_no_diff` | initial vector, both sources, and destination all `0x44` | final bytes remain all `0x44`, yet lanes 0..2 are initial, 3..4 source A, 5..15 source B |
| `mtc2_clobber` | full load, then decoded `MTC2 r4=0xcafe,e=6`, then store | only lanes 6..7 switch to `ca fe` / GPR origin |

The replay also performs 4,096 deterministic equal-payload trials. All 4,096
change source generation while leaving vector values indistinguishable by content;
4,057 exercise a partial load that leaves mixed old/new origins in one vector.

## Executed observations

Final GitHub Actions run `37921935199` on Ubuntu 24.04 checked out research head
`abed01fdaa124815d6418298254649f58845195e`, fetched both exact pinned references,
verified the ares interpreter/decoder blobs and the Gopher64 RSP source blob, built
and executed exact pinned ares from clean source, and uploaded the evidence.
Syntax/model/source guards passed, the decoded reference fixture passed, a second
reference execution was byte-identical, and all six reference vector/DMEM outputs
matched the replay model. Earlier clean run `37921653332` produced the same result,
reference-stdout and model hashes.

Evidence hashes from the final cross-reference run:

- results JSON SHA-256:
  `b67edae8dd4a0eb3fd0e7e0abe6117e8f89da495bccb77a6c196b10786d7e46d`
- exact-reference stdout SHA-256:
  `d7340441045beab810b9247d10532078da3ac09b012eb7efb15608c3b8ec5652`
- replay/model SHA-256:
  `afe4f5549b16c3be78088b1b4a109c1646b9c7f3b10da7f11244848fe4e212a3`
- uploaded evidence artifact ZIP SHA-256:
  `03f01f3c1abd53346cd79897acaa9a06faae32b27767c54c2d3c50c7d40f4ec0`

The strongest counterexample is `mixed_same_value_no_diff`: all 16 destination
bytes are `0x44` before and after, and all vector bytes are also `0x44`. Numeric
state therefore contains no information that can distinguish the three required
producer generations. Ordered lane events do. A verifier that selects origin by
matching payload can attribute the same final bytes to multiple incompatible
histories and is unsound for provenance.

## Reproduction

```bash
# refs.lock.toml pins must be checked out at .refs/ares and .refs/gopher64
python3 spikes/043-ares-rsp-vector-load-store-lineage/model.py
python3 spikes/043-ares-rsp-vector-load-store-lineage/source_guard.py .refs/ares
python3 spikes/043-ares-rsp-vector-load-store-lineage/gopher_source_guard.py .refs/gopher64
python3 spikes/043-ares-rsp-vector-load-store-lineage/run.py
```

The branch workflow `.github/workflows/research-rsp-vector-load-store-lineage.yml`
fetches both exact pins and performs the same checks from a clean runner.
Generated executables, copied reference notices/source and result JSON remain under
ignored `target/` paths; no ROMs or upstream source are committed.

## Result and integration guidance

**PARTIAL.** The bounded lane-state rule is strongly supported: whole-vector
single-origin provenance and value-only origin recovery are both invalid for these
paths. Any future causal RSP producer tracker that covers `LQV`/`LRV` and
`SQV`/`SRV` should maintain at least byte-lane origins for vector registers and
apply partial writes/clobbers exactly, including same-value generations.

However, this experiment intentionally does **not** observe completed DMEM reads
with a runtime callback. Read addresses are derived from guarded exact-pin
interpreter semantics plus the actual executed instruction inputs. Therefore it
does not yet prove an end-to-end runtime evidence schema linking a concrete DMEM
producer generation through a successful read event into the vector lane and then
to ADR-0077's concrete store sink.

It also does not prove all RSP vector memory families, vector ALU transformations,
DMA/CPU producer ancestry, IMEM executable transfer, executable lifetime,
hardware timing, hardware truth, whole-ROM reachability, or native-complete
closure. Emulator/source agreement must not be promoted into an N64-wide
invariant without stronger oracle/hardware evidence.

**Recommendation: ADOPT** the byte-lane vector-origin requirement as a design
constraint, but **INVESTIGATE** a completed-read sensor / end-to-end event replay
before treating the bounded path as ultimate executable-byte provenance.
