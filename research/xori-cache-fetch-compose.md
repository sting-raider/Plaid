# CPU XORI transform -> cache residency -> executable fetch composition

Date: 2026-10-10

Result: **VALIDATED** for the bounded composition described below.

Worker: `gpt56sol-xori-cache-fetch-compose-20261010`

## Exact revisions

- Plaid canonical base: `211176e7a489fecf8331d02915ee982cd279cb62` (`main` at claim time and still current after the first evidence run).
- Research branch: `research/xori-cache-fetch-compose-gpt56sol`.
- Exact ares revision from `refs.lock.toml`: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.
- First successful evidence head: `1f957f5aee31217ab9b6ac4198b249cd7ed8c093`.

This work composes two completed research results rather than introducing a new emulator semantic assumption:

- `research/cpu-xori-transform.md`: exact interpreted `LW/LWU -> XORI -> SW` def-use provenance, including identity-valued `XORI 0` and equal-payload decoys;
- `research/cached-code-patch-visibility.md`: cached CPU executable mutation remains distinct from backing mutation and I-cache fetch visibility.

## Question

Can an exact CPU-source generation remain causally attributable to a later executable fetch after an ALU transform, cached store, D-cache writeback, I-cache replacement/fill and fetch, without ever reconstructing provenance from payload equality?

The dangerous shortcut is a transitive value rule such as:

```text
source_value XOR imm == final_fetched_value
=> final fetch came from that source
```

That rule is unsound even when every intermediate payload happens to match. The bounded safe rule tested here is a chain of explicit parent generations:

```text
successful source backing generation
-> exact load/GPR generation
-> explicit XORI transform generation
-> cached SW / D-cache resident generation
-> completed D-cache writeback / backing generation
-> later I-cache fill from that exact backing generation
-> I-cache resident generation
-> fetch from that exact resident generation
```

Any intervening writer or stale resident line must change or terminate that chain even if all visible bits are equal.

## Durable artifacts

- `spikes/045-ares-xori-cache-fetch-compose/driver.cpp`
- `spikes/045-ares-xori-cache-fetch-compose/run.py`
- `spikes/045-ares-xori-cache-fetch-compose/model.py`
- `spikes/045-ares-xori-cache-fetch-compose/README.md`
- `.github/workflows/research-xori-cache-fetch-compose.yml`

No production Plaid file and no pinned-reference source file is modified.

## Exact pinned-source guards

The runner checks exact ares HEAD and a clean reference tree before and after execution. It also guards the same source objects established by the earlier cache-visibility work:

| ares source | Git blob |
| --- | --- |
| `ares/n64/cpu/cpu.hpp` | `b51000d99e1e8818ad04a8c747a8170b0e98fae8` |
| `ares/n64/cpu/dcache.cpp` | `4de28e0ad9566d31f47210a997c22fa994785d26` |
| `ares/n64/cpu/memory.cpp` | `f362ef67ab41ccf57330bbedd6f614e07a61dd17` |
| `ares/n64/cpu/interpreter-ipu.cpp` | `938ccbd0af1f127439d9859c1fd6be2bbd5222a3` |
| `ares/n64/rdram/rdram.hpp` | `c718ec2e9b2a78610353562cbc81dd973b278ee2` |

The runner additionally asserts exact decoder/implementation text for `LW`, `XORI`, `SW`, I-cache hit invalidate and D-cache hit writeback before building.

## Exact executable fixture

The unmodified pinned ares interpreter executes synthetic real CPU instructions with both recompilers disabled and controlled identity RDRAM. Four target lines are independent and caches are reset between scenarios.

The executable target starts as:

```text
0x24020001  ADDIU v0,zero,1
```

The desired transformed instruction is:

```text
0x24020002  ADDIU v0,zero,2
```

For the non-identity transform the source word is `0x240200fd`; `XORI 0x00ff` produces `0x24020002`. Each scenario executes:

