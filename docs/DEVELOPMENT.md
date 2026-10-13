# Development guide

This document keeps build, verification, CLI, and reference-lab details out of the README.

The authoritative engineering state is still [`STATUS.md`](STATUS.md) and [`NEXT.md`](NEXT.md).

## Toolchain

Core development requires:

- Rust toolchain from `rust-toolchain.toml`
- a C compiler for the pinned Rabbitizer dependency
- Python 3.11+
- additional Linux/WSL build tools for reference experiments

Some pinned Mupen/ares experiments require GCC/G++, make, NASM, SDL2/zlib/libpng development packages, or other dependencies described by the relevant `spikes/` README.

External reference repositories are pinned in [`../refs.lock.toml`](../refs.lock.toml) and are kept outside the repository.

Fetch the reference lab with:

```bash
python scripts/fetch_refs.py
```

Local ROMs belong in ignored `roms/`. Derived traces, maps, reports, and corpora belong in ignored `artifacts/`.

## Fresh-worker environment bootstrap

A new direct-integration worker is expected to bootstrap its environment when it starts empty.

Missing `cargo`, a missing Plaid checkout, or absent pinned references at startup are setup tasks, not reasons to skip the lane.

Typical bootstrap flow:

```text
1. clone or obtain a writable Plaid checkout
2. fetch latest main
3. inspect rust-toolchain.toml
4. install the required Rust toolchain if necessary
5. ensure Python and required native build packages are available
6. fetch refs with scripts/fetch_refs.py or fetch only the exact pinned ref needed
7. verify the local commands work
8. continue with integration work
```

Workers may use the environment's normal package manager, Rust bootstrap tooling, and network access to install open-source build dependencies. Do not use GitHub Actions merely because the fresh runtime starts without the toolchain.

Only treat environment setup as genuinely unavailable after reasonable setup attempts show a hard runtime restriction, such as no usable shell/install path or no way to obtain a required dependency. If useful candidate work already exists by then, preserve it as a validation handoff.

Historical direct-integration results marked `BLOCKED` only because a fresh session lacked `cargo`, a checkout, or a pinned reference should be treated as recoverable prepared candidates after bootstrap.

## Canonical local validation

GitHub Actions is manual-only. Integrations should be validated locally.

Run at minimum:

```bash
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace
python scripts/test_cli.py
python tools/progress.py --check
```

When a change touches a retained synthetic contract, run the relevant `spikes/*/test_verify.py` checks as well.

When reference semantics matter, reproduce against the exact revision in `refs.lock.toml` rather than an arbitrary upstream checkout.

Historical CI is supporting evidence only. It is not a substitute for validation of the exact candidate tree being proposed for `main`.

## Main CLI

Useful discovery commands include:

```text
plaid rom-info <rom>
plaid check-trace <trace.ndjson>
plaid check-map <map.json>
plaid discover <rom> <rom_offset> <guest_start> <size> <entry> <out.json>
plaid import-trace <rom> <trace.ndjson> <out.json>
plaid import-fetch <rom> <fetch.ndjson> <out.json>
plaid verify-fetch <rom> <fetch.ndjson> <map.json>
plaid import-boot-fetch <rom> <firmware> <fetch.ndjson> <out.json>
plaid verify-boot-fetch <rom> <firmware> <fetch.ndjson> <map.json>
plaid merge <left.json> <right.json> <out.json>
plaid solve [rom] <map.json>
```

Numbers accept decimal or `0x` notation.

For a canonical local `.z64` ROM, the ignored capture recipe in
`spikes/057-local-boot-capture/` accepts an explicit NTSC CIC configuration
(`CIC-NUS-6102` or `CIC-NUS-6105`). It reuses the pinned v5 observer, records
disabled/repeated controls and keeps ROM/firmware/captures external to git.
Reuse a compatible build with `--build`, or replay sources with
`--verify-existing`. Preserve an independent CIC diagnostic; the selected
profile is a reference configuration declaration. Import and recheck with the
boot-fetch commands above; finite raw fetches retain unknown execution identity.
The recipe's optional `--history sp` mode selects the existing actual PI/queue/SP
observer. `--baseline` requires exact prior v5 trace/checkpoint/message equality;
canonical `inspect-sp-writer-fetch` / `verify-sp-writer-fetch` provide complete
typed primitive rechecking under independently retained paired source digests.
For multi-million-record sources, build the project CLI with
`cargo build --locked --release -p plaid`; this does not rebuild the reference.

