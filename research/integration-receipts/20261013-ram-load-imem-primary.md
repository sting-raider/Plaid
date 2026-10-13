# Primary integration: current RAM writers through decoded loads to RSP execution

Base:efde4daf0fc182843037cdb25fc442ce04c0e273. Claim:6151111749.
Harvest canonical unified CPU-copy/RAM/DMA/IMEM graph and exact pinned uncached
scalar/LW evidence. No raw branch/scaffold merge or separate lineage engine.

Controlled v24/fixture25 adds completed aligned direct-KSEG1 Word LW operand
reads, distinct from RAM instruction-fetch reads. Full before/completed GPR,
control/link/endian snapshots bind kernel32/IE0/BEV0/EXL0/ERL0/non-delay/big-endian
scope. Actual payload matches current captured RAM; full64 result sign-extends.
Each CpuRamLoad ancestry wrapper retains decoder/read/physical byte and current
RamByteOrigin. It is not an installed SP writer. Existing held CPU register,
XORI, RAM/IMEM copy and actual SP writer structures compose these parents.

Handler CPUwriter473 atRAMe02c already retains DMEM ingress152/read153/write155/
RAMwriter58/RSP parents. LW575/read576 selects473; identity XORI581 supplies a
fresh expression to IMEMwriter587/RSP589. RAMwriter595 installs equal NOP from
the same held old read/transform. Fresh LW600/read601 selects595, then IMEM607/
RSP609. The older read keeps473; a future/equal write cannot change it. Final
IMEM0 writers607. Both executable words and final RAM bytes are equal despite
distinct ancestry. Opaque RAM writers remain Unknown after equal writes. General
source/census/executable lifetime is not inferred from these discrete joins.

Actual610 events/102 full existing machine/cache/CP0/pipeline/TLB controls,
77 CPU steps/28 RSP words/7 RSP definitions agree baseline/disabled/enabled/repeat.
Full independent source/report graphs agree. All TWENTY-FIVE prior report bytes
remain EXACT; repeated generation/stale-source rejection PASS. No older
reference/full-ROM rebuild, Actions, ROM/assets or upstream production reuse.

Source:1c31804ba9f6d6f9bfbe408b4801816b6bb43182bc07a35324ccda7f6675bc6e.
Report:fc3cc641408506f716ee6363390fb3fae43498a9c41556750fc78f4dd8fbd3f4.
Baseline:ff26ba344b5d888e705449cdd55a47e19e99bb0acd4cb05dd40d5e3b12037f37.
Build:496ddec554cd35d44991509f92bd902987e7bd871bc43c6a9244c8bff530b6f7.
Sensor:ec672a9a6a889bb2b13f8833926b93924637b55e11354c90db5b708238051af6.
Build:4f3ed084057290ed71508e3fecf664e32e77015046b173c28f91966254665dad.
Results:faf5ef9e94690dc88bdf174b62cfda76ac956512825c389864e5d1b106c522fa.
Ignored capture:target/ram-load-imem-consumption-primary; reports:
target/ram-load-imem-integration-primary; logs:target/ram-load-imem-*.
Exact clean ISC ares9408cb43d4948fc3ea6e152a307a34348df3fe04; complete prior
source guards retained. Explicit pinned LW sign-extension check and immutable
lsb/readable.hpp audit7345688432645b5beab92df8f4899f7f27132ace0f08aa8e2d451e3ad632f96b
supplement existing RAM sink/layout/bus/io/CPU guards. Verify-existing reapplies
the current audit without rebuilding the reference or changing source bytes.

Focused62 Rust tests, actual/synthetic CLI and all prior adversaries PASS, with
15 RAM-load source/11 report forgeries. Missing/repeated/misbound/miswidth reads,
instruction-fetch-as-operand, wrong backing/state/endian/full result, stale equal
writer/read, future-writer substitution and old IMEM/final writer reject. Pure
tests retain per-byte physical offsets, opaque equal cuts and signed64 result;
cached/unaligned/foreign contexts reject. Earlier XORI report adversaries now
select actual transforming RAMwriter276 instead of the latest identity XORI-0,
so the changed-result forgery remains meaningful. Earlier shifted SB test selects
its code step by PC rather than assuming the penultimate instruction. No assertion
waiver or weakened production obligation.

Canonical gate on this final tree: cargo fmt --all -- --check; cargo clippy
--locked --workspace --all-targets --jobs2 -- -D warnings; cargo test --locked
--workspace --jobs2; python scripts/test_cli.py; git diff --check. Corresponding
issue4 closeout records final results, exact-head CAS and fetched verification.
STATUS/NEXT/DEVELOPMENT/ADR0118 record actual production composition, with no
progress milestone/native fallback change. Cached/mapped/degraded/failed/other
loads, global source/mutation census/root/lifetime/whole-ROM/native stay OPEN;
all flags false, ordinary static ERET unsupported.