```text
LW    t1,0(s3)      # equal-valued decoy source
LW    t0,0(s1)      # actual source
XORI  t0,t0,imm
SW    t0,0(s0)      # cacheable executable destination
CACHE 0x19,0(s0)    # D-cache hit writeback
CACHE 0x10,0(s0)    # I-cache hit invalidate where applicable
```

The foreign-writer scenario additionally performs a successful uncached `SW t2,0(s2)` of the *same* `0x24020002` bits after the transform writeback and before the final I-cache fill.

The prefill scenario invalidates and refills I-cache before D-cache writeback, then deliberately leaves that valid old resident line in place after backing changes.

The identity scenario loads `0x24020002` and executes `XORI 0`; source and transformed bits are equal by construction.

## First evidence run

GitHub Actions run `38005375714`, job `114072832880`, completed successfully on Ubuntu 24.04 at branch head `1f957f5aee31217ab9b6ac4198b249cd7ed8c093`.

The exact-reference executable ran twice with byte-identical stdout. Canonical facts hash:

```text
EVIDENCE_SHA256=707e06fecb81975e8e611b13cfc55f6cdc28ab1916975f8ab105eaf083e51910
```

The pretty `evidence.json` file SHA-256 was:

```text
9f7f571b9eb0229d27cd9af76b9e8445b6060170ad5bc8f7645b2322494fc068
```

Observed facts were:

```json
{
  "exception": 0,
  "foreign_after_store": 1,
  "foreign_after_writeback": 1,
  "foreign_backing": 604110850,
  "foreign_final": 2,
  "foreign_icache": 604110850,
  "identity_backing": 604110850,
  "identity_final": 2,
  "identity_source": 604110850,
  "identity_transform": 604110850,
  "normal_after_store": 1,
  "normal_after_writeback": 1,
  "normal_backing": 604110850,
  "normal_final": 2,
  "normal_icache": 604110850,
  "normal_source": 604111101,
  "normal_transform": 604110850,
  "prefill_after_store": 1,
  "prefill_after_writeback": 1,
  "prefill_backing": 604110850,
  "prefill_final": 1,
  "prefill_icache": 604110849
}
```

Here `604110849 == 0x24020001`, `604110850 == 0x24020002`, and `604111101 == 0x240200fd`.

The behavioral conclusions are therefore direct:

1. **Normal transform:** after the cached transformed store, the target still executes old code (`v0=1`); after completed D-cache writeback it still executes old code; only the later invalidate/refill executes transformed code (`v0=2`).
2. **Same-value foreign writer:** transformed writeback is followed by another successful backing writer with exactly the same `0x24020002` payload; the final refill/fetch still executes `v0=2`, so final payload cannot reveal which backing generation supplied it.
3. **Refill-before-writeback:** I-cache refills old backing before the transform writeback; after backing becomes `0x24020002`, the valid resident line remains `0x24020001` and final fetch still executes `v0=1`.
4. **Identity transform:** source and XORI output are both `0x24020002`; the final post-writeback refill executes `v0=2`, while generation replay preserves a distinct XORI node despite unchanged bits.

## Independent generation replay

`model.py` is deliberately not an emulator. It replays only the source-established contracts and requires every transition to name its exact parent generation.

The model was executed twice and both stdout and report files were byte-identical. Its canonical compact report hash was:

```text
MODEL_SHA256=d49f6730ae0d81bfe7dd38476e97419a174fbfb8e354d7f098080e89c069b2a4
```

The pretty `model-report.json` file SHA-256 was:

```text
4908c05d000b056b151359ebdc3c4ddfdb19d20de91272f63c2f9fbb34fb2836
```

The decisive ancestry chains were:

| Scenario | final resident ancestry | transform generation included? |
| --- | --- | --- |
| normal | `[10,9,8,7,6,2]` | yes (`7`) |
| identity `XORI 0` | `[10,9,8,7,6,2]` | yes (`7`) |
| same-value foreign writer | `[11,10]` | **no**; `10` is the foreign writer |
| pre-writeback refill | `[9,1]` | **no**; `1` is old program backing |

