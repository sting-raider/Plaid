# Primary integration: lower DMEM effects cut raw-clock SP ancestry

Base:1287d9a64e1727a38f2448aaa42ca2b6acc1365e. Claim:6169264103.
Source research: canonical spike042 lower primitive sensor and spike052 store
domain isolation, composed with the existing storage/SP clock and shared writer
state. The current source admitted only CPU/DMA wrappers; the v6 contract first
reproduced missing source admission on unchanged main.

Strict v6 now records bounded completed DMEM primitive lanes on the original
counter. Byte/Half/Word/Dual widths retain masked alignment and truncated payload
validation; malformed lanes or fetch/copy interleavings reject. The shared SP
writer state revokes only affected DMEM candidates, including equal bytes.
IMEM stays independent. Lower DMA effects precede their separate higher store,
so the existing frozen source-read receipt remains eligible for that installation.
No RSP producer/register/task parent is minted by a sink callback. V3/v5 reject
the new record and retain their old semantics/reports. V6's containing projection
uses report-v2; all broad proof flags remain false.

Reference receipt rechecking now hashes the explicit six baseline/sensor control
files and the declared executables/build manifests. Unrelated full-replay JSON
files had temporarily changed the earlier receipt despite unchanged controls.
The bounded artifact set restores its exact1374cdb6... digest, and the new receipt
retains its exacta91a35f2... digest. Both rechecks pass with the extra files present.

Two bank domains retain full/partial/unknown effects, equal bytes/four-Byte cuts,
pre-install read survival, valid widths and twelve malformed/legacy-policy
controls. Both production SP writer and PI consumers agree with the independent
model. Earlier PI/SP and storage/cache contracts remain green.

The fresh pinned ISC ares9408cb43 fixture joins PI RAM copying, DMEM DMA, CPU DMEM
consumption, an equal decoded RSP SW and later CPU DMEM/IMEM execution. Its142
events and22 full machine/backing checkpoints agree baseline/disabled/enabled/
repeat. The full RSP register/vector/pipeline/timing/DMA/status digest is included.
An initial fixture expectation incorrectly treated aligned RSP SW as one Word
effect; the actual pin performs four Byte effects, including zero. Correcting
that exact expected lane sequence on retained unchanged binaries passes. No
production rule, reference source, assertion or proof obligation was weakened.
Opaque host mapping/descriptor/IMEM seed/register/stepping controls supply no
hardware scheduling or RSP producer ancestry claim.

Actual source SHA-256:
3522b3f00c867cf9a2a3937faff001427f70e0178c297d919f4dfbd03d89ccd1.
Baseline/disabled SHA-256:
fc199a69bb212a2f85f714727c93ecff326716e5a90690ae7ae4a285773c142d.
Actual control receipt SHA-256:
a91a35f2f8356aa7d0655bf99a427a576a57ea19b8298b5e59d32e32fd124d6b.
Baseline/sensor build SHA-256:
61236122b470ac0f134416c5726f8f9ed2029fbd5d1161576fbb32002c052ee1 and
2ce2460c1dae490a6f224085ffeb6a4dbe214d51767c54b982cc46eaaf108e7a.
Executable hashes remain bound by that ignored receipt. The retained30-case/
209-effect/329-record reference contract and ten forgeries also recheck at its
independently documented2dc15b71d45507e21d188f4e5e1a07af5101c507fd5253cc6b706f09f60e23eb.

The actual supplied100k prefix retains424,660 records including1,008 DMEM effects,
with byte-exact earlier paired fetch/checkpoint controls and repeated raw source
equality. Both complete consumers agree on100k fetches, no PI byte ancestry and
the ordered digest bf9653cea12e9546e33724f4c32603455b467324554bdcbfcdbabf3cf5ff1ad8.
Source SHA-256:
d3eb689c3b9c791e5ea8dbf9e87b77d11bb99d94cdfe99c47bf8baa3ce698b1f.
Fetch SHA-256:
ce66498314c58b448fc95ecd4ef8adbd795e83c60c9ac5e49189e4406f8039a4.
Checkpoint SHA-256:
c79e2c3f287ea017794e59315cbb95b403568db00a86e4bea045487f9e51ed42.
Capture receipt SHA-256:
f4d2358d8e94ea0b5514d756c942d289b9b4b7607b96e69f978bf33f142a0020.
Canonical/independent report SHA-256:
d57a1b4b295accaf98c31cc6010de577f6c7ff033852dd0df6c3fe6faafd5063 and
ddf6ae2182bfe49da3bbb31b7411da9b449e7a7cd392670100b00fbf5d7179b6.
Boot build SHA-256:
11c8bd44f33eb4e0990153c06c167f8b0cfeea33818dccc4203372125c3d826e.

Removing only the1,008 added DMEM records and normalizing the shared counter
recovers every423,652 legacy record of the authenticated old100k prefix exactly.
Both complete sources were authenticated separately. The normalized-prefix digest
is239b405a651c5852998ad6304d14d096714080bfab0e327a476108cb418239f2;
comparison receipt89e9b0e486fb7743cdf620248933e57255e4455a48533688aa5b51f5b78e346d.
This is a finite legacy projection comparison, not a source-coverage waiver.

The earlier authenticated20M v5 result is reused from1287d9a. Both entire sources
freshly hash to41f88d.../d0e2cf...; the added record is forbidden under v5 and
unreachable on its already-validated source. Review confirms every legacy writer,
read, header, report and digest path remains unchanged when v6 is unselected.
Focused legacy graphs pass. No fresh full20M re-emission or equivalent emulator
rebuild is claimed; the separate new100k producer contract exercises v6.

Complete locked workspace/all-target Clippy, workspace tests including outer-limit
deletion, fmt and CLI pass. Final expected-head CAS and fetched verification
belong in the closeout. STATUS/NEXT/DEVELOPMENT/ADR0124 update for this finite
production change; progress stays unchanged. No raw research branch, branch CI,
ROM/assets or reference implementation is imported. Generated shadows retain ISC
notices under ignored target/. Broader writer/source/backend/scheduler/epoch,
RSP producer ancestry, executable lifetime, whole-ROM and native remain OPEN.
