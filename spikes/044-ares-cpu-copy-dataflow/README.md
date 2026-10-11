# Adjacent interpreted CPU-copy evidence

This reconciles the completed swarm CPU-copy experiment with a strict history
verifier and per-instruction independent checkpoint comparison. It is a bounded
reference experiment, not a production copy or lifetime certificate.

The six synthetic phases retain successful adjacent LW/SW and LWU/SW controls,
an equal-valued competing source, an ORI same-value register clobber, a NOP gap
and a failed misaligned load. Only the two adjacent successful controls certify.
The verifier checks captured GPR continuity, sequential PCs, complete scoped
Word effects and canonical aligned uncached identity-RDRAM addresses. Twelve
forged histories are retained, including three newly found branch-verifier gaps.

Result: VALIDATED for this controlled scope. Original-reference, disabled,
enabled and repeated runs agree at all fourteen reported instruction checkpoints;
28 boundary records and eleven completed scalar effects produce exactly two
certificates. Seven independent synthetic contract tests also pass, including
the zero-register control. Result SHA-256:
`a0903ba3ae1e2f05144a1968a065348edd344debb7ded9fac450bfdd1427fa6a`.

Reproduce from the repository root:

```sh
python spikes/044-ares-cpu-copy-dataflow/run.py
```

Windows delegates to WSL Ubuntu. The builder requires unchanged ares
`9408cb43d4948fc3ea6e152a307a34348df3fe04`. Generated reference builds/notices and
synthetic results remain in ignored `target/ares-cpu-copy-dataflow-primary`.
See `research/adjacent-cpu-copy-primary.md` for source review and explicit limits.