`discover` requires an explicit load mapping. Trace import compares captured DMA-backed code against canonical ROM bytes. Supplying a ROM to `solve` enables source-witness rechecking. The CLI whole-ROM solve path remains fail-closed; producing a report is not the same as reaching `CLOSED`.

For discovery sources preserved independently at a trusted capture/import boundary:

```bash
plaid create-trace-expectations <new-expected.json> <trace.ndjson>...
plaid solve-traces <rom> <map.json> <expected.json> <trace.ndjson>...
```

Expectation creation refuses to overwrite an existing file. Preserve that file
under a stronger trust boundary than editable maps and traces; recreating it from
an edited submission removes deletion resistance. `solve-traces` authenticates
the exact expected source set and rechecks raw primitives, installed-entry
projections using the ROM-aware importer before running the existing whole-ROM
solver. Completed compilations must retain their source-bound roots, even without
install events; supplied instruction words cannot replace the captured snapshot.
Its report includes the expectations and canonical map digest. It uses
the same empty known-image set and budget as CLI `import-trace`; library callers
must supply their original import context separately from solver image witnesses.
This does not authenticate every derived fact, prove complete sensors, or replace
fetch/cache/mutation/lifetime verification for other evidence domains.

Compose SP captured writers with executable backing reads using independently
preserved source receipts:

```bash
plaid inspect-sp-writer-fetch <rom> <firmware> <fetch.ndjson> <history-v3.ndjson> <expected-history-sha256> <expected-fetch-sha256> <report.json>
plaid verify-sp-writer-fetch <rom> <firmware> <fetch.ndjson> <history-v3.ndjson> <expected-history-sha256> <expected-fetch-sha256> <report.json>
```

These commands retain the complete existing SP/PI/access/fetch projection and
add compatible per-byte captured writer candidates. Unknown ordinary RSP or
out-of-band writers prevent ultimate-ancestry claims even when all fetched bytes
match recorded sinks. A contradictory actual read cuts affected candidates until
a new sink; later equal bits cannot heal them. Keep the external receipts outside
editable submissions. `python scripts/test_sp_writer_fetch.py` exercises this
composition and its legacy/source/report/input boundaries with synthetic bytes.

Compose recorded PI ROM-byte writers through RAM backing, full I-cache fills and
discrete executable consumption on the same complete v3 clock:

```bash
plaid inspect-sp-pi-fetch-lineage <rom> <firmware> <fetch.ndjson> <history-v3.ndjson> <expected-history-sha256> <expected-fetch-sha256> <report.json>
plaid verify-sp-pi-fetch-lineage <rom> <firmware> <fetch.ndjson> <history-v3.ndjson> <expected-history-sha256> <expected-fetch-sha256> <report.json>
```

These reuse the existing finite PI byte-chain engine, retain all nested SP/queue/
PI/access/fetch reports and bind original raw v3 writer/fill/read ordinals. Equal
scalar/burst writes cut old backing candidates; resident cache bytes retain their
captured parents until a witnessed replacement/invalidating transition. Unsupported
or contradictory observations stay unknown. Sample endpoints are discrete fetches,
not lifetime intervals; same-value unsensed writes prevent a mutation census.
No ProgramMap identity or whole-ROM/native certificate follows from this report.
Legacy v2 commands remain compatible. The independent spike038 replay accepts
both formats; raw SP rows remain hashed without supplying RAM origin claims.

For the declared RSP/CPU IMEM source profile:

