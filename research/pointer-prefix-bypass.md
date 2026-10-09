# Pointer-table guarded-prefix reachability bypass

Status: **VALIDATED**

Worker: `gpt56sol-pointer-prefix-bypass-20261009`

Research branch: `research/pointer-prefix-bypass-gpt56sol`

Canonical Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Pinned decoder/reference revision exercised by Cargo: Rabbitizer `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8` from `refs.lock.toml`.

## Question

Can the scalar pointer-table recognizer attach bounded pointer candidates to a dispatch even when another valid `ProgramMap` reachability fact enters the already-recognized dispatch prefix after the selected guard edge, thereby bypassing the guard and/or prefix state setup?

The narrow hypothesis was that `tables.rs::pattern` only rejected alternate reachability exactly at `block.start`, unlike the local constant-target certificate in `indirect.rs`, which rejects same-image/generation reachability anywhere inside its analyzed prefix. Therefore a valid entry, direct edge, indirect candidate, or indirect observation targeting `(block.start, jr_site]` could retain pointer-table evidence even though that target reaches the dispatch without traversing the selected guard path.

## Why this state is representable

`ProgramMap::validate` validates alignment, execution identity and evidence references for entries/edges/indirect facts, but does not require every reachability target to coincide with a current basic-block leader. A map produced by `direct_cfg` can therefore be augmented with a provenance-bearing mid-block reachability fact and still pass validation.

This is narrower than a blanket `discover_image` failure. The normal fixed-point pipeline feeds roots back through direct discovery, which repartitions an explicitly declared mid-prefix root into a new block leader before final analysis. The synthetic control below verifies that behavior. The bug is local certificate robustness on otherwise-valid `ProgramMap` inputs, which matters for composition/merge/reanalysis and for keeping proof obligations local and fail-closed.

## Fixture

The synthetic image uses this guarded scalar dispatch layout, with virtual base `0x80000000`, image `prefix-bypass`, generation `0`:

| PC | Word | Role |
|---|---:|---|
| `0x80000000` | `0x2c890003` | `SLTIU t1,a0,3` |
| `0x80000004` | `0x11200016` | selected guard branch |
| `0x80000008` | `0x00000000` | guard delay slot |
| `0x8000000c` | `0x3c088000` | recognized dispatch block start / base setup |
| `0x80000010` | `0x25080100` | base setup |
| `0x80000014` | `0x00045080` | index shift |
| `0x80000018` | `0x010a4021` | address add |
| `0x8000001c` | `0x8d080000` | pointer load |
| `0x80000020` | `0x01000008` | `JR t0` |
| `0x80000024` | `0x00000000` | jump delay slot |

The table snapshot at guest `0x80000100` contains `[0x80000040, 0x80000050, 0x80000040]`.

The test matrix injects same-image/generation reachability into the prefix through:

- entries at `0x80000010`, `0x80000014`, `0x80000018`, `0x8000001c`, and `0x80000020`;
- a direct edge targeting `0x80000014`;
- an indirect candidate targeting `0x80000014`;
- an indirect observation targeting `0x80000014`.

Controls cover an entry at `block.start`, an entry after the prefix at `0x80000040`, the same mid-prefix PC in generation `1`, a different image identity, and a normal `discover_image` root at `0x80000014`.

The deterministic classification reducer is `experiments/pointer_prefix_bypass.py`. Its 12-case canonical payload hashes to:

`16a6c103f695b5636e7e33280d2c97f989fc55f5514efe8320e6afdaf5298210`

The reducer only freezes the identity/range matrix. The Rust regression is the executable analyzer evidence.

## Baseline and falsification attempts

### Explicit baseline

Commit: `d8457b2ca43c5e02594e01ab23af5e348a02479e`

GitHub Actions run: `37917434904`

The baseline test intentionally asserted current unpatched behavior: after adding a provenance-valid entry at `0x80000014`, `ProgramMap::validate()` succeeds and `analyze_indirect()` still attaches pointer-table candidates `0x80000040` and `0x80000050`. The same binary also declared `0x80000014` as an input root to `discover_image` and confirmed the fixed-point pipeline repartitioned that address into a block leader and emitted no pointer-table candidates. The focused test and full `cargo test -p plaid-core` both passed.

This established that the reachable counterexample was a local-map/certificate issue rather than merely an invalid test map or a whole-pipeline discovery failure.

### Adversarial red matrix on unpatched recognizer

Commit: `e7692e0c9c06dab129ec14cceb0d864162e7ebe8`

GitHub Actions run: `37917606421`

Command:

```sh
cargo test -p plaid-core --test pointer_prefix_bypass -- --nocapture
```

Observed failures on the unpatched recognizer:

- first same-generation mid-prefix entry (`0x80000010`) retained one `plaid-pointer-table-candidates/v0` evidence object instead of zero;
- a same-generation direct edge to `0x80000014` retained one table evidence object;
- a same-generation indirect candidate to `0x80000014` retained one table evidence object.

