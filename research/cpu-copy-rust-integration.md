# Rust integration of validated CPU-copy histories

Hypothesis (2026-10-11): the validated spike 044/045 instruction/scalar captures
can supply a reusable original Rust replay without identifying producers by
value equality. A bounded LW/LWU -> optional in-place XORI -> SW chain must retain
its read/write ordinals and each instruction context, including XORI zero.

Scope: canonical sign-extended KSEG1, aligned identity-RDRAM Word effects,
big-endian byte interpretation, contiguous captured instructions within a
declared segment, full 64-bit GPR continuity. ORI/NOP are validated cuts; failed
loads supply no definition. Other instructions/domains reject. A supplied
external complete-source SHA binds the input; the report does not establish
sensor completeness, ultimate byte ancestry, executable lifetimes or native
closure. It does not promote writes into ProgramMap solver proof.

Use existing source receipts and retained actual captures under ignored target;
do not rerun the ares builds. Add deterministic semantic/adversarial regressions
for the Rust implementation, compare its witnesses to the independently retained
Python results, and run canonical checks once for the implementation batch.

Implemented `cpu_copy` plus inspect/verify CLI. Strict typed wire input preserves
every event, rejects unscoped/duplicate/truncated records and checks complete
GPR state, decoded addresses, sizes, payloads and state effects. Successful
copy/transform witnesses preserve actual read/write ordinals and context IDs.
Unsupported operations reject; failed reads, register zero, segment boundaries
and intervening definitions supply no copy. No ProgramMap proof promotion.

Authenticated saved primary results before comparison:
copy `a0903ba3ae1e2f05144a1968a065348edd344debb7ded9fac450bfdd1427fa6a`;
XORI `e73a87e0106b5bc6b9631f35795015aa6275a6d70f171a9c186d2c32a732e783`.
Their complete instruction/scalar arrays adapt to the new wire without changing
event fields. Rust agrees exactly with the independent Python witnesses: 14
instruction contexts / two copies; 20 contexts / four XORI transforms. All
producer context/address/opcode/value/mask fields agree. Source hashes of those
adapted complete inputs are respectively
`f97b2262c7e61cf28024f0bd0a678a0cb52e1247050b9d18465b7178c3382cfc` and
`0fdc274395c3e57fe27d85465a3f267411e301824465edbce0910e5b4581376d`.
This comparison uses retained captures; no C++ reference rebuild was performed.

Five Rust semantic/adversarial tests and synthetic CLI receipt/report/deletion/
input-protection checks pass. Full locked workspace tests, fmt check and strict
locked workspace/all-target Clippy pass. Clippy's CLI conditional style repair
was followed by strict Clippy and CLI checks, without repeating the full suite.
Interpretation remains confined to the
declared controlled segment/domain; supplied source receipts do not establish
physical hardware truth, execution-mode/capture completeness or whole-ROM closure.

Follow-up implementation retains four explicit big-endian byte expressions per
Word witness, anchored to the parent read/context/source receipt. All four
measured XORI expressions match the independent saved byte mappings. The 0xf00f
mask maps to [0,0,0xf0,0x0f]; each source/destination lane is explicit. XORI zero
has copy-equivalent byte expressions but still retains its transform context.
A sixth Rust test rejects altered source/XOR lanes during report rechecking.
Focused Rust tests/fmt/strict Clippy pass. Canonical CI 38147498790 is green at
exact pre-byte-expression CLI head `3c0fbe7d3dc5d6b68538c8e168b966dfbe120131`.