```bash
plaid inspect-rsp-cpu-imem <history.json> <expected-source-sha256> <report.json>
plaid verify-rsp-cpu-imem <history.json> <expected-source-sha256> <report.json>
python scripts/test_rsp_cpu_imem.py
```

The explicit `plaid-rsp-cpu-imem-history-v1` definition profile additionally
checks full ORI/ADDU register/control boundaries and retains raw-context parent
nodes through scalar RSP stores into CPU IMEM copy chains. Reentry cuts tags;
captured incoming registers remain opaque. Legacy v0 reports stay byte-compatible.
`python scripts/test_rsp_definitions.py` exercises source/report/profile/phase
boundaries; spike058 retains the exact pinned actual component controls.

The v2 word-read profile additionally requires an actual in-context completed
RSP LW read, checks raw address/modulo-bank offset/payload and retains each byte
writer in a load definition before propagating it through later stores/copies.
The original unaligned-read result is sensed once. Missing, duplicate and
equal-valued decoy reads reject; zero destinations still require the read.
Use spike059 controls and `python scripts/test_rsp_definitions.py --word-reads`.
V0/v1 inputs/reports remain compatible; no mutation/lifetime/closure flag changes.

The controlled v3 profile additionally requires complete initial/final IMEM
images, records opaque host code seeds and checks each actually decoded RSP word
against current modeled bytes. Discrete fetches retain four current writer IDs,
connecting a CPU install to the existing RSP definition/copy graph. Use spike060
controls and `python scripts/test_rsp_definitions.py --execution`. Retained
v0/v1/v2 reports remain exact; general mutation/lifetime/closure stays uncertified.

Controlled v4 additionally declares a bounded identity-RAM snapshot, retains
actual descriptor-selected DMEM reverse-DMA Word effects and requires each CPU
decoder context to consume the exact completed uncached fetch/read. Byte parents
stay separate from request lifetime and DMA atomicity. Use spike061 controls and
`python scripts/test_rsp_definitions.py --dma`; v0-v3 reports remain exact.
General mutation/cached/mapped/lifecycle/closure obligations stay open.

Controlled v5 additionally requires actual promoted-current identity and complete
descriptor-derived DMA Word/lane/length/count/skip/end progression. A partial
nonempty sink set cannot acquire completion. Use spike062's authenticated reused
baseline controls and `python scripts/test_rsp_definitions.py --promoted`.
V0-v4 reports remain exact; pending/FIFO/hardware/general-lifetime flags stay open.

Controlled v6 additionally requires actual Dual RAM read/IMEM install pairs and
retains each current RAM byte writer through actual RSP fetched-word consumption.
IMEM ingress completion counts one Dual install per block; DMEM egress counts
two Word writes. Use spike063 controls and
`python scripts/test_rsp_definitions.py --roundtrip`; v0-v5 reports remain exact.
Unknown parents and equal-value overwrite cuts remain explicit; closure stays open.

Controlled v7 distinguishes all three represented DMA directions and requires
both actual Word source reads before either lower DMEM store. Each store retains
its own exact read and prior RAM byte parents; subsequent RSP LW definitions
consume them. Use spike064 controls and
`python scripts/test_rsp_definitions.py --dmem-ingress`. V0-v6 reports remain exact;
unsupported failed/OOB sources and general completeness obligations stay open.

Controlled v8 adds an initially empty pending-slot snapshot and completed address/
length mutations before transfer-start. Replay masked fields, keep equal recommits
distinct, retain latest address writers even after the length commit, and require
immediate promotion whenever FULL is idle. Use spike065 controls and
`python scripts/test_rsp_definitions.py --pending`; v0-v7 reports stay exact.
The host-driven MMIO fixture supplies no guest operand ancestry or hardware policy.

Controlled v9 additionally checks decoded CPU SW effects into direct-KSEG1 SP
address/length registers, with one exact pending mutation per decoder context and
synchronous promotion only immediately after the accepted length effect. Retain
the commit decoder identity through the existing install/fetch graph. Use spike066
controls and `python scripts/test_rsp_definitions.py --decoded-mmio`; v0-v8 reports
stay exact. Its explicit post-decoder DMA drain schedule proves no general timing.

