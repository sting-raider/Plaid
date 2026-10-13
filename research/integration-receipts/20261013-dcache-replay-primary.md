# Primary integration: reusable canonical D-cache state on the original clock

Base:b0b0df557e1ed71cc364a035abd8dcdcb18d4165. Claim:6151562152.
Harvest canonical dcache_writeback v0/v1/v2 and retained actual spike034,
pointer resident/read and store64 composition contracts (ADR0119/0121).
This is the prerequisite shared-state batch for decoded cached operands;
no separate cache policy or raw branch/scaffold merge.

Extract the exact existing primitive transition body into internal DcacheReplay.
Original transition bytes remain unchanged before/after extraction, SHA-256
05ec5c830b66cbc148bf9767ba4c3e74595dcff28795b9280790c3a8aa37932e.
Standalone v0/v1/v2 wrappers still authenticate the external complete source and
require contiguous ordinals. Internal containing-source callers own their full
authenticated global clock and pass strictly increasing original occurrences;
gaps for foreign observations never authorize stale/reused primitive identity.
Backing-read/fill pairing still requires actual adjacency. Resident generation,
mutation revision, full-line export, clean-lane origins, pending stores and all
existing validators are unchanged. Event count is primitive count, not last
global ordinal. A failed transition consumes state instead of allowing retry
against partially mutated storage. No performance improvement is claimed.

Fresh base validation before editing, then current validation, both retain:
five authenticated pointer/read cases with complete canonical report-set digest
e31ac3dff47c55b42140049691ee0b0b8e3d5a912a6633bde4cc6cd6ac7c17d1;
48 actual cached store64 cases/82 decoded attempts/34 backing exports, normalized
source-set digest7da79e147e7407d1e470ea2f19ef98ecfaab38f0d80b068a16d661e6838e0eda,
report-set3490160a258621875c88dbea21642513e62a8c5a424bb8b6854693cb6fb4ea32.
The exact retained pointer raw source6a1bdf2b2f59916ba32f9951db6bae2378eec4fa21854ceae0660970c222f0e9
and store64 source28d34bb07660e39fbed5b652d10d687c011622142ae4555828b08a50920bf7aa
remain authenticated by the existing scripts. No emulator/reference rebuild,
new sampling, full-ROM replay or Actions. Ignored logs:target/dcache-replay-*.

Focused17 Rust PASS: three shared-clock boundary regressions plus14 existing
v0/read/store64 regressions. Shared gaps preserve old resident origins despite
changed captured backing, with correct original read/fill/mutation clocks and
primitive counts. Stale/repeated/zero ordinals, nonadjacent fills, dangling
reads and standalone gap laundering reject. Five actual pointer cases/ten
fresh forgeries and48 actual store64 cases/150 source/report forgeries pass.
Existing source/report/input guards, full untouched-line origins and proof flags
remain exact. The v0 boundary is tested through its existing Rust API regressions;
it does not have an inspect-dcache-writeback CLI command.

Canonical gate on final tree: cargo fmt --all -- --check; strict locked workspace/
all-target Clippy; full locked workspace tests; python scripts/test_cli.py;
git diff --check. Corresponding issue4 closeout records final results, exact-head
CAS and fetched verification. DEVELOPMENT/ADR0119 describe internal reuse;
STATUS/NEXT/progress unchanged because no new supported scope or proof result
is supplied. Future shared consumers must bind actual decoded callbacks, full
control/register results and RAM writer snapshots to this state. Cached operand
definition/backing ancestry/dispatch/global source/census/lifetime/whole-ROM/
native remain OPEN; all flags false. No ROM/assets/upstream production reuse.
