# Primary integration: exact IMEM read parents feed performed RSP instructions

Base:77388a5316d97b9196fff3b00d51ed7607b2c179. Claim:6169995873.
Compose canonical spike042/060 performed-instruction evidence with the shared
SP writer state and raw PI/RAM/IMEM parents. No new standalone lineage consumer
or writer-selection policy is introduced.

The initial PC-only candidate is rejected before landing. Pin inspection proves
JR/JALR retain low logical PC bits while Word reads mask their address. A performed
prologue alone supplies no exact read occurrence. The final opt-in recipe records
both original returned Word reads, including lookahead, and returns each global
raw-clock read ID. Performed instructions carry that ID through begin/end.
Parents freeze at the actual read, before later mutations or installations.
Logical PC, actual read address and masked offset remain separate. Missing/stale/
foreign/mismatched read identities, incomplete pairs, invalid geometry, CPU-fetch
interleavings and legacy-source admission reject. Unused lookahead supplies no
execution occurrence, and unknown code roots remain explicit samples.

The pin can perform a paired VNOP after MTC0 sets HALT; retain actual begin/end
status rather than excluding that observed instruction. New optional RSP
consumption/report-v2 fields retain every read/begin/end occurrence in the digest,
with compact discrete samples. V7's containing SP projection is report-v3. Earlier
paths and serialized fields remain unchanged when unselected; all census/lifetime/
native flags remain false. No extra guest read or reference object field is added.

Focused CLI/independent graphs retain repeat identities, equal changes before and
after the read, frozen parents across later installs, unaligned logical PCs,
wrapped lookahead address4096/offset0, unknown roots, permanent contradiction cuts,
status observations, unused lookahead and refusal to borrow equal discarded reads.
Malformed source and forged/deleted report identities/digests reject. The recipe
check proves exact default generated shadows against the retained v6 build after
output-path normalization, and exactly two original read sites in the new variant.

Fresh pinned ISC ares9408cb43 controls perform identity/translated PI copying,
RAM/IMEM installation and actual RSP execution of the installed words. Guest JR
demonstrates logical3/7/11 versus aligned0/4/8. MTC0/VNOP demonstrates begin-HALT1
for a performed second instruction. The222-event source contains32 reads,
24 performed instructions and8 unused lookaheads. All28 full machine/backing
checkpoints agree baseline/disabled/enabled/repeat, including full reported RSP
register/vector/pipeline/timing/DMA/status state. Explicit descriptor/mapping/
register/IMEM-seed/component-step controls stay opaque. No register/task ancestry,
hardware consensus or continuous lifetime follows.

Actual source SHA-256:
07714b7b947374377de049643d765b82618be2d8a68030dd25cf354428c8eaa4.
Baseline/disabled SHA-256:
e0bc519accfd98e7e816b59bf1074748adb0ca70816ce8976adef646356c8518.
Reference receipt SHA-256:
06c150769cdb810b750a7311ae000b36c4f5059c5ff59684f1e12c2d7d01321a.
Baseline/sensor build SHA-256:
5d4c341cee89dff1366dc5ea43b24101f0ce5b46c69427af29f0b8fa3984fdab and
bb36067bccc857c0af515122116b1cd3846de0f1e16494f10b54ed863b259e46.
Executable hashes and the bounded control artifact set are pinned in that receipt.
The earlier aligned trial is not presented as the final gate.

The actual supplied100k v7 producer preserves the entire424,660-record legacy
body byte-for-byte, including1,008 DMEM effects. There are no performed RSP
instructions in this early commercial prefix. Complete canonical/independent
replay agrees on100k fetches and no PI ancestry, with ordered digest
bf9653cea12e9546e33724f4c32603455b467324554bdcbfcdbabf3cf5ff1ad8.
Only the containing source hash/version differ from the earlier complete report.
Source SHA-256:
673e3766d2c90782aa762986b8fa155fe9a83b85f87f70c28c6a28d9eb516356.
Fetch/checkpoint SHA-256 retaince66498314c58b448fc95ecd4ef8adbd795e83c60c9ac5e49189e4406f8039a4
andc79e2c3f287ea017794e59315cbb95b403568db00a86e4bea045487f9e51ed42.
Capture receipt/build SHA-256:
244a5fe7f12d22d931473e8db6c8108e3f1a3b363853df7b3ba948617f1b9e8c and
220a9d8b6cc39efd7eebeb1cca0eaf8bb5d3e2af2491f223af836ae3419b1452.
Canonical/independent report SHA-256:
2dff0f83c0a884d1d3462ed2b53db7421938e6d68df7d862e63fd272f2240317 and
ddf6ae2182bfe49da3bbb31b7411da9b449e7a7cd392670100b00fbf5d7179b6.

The authenticated earlier20M v5 result is reused: new read/instruction records
are forbidden and unselected there, the CPU parent selector extraction preserves
its old rule, and old report fields omit the new optional data. Focused legacy
contracts and exact default-shadow checks pass; no new full20M re-emission or
equivalent reference rebuild is claimed.

Final corrected full local workspace/CLI, strict all-target Clippy and fmt pass,
including outer-limit deletion. Exact-head CAS/fetched verification belong in the
closeout. STATUS/NEXT/DEVELOPMENT/ADR0124 describe the final read-bound design;
progress remains unchanged. No raw research branch, branch CI, ROM/assets or
reference implementation enters production. Ignored shadows retain ISC notices.
Whole-ROM/native, complete source/writer/backend/epoch, RSP register/task and
hardware obligations remain OPEN. The overall user goal remains active.