Controlled v10 adds actual completed I-cache burst/fill records, uses the canonical
`FetchCacheLine.validate` boundary and keeps fill-time RAM byte parents through
cached hits after backing changes. Cached receipts are separate from uncached
scalar reads. Explicit host PC seeds cut register definitions and remain unknown
execution roots. Use spike067 controls and
`python scripts/test_rsp_definitions.py --cached-cpu`; v0-v9 reports stay exact.

Controlled v11 binds actual decoded direct-KSEG0 CACHE HitInvalidateI to one
completed operation with exact effective address and complete cache before/after
tuples. Hits end resident fill eligibility; misses preserve it. Keep invalid
slot contents for later transition checks. A subsequent DMA writer and completed
refill supply new executable parents even when instruction bits equal the old
line. Use spike068 and `python scripts/test_rsp_definitions.py --cache-invalidation`;
v0-v10 reports stay exact. Other cache operations remain unsupported; the powered
initial cache and explicit host roots grant no general lifetime/census proof.

Controlled v12 joins the existing actual SP LW/held-register verifier to one
completed direct-KSEG1 CPU SW RAM effect per decoder. Preserve load/read IDs and
byte parents in its writer receipt; no held definition means UNKNOWN byte cuts.
SW copies low32 bits but the held definition must match the complete source GPR.
Cached hits keep fill-time parents; invalidation/refill captures the new CPU
writer. Explicit opaque roots may include uncached fetch/scalar-read boundaries
in this profile and still cut register definitions. Use spike069 and
`python scripts/test_rsp_definitions.py --cpu-ram-copy`; v0-v11 reports stay exact.
General cached data copies/transforms/source/mutation/lifetime remain OPEN.

Controlled v13 checks full64 XORI with a zero-extended u16 immediate, no scalar
effect and exact complete GPR result. One in-place transform retains its held
LW definition and original byte parents with a distinct expression/context;
repeated/renamed/unattributed transform sources lose that candidate. Transformed
SP stores do not receive identity IMEM-copy witnesses. Use spike070 and
`python scripts/test_rsp_definitions.py --cpu-xori`; v0-v12 reports stay exact.
This composes actual transformed RAM code with cache invalidation/refill and
decoder consumption; broader transforms/decompression/relocation stay OPEN.

Controlled v14 binds BREAK before/after exception state in its actual decoder
scope, using `resolve_exception_root` for the BEV0/kernel32 General vector. Check
non-delay/non-nested cause9/EPC/EXL and unchanged complete GPRs. Require immediate
first cached root fetch/decoder, preserving the handler fill/writer identities;
reject opaque reseeding, interleaving and truncation. The fixture uses the actual
exception PC for handler entry, without a host setter. Use spike071 and
`python scripts/test_rsp_definitions.py --break-root`; v0-v13 reports stay exact.
This proves one controlled occurrence, never complete root reachability/lifetime.

Controlled v15 requires an uncut live exception-produced EPC generation through
the permitted handler stream. Opaque PC seeds cut candidate ownership; unknown/
unsupported CP0 writers/reset/restore cannot borrow equal past capture values.
ERL0/kernel32/IE0 ERET must select that current EPC, clear EXL/LLbit, preserve full
GPRs, then immediately fetch/decode the cached target. The bounded frame is
consumed, without clearing physical EPC. Use spike072 and
`python scripts/test_rsp_definitions.py --eret-return`; v0-v14 reports stay exact.
Handler/return steps use actual PCs without host setters. Static discovery still
rejects ERET; general CP0/ERL/interrupt/mutation/lifetime closure remains OPEN.

Controlled v16 adds completed MFC0/MTC0 EPC access states in the original decoder
clock. CP0 ancestry is separate from physical SP/RAM loads. A held read must match
the full source GPR and current EPC generation; every accepted equal-value MTC0
gets a fresh writer ID. ERET selects that writer. LW/XORI/ADDU destinations and
opaque roots cut held CP0 ancestry even on equal values. Changed targets and other
CP0 writers remain unsupported. Use spike073 and
`python scripts/test_rsp_definitions.py --guest-epc`; v0-v15 report bytes stay exact.

