# CIC-configured local capture through actual PI/queue/SP source replay

Base: 6db9878b39cfac1ea3d61323ffbb7c38dd652bf0. Claim: 6118638930.

Add optional --history sp to the generic local recipe, selecting the existing
canonical spike-040 observer and its exact build recipes. No new sensor/schema,
PI semantics, writer inference or native consumer. Pair original v3 history and
v5 fetch digests; require repeated full bytes, disabled/repeated full existing
checkpoints/messages and optional independently retained baseline equality.
Header/footer checks are supplementary; canonical typed replay remains required.

One necessary sensor build supplies the source the simple observer lacks. The
local million-call 6105 capture reproduces the prior basic v5/checkpoint/messages
byte-for-byte and repeat controls agree. Replay now reuses its artifacts/build.
8,168,531 records; source SHA256
 e2a1b123a52474fa9ea4b92fcf962287c621b2cc374bc773e6157c7f5c9a6cb7.
Paired fetch SHA256 unchanged
 aa6ee65d48121740f2d9d6b14cc739dfcf78318fa21b3b18382ec55c2676b157.
Checkpoint unchanged
 6b3e04574c520d8e86ee34374ac1ab7a09478498724f1d01eda80f30bd2beac7.
Exact pin and source/recipe guards remain 9408cb43d4948fc3ea6e152a307a34348df3fe04;
reference notices stay ignored. No ROM/firmware or raw words/maps in git.

Canonical complete-source inspect/recheck passes. Original debug and release
reports are byte-identical:
 6f4ffb605c2f10bf873d472c59c8a7de0af4367c9fbf1623eb674d64d50129ff.
Ordered SP candidates:
 a1fb25b148c8730a386920f755a2fe13f62996e35764c62e5ed98a969ac055ab.
56,080 captured SP writes; 841,500 fully compatible observed SP fetches, zero
contradictory byte candidates. Compatibility is not ultimate source ancestry or
a complete mutation/lifetime certificate. All corresponding flags remain false.

Nested PI replay binds 524,288 canonical half reads to 1,048,576 successful RAM
byte writes and ROM origins, zero unknown origins/failed destination witnesses.
PI effects hash:
 76a689a126b15dd02ee81cc37f368f8422c51e1d17e2ff8212f55c07d6ab5797.
Request 1 (RAM1024, PBUS268439552, length1048576) accepted token6; copy returns,
zero completion status transitions. Requests-without-status retains [1]; no
transfer-completion certificate. Queue insertion clock75848380 is a captured
queue-domain value, not interchangeable with CPU Count or proof of a stall.

The prior ten-million-call simple source also completes repeated controls and
canonical import/rechecking: 2,055 PIF, 841,500 SP, 9,156,445 RAM fetches; 989
summaries and WholeRom OPEN/eight blockers, ROM entry unobserved. Source:
 10c8550af7e919da821097274fcdf755789edffca0adf77428188ec475e66471.
Checkpoint:
 dfbf8a093573edaa7cdfe029f886bd52b41cdb0adbd4799acbc26d32c5d7a096.
These data do not certify completion from the last copy effect or busy bit.

Full local fmt, strict locked workspace/all-target Clippy, locked workspace,
canonical CLI and diff pass. Retained SP writer/fetch adversarial CLI contract,
actual native-flag forgery, wrong baseline and retained recipe replay pass.
Debug full inspection completed; its slower verification was replaced with the
current-tree release reader, which reconstructs identical reports and verifies
complete sources. Standard project release build only, no semantic/parser change
or additional emulator build. No Actions execution or proof/milestone waiver.

Ignored raw sources/reports: target/local-boot-primary/oot-sp-1m and oot-10m.
Next observe actual PI dispatch/status and installed-code consumption. Preserve
unknown mutation census, cache/mapping/lifecycle and whole-ROM/native obligations.
