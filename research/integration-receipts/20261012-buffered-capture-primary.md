# Measured machine-readable capture buffering

Base: 0452f890e99eeba831ad60333a8e8119acb5b77d. Claim: 6119771685.

Explicit owned 1 MiB buffers replace default small stdio buffers on fetch and
history output. Keep all formatting, tracer callbacks, register queries, guest
accesses/state/clocks and record order. The fetch buffer remains alive until
fclose; close even on ferror before freeing it. The history buffer has static
lifetime. Allocation/setup/flush failures are errors, never successful captures.

Baseline actual100k: 29.827 seconds, 15,488,047 v5 bytes +73,577,811 v3 bytes.
Matched buffered run: 5.837 seconds (about5.1x). Fetch/history/checkpoint/messages
match byte-for-byte; disabled/repeated controls and repeated bytes agree. Final
lifetime-safe implementation reproduces those exact sources; canonical typed
inspect/recheck passes. /dev/full flush test returns7 without a checkpoint.
V5 SHA256: ce66498314c58b448fc95ecd4ef8adbd795e83c60c9ac5e49189e4406f8039a4.
V3 SHA256: e2732d22c99bf4fd5a41446bfdf69c2d054d4fd3b94159dbfa16d7e30c577090.
Checkpoint: c79e2c3f287ea017794e59315cbb95b403568db00a86e4bea045487f9e51ed42.
All ancestry/census/lifetime/native flags remain unchanged/false.

A local libc probe showed null-buffer setvbuf retained4096 bytes; an explicitly
owned buffer uses1048576. Do not claim a large requested size alone ensures the
actual buffer. Storage lifetime follows GNU documentation:
https://www.gnu.org/software/libc/manual/2.34/html_node/Controlling-Buffering.html
No library implementation is copied into production.

Rejected prior prototype (claim6119654125) removed unused disassembly formatting.
Its limited100k bytes/state matched but benchmark33.617s was worse. Source review
also found Random operand formatting calls getControlRandom()->random(); a
broad bypass needs a separate non-interference contract. Reverted the complete
owned prototype. No new raw-logging option, altered getter or skipped record lands.
Generated prototype binaries/data remain ignored and are not source authorities.

Full local fmt, strict locked workspace/all-target Clippy, locked workspace,
canonical CLI and diff gate pass. Exact pinned reference unchanged; only original
project-owned buffering/cleanup code changed. No Actions/asset bytes in git,
guest performance claim, source-contract waiver or milestone promotion.

The twenty-million buffered capture is ongoing/rechecking; its larger outcome
is not asserted here. Preserve authoritative earlier complete source receipts;
exclude the previously timed-out partial stream. Next observe and independently
recheck actual pending PI completion and installed-code consumption.