Controlled v17 retains one actual in-place XORI on a held current EPC read using
the existing full64/unsigned-u16 transform receipt. MTC0 binds the computed value
to its completed EPC, and ERET selects the latest writer's state. Repeated,
renamed, unattributed or opaque-cut transforms cannot supply target ancestry.
New reads bind to the current writer even after a changed target. V16 policy and
v0-v16 reports remain exact. Use spike074 and
`python scripts/test_rsp_definitions.py --epc-target`; general mapping/root/
mutation/lifetime/native obligations remain OPEN.

Controlled v18 observes TLBWI at the actual selected-slot write/synchronize
boundary. Before/after CP0 eligibility/staged/table states retain full32-entry
normalized data; snapshot differences cannot mint generations. Reuse the typed
`TlbwiGeneration` receipt with original unified ordinals and derived entry hashes.
Mapped fetches require current raw table/ASID/mode, unique low-region4KiB valid
CCA3 translation and latest completed selected-slot writer. Invalid overlapping
matches also cause rejection. Mapping writes do not retire I-cache generations.
Use spike075 and `python scripts/test_rsp_definitions.py --mapped-root`; all
v0-v17 report bytes remain exact. Broader mapping/context/census/lifetime/native
remain OPEN; pinned Gopher/ares synonym-index disagreement stays explicit.

Controlled v19 adds an actual EntryHi setter callback and before/completed CP0/
staged/table snapshots. Bind decoded MTC0/nonzero GPR/full value to masked ASID/
VPN/region while requiring installed table unchanged. Current context writer
is separate from the slot operation; same-value writes still replace it. Mapped
fetches select both identities. Use spike076 and
`python scripts/test_rsp_definitions.py --entryhi-context`; v0-v18 bytes stay
exact. Initial captured GPR/context values retain unknown ultimate ancestry;
broader context sources/hazards/census/lifetime/native remain OPEN.

Fixture20/spike077 reuses that v19 protocol for nonidentity VA e028 -> PA6028.
Mapped hits on both sides of guest ASID restoration select surviving fill292,
not current RAM BREAK bytes; actual invalidation/refill then enters BREAK and
the natural changed-EPC return. Run
`python scripts/test_rsp_definitions.py --mapped-reactivation`; no new consumer
or profile is needed. Cache colors are congruent; the pinned reference index
disagreement and general changed-physical-selection/census/lifetime remain OPEN.

Controlled v20/spike078 adds the actual EntryLo0 masked setter occurrence and
full decoded GPR/CP0/staged/table state. Staged page writes stay separate from
installed mappings; TLBWI fixes the completed page-writer parent for that slot,
and mapped executable consumption retains it separately from current ASID.
Same-value writes replace occurrence identity. Run
`python scripts/test_rsp_definitions.py --entrylo-remap`; earlier report shapes
omit the new optional parents. General CP0/mutation/mapping/lifetime remain OPEN.

Controlled v21/spike079 observes successful TLBR after the selected-slot copy.
Full normalized data derives canonical `TlbrContextGeneration`; selected
installed write/page parents remain separate from latest active context. Mapped
consumers select EntryHi or TLBR by occurrence. Loads preserve installed table/
cache, and restore staged page ancestry for later TLBWI. Run
`python scripts/test_rsp_definitions.py --tlbr-context`; older optional report
fields remain omitted. General no-load/Index/privilege/census/lifetime remain OPEN.

Controlled v22/spike080 composes direct-SP Word LL/SC with actual IMEM/RSP
consumption. Before/completed GPR/CP0/link snapshots check pinned transitions;
completed sinks use `cpu_sp_conditional` and preserve pre-SC payload separately
from rt's success flag. The flag cuts held register ancestry. Failed attempts
leave old writers; equal successful effects create fresh generations. Run
`python scripts/test_rsp_definitions.py --conditional-imem`; earlier report bytes
stay exact. The direct-SP check is pin-specific, not a hardware reservation policy;
general fault/cached/mapped/lifetime/census/native obligations stay OPEN.

