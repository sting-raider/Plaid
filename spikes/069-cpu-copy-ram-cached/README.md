# CPU copy composes with cached executable ancestry

Original controlled v12 extension of spike068 at exact ISC ares
9408cb43d4948fc3ea6e152a307a34348df3fe04. Run `python run.py`; use
`--verify-existing` to recheck controls without rebuilding. Outputs stay ignored
under `target/cpu-copy-ram-cached-primary`.

Actual SP LW233/read234 captures DMEM bytes retaining ingress152/read153/write155,
RAMwriter58 and original RSP producer parents. Sequential CPU SW239/write240
copies that register into RAM6028. Its full decoded effective direct-KSEG1
address, low32 value, context and unchanged GPR result are checked. A resident
cached hit still uses prior DMAwriter219/fill225 despite equal backing bits.
Guest CACHE250/operation251 ends that fill; new burst255/fill256 then supplies
CPUwriter240 parents to actual executable consumption. Explicit host PC seeds
remain opaque; held register definitions do not cross them.

Baseline/disabled/enabled/repeat match21 CPU steps and39 complete reported
machine/cache checkpoints (all512 tuples hashed at each point); enabled sources
repeat exactly. Independent complete source/images/definition/parent/cache graph
matches the Rust report. Parent/scope/width/operand/cardinality/result/profile/
source/report forgeries fail. Unattributed captured registers produce UNKNOWN
RAM ancestry cuts, including equal writes. Other stores/transforms/cached data
operations, complete mutation/root/mapping/lifetime/whole-ROM/native coverage
remain unsupported or OPEN; all certification flags stay false.
