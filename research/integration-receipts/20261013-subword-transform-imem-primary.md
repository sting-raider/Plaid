# Primary integration: subword whole-SP-Word effects through transformed execution

Base:c44ecc9357f8926ec3fca50f45e10a4a377a4889. Claim:6150553046.
Harvest canonical cpu_sp_subword, ADR0066/spike018 completed device-width evidence
and the current unified graph. Preserve ares/Gopher/systemtest vs Mupen masked-
source disagreement; no raw branch/CI scaffold merge or hardware generalization.

Controlled v23/fixture24 binds decoded SB/SH full GPR/control/link/endian snapshots
and actual raw device addresses separately from aligned whole-SP-Word sinks.
Reuse verify_cpu_sp_subword_effect: nominal instruction width does not define
mutation width. Only completed Word effects create four-byte writer generations.
The optional existing CpuXorTransform representation now also accompanies IMEM
copy receipts in this profile; older profiles retain their original policy/shape.

Actual LW547/read548 loads current DMEM ingress152/read153/write155 with
RAMwriter58/RSP byte ancestry. XORI553 derives ADDU21. SB558/write559 at raw
device04001003 installs aligned Word04001000; RSP561 actually consumes writer559.
SH566/write567 at raw device04001002 installs the equal full Word; RSP569 selects
writer567. Both copy receipts retain read548/transform553 and distinct sink
identity. Final IMEM0 bytes select567. No opcode/equality/final image creates
source ancestry. Existing root/return/mapping/cache/RAM graphs remain intact.

Only actual shift-zero lanes (SB lane3/SH lane2) support identity-word ancestry.
A synthetic SB lane0 variant retains the21000000 Word witness while omitting
that copy receipt (six copies instead of seven); its unsupported shifted RSP
word is not executed. This is a reducer regression, separate from the actual
reference capture. Shifted-lane/general transform ancestry remains OPEN.

Actual570 events/94 full existing machine/cache/CP0/pipeline/TLB controls,
71 CPU steps/26 RSP words/7 RSP definitions agree baseline/disabled/enabled/repeat.
Independent complete event/report graphs agree. All TWENTY-FOUR older report
bytes remain EXACT, repeated generation and stale rejection PASS. No older
reference/full-ROM rebuild or Actions.

Source:dc5cb5beb9514b807e6917ef942d0c2029d86dbd28807e736b4d50999cdbc424.
Report:8a36cdde08e19c12866f7a0069278a76c53029e038f7cff99ca2dbb051bc8825.
Baseline:c264ef28810c3872cb9092955335b4c9c85be9e63cfa33d3afb5f024c6c239ca.
Build:d512ebb7939c93ab85c86b5cb0873021c6edac78032e8f0dd8380e22f0a55a7a.
Sensor:7d075b8dfbb4220e6c0bd43cb50a2baa10a79d6099bf000809eab96a276d3a28.
Build:d3f7ab553dac93e20166e3f8209a20fd0945671982b85b3b1476a79d152ee386.
Results:804f0ecae43a156da7921cb9d62c66c197af1b9494a0fad58cb419319591cbf4.
Ignored capture:target/subword-transform-imem-consumption-primary; reports:
target/subword-imem-integration-primary; logs:target/subword-imem-*.
Exact clean ISC ares9408cb43d4948fc3ea6e152a307a34348df3fe04. New immutable
memory/io.hpp audit:54089251052dbffddf7ae77819c3a3bb494cf7269ae874a3015a23907370a69c;
memory/bus.hpp:1cbe65b06ab32c10134912b45b33100dfec4b1703104fadb304dcf03b343b295.
Existing complete CPU/IPU/SCC/TLB/exception/DMA/cache guards retained. Passive
getters/existing callbacks only; no changed guest semantics or upstream production reuse.

Focused60 Rust tests plus actual/synthetic CLI adversaries,14 source/10 report
forgeries, shifted-lane positive check and original v22 adversaries PASS. Missing,
duplicate, nominal-width, misbound bank/address/payload/endian/control/fullGPR
effects and stale equal sink/read/transform/final-writer parents reject. The
shifted synthetic code's RAM-fetch completion must match its changed raw read;
the regression was corrected to bind both observations, without an assertion
waiver. A conditional forgery now selects its actual failed-attempt context513
instead of assuming a position in the longer tail.

Canonical gate on this final tree: cargo fmt --all -- --check; cargo clippy
--locked --workspace --all-targets --jobs2 -- -D warnings; cargo test --locked
--workspace --jobs2; python scripts/test_cli.py; git diff --check. Corresponding
issue4 closeout records final results, exact-head CAS and fetched verification.
STATUS/NEXT/DEVELOPMENT/ADR0118 record production composition. No progress
milestone/ROM/assets/native fallback change. Hardware, fault/alias/endian,
global source/mutation census/root/lifetime/whole-ROM/native remain OPEN;
all completeness flags false, static ERET unsupported.
