# Primary integration: completed conditional writers through IMEM execution

Base:c89450590fb1a5b6289781a2f9cd729c92fa5196. Claim:6149970875.
Harvest canonical cpu_sp_conditional and LL/SC completed-effect research
cb037060c43c8bc4bace1b7db1fc8b607be3a8d3, preserving reservation disagreement
8abead9a26e5e086d54a395e060505a1002a1704. No raw branch/CI scaffold merge.

Controlled v22 extends the shared graph for aligned direct-SP Word LL/SC.
Capture full before/completed GPR/CP0/link state at existing decoder callbacks.
LL requires its actual Word read, signed register result and pinned link address/
LLbit update. SC normalization consumes an independently completed Word sink
through canonical verify_sc_sp_effect; opcode, equality, LLbit and rt=1 alone
never mint a writer. Before-state binds address/payload before rt is overwritten;
successful/failed SC ends cut held GPR/CP0 ancestry. Pinned direct-SP effect/result
checks reject contradictory captured state, without defining universal reservation
semantics. Continuous linked state is checked through permitted observations;
opaque roots and other CPU instructions cut observer ownership, not LLbit itself.

Failed SC511/no sink -> RSP513 selects old IMEM writer50. Actual LL518/read519
captures current DMEM ingress152/read153/write155 -> RAMwriter58/RSP parents;
SC524/write525 installs equal NOP atIMEM0, then RSP527 selects525. Fresh LL532/
read533 supplies a distinct generation; SC538/write539 installs equal NOP again,
and RSP541 selects539. Both successful copy receipts retain distinct LL/read
parents and the same independently authenticated byte ancestry. The final bytes
stay equal while the final IMEM writer changes. Existing handler/return/mapping
and RAM/cache graphs remain intact. New pre-tail CPU entry is an opaque root;
there is no hidden emulation or native lowering.

Actual542 events/88 complete existing machine/cache/CP0/pipeline/TLB controls,
67 CPU pairs and24 RSP words agree baseline/disabled/enabled/repeat. Full independent
event/graph checks agree, including attempts/copies/final writer. All TWENTY-THREE
older report bytes (v0-v21 plus fixture20) stay EXACT; repeated generation and
stale report rejection PASS. No old reference/full-ROM rebuild or Actions.

Source:f3c962292a500d4f804132f18a358cb270b82f98805a7b04f3ce9b4435927038.
Report:5119ca18cb6502795b4f12b43ffac418a4db5cc893608cfe65906760d8d2310d.
Baseline:e6633dff6825778608436b9d7ed9e0a9dbbfa2925a226d476e0cb7599dfe5807.
Build:c66fd571d421f0a114b9b4904bc1b449b4e042e7d7259c5a6cd11ad06264ea12.
Sensor:13e17f6a0776c5103e0493ed00faa5c5bf57f3cfa92589b0233efe206b4905fe.
Build:795098e70ba120cb3e1355a44414b0d24dce34c8da8ad6fee5c60b157d9d45eb.
Results:9396721fc738c12e72d450b2bed24c618533320df443a88efbd74db8d8bdd253.
Ignored source/controls:target/conditional-sp-imem-consumption-primary; reports:
target/sc-imem-integration-primary; logs:target/sc-imem-*.
Exact clean ISC ares9408cb43d4948fc3ea6e152a307a34348df3fe04; complete CPU
header/IPU/SCC/TLB/exception/DMA/cache guards remain. Existing callback/passive
getters only; no modified guest semantics or upstream production code reuse.

Focused59 Rust plus complete actual/synthetic CLI/all applicable prior adversaries
PASS, with14 conditional source/10 report forgeries. Missing/repeated/misbound/
wrong payload/bank/address/state/scope effects, flag used as store data, failed
attempt promoted, stale equal writer/read and final writer substitution reject.
Pure linked-state regression checks completed read, physical link, privilege,
metadata and unchanged SC control; canonical normalizer regressions retain full
source/base==rt/absence distinctions. Original v21 actual adversaries rerun.
An old cache forgery assumed the final CPU fetch was cached; it now selects an
actual cached completion despite the new uncached tail. No assertion waiver or
production obligation weakening. Complete actual capture/model matched directly.

Canonical gate on this final tree: cargo fmt --all -- --check; cargo clippy
--locked --workspace --all-targets --jobs2 -- -D warnings; cargo test --locked
--workspace --jobs2 (including outer fixed-point deletion); python scripts/test_cli.py;
git diff --check. Corresponding issue4 closeout records final results and exact-
head CAS/fetched verification. STATUS/NEXT/DEVELOPMENT/ADR0118 record production
composition; no progress milestone/ROM/assets/native fallback change. General
fault/cached/mapped/endian/reservation/epoch/source/census/root/lifetime/whole-ROM/
native remain OPEN; all flags false, static ERET remains unsupported.
