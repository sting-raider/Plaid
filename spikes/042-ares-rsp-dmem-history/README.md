# Actual RSP DMEM mutation chronology

Hypothesis: existing primitive DMEM sink callbacks inside actual decoded RSP
instruction prologue/epilogue contexts can retain successful scalar/vector
writes, including modulo-bank wrap and same-value effects, without inheriting
RSP producer identity for out-of-instruction sinks.

Verdict: VALIDATED for the controlled interpreted fixture; general coverage remains
PARTIAL. All 30 probes preserve independent checkpoints and replay 209 primitive
DMEM writes in 329 records. Ten measured-history forgeries fail. Thirty controlled decoded probes
extend the prior 29-case fixture with a same-value SB. Separate unchanged-reference,
disabled and repeated-enabled builds preserve full reported CPU/RSP register,
pipeline/timing/status/DMA and RAM/DMEM/IMEM checkpoints. Strict byte replay reconstructs each actual DMEM hash. IMEM identity remains separate. The first 29 cases retain the prior exact results.
See `research/rsp-dmem-mutation-history.md` for measurements and the initial-byte
pattern counterexample.

The optional sensor changes generated ignored pinned-reference shadows only.
No extra guest read, decode, clock step, serialization/reset or object-layout
change is introduced. Callback counts are primitive effects, not hardware
atomicity. General interpreter/JIT, DMA, host mutation, reset/restore coverage,
producer origin, executable lifetime and whole-ROM closure remain unclaimed.
No reference implementation or copyrighted asset enters production.
