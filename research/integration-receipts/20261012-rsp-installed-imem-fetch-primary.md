# RSP installation graph reaches actual IMEM consumption

Base:3032c1ace9bbe7792d03de4838d848c03036d2fe. Claim:6124301065.

Controlled v3 extends the original-clock RSP ORI/ADDU/LW -> DMEM -> CPU LW ->
IMEM SW graph with actual decoded instruction consumption. Require full4096-byte
initial/final IMEM images and explicit controlled opaque host code-seed events.
Those events always cut byte parents, including equal-valued replacement. Each
actual RSP begin word must match current modeled IMEM bytes; its discrete fetch
retains four current writer identities. Definitions and copies retain their raw
source context IDs, so the graph can follow the fetched word back to its install
and RSP data producers without an ordinal/value-only cross-clock join.

The optional fixture uses a legal NOP payload and executes that installed word
once under single issue, avoiding an unintended lookahead instruction. Existing
instruction-prologue sensing observes the actual decoded word without an extra
guest read. Controlled host seed callbacks observe existing writes. Default
fixture modes stay unchanged. Pinned ares9408cb43d4948fc3ea6e152a307a34348df3fe04
is clean; ISC notices remain in ignored reference shadows. No Actions or upstream
implementation import.

Baseline, disabled, enabled and repeated runs agree on all17 independent machine/
timing/exception checkpoints, CPU steps, reported state and full bank/RAM hashes.
The repeated enabled source is exact. Independent COMPLETE97-event census and
full-image replay agree on six definitions, three copies and seventeen fetched
words with every byte parent. Exactly one fetch (PC0/word0) has the first copy's
CPU writer identity; its source retains the final original-clock LW/ADDU
definition. Later equal-payload reentry remains opaque.

Source SHA256:
091768b8c14fa612b6b0fd3864a509f309b3c956625ec1786fc686d7ab92adb0.
Report SHA256:
387a1c8e787543dfbb2852a48f73bcbae2c8a4ad4c396afbd18f0e41e2bf0775.
Retained v0/v1/v2 reports remain EXACT respectively:
2dc31e222304cb1818d863bb3134eb3bf4dc76eb7885057f813899aa77005896;
e32c0d7fc7860210a1a4c8dc01adf9087486c246166178438737bd8417dbde9a;
d4d49f277965ecb207ab611581eb51e97da6c495c7101d83f853d63c08a6e3b4.

Focused13 and actual/synthetic CLI source/report/profile/input adversaries PASS.
They reject partial bank images, contradictory final state/fetched words, malformed
opaque seeds, missing/report-replaced fetches, forged writer parents and proof
flag changes. An equal opaque install loses CPU parents despite unchanged bits.
Retained actual inspect/verify and independent all-node/fetch/copy comparisons
PASS. Generated controls/source/reports remain ignored under
target/rsp-installed-imem-fetch-primary and target/rsp-execution-integration-primary.
Full local fmt, strict locked workspace/all-target Clippy, locked workspace tests,
canonical CLI and diff gate PASS with two build jobs. No tests skipped or reference
rebuild repeated; the exact validated tree is reconciled directly onto its base.

No general producer census, DMA/asynchronous/cache/TLB/reset/restore interleaving,
continuous executable lifetime, hardware consensus or whole-ROM/native certificate
follows from this controlled source. All corresponding flags remain false. PR8's
remaining scalar widths and PR29/37's DMA work remain pending, not raw-merged.
No branch-only CI scaffolding, ROM/assets or progress milestone change.