Controlled v23/spike081 composes actual CPU SB/SH with the canonical subword
normalizer and IMEM/RSP consumption. Keep raw device and aligned Word addresses
separate, bind direct mapping and before/completed control/endian data, and reuse
the existing XORI receipt in optional IMEM-copy transforms. Identity-copy ancestry
requires an actual shift-zero lane; other lanes retain the mutation witness only.
Run `python scripts/test_rsp_definitions.py --subword-imem`; earlier shapes/bytes
stay exact. General faults/aliases/endian/shift ancestry/census/native remain OPEN.

Controlled v24/spike082 composes actual decoded direct-KSEG1 RAM LW with current
RAM writers and existing held CPU expressions/RAM/IMEM sinks/RSP execution.
Operand reads have their own kind, control/endian snapshots and full signed GPR
result; `cpu_ram_load` byte wrappers preserve the actual read and physical writer
parents. Equal later RAM writes cannot change earlier held reads, while a fresh
read selects the new writer. Run `python scripts/test_rsp_definitions.py
--ram-load-imem`; earlier report bytes remain exact. Cached/mapped/degraded/failed
and other loads/global census/root/lifetime/whole-ROM/native stay OPEN.

Controlled v25/spike083 uses the canonical D-cache replay for actual cached
direct-KSEG0 Word LW and HitInvalidateD. Bind primitive occurrences to their
decoded scope, complete resident snapshots and bounded control/GPR results;
capture RAM parents at actual backing reads and resolve each delivered byte
through its resident fill. Current backing is diagnostic context. Existing held
CPU expressions/RAM/IMEM copies retain these cached parents. Run
`python scripts/test_rsp_definitions.py --cached-ram-imem`; all earlier shapes
stay exact. Cached mutation/writeback/mapping/dirty/global census/lifetime/native
remain OPEN.

Controlled v26/spike084 adds actual cached Word SW and successful dirty-hit
HitWritebackD to that same state. Bind complete after-store payload/dirty mask
and full control/GPR boundaries; preserve equal mutation identity. Only an actual
complete16-byte backing burst creates RAM writeback parents, including clean
lanes. CPU completion must preserve the line and clear dirty bits. Cached reads
resolve mutation occurrences; uncached reads resolve exported RAM occurrences.
Run `python scripts/test_rsp_definitions.py --writeback-imem`; all prior reports
remain exact, broad width/mapping/census/lifetime/native obligations stay OPEN.

Fixture28/spike085 reuses v26 for complete writeback -> mapped I-cache/CPU
consumption. Surviving cached bytes retain old fill/writer identity despite equal
new backing; actual guest invalidation and fresh complete refill selects the
export. Run `python scripts/test_rsp_definitions.py --writeback-cpu`. Source
profile downgrade tests select an older distinct protocol when fixture versions
share one format. No new verifier/schema or general lifetime/native scope.

`plaid-rsp-cpu-imem-history-v0` preserves unified decoder/effect ordinals, initial
and final byte snapshots, and independent CPU step snapshots. Its explicit ares
profile permits controlled RSP reentry seeds, CPU register/control continuity,
scalar RSP stores and the observed SBV vector-register-2/element-0 input. Other
vector sources, branches, cache/TLB/DMA/restore interleavings reject. The report
connects observed writers to CPU register definitions and IMEM installs; it does
not claim incoming operand ancestry, executable consumption or a complete census.

Use `plaid --help` and the relevant subcommand `--help` for the exact current argument list.

The library's cached exception-root history v2 (`RESTORE_FORMAT` and
`RESTORE_PROFILE`) admits successful `restore` boundary records with a captured
snapshot SHA256 label. Each boundary cuts all old resident/backing observer
parents; it does not invalidate hardware cache or authenticate the snapshot bytes.
V0/v1 continue rejecting restore. Test the complete source/report boundary with
`cargo test --locked -p plaid-core --test exception_root_lifetime_composition`.

