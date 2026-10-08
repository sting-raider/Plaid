# Spike 018: ares I-cache reset/restore lineage boundary

Verdict: **PARTIAL** (source-backed counterexample + executable contract model; pinned full-core harness prepared but not executed in this sandbox).

Base Plaid commit: `3cf45dc323cbcd9e6463ccc781d3de093a433097`  
Pinned ares revision: `9408cb43d4948fc3ea6e152a307a34348df3fe04`

## Hypothesis

A CPU/cache reset must end every previously observed I-cache fill lineage. A savestate restore can then repopulate a valid I-cache line directly from serialized state, without a contemporaneous backing read or completed cache fill. Therefore tag/index/payload equality is insufficient to connect a post-restore fetch to any pre-restore fill.

## Pinned-source contract

At the pinned ares revision:

- `CPU::InstructionCache::power()` clears every line tag and all eight resident words.
- `CPU::power()` invokes `icache.power(reset)`.
- `CPU::serialize()` serializes each I-cache line's `tagKey`, `index`, and `words`.
- the nall serializer is bidirectional; its read mode overwrites fields from serialized bytes.
- `System::unserialize()` for a synchronized snapshot first calls `power(false)`, then deserializes the complete system including RDRAM and CPU state.

Thus a valid line can appear *after* a reset through restore, with no post-reset `Line::fill()` and therefore no completed-fill callback.

## Adversarial experiment

`contract_model.py` executes the minimum state machine implied by those exact source operations:

1. fill line 0 with instruction A (`0x24100001`) => fill 1;
2. snapshot the resident line;
3. invalidate/refill the same bytes => fill 2, deliberately equal in tag/index/payload;
4. power/reset the line => invalid, zero resident words, no fill;
5. restore the saved line => valid instruction A, still no fill;
6. run the existing spike-012 tuple/payload matching rule conceptually: it selects historical fill 2 even though restore, not fill 2, created the current resident line;
7. change current backing to instruction B (`0x24100002`): cached resident A and current backing B diverge;
8. reset again and fetch: a new fill 3 is required and obtains B.

Local deterministic command:

```sh
python3 spikes/018-ares-cache-reset-restore/contract_model.py
```

Observed SHA-256 in this session:

- model: `c5c3dd0dd41bcef6eea94d727236332d1824b60c1d82edaaae64621db8fbe83c`
- result JSON: `3d0f32954a25ce5616f49ddf21967fc5dbce7168d53e6f5038af0d03954fdbe0`

The model reports `naive_post_restore_join = 2` and `naive_join_is_pre_reset = true`, then requires fill 3 after the next reset.

## Pinned ares harness

`fixture.cpp`, `baseline.cpp`, `driver.cpp`, and `run.py` prepare the corresponding full pinned-reference experiment. The traced path deliberately leaves the existing fill observer's external `lastCacheFill` table untouched across `System::unserialize()`. The saved line comes from fill 1, an equal-payload fill 2 occurs later, restore recreates fill-1 cache state after `power(false)`, and the old tuple matcher consequently returns fill 2. After a backing mutation, cached and uncached fetches execute different instruction values; `icache.power(true)` then forces a third fill.

Run where `.refs/ares` is available:

```sh
python3 spikes/018-ares-cache-reset-restore/run.py
```

The runner builds an uninstrumented baseline and an instrumented pinned ares binary, requires byte-identical repeated traced JSON, and requires the complete reported guest/cache state to match baseline. This full reference execution could not be performed in the current sandbox because outbound Git access is unavailable and no local `.refs/ares` checkout is mounted. That limitation is why the verdict is PARTIAL rather than VALIDATED.

## Architectural implication

Do not carry a completed-fill identity through reset or restore merely because the selected line later has the same slot/tag/index/words. Reset is a hard lineage boundary. Restore needs its own provenance event/capture identity; absent that, post-restore resident-byte origin must remain unknown until a new witnessed fill replaces the line. For save/restore-based exploration, restored RDRAM/cache bytes belong to the snapshot lineage, not to the pre-restore live transaction chronology.
