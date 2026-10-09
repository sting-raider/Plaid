# CPU XORI transform -> D-cache -> I-cache -> executable fetch

This bounded research spike composes two previously validated Plaid research primitives:

1. exact interpreted CPU `LW/LWU -> XORI -> SW` def-use provenance;
2. cached executable mutation visibility through D-cache writeback and later I-cache refill.

It does **not** claim whole-ROM closure, arbitrary dataflow, or hardware-wide cache semantics.

## Hypothesis

For exact pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, a later cached instruction fetch may inherit the CPU transform provenance only through a causal chain of distinct generations:

```text
successful source backing read
-> load/GPR generation
-> explicit XORI transform generation
-> cached SW / D-cache resident generation
-> successful D-cache writeback / backing generation
-> later I-cache fill from that backing generation
-> I-cache resident generation
-> instruction fetch from that resident generation
```

Matching payloads are deliberately insufficient. In particular:

- the fixture performs an equal-valued decoy source load before the real load;
- `XORI 0` is an identity-valued transform but must remain a distinct generation;
- a valid old I-cache line remains stale after both the cached store and D-cache writeback;
- an invalidate/refill **before** writeback captures old backing and remains stale afterward;
- a later uncached same-value backing store can replace the transform writeback generation without changing final instruction bits.

## Files

- `driver.cpp` executes real decoded CPU instructions and real ares D-cache/I-cache behavior without patching the reference emulator.
- `run.py` checks exact pinned source/blob identities, builds the headless exact-reference fixture, runs it twice, and checks deterministic scenario facts.
- `model.py` is a separate generation replay, not an emulator. It carries explicit source/transform/resident/backing generation identities and rejects forged histories.

## Executed scenarios

The exact fixture uses synthetic instructions only:

- old target: `0x24020001` (`ADDIU v0,zero,1`);
- new target: `0x24020002` (`ADDIU v0,zero,2`);
- transformed source for `XORI 0x00ff`: `0x240200fd`;
- identity transform source for `XORI 0`: `0x24020002`.

Each scenario first fills I-cache with the old target, then executes real helper instructions:

```text
LW    t1,0(s3)      # equal-valued decoy source
LW    t0,0(s1)      # actual source
XORI  t0,t0,imm
SW    t0,0(s0)      # cacheable executable destination
CACHE 0x19,0(s0)    # D-cache hit writeback
CACHE 0x10,0(s0)    # I-cache hit invalidate
```

The foreign-writer scenario additionally executes `SW t2,0(s2)` through the uncached alias after the transform writeback, storing the *same* instruction bits. The prefill scenario instead invalidates/refills I-cache before the writeback and proves that this valid resident line stays old afterward.

## Replay adversaries

`model.py` rejects at least these forged histories:

1. equal-payload decoy substituted as the XORI input generation;
2. `XORI 0` generation collapsed into its load generation;
3. post-writeback fill forged to read the old backing generation;
4. pre-writeback fill forged to read a future writeback generation;
5. same-value foreign writer erased so the fill is falsely attributed to the transform writeback;
6. a backing generation forged directly as an I-cache resident generation;
7. writeback deleted while the later fill claim is retained;
8. same-value backing writers reordered without repairing dependent generations.

The model also contains a deliberate payload-only false positive: in the foreign-writer history, final fetched bits equal the earlier XORI output even though the actual I-cache fill ancestry ends at the later foreign backing writer.

## Reproduction

With the repository branch checked out:

```sh
mkdir -p .refs
git clone https://github.com/ares-emulator/ares.git .refs/ares
git -C .refs/ares checkout 9408cb43d4948fc3ea6e152a307a34348df3fe04
python3 -m py_compile spikes/045-ares-xori-cache-fetch-compose/model.py \
  spikes/045-ares-xori-cache-fetch-compose/run.py
python3 spikes/045-ares-xori-cache-fetch-compose/model.py
python3 spikes/045-ares-xori-cache-fetch-compose/run.py
```

The branch-only workflow performs the same exact-pin execution on GitHub Actions. Results and hashes are recorded in the durable research note after execution.
