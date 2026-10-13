# Primary composition: restore cuts cached exception-root ancestry

Base:47fadbc867b7bc4311de77ae53fcf967bb12e4d2. Claim:6139425616.
Source research: `spikes/018-ares-cache-reset-restore`, retained actual equal-fill
false causal join; PR19's portable fresh-restore-root obligation. Existing
canonical full-line/reset root replay is authoritative. No standalone restore
consumer or raw branch/workflow merge.

Explicit root-history v2 admits source-bound successful restore boundary records.
Cut all old resident/backing observer ancestry, including repeated loads of equal
snapshots. Never relabel an old fill/writer from equal PC/address/payload/hash.
Post-restore root fetches and refills stay unknown until a fresh captured backing
writer and later completed fill establish new ancestry. A later equal writer
cannot repair an earlier fill's missing parent. Root selection remains independent.
Snapshot digest labels are metadata in the authenticated history, not authentication
of snapshot bytes or certified component roots. V0/v1 still reject restore;
their shape omits the new optional receipts and original regressions pass.

Retained-reference enrollment: issue4 comment6139480819. Exact clean ares:
9408cb43d4948fc3ea6e152a307a34348df3fe04,ISC.
Driver and every declared fixture/observer extra match retained build manifests.
- baseline binary:aab915056bf7dedf126fad220bc6fceaa422bdbd9332c964b3e620eca9b8dd97
- baseline build:600a3d213975c0d805a00f9171e7bc6323d67687fa446389a853ba1295eae635
- sensor binary:6fa505be0087eff27f35b07d93cd86612afa578133d3ee338489f1904e9b02b6
- sensor build:c529f9de2fb69c7608c0e09ed74de19a756fdbb5bcb601b5987dc03fb05f930e
- retained results:9493d250038991e97f3477e3499d4bcc1183c70767ecae629e3f4a9f54f230ba
- repeated enabled stdout:d76f915c3f51a5b91fffed9e52ccaa0bd65ee424fc7ee56339f7c000b5175208

Re-executed enrolled unchanged binaries: baseline/disabled/enabled/repeat reported
states match, enabled stdout repeats exactly and both retained result objects are
unchanged. The naive post-restore equal tuple matcher selects fill2 while the
restore emitted no fill; a later explicit cache reset produces fill3. No rebuild.

Exact canonical Git source SHA256 values reviewed:
- system/serialization.cpp:284dde684315884a5ae5cfb7e5a9ce2e2d3e261a8cecaab508cd18a339425744
- cpu/serialization.cpp:8cc65fad5508ef9d85e6715c31a6b5c577a46c8967b8e57d594d4f20d0dd369d
- rdram/serialization.cpp:6301d7e32a40064047fcd30473dd7efaf8ae5b6e46a5532660558a84fc49b12a

Successful synchronized unserialize checks the header/version, power-clears and
then reinstalls component state. CPU serialization includes I-cache tags/index/
words; RDRAM serialization reinstalls RAM/map state. That is not a new observed
fill or successful RAM writer. Observer sidecars are not recovered by equality.
The retained fixture executes ordinary PA0 code, not actual exception delivery at
PA180. The new root composition histories are synthetic and use that shared cache
mechanism; they are not claimed as a fresh combined emulator/root capture.

Focused PASS:11 root-composition tests (three new restore families),14 root library
tests including ten generation regressions. Repeated equal snapshot cuts, fresh
writer/refill recovery, late-write nonrepair, nonroot-slot replacement, NMI
preservation, source/profile/metadata/deletion/report forgery and legacy rejection
all pass. Mandatory local fmt/strict locked workspace all-target Clippy --jobs2/
full locked workspace --jobs2/canonical CLI/diff gate completed before CAS.
Ignored authenticated controls/logs: `target/root-restore-integration-primary`.

PR19's equal-restored-state/nonmonotonic chronology invariant is partially
reconciled as a conservative cut. Its three-component snapshot-label/root
certification surface is not imported. Snapshot-byte/component authentication,
restored executable contents/producer epochs, root-entry/fetch sensing, complete
writer/cache/mapping/restore census and whole-ROM/native closure remain OPEN;
all reachability/mutation/lifetime/native flags stay false. No milestone, ROM/
assets, upstream implementation, branch-only Actions or native fallback changed.
