# Accepted PI requests in the bounded boot chronology

Hypothesis: compose actual PI request, queue insertion/removal and CPU dispatch
scopes with the complete v1 buffered-copy stream while preserving every prior
source/checkpoint byte. Scheduling identity must come from actual successful
insertion and valid removal, never the nearest/last copy or equal event/deadline.

Status: **VALIDATED for the bounded primary research fixture**, 2026-10-09.
No production ProgramMap, general executable lifetime or native closure claim.

## Original optional implementation

`spikes/037-ares-boot-pi-queue-history/` emits research history v2 using the current
shared builder's layout-neutral callbacks and the validated queue sidecar. It
records accepted read/write MMIO scope before insertion/copy, actual queue heap
moves/outcomes, immediate valid-removal/CPU-dispatch boundaries, explicit copy-to-
request binding and actual PI status scope. Rows existing before capture retain
unknown token/request zero. Original reference object layout, accesses, clocks,
original handler calls and legacy v1 status metadata remain unchanged.

The reducer replays token moves and cancellations, enforces monotonic insertion/
request identities and rejects stale/removed identities. New scheduling records
cannot disappear through projection inside fetch or buffered-copy intervals.
Save preserves identity; the declared no-host-restore boot policy rejects a load
boundary. Generation/cut behavior is independently tested by component fixtures.
Record/request/token bounds keep the declared research inspection finite.

The shared formatter now accepts named start/finish and format/policy overrides,
with unchanged defaults. The 10,000-call rebuilt v1 default capture is exactly
byte-identical to the historical v1 trace, sidecar, checkpoint and messages.
The new 10,000-call preflight preserves every prior projection and checkpoint.
It executes no accepted PI requests, so it alone does not validate their join.

## Complete 610,000-call reproduction

Both reference recompilers remain disabled. Inputs are the same declared legal
systemtest ROM and supplied NTSC firmware; source digests/profile remain in the
raw headers and original prior notes. Original baseline, disabled, enabled and
repeated reported states/messages match. Repeated v2 sidecars are byte-identical.
Complete v1/v0/v5 byte comparisons and source/footer verification all pass.

- Raw v2: **8,823,189 records**, 1,572,151,304 bytes; SHA-256
  `ac2261edb74f90d00b11cecabe0f72e0bdbb3dd0aee1205c0f445221554b342d`.
- Complete v1 projection: **8,823,134 records**, 1,572,142,700 bytes; SHA-256
  `994d62686ff5d57a0a9a26ab6bc8454c6026d79c3bd069d1c921513431cfc7af`.
- Complete v0 projection: 656,507,083 bytes; SHA-256
  `2c84bd02adeb9bfef68e46dbc300df735c1c56b06240d951c36621204d43e07f`.
- Paired v5 SHA-256:
  `6213a9159efc5bca9e64c0ee2d4e5b2b866a0ba22a438626b28c84d99b1ec1c5`.
- All **1,638,808** prior successful PI writes retain exact canonical ROM origins;
  the origin/effect digest stays
  `12512b865aab077dc980c10b930adfb05cb9337f1a496189e1ecb0c4b943b1ae`.

Only 55 extra scheduling records are added: 26 queue, 14 dispatch boundary,
eight request boundary, four copy binding and three status scope records. Nine
successful insertions include non-PI work; accepted PI requests receive distinct
insertion tokens 6, 7, 8 and 9. Requests 1/2/3 have actual status witnesses under
the dispatch of tokens 6/7/8. Request 4 has no observed status at this budget.
All four synchronous copies return; that fact does not certify scheduled status.
The final busy flag remains asserted, with the original baseline checkpoint.

Twelve synthetic forged scheduling histories and four forgeries against the
actual retained stream are rejected. A separate full raw replay rechecks every
scheduling record using the final reducer. Synthetic scheduling tests claim no
byte origins; complete legacy source validators separately prove those effects.

## Scope and next step

This demonstrates actual request/dispatch bookkeeping in this pinned boot prefix.
It does not prove N64 hardware timing, guest-suite completion, PBUS destination
lineage for PI reads, arbitrary cancellation/reentrancy/restore behavior, general
cache/copy/mutation completeness, executable lifetimes or whole-ROM closure.
The component fixtures supply separate canceled/rejected/unbound/read/load cases.

The original strict Rust v2 API now streams typed scheduling records into the
unchanged strict v1 consumer, preserving exact canonical v1/v0 serialization and
complete paired-v5/input checks. Its report binds the raw v2 digest and all
request/outcome/status facts; the rechecker reconstructs the entire nested report.
Observed slot identity is not a full heap emulator or hardware timing model.
Six original Rust integration tests cover equal deadlines, cancellation, save,
load rejection, failed insertion with copy effects, unknown pre-capture and unbound
entries, read/direct status, malformed wire fields, raw interval laundering and
source/report tampering. Legacy consumers still reject v2.

The complete 8,823,189-record capture passes both API inspection and source
rechecking. Every count/status link agrees with the independent Python result;
the entire nested Rust v1 report is equal to its retained prior report. The new
3,156-byte pretty JSON report SHA-256 is
`34a2f880cb2164b2e8d1fef47ed757dd8fa31a9a8c40163ddf5d968987c4e96f`.
Request 4 remains without an observed status; this does not claim queue liveness.
All native/guest/transfer completion flags remain false. Generated reference
sources, ROM, firmware and trace data remain isolated and ignored.

The existing strict Rust v1 API independently rechecks the entire projected
source and reproduces report SHA-256
`93ec36ff03f592a3e5c82b6c7b942502dbcd9e002bd27c1a6d7da1262e26620b`.
Its CLI rejects the new v2 raw input and creates no report, retaining version
separation until the original typed v2 consumer is implemented.

The separate `inspect-pi-queue-boot-history` and `verify-pi-queue-boot-history`
commands expose this finite report without altering old-version consumers or the
solver. Synthetic CLI tests reproduce canonical ROM byte-order equivalence,
complete source/report binding, malformed identity/truncation rejection and
protection of all four supplied inputs. Use these commands with the retained
v2 sidecar and paired fetch source to reproduce the complete API result.