For composed D-cache resident reads and writebacks:

```bash
plaid inspect-dcache-resident-reads <history-v1.json> <expected-source-sha256> <report.json>
plaid verify-dcache-resident-reads <history-v1.json> <expected-source-sha256> <report.json>
python scripts/test_dcache_resident_reads.py [retained-pointer-evidence.json]
```

The explicit `plaid-dcache-resident-read-history-v1` source extends the v0
writeback events with completed backing Word mutations and cached Word reads.
Direct KSEG0 identity RDRAM geometry, captured resident bytes and slot continuity
are checked. Reads and exports share generations/revisions/byte origins; the
nested writeback projection's source digest and event count cover the entire v1
clock. V0 inspection/report bytes keep their previous contract and reject v1.
Backing context records only captured writes, never invented initial writers.
This normalized access protocol does not authenticate decoded LW operands or a
subsequent JR, physical table immutability, complete sensing or target closure.

Compose source-bound COP1 FPR lineage with separately preserved completed-store
normalization contexts:

```bash
plaid compose-cop1-mutations <fpr-history.json> <expected-source-sha256> <contexts.json> <expected-contexts-sha256> <report.json>
plaid verify-cop1-mutations <same-inputs>
python scripts/test_cop1_mutation_lineage.py [retained-actual-matrix.json]
```

Every store occurrence must have exactly one normalization context. The canonical
COP1 verifier checks the supplied instruction/GPR/FPR/FR/CU1 inputs and completed
effect; its FPR snapshot, selected lanes, ordinal and direct-KSEG1 destination
must agree with the source replay. Reports preserve the full lineage and all
normalization inputs. External digests must be retained independently of editable
submissions. This checks the represented facts, without proving the ancestry or
complete capture of those architectural contexts or backing memory producers.

For decoded cached store64-to-backing composition:

```bash
plaid inspect-dcache-store64 <history-v2.json> <expected-source-sha256> <report.json>
plaid verify-dcache-store64 <same-inputs>
python scripts/test_store64_writeback.py [retained-reference-results.json]
```

V2 retains decoded operand/register/control snapshots and ordered concrete
subwrites. Each effect must match the pinned decomposition, actual direct/endian
physical sink, selected resident line and complete after-snapshot. Source
generations flow through exact successful backing exports. This bounded profile
requires prefilled identity-RDRAM, kernel32 and BEV1; unsupported contexts reject.
V0/v1 source/report contracts remain compatible, including the exact retained
v1 pointer report digest. Reports certify neither upstream register definitions,
hardware atomicity, complete source coverage nor executable/native lifetime.

## Source-bound history consumers

Plaid also contains strict consumers for bounded research histories. These are deliberately separate from claims of whole-ROM completeness.

Current families include:

```text
inspect-boot-history / verify-boot-history
inspect-pi-boot-history / verify-pi-boot-history
inspect-pi-queue-boot-history / verify-pi-queue-boot-history
inspect-pi-fetch-lineage / verify-pi-fetch-lineage
inspect-sp-boot-history / verify-sp-boot-history
inspect-pif-boot-history / verify-pif-boot-history
inspect-cpu-copy-history / verify-cpu-copy-history
inspect-cpu-definitions / verify-cpu-definitions
```

Each verifier reconstructs or rechecks facts from complete supplied sources rather than trusting an editable report. The exact supported protocol/version and remaining obligations are documented in the corresponding module, tests, ADR, research note, or integration receipt.

A bounded source-bound receipt does **not** by itself establish:

- sensor completeness;
- whole-program mutation completeness;
- executable lifetime;
- universal mapping/TLB history;
- whole-ROM closure;
- native completeness.

## Reference experiments

### Mupen

The Mupen instrumentation is maintained as a separate research boundary because of licensing and architectural separation.

Useful scripts include:

```bash
python scripts/test_mupen_hooks.py
python scripts/test_mupen_execution.py
python scripts/test_mupen_session.py
```

