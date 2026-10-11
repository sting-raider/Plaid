# Primary takeover: completed CPU SB/SH SP Word sinks

Hypothesis: the prepared subword sink verifier can consume already-validated
SP semantics on current main while preserving decoded occurrence, GPR source,
physical-bank and completed-effect identity. Local execution capability is now
available; missing tools in the preparing worker do not require new research.

Candidate reviewed: `380dd45b828f10ae17e46c386f102453ccf0fc1a`, code head
`9b0ef3bb6c11908e4acd3d155f6a1faec9583fcb`, blocked ledger closeout `6111148138`.
Reconciliation base: `d23515e9dffba26774bc26821b3c26e6b824de4c`.
Only its original Plaid Rust verifier/tests are transplanted. Its historical
BLOCKED receipt, branch-only workflows and other branch changes are not adopted.

Current `cpu_mutation` covers completed COP1 effects and `llsc_mutation` covers
completed SC/SCD effects. Neither validates decoded SB/SH to the SP adapter.
`sp_history` preserves completed SP Words without inferring their operand source.
This primitive keeps those responsibilities distinct and gives no solver waiver.

Review found two unchecked architectural preconditions in the prepared verifier:
a nonzero captured GPR0 can falsely supply a zero-register store, and a misaligned
PC can claim a decoded occurrence. Retain explicit regressions before fixing them.
The external caller still owns authenticating context/effect source, mapping,
ordering uniqueness and sensor completeness; this single-effect API does not
claim a complete-history SHA verifier or source/mutation/lifetime census.

Pinned ares CPU::SB/SH, endian address mapping, RCP::write and RSP::writeWord;
Gopher64 SP sink; Mupen masked sink; and n64-systemtest SPMEM oracle are source
context only. No upstream implementation is copied. The 8-KiB physical aperture
is a deliberately bounded subset; mirrored/device-register targets stay unsupported.
Preserve the documented Mupen disagreement and broader hardware/lifetime unknowns.

Use the saved canonical spike-046 capture receipt
`2cadac7ab077a2575d19360743161976789a72fd3a00173fda0f891f14792864`
for actual decoded SB +1 comparison. Do not rebuild the reference emulator unless
the production comparison exposes a semantic discrepancy.

## Validation

Both new architectural regressions failed on the prepared candidate before the
two checks were added. Its 17 retained unit regressions pass after reconciliation.
Three additional production regressions cover those failures and 64 bank/endian/
opcode/lane cases, including odd SH attempts without sinks.

An ignored local Rust harness authenticates all saved spike-046 result bytes,
then feeds its actual decoded SB context and completed effect into the production
API. It agrees on full Word `77880000`, IMEM destination `04001000`, and final
guest bytes; an unscoped producer-context substitution is rejected. The harness
is preserved in ignored `target/cpu-sp-subword-primary/saved-capture-test.rs` and
is not a new canonical capture dependency or sensor-completeness claim.

Exact ares HEAD and relevant source-file cleanliness pass. The retained
`compare_refs.py` also checks exact Gopher/Mupen/systemtest pins and selected-file
cleanliness, preserving the masked-vs-widened disagreement; comparison digest
`6ce196f015e985dd79921ac707ab5ef546124caed5ca0f927220aab0e90fbb87`.
No reference builds or Actions runs are triggered.

Final local gate before publication:

```text
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace
python scripts/test_cli.py
python spikes/046-ares-cpu-sp-producer-context/test_verify.py
python tools/progress.py --check
git diff --check
```

All progress milestones and solver proof obligations remain unchanged. This
supersedes the prepared candidate for this bounded production primitive, while
retaining its research evidence and broader OPEN obligations. Canonical writes
use a direct-child commit and exact-head CAS with force disabled, not the old
lease procedure in the preparing worker's historical closeout.
