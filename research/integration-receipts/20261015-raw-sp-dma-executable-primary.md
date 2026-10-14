# Primary integration: reverse SP DMA carries computed writers to RAM execution

Base: bb81896e7fa0c21d529e1f1f05829aa672940ab9. Claim: 6178516353 (opened by
the Codex primary integrator; finished and closed by the Claude co-integrator).
Compose the raw v10 scalar SP writer graph (spike094) with exact reverse-SP-DMA
source reads and completed identity-RAM sinks, then with CPU executable reads.

Raw v11 adds `sp_dma_egress_read` and `sp_dma_egress_store` records. A read
freezes the shared SP writer parents of its DMEM Word or IMEM Dual lanes at its
ordinal. A store must name that read and the immediately preceding identity-RAM
scalar write (device 4) whose context, PC, address, width and value match.
Completed sinks install computed byte chains in RAM; a later uncached CPU read
or joined cached fill selects them per byte. Any later RAM storage effect,
including an equal value, revokes the chain; full backing cuts clear it.
Computed chains never become PI/ROM origins (`fully_attributed_fetches` stays 0).
Source-v11/report-v7 is explicit; v10 and older policies keep their shapes.

Synthetic graph (spike095 `test_consumer.py`): rooted ORI -> scoped SW -> fresh
DMEM writer -> reverse DMA -> RAM -> CPU executable fetch. Both consumers match
the independent `verify.py` replay/digest. SP cuts before the DMA read degrade
the fetch to partial; cuts after it do not. RAM cuts after installation revoke
lanes; cuts after the CPU read preserve that read's frozen parents.

Pinned ISC ares 9408cb43d4948fc3ea6e152a307a34348df3fe04: baseline,
disabled, enabled and repeat runs agree on all 46 complete machine+backing
checkpoints; the enabled trace has 388 records with six actual reverse-DMA
read/sink pairs covering both DMEM (Word pair) and IMEM (Dual) banks. Ordered
stores SHA256 d3184ed989f9c61fe026c179af59b65e024b8d514c029e8c8ae43adec77984af;
sensor trace SHA256
e984e7bdafb40b9fe8cd98e7233568709c46be79dae45e36f7f5e1299c839fca.
Builds, binaries and traces stay under ignored target/; no upstream code added.

Fix made while finishing: the spike088 driver's new post-DMA assertions called
`rdram.ram.read<Word>(addr)`, which has no one-argument overload and, had it
compiled through the RDRAM wrapper, would have been sensed as an extra guest
read. They now read through the unsensed `ares::Nintendo64::Memory::Writable` base.
Spike094's committed `run.py --verify-existing` called the spike093 replay
without `stores=True` and so failed on its own retained trace; fixed. Retained
spike088-094 rechecks now PASS.

Local gate on the exact tree: `cargo fmt --check`, locked workspace Clippy with
`-D warnings`, locked workspace tests, `scripts/test_cli.py`, spike094/095
consumer and spike094 prepare tests, `tools/progress.py --check`: all PASS.
Logs under ignored `target/`.

ADR-0125 pauses further RSP/SP-side composition after this cluster. The local
OoT conditional baseline was re-run on this tree and is unchanged: 293 blocks,
45 indirect sites, 62 whole-ROM blockers (44 unresolved indirect sites).
Task/reset roots, vector producers, writer census, lifetimes and whole-ROM/
native closure remain OPEN; all broad certification flags stay false.
