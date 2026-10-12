# Complete local PI status and ROM-entry observation

Base: 28cc04f978f5d4b4056cb9811d7b013f429b77d6. Claim: 6120273893.

The complete buffered CIC6105 twenty-million-call capture has matching repeated
v3/v5 sources and disabled/repeated checkpoint/messages. Independent Windows
hashes agree. Reuse the existing exact pinned ares9408cb43d4948fc3ea6e152a307a34348df3fe04
ISC sensor build; no additional emulator build or Actions run.

Canonical inspection initially rejected the source: `history requires bounded
v5 boot capture`. Fetch/map/driver accepted20million calls but the access-history
reader retained a separate1million ceiling. Set history MAX_BUDGET to the
canonical fetch constant; retain MAX_RECORDS100million, transaction/identity
limits and all matching headers/footers/source obligations. Six focused history
tests cover accepted maximum, mismatched budgets, zero/overflow/over-capacity,
report rechecking and unchanged record guard. Full fmt, strict locked workspace/
all-target Clippy, locked workspace, canonical CLI and diff gate pass.

Current-tree release canonical SP writer/fetch inspection and complete source
verification both pass. History has66,486,351 records and20million fetches:
PIF2055, SP841500, RAM19156445. ROM SHA256:
49acd3885f13b0730119b78fb970911cc8aba614fe383368015c21565983368d.
Firmware SHA256:
fa7b09795ef1e54461e59f6f2d902368133e3f1cd980e34383e6a780d74beffd.
V5 SHA256:
d0e2cf0ade942c4c4cf266bf9f8d6f4309ce0186e425fbadbcb1724b6f7889f1.
V3 SHA256:
a9009c34dfb5273f0ffc20b9746468aa9374c8d02a02884e4f856ce3382396ff.
Checkpoint SHA256:
3cc53c0a59790fa70b786afc8de4cb7cb85c7a8eb43be69cdf57eb29f217f810.
Reconstructed report SHA256:
f5ad41715a1bd3844c38c5d83daad20cdea7aedb1dced806b71d4d8554078b0a.

The existing one-MiB PI effects remain unchanged:524288 ROM half reads,
1048576 successful canonical-ROM-origin bytes, no unknown origins/failed sinks,
one returned transfer. Actual request1/token6 joins dispatch event1 and one
completion-status transition; requests_without_status is empty. Preserve
transfer_completion_certified=false: observed primitive linkage is not a general
guest completion or lifecycle certificate. PI effects SHA256 remains
76a689a126b15dd02ee81cc37f368f8422c51e1d17e2ff8212f55c07d6ab5797.

59154 captured SP writes supply compatible candidates for841500 fetches,
with no partial/contradicted candidates. Ordered candidate digest remains
a1fb25b148c8730a386920f755a2fe13f62996e35764c62e5ed98a969ac055ab.
Ultimate ancestry, mutation census, executable lifetime and native flags false.

The declared ROM entry is first observed at seq17527797, PCffffffff80000400,
physical0x400, cached, source unknown. Final checkpoint PCffffffff80003080,
PI busy0, exception0, Count81211040. Queue clock is not CPU Count. No claimed
hardware boot, whole-ROM coverage, installed executable ancestry or CLOSED scope.
Raw instruction/asset bytes, reports and repeated sources remain ignored local
artifacts under target/buffered-capture-primary/20m; no copyrighted assets in git.

This complete capture supersedes the prior unbuffered timeout as an observation
limit, while all earlier complete compatibility receipts remain valid. Partial
streams stay excluded. Next compose actual PI writers with RAM fill/consumption
using source clock and resident generations, retaining unknown lifetime/census.
No milestone promotion, raw research merge or branch-only CI scaffolding.