The outside-prefix/different-generation control passed, and the fixed-point discovery-root control passed. The run therefore falsified the assumption that the existing `block.start` checks were sufficient for all valid `ProgramMap` reachability facts.

## Patch

Commit: `a2949639de59476a5139951fe482f5fd16f88be2`

`tables.rs::pattern` now defines a conservative same-image/generation prefix predicate:

```text
block.start.pc < target.pc <= indirect_site.pc
```

and rejects a pointer-table certificate when any of these target that interval:

- `map.entries`;
- `map.direct_edges[*].target`;
- any indirect site's candidate target;
- any indirect site's observed target.

The existing exact `block.start` rules remain intact. The selected guard's own direct edge to `block.start` remains permitted through the existing single-incoming-edge check. Facts after the prefix, from another generation, or from another image do not trigger this rejection.

This intentionally mirrors the dominance/bypass standard already used by the local constant-target certificate rather than inventing a stronger global policy.

## Harness correction during green-up

The first patched run, `37917674468`, compiled and showed four of five focused tests passing. The indirect-target test had already passed its important assertion that pointer-table evidence count was zero, but then incorrectly expected a pre-existing indirect candidate to survive `analyze_indirect` unchanged. The analyzer currently drops that candidate in this construction, which is unrelated to the guarded-prefix certificate question.

The test was corrected in `aa79f186b86ade2ab5de4f6d4777e8467219aee0` to assert the owned property: no table-derived `0x80000040`/`0x80000050` targets are acquired after the bypass fact. No production change was made for this harness correction.

## Final execution

Final evidence commit before this note: `9a94c73b5b557009392cbc881b402d6a2f235943`

GitHub Actions run: `37918043011`

Commands executed by the branch-only workflow:

```sh
python3 experiments/pointer_prefix_bypass.py
cargo test -p plaid-core --test pointer_prefix_bypass -- --nocapture
cargo test -p plaid-core
```

Deterministic reducer output:

```json
{"block_start":"0x8000000c","cases":12,"sha256":"16a6c103f695b5636e7e33280d2c97f989fc55f5514efe8320e6afdaf5298210","site":"0x80000020"}
```

Focused result: **5 passed, 0 failed**.

Full `plaid-core` suite: **passed**.

The build log also shows Cargo compiling the exact pinned Rabbitizer dependency:

`rabbitizer v1.16.2 (...?rev=724a49a5b4dbfb99f1a9e6992e63964fd29c90c8#724a49a5)`

No ROM, firmware, copyrighted game data, emulator patch, or generated trace was used.

## Instrumentation neutrality

The baseline and adversarial evidence are synthetic `ProgramMap`/`CodeImage` fixtures using the production analyzer. The production decoder dependency was not patched. The only production change under test is the conservative target-range rejection in `tables.rs`; the workflow and reducer do not alter analyzer behavior.

## Result

**VALIDATED**: on canonical base `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`, the pointer-table recognizer can attach table evidence to a valid `ProgramMap` whose same-image/generation executable reachability enters the recognized dispatch prefix after `block.start`, bypassing the selected guard/prefix path. Entry, direct-edge and indirect-target classes reproduce the issue. A local same-image/generation `(block.start, jr_site]` rejection closes the tested cases without rejecting the outside-range/different-generation controls, and the full `plaid-core` suite remains green.

Recommendation: **ADOPT**, but compose this change with the separate completed pointer-guard delay-slot/trap work rather than blindly cherry-picking competing `tables.rs` edits.

## Limitations / explicitly not proved

This result does **not** prove:

- pointer-table data immutability; `pointer_table_immutability_unproven` remains a real blocker;
- whole-ROM indirect-control-flow closure;
- that a shipped N64 title reaches this exact synthetic topology;
- that every merge/discovery path will construct the demonstrated post-partition map shape, only that the public validated map model admits it and the analyzer accepted it;
- preservation semantics for pre-existing indirect candidates across `analyze_indirect`;
- physical/cache/TLB alias immutability of table bytes;
- delay-slot exception/trap safety, which is a separate research result;
- hardware truth beyond the decoder metadata used by this synthetic pattern.

## Reproduction

Green branch head:

```sh
git checkout research/pointer-prefix-bypass-gpt56sol
python3 experiments/pointer_prefix_bypass.py
cargo test -p plaid-core --test pointer_prefix_bypass -- --nocapture
cargo test -p plaid-core
```

Red adversarial matrix:

```sh
git checkout e7692e0c9c06dab129ec14cceb0d864162e7ebe8
cargo test -p plaid-core --test pointer_prefix_bypass -- --nocapture
```

Explicit buggy-behavior baseline plus fixed-point control:

```sh
git checkout d8457b2ca43c5e02594e01ab23af5e348a02479e
cargo test -p plaid-core --test pointer_prefix_bypass -- --nocapture
cargo test -p plaid-core
```
