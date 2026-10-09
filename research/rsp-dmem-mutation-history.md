# Actual RSP DMEM mutation history

Hypothesis: existing primitive DMEM sink callbacks inside actual interpreted
instruction prologue/epilogue contexts can retain scalar/vector stores without
assigning RSP producer identity to out-of-instruction writes.

## Executed evidence

At clean pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, the separately
built sensor preserves independent unchanged-reference, disabled and repeated
checkpoint hashes. These include all reported CPU/RSP registers, vector/accumulator
state, branch/pipeline/timing/status/DMA fields and complete RAM/DMEM/IMEM bytes.
No callback issues a guest access, clock step, serialization/reset or layout change.

Thirty actual decoded probes execute 60 instruction contexts and retain 209
primitive Byte stores in 329 ordered records. Scalar SH/SW wrap and all twelve
vector-store families are covered, including the real 15-byte SRV at 0x100f.
The first 29 cases retain every original probe result from the independently
validated self-store fixture. Its IMEM-isolation checks remain enforced.

One added same-value SB retains a successful sink despite unchanged backing.
Thirty equal out-of-instruction Word sinks are excluded from RSP provenance;
baseline/disabled observers retain no rows or foreign-sink metadata. Per-probe
byte replay reconstructs every full actual DMEM hash and changed-byte count.
Ten measured-history forgeries are rejected, including deletion of that same-value
sink, forged contexts/PC/word/width/offset/value and an extra field.

Full result SHA-256:
`2dc15b71d45507e21d188f4e5e1a07af5101c507fd5253cc6b706f09f60e23eb`.
Run `python spikes/042-ares-rsp-dmem-history/run.py`. Source guards also pass
repeated RSP-only builds and composition with existing SP shadows; the latter
is a source-composition check, not yet an executed CPU/RSP refetch claim.

## Initial backing counterexample

The first replay assumed `dmem.fill(0x11223344)` produced guest big-endian words.
It does not: the reference helper fills with a host u32 byte pattern. Actual
little-endian backing repeated 44 33 22 11. The test now records initial bytes
and their full hash explicitly; its equal setup/store uses those actual bytes.
The observer was correct while the replay's starting-state assumption was wrong.
Keep declared numeric setup separate from observed backing identity.

## Limits

Primitive effects are not hardware atomicity, ultimate producer origin, complete
mutation coverage or continuous executable lifetime. Reference recompilers are
disabled. General JIT, DMA, host/reset/restore coverage and hardware-wide timing
remain unclaimed. Generated reference shadows/notices, assets, binaries and raw
outputs stay ignored. No reference runtime or native artifact enters production.
All mutation/lifetime/native certification flags remain false. Compose these
sinks with actual CPU refetch contexts before building broader writer chains.
