# Fresh MP2 declaration reconciliation (ADR-0269)

Base: `8539c9738c2f05002fa011da728db85718de53f9`.
Worker: `mp2-fresh-analysis-14d72d1f`; issue #4 contains the claim/closeout.

## Reproduction and cause

The initial worktree had no target/native output or analysis cache. With current
main built locally, `SDL_AUDIODRIVER=dummy python scripts/native.py <local MP2>
--rt64 --seconds 30` stops in `infer-call-loads`:

```
plaid: copy-call map has stale load declarations; rediscover first
```

`apps/plaid/src/infer_calls.rs` compares mapped loads carrying `loads:` evidence
against the original parsed declarations with `same_load`. That comparison
requires exact size and execution address as well as source, encoding (including
replay entry), slot/fixed kind and relocatability. Discovery has already applied
ADR-0267, removing catalog text from fixed first-fetch replay loads.

Fresh infer-loads writes zero loads. Discovery finds 116 segment-table overlays,
157061 blocks and eight address-taken blockers. Copy-call inference adds nothing;
the neutral analysis-time harvest adds an AresBoot declaration at `0x801016c0`,
size `0x1360`, source zero, replay entry `0x80102800`. The next discovery trims it
to size `0x1140`, ending exactly at the catalog's linked text. The unchanged
original declaration then fails the stale-map size check.

The freshly harvested loads file and the previously retained file at
`X:/Plaid/target/win-oracle/target/native/marioparty2usa/loads.json` are byte-identical,
SHA-256 `05141f50814a21411cd062bb43dafca7d6061db24882859e2634c947d5adb070`.
There is no divergent inference result: explicit --loads exits the refinement
loop before infer-call-loads, hiding the mismatch. ADR-0258 removes inferred raw
slots superseded by a catalog; ADR-0263 preserves validated non-raw formats and
deduplicates sources. Neither causes this refusal. ADR-0267 changes the remaining
fixed replay's shape, and refinement must apply that same rule before comparison.

## General fix and verifier

Rebuild/hash-check the map's ROM images first using the existing rom_images
verifier. Add its discovered CatalogOverlay declarations to the current comparison
context, then call the existing exclude_replayed_catalog_text rule. Catalogs
carrying loads-file evidence are not copied from the map: they must match their
current declarations, preventing self-authentication. The existing exact
same_load comparison then checks the normalized declarations. Candidate overlap
and duplicate checks use that same effective context. No normalized slices are
written back into loads.json; the original replay witness remains intact.

No game address, name, checksum, runtime check relaxation, decoder or fallback is
introduced. Discovery, catalog source decoding, native text/data/BSS binding,
ambiguity refusal and executable-write revocation remain unchanged.

The authored Rust test catalog_trimmed_replays_match_only_the_same_current_declaration
covers prefix/suffix preservation and updated evidence IDs; removal, changed
entry/source/size/address/encoding, arbitrary sub-slices, nonbinding catalogs and
removed manually declared catalogs all refuse. Disabling normalization fails the
positive case (exit 101); removing the loads-evidence exclusion guard fails the
self-authentication negative (exit 101). Restored production code passes. The
existing CLI stale/foreign source tests remain part of the required CLI gate.

Direct same-input measurement: baseline refinement refuses in 1.188 s; fixed
refinement completes in 1.575 s and leaves loads.json byte-identical. This is
restored work, not a speedup claim; the existing single image reconstruction is
moved before reconciliation and reused for inference, rather than repeated.

## Fresh native validation

The empty-output MP2 pipeline completes in 476.421 s, including 30.714 s in
native validation: VI 1798, fault 0, fault_pc 00000000, graphics 2349/audio 1788,
PI DMA 2144. The 28-second capture visibly reads "Now then, please choose your
destination." The manifest records eight residual sites/native_complete:false.
Board gameplay and complete closure remain unverified.

Exact input command (local ROM path omitted here):

```
python scripts/native.py <MP2> --rt64 --seconds 30
  --press 0x1000@600:4 --press 0x1000@1250:4
  --press 0x8000@1360:4 --press 0x8000@1440:4 --press 0x8000@1520:4
  --press 0x8000@1600:4 --press 0x8000@1680:4 --press 0x8000@1760:4
```

A recording-only harness invokes the unmodified native.main with those CLI
arguments, capturing its subprocess stdout and elapsed times. It asserts the
output directory does not exist before starting. No --loads, retained map,
generated C, object files or save is supplied. The initial worktree analysis
cache is private; analysis-time ares retains its normal content-addressed replay
cache (whole ROM, exact sources, revision and arguments are in its key).

The first empty-output control, Paper Mario, completes in 371.309 s including
30.724 s native execution: VI 1798, fault 0/fault_pc 00000000. The acceptance
batch also runs fresh BK, MM, SF64 and OoT, each 30 seconds, then the requested
OoT 60-second save-load command with a copied local SRAM save:

```
python scripts/native.py <OoT> --rt64 --seconds 60
  --press 0x1000@1200:4 --press 0x8000@1400:4 --press 0x8000@1550:4
  --press 0x8000@1700:4 --press 0x8000@1850:4
```

Per-game full stop records, exact subprocess/CLI inputs, timings and manifest
are retained in ignored target/receipts/mp2-fresh/*-fresh.json and oot-save.json.
The issue #4 integration closeout records the complete final numerical results.
Acceptance requires all controls and the save-load reproduction to finish with
fault 0; a control failure blocks integration.

The full local gate runs on one frozen staged tree, checking its tree hash and
absence of unstaged changes before/after every command:

```
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace
python scripts/test_cli.py
python runtime/test_runtime.py
python tools/progress.py --check
```

Complete logs and command exits/timings are retained in final-gate.json and
gate-*.log in the same ignored receipt. Before the plain fast-forward push,
refetch origin/main, require it still equals the validated base, require the
new commit's direct parent/tree match that base/frozen tree, and run
`git merge-base --is-ancestor origin/main HEAD`. Main drift requires reconciliation
and a new exact-tree gate. README.md belongs to the integrator and is untouched.
All native/game processes use SDL_AUDIODRIVER=dummy with visible windows. ROMs,
saves and screenshots stay ignored. No shared shim rebuild, reference refetch,
recursive junction deletion or child agent is used. Before the fixed fresh run,
the worker verified that its exact MP2 output path was a real directory below
its own target/native, checked all descendants for reparse points, retained the
failing declarations/map in its ignored receipt, then deleted only that output.

The shared native-slice oracle has the pinned revision/driver but an older builder
recipe. For exact synthetic reference checks, this worker nonrecursively unlinks
only its own local oracle junction and copies the already-built current-recipe
oracle, build.json and license from the ADR-0268 worker into a private directory.
Revision, recipe, driver and binary hashes are checked. The shared oracle and
X:/Plaid/.refs remain untouched. Details are in oracle-setup.json.
