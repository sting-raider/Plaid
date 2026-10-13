# CPU XORI composes with cached executable consumption

Original v13 extension of spike069 at exact ISC ares
9408cb43d4948fc3ea6e152a307a34348df3fe04. Run `python run.py`; use
`--verify-existing` to recheck retained controls without rebuilding. Outputs
stay ignored under `target/cpu-xori-ram-cached-primary`.

Actual SP LW264/read265 captures DMEM NOP bytes retaining earlier DMA/RSP
parents. In-place XORI270 changes the full held register from0 to0x21. SW275/
RAMwriter276 installs that transformed instruction at6028. Resident CPU NOP281
still uses fill256/CPUwriter240; guest CACHE286/operation287 ends that fill.
New completed burst291/fill292 then exposes ADDU r0,r0,r0 to actual decoder294
with writer276 -> transform270 -> original load264/read265/DMEM/RAM/RSP ancestry.
Original source bytes and the transform expression remain distinct.

Baseline/disabled/enabled/repeat agree on27 CPU steps and45 complete reported
machine/cache checkpoints, each hashing all512 I-cache tuples. Enabled sources
repeat exactly. Independent complete source/image/definition/cache/parent graph
matches Rust. Exact source guards include the pinned full64 XORI/u16 behavior.

The production gate retains one in-place XORI on a held load, following the
existing bounded CPU-copy policy. Repeated transforms, renamed or unattributed
sources yield UNKNOWN copy parents. Transformed SP stores never acquire an
identity IMEM-copy witness. Tests cover sign-extended inputs, immediate width,
high GPR bits, required result/no effects and source/report forgeries. Explicit
host roots remain opaque; general transforms/decompression/relocation, complete
mutation/mapping/root/lifetime/whole-ROM/native coverage remain OPEN.
