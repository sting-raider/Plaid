# Actual RSP DMEM reads through definitions into IMEM

Base:286d70af6fa33ba30a1fa5da5a39bd154ad6975e. Claim:6123674483.

Compose prepared PR8's LW semantics with the canonical original-clock definition/
DMEM/CPU/IMEM path. Do not join selected-register sources or infer a performed
read from equal bits. Explicit v2 requires an actual completed LW read witness;
validate its context, decoded pre-write base, raw address, modulo4096 offset,
four returned bytes and latest captured byte parents. Verify full post-GPR/
control/vector state. Zero destinations consume the read without minting a node.
Later ADDU and scalar stores keep definition IDs; reentry cuts equal-value tags.

The optional pinned-source hook evaluates the existing
`dmem.readUnaligned<Word>` once, observes its returned value before assignment,
and preserves the original register result. It adds no guest access or decoder/
width/alignment change. Exact method-seam guards fail on reference drift; ISC
reference/shadow notices stay in ignored builds. Small seam markers are used
for instrumentation, not a runtime/upstream implementation import. No Actions.

A required small baseline/shared-clock fixture extends the retained arithmetic
prefix with SW -> LW -> ADDU -> SW before CPU LW/IMEM SW. Baseline, disabled,
enabled and repeated runs agree on all16 machine/timing/exception checkpoints,
CPU steps, reported state and full bank/RAM hashes; repeated events are exact.
Independent COMPLETE79-event census agrees:16 RSP/10 CPU instructions, six
nodes, three copies. Actual read18/context17 keeps four distinct writer events
12..15/context11 with definition9; ADDU20 consumes definition17, and the first
IMEM copy retains definition20. Later equal-payload reentry retains no such tag.

Actual source SHA256:
46651111a1ab5fe06a0583d7be357d6cea35f8e079ed1b7a1dc583bf344b0c55.
Actual report SHA256:
d4d49f277965ecb207ab611581eb51e97da6c495c7101d83f853d63c08a6e3b4.
Retained v0 and v1 reports remain EXACT byte-compatible respectively:
2dc31e222304cb1818d863bb3134eb3bf4dc76eb7885057f813899aa77005896;
e32c0d7fc7860210a1a4c8dc01adf9087486c246166178438737bd8417dbde9a.

Validation: focused11, actual inspect/verify, independent all-node/copy/census
comparison, synthetic/actual CLI and old report replay PASS. Adversaries include
target/base alias, ignored zero target, raw/normalized-address/width/context/
value forgeries, same-value decoy location, forged byte parents and consistently
reclocked missing/duplicate callbacks. Full local fmt, strict locked workspace/
all-target Clippy, locked workspace, canonical CLI and diff gate PASS.
An initial Clippy test-style failure was repaired. Windows paging capacity then
prevented parallel rustc mmap; the unchanged full gate passed with two build jobs.
No test skipped, source obligation weakened or emulator rebuild repeated.

PR8 is further partially reconciled; other widths/signed loads and general
incoming scalar/vector/source/root ancestry remain pending. Captured parents
are finite compatible observations, not a complete writer census. DMA/cache/
TLB/restore interleavings, IMEM execution/lifetime, whole-ROM/native and hardware
consensus remain OPEN with all corresponding flags false. No progress milestone,
raw research/workflow merge, ROM or copyrighted asset in git. Generated source,
reports/binaries/controls stay ignored under target/rsp-word-read-imem-primary.
