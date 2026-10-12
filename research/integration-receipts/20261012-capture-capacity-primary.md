# Explicit bounded capture capacity and strict numeric arguments

Base: 53b9d760d40ab0382354c5f14189d808fdd67686. Claim: 6119207529.

Extend the finite capture ceiling from ten to twenty million calls in canonical
fetch/map validation, the shared reference driver and the generic local recipe.
No CPU/device semantics, sensor protocol, closure flags or solver obligations
change. Existing complete-source count/sequence/firmware/census/lifetime checks
remain required. Parse driver numeric arguments before narrowing; zero, overflow,
trailing junk, negative and over-capacity inputs reject instead of wrapping.

Fifteen focused fetch regressions pass, including accepted maximum, invalid
maximum/zero/u64 overflow, forged map capacity and unchanged WholeRom OPEN status.
Actual driver input tests reject 0, 20000001, 4294967297, 1junk and -1 before
capture outputs. One hundred thousand valid calls produce a complete source and
checkpoint. Baseline total wall time is 29.827 seconds, 15,488,047 v5 bytes plus
73,577,811 v3 bytes; use this measurement for subsequent overhead work.

Current-tree release rechecking of the retained million-call source/report
passes unchanged: history e2a1b123a52474fa9ea4b92fcf962287c621b2cc374bc773e6157c7f5c9a6cb7;
report 6f4ffb605c2f10bf873d472c59c8a7de0af4367c9fbf1623eb674d64d50129ff.
Full local fmt, strict locked workspace/all-target Clippy, locked workspace,
canonical CLI and diff gate pass. Exact ares pin remains unchanged; the new
capacity driver is compiled locally. No Actions or ROM/assets in git.

The twenty-million plain reference run completes with PI busy0, PC
ffffffff80003080, exception0 and Count81211040. These are preliminary diagnostic
state values, not independently validated boot/entry evidence. The instrumented
run timed out after 600 seconds while emitting a partial v5/v3 pair, with no
complete footer/checkpoint. Exclude it from source admission and any certificate;
do not claim a completion observation or milestone. Preserve it only as a local
diagnostic of logging overhead. The prior complete sources remain authoritative.

Next compare bounded raw-only tracing overhead against the measured existing
path, preserving exact source bytes and machine checkpoints before use. No proof
waiver, guest timing optimization or new architecture/lowering lane is authorized
by this capacity change. All whole-ROM/native/source-census obligations stay OPEN.
