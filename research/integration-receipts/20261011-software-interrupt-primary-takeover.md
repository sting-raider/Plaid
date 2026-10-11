# Primary takeover: guest Cause software-interrupt operations

Hypothesis: recover the prepared complete-source replay of guest MTC0 Cause
writes. Preserve fresh successful operation generations, including same-value
writes, while retaining IP2..IP7 as independent hardware-produced state.
Architectural source register zero must not carry a nonzero operand.

Base: 1cf9738470df819d131df4d9e80c9b4d106d04b7.
Candidate: b8f76594e642bd94ed438376194f58c24272c1a9, PR #34.
Research: 93483c33832069680d31f969cfb599d631e45dbf.
Only the original Plaid Rust module/tests are retained from the prepared branch;
branch-scoped workflow and historical validation receipt are not merged.

## Evidence and design

Authenticate historical artifact 11707294210 ZIP
4db2fa91a2cc463ae296d526b7455629a0103402856c637c0587f5ba92e6eb41
and complete 21-case result
589eb9d5795106753e5de3f055dd14977702bb136c68793e3c4dc464ebaa3bda.
The guest MTC0 retires before the next boundary enters or suppresses the handler:
PC/GPR/EPC/Cause/EXL distinguish that behavior, not just pending equality.
Compare the saved first-boundary software ownership relation and next-boundary
gate with current production. A local protocol fixture adapted from these state
rows uses synthetic ordinals; it is not newly sensed operation chronology.

Actual successful Cause writes replace only pending IP0/IP1 and preserve the
hardware portion. Full typed input bytes require an externally trusted SHA; report
rechecking reconstructs every field. Missing/reordered/truncated/duplicate or
faulting-successful boundaries reject. Each successful same-value write retains
its own operation generation. Independent hardware changes between attempts are
allowed and their producer ancestry stays uncertified.

Review identified one architectural gap: a decoded MTC0 using GPR0 could supply a
nonzero raw operand. Retain a regression against the prepared code, then reject
that impossible source while accepting real zero-register clears.

The complete sensed source, raw operand authentication/ancestry and all producer/
Status/BEV chronology remain separate obligations. Current interrupt_roots can
evaluate an independently supplied next boundary; this history is not a general
producer census or root transfer/lifetime certificate. All coverage/hardware-
producer/gate/handler/root/native flags remain false.

## Local validation before publication

Retain the candidate's deterministic/adversarial regressions. Add public tests
for zero-register operands, complete-source deletion/report edits and schema
aliases. Check exact pinned ares/Gopher/Mupen source blobs and selected-file
cleanliness. Preserve the existing Mupen instrument elsewhere in that checkout.
No reference builds or Actions runs are triggered.

cargo test --locked -p plaid-core --lib software_interrupt
cargo test --locked -p plaid-core --test software_interrupt
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace
python scripts/test_cli.py
python tools/progress.py --check
git diff --check

Canonical publication uses a direct-child commit on the exact locally validated
head, refetch and expected-head CAS with force disabled. No solver waiver or
progress milestone change.

Outcome: local gates PASS on the exact base above. Eleven retained module tests
and three public regression groups pass; the zero-register adversary failed
against the prepared code before the guard. The authenticated 21-row comparison
passes (12 admitted, 9 suppressed), including PC/GPR/EPC/Cause/EXL and retained
hardware pending bits. The suppressed sentinel instruction sets s0 to hexadecimal
0x1234. The temporary adapter is retained only under ignored target, not linked
into production or the permanent test suite. Exact source guards pass for all
three pinned revisions and recorded Cause implementation blobs. Full workspace
and CLI checks pass, including the retained outer fixed-point deletion adversary.
