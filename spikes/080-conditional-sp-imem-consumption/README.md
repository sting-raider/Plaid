# Completed conditional stores compose with actual IMEM consumption

Run `python spikes/080-conditional-sp-imem-consumption/run.py` or `--verify-existing`,
then `python scripts/test_rsp_definitions.py --conditional-imem --source
target/conditional-sp-imem-consumption-primary/source.json`.

Controlled v22/fixture23 extends the existing unified graph with aligned direct-
SP Word LL/SC. Full GPR/CP0/link before/completed observations verify the pinned
read and control transitions. Actual completed Word sinks use the existing
`cpu_sp_conditional::verify_sc_sp_effect` normalizer; opcode, flag and equal
payload alone never create writers. The pinned direct-SP effect/result check
rejects contradictions; it is not an N64-wide reservation policy. Interrupted,
faulting, cached/mapped/reverse-endian accesses and general reservation lifetime
remain unsupported. Continuous linked snapshots are checked; opaque roots and
other CPU instructions cut observer ownership, not physical reservations.

Failed SC511 has no sink and sets rt=0; RSP fetch513 still consumes old CPUwriter50.
Actual LL518/read519 captures current DMEM/DMA/RSP byte ancestry. SC524/write525
installs equal NOP bytes in IMEM0 and sets rt=1, cutting the held source-register
parent. RSP fetch527 selects writer525. Fresh LL532/read533 supplies another read
generation; SC538/write539 installs equal NOP again, and RSP fetch541 selects539.
Both successful copy receipts retain their distinct LL reads and source bytes.
All IMEM images remain equal while actual writer identities change.

Complete542 events/88 existing full machine/cache/CP0/pipeline/TLB controls and67
CPU steps plus24 RSP words agree baseline/disabled/enabled/repeat. The independent
complete source/graph agrees, including new attempts, copies and final writers.
All prior reports are replayed without older reference builds. Missing/duplicate/
misbound sinks, success flag substituted for payload, wrong linked state, stale
equal writer/read parents and failed attempts promoted to writers reject.

Preserve the retained ares/Mupen/Gopher reservation disagreement. These finite
reference facts do not establish hardware reservation semantics, census or
executable lifetime. All general proof/native flags stay false; whole-ROM/native
closure and static ERET remain OPEN/unsupported. Generated reference objects,
notices, controls and reports stay ignored under target/; no upstream production
implementation copied or linked.