These exercises cover different scopes. For example, the hook harness can compile and test instrumented routines without executing generated host code, while the execution harness compares synthetic integer/control behavior between the pinned dynarec and interpreter.

Do not generalize a bounded fixture into a whole-ROM or hardware claim.

### ares

`spikes/003-ares-oracle/run.py` builds the pinned ares reference separately and runs original synthetic cartridge, memory, exception, and cross-reference cases.

Many later `spikes/` directories contain more narrowly scoped cache, TLB, PI/SP/PIF, RSP, exception/root, and mutation experiments. Their README and verifier define the exact claim.

Reference disagreement is evidence, not something to silently average away.

## Raw fetch and boot-source formats

The repository has several versioned fetch/history formats created during provenance research. Later formats retain progressively more physical/cache/source context while preserving explicit unknown states.

Important rules across these formats:

- current backing bytes do not identify cached resident bytes;
- equal payloads do not identify producer generations;
- physical addresses do not establish ultimate origin;
- observations do not prove an exhaustive event census;
- missing/ambiguous source information remains unknown;
- source/report verification must bind the complete supplied inputs.

See [`STATUS.md`](STATUS.md), [`NEXT.md`](NEXT.md), [`DECISIONS.md`](DECISIONS.md), and the relevant `research/` receipts for exact protocol details.

## Progress-map generation

[`progress.json`](progress.json) is the milestone source of truth.

Regenerate:

```bash
python tools/progress.py
```

Check without rewriting:

```bash
python tools/progress.py --check
```

Do not mark a milestone verified merely because a research branch exists. The progress map describes canonical `main`.

## Swarm development and canonical writes

Automated workers should read:

- [`../AGENTS.md`](../AGENTS.md)
- [`../ORCHESTRATION.md`](../ORCHESTRATION.md)
- [`STATUS.md`](STATUS.md)
- [`NEXT.md`](NEXT.md)
- [`DECISIONS.md`](DECISIONS.md)

Research/integration workers coordinate semantic ownership through issue #4.

In user-authorized direct-integration mode there is **no main-write lease**. Workers may prepare and validate in parallel, but a canonical write must use exact-head compare-and-swap:

1. fetch `main` and record exact SHA `A`;
2. reconcile the candidate onto `A`;
3. run all required local validation on that exact tree;
4. refetch `main` immediately before the write;
5. if it moved, reconcile and rerun validation;
6. if it is still `A`, update `main` atomically with `expected_sha=A`;
7. if the CAS loses a race, fetch the winner, reconcile, retest, and retry.

Never force-push `main`. Never land a candidate validated only against an older parent. A claim in issue #4 prevents duplicated semantic work; it does not reserve the canonical branch.

### Validation handoffs

Workers should bootstrap required tooling themselves. A handoff is for a genuine late task-specific setup failure after useful work exists, not for an initially empty fresh runtime.

When a handoff is necessary, record what setup was attempted, the exact candidate branch/head, the remaining commands, and the environment failure. Another worker should bootstrap the required environment, reconcile the semantic change to current `main`, rerun the full gate, and perform the CAS.

Do not relax the local gate to avoid a handoff.

## Scope discipline

The canonical D-cache primitive state can also replay occurrences on a containing
source's original clock. Internal callers authenticate and validate that complete
clock; primitive ordinals must increase, and a backing read/fill pair still must
be adjacent. Standalone v0/v1/v2 sources retain their complete contiguous ordinal
gate and existing report shapes. Reuse this state for decoded cached operands;
do not create another resident policy or infer incoming writer ancestry from
current backing equality. A rejected transition consumes its state and supplies
no usable continuation or receipt.

Plaid's strongest rule is also the boring one: do not convert uncertainty into confidence by changing vocabulary.

A fact can be useful while still being partial. A reference can be informative while still disagreeing with hardware or another reference. A source-bound receipt can be valid while still not proving a complete executable lifetime.

When in doubt, leave the obligation open and document why.
