# RSP register definitions through DMEM and CPU into IMEM

Base:722de35c5d06f27cc777fcf9220351d08240948d. Claim:6123056751.

Reconcile prepared PR8/direct-integration/rsp-scalar-gpt56sol's validated ORI and
ADDU rules with the stronger canonical rsp_cpu_imem source. It already captures
full before/after RSP GPR arrays, decoded words, control, byte sinks and CPU steps
on one clock. Do not fabricate full state from selected-register input or join
independent clocks by equal values/labels. No raw branch module/Actions imported.

Explicit v1 admission checks full post-register/control/vector state and effects.
Mint nodes at raw begin contexts with architectural-zero, earlier-definition and
opaque captured-input parents. IDs avoid recursively cloned expressions. Equal
definitions stay distinct. Scalar RSP sinks retain their rt definition through
the existing DMEM -> CPU LW -> IMEM SW consumer. Reentry cuts tags even for equal
bits; zero-register destinations produce no node. Incoming registers and fetched
instruction-byte ancestry remain opaque, not certified.

Retained v0 actual source replays to EXACT old report bytes, SHA256
2dc31e222304cb1818d863bb3134eb3bf4dc76eb7885057f813899aa77005896.
Legacy decoder/foreign-sink/clobber/renamed-PC/phase adversaries still pass. Seven
focused tests cover parent identity, equal definitions, full register changes,
opaque inputs, reserved fields, profiles, reentry and source/report/tag forgeries.

A necessary small fixture build supplies baseline and shared-clock sensor at
exact clean pinned ares9408cb43d4948fc3ea6e152a307a34348df3fe04. An optional prefix
leaves spike047 unchanged by default. It executes ignored zero-register ORI,
two equal ORIs and two ADDUs before RSP SW/CPU LW/IMEM SW. A later opaque reentry
with identical payload cannot borrow the first phase's tags. Existing mixed/
unknown/vector and same-value CPU clobber cases remain. No full-ROM recapture.

Baseline, disabled, enabled and repeated outputs agree on all16 independent
machine/timing/exception checkpoints, CPU steps, reported state and full bank/
RAM hashes; repeated events match. Independent complete census reproduces68
events,13 RSP/10 CPU instructions, four nodes and three copies. Contexts3/5/7/9
retain distinct equal ORIs; first copy carries definition9, later reentry none.
Actual canonical inspect/verify and independent all-node/copy comparison PASS.
Source SHA256:
45c8ab1e8192dbbc1fe7a7b60449a6293e547177abe7cbcc8da635f996304b2d.
Report SHA256:
e32c0d7fc7860210a1a4c8dc01adf9087486c246166178438737bd8417dbde9a.
Pinned interpreter-ipu ORI/ADDU semantics were read; ISC notices remain in ignored
builds. No upstream implementation is copied into Rust or git.

Validation: focused7, new synthetic/actual CLI source/report/input/phase tests,
old actual report-byte replay and legacy CLI adversaries PASS. Full local fmt,
strict locked workspace/all-target Clippy, locked workspace, canonical CLI and
diff gate PASS. No Actions, progress milestone or copyrighted assets in git.

PR8 is partially reconciled; broader scalar-load/store lineage still needs a
compatible actual read/definition source. Its selected-register module remains
unmerged. Scalar/vector incoming ancestry, instruction/root backing, DMA/cache/
TLB/restore interleavings, general mutation census, IMEM execution/lifetime and
whole-ROM/native remain OPEN with all certification flags false. Artifacts stay
ignored under target/rsp-defined-imem-primary and integration logs.