The same-value foreign case is the explicit falsifier for payload-derived transitivity: the final fetched word equals the earlier XORI result, but the actual replay ancestry terminates at the later foreign backing writer. The model reports `naive_payload_false_positive=true`.

## Forged-history rejection

Eight adversarial histories are rejected:

1. equal-payload decoy load substituted as the XORI input generation;
2. identity-valued `XORI 0` collapsed into the preceding load generation;
3. post-writeback fill forged to read an older backing generation;
4. pre-writeback fill forged to read a future writeback generation;
5. same-value foreign writer erased so the fill falsely inherits the transform writeback;
6. a backing generation forged directly as an I-cache resident generation;
7. the D-cache writeback removed while the later fill claim is retained;
8. same-value backing writers reordered without repairing their dependent generations.

All eight fail closed even though several retain payloads compatible with the desired result.

## Evidence artifact

Run `38005375714` uploaded artifact `11651390568` (`xori-cache-fetch-compose-evidence`). The artifact ZIP SHA-256 reported by Actions was:

```text
f29944a767893fa3fb3e8553003bb1e8d9f5efa58bb3ee502a979ac544cab531
```

## Result

**VALIDATED** for this bounded composition.

Independent source/transform/cache facts can be composed soundly only when each edge names the exact generation it consumes and produces. This makes composition monotonic under same-value events: an identity-valued transform still creates a transform generation; a same-value backing writer still replaces backing ancestry; a stale I-cache resident remains tied to the older fill generation; and a later writeback does not retroactively rewrite that resident's provenance.

The result specifically rejects any proof rule that joins stages by payload equality, by current backing contents, or merely by the existence of an invalidate somewhere in history.

## Closed-world impact

A future executable-lineage certificate can safely compose CPU transformation evidence with cache-visibility evidence if it retains typed generation identity through every join:

- exact source storage generation;
- load/register generation;
- transform generation and expression;
- D-cache resident generation/revision;
- completed writeback backing generation;
- I-cache fill parent backing generation;
- I-cache resident generation;
- fetch-to-resident identity.

If any required parent is missing, ambiguous, replaced by an untracked writer, or only value-compatible, the executable origin must remain UNKNOWN/OPEN. Same-value operations are not removable from history.

This reduces one composition uncertainty, but it does **not** make `Scope::WholeRom` closable by itself.

## Remaining gap

This result is intentionally narrow:

- The exact composed fixture is uninstrumented and establishes real pinned-ares instruction/cache behavior and chronology; the explicit generation ancestry is replayed from already validated causal primitives. A future production observer still needs one unified measured event stream if Plaid wants to issue the same certificate directly from emulator execution.
- Only aligned Word `LW -> XORI -> SW` with uncached KSEG1 source and cacheable KSEG0 identity-RDRAM destination is covered.
- No arbitrary register dataflow, decompression, relocation, partial/64-bit/COP1/LL-SC stores, TLB aliases, reverse-endian paths, overlays, interrupts, reset/NMI, save/restore, PI/SP DMA, RSP producers, or concurrent writers are proven here.
- The foreign same-value writer is a controlled CPU uncached store, not an exhaustive mutation census.
- Exact pinned ares is a behavioral oracle, not hardware truth. No independent emulator or physical N64 was executed for this whole composed chronology.
- No production Plaid certificate type or solver obligation was implemented on this branch.

## Integration recommendation

**ADOPT the evidence model, not the fixture recognizer.** Production provenance should represent transformations, cache residents and backing mutations as typed generation nodes with explicit parent identity. Do not infer a transitive source from equal values or algebraic compatibility. A same-value writer or identity transform is still a real causal event. If a later fill consumed a different backing generation, prior transform ancestry ends there even when the instruction bits are identical.

The primary integrator may cherry-pick/adapt the standalone replay as a regression/specification artifact. The branch should not be merged wholesale merely to preserve the research workflow.
