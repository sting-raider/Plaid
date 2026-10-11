# Actual CPU decoder context to SP Word effects

Reconciles the researched SW/SB/SWC1 source-context fixture through the actual
pinned CPU decoder callback, rather than caller-supplied instruction metadata.
Capture all GPR/FPR bits and FR/CU1 state at instruction boundaries. Derive source
selectors from the actual decoded word; require exact physical address, bank,
offset and completed Word payload, then replay guest-visible IMEM bytes.

Run from the repository root:

```sh
python spikes/046-ares-cpu-sp-producer-context/run.py
```

Windows delegates to WSL Ubuntu. At clean ares
`9408cb43d4948fc3ea6e152a307a34348df3fe04`, original/disabled/enabled/repeated
runs agree at eight reported checkpoints, including all captured FPR bits.
Twenty-one records retain six attributed writes, one direct out-of-context
write, and a CU1-disabled SWC1 fault without a sink. Sixteen measured forgeries
and eight independent synthetic regressions pass. Schema-0 result SHA-256:
`2cadac7ab077a2575d19360743161976789a72fd3a00173fda0f891f14792864`.

Same PC/value writes have distinct decoded contexts. SB preserves this pin's
full Word normalization, including upper source bytes. FR=0 odd SWC1 selects
the paired-even high half; FR=1 selects the named low half. A direct CPU write
outside decoded execution stays unattributed.

Initial/final snapshots use the pinned guest-byte accessor. Generic IMEM host
storage order differs from guest byte order; raw host bytes cannot be relabeled
as a guest snapshot. Required notices and generated reference builds/results
remain in ignored `target/ares-cpu-sp-producer-primary`.

This is a finite reference contract. It does not establish ultimate register
ancestry, complete sensing, hardware SP subword semantics, executable lifetime,
all store families, reentrant/asynchronous execution or native closure.
