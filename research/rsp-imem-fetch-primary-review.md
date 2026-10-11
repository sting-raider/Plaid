# Primary harvest review: byte ancestry through an abstract IMEM fetch

2026-10-11. Retain the projection counterexample; no new fetch certificate.

Reviewed `research/rsp-dmem-cpu-copy-imem-fetch-gpt56sol` at
`537f230bc85788c4ff573a716a42acb7809f4989`, its note, README, model, exact input
guard and [closeout](https://github.com/sting-raider/Plaid/issues/4#issuecomment-6090530221).
The prior commit/blob guards reproduce against current main. The 26-event model
and all ten stated adversaries reproduce result SHA-256
`af306594330d7ec3124bb9030e8ba1f0407573a11a3c24f4dd971dbd57b6de4c`.
This is abstract replay, not newly executed ares fetch behavior.

The useful counterexample is valid within that abstraction: two histories with
different seed-writer labels have equal projected read/write ordinals, values,
destination and resident generation, but different byte ancestry. A scalar copy
fact alone loses ancestry information. A complete immutable history with source
authentication may supply that information; the intentionally flat projection
omits that identity. Do not infer a current ProgramMap flaw from the projection
collision alone.

The model does not authenticate decoded RSP producers. Primary review changed
every producing begin/end opcode to BREAK (13), kept the claimed report, and
verify_claim still accepted. It checks matching context labels and payload replay,
not whether the operation can create the stated effects. Its original abstract
SB/SBV words and synthetic CPU instruction IDs similarly omit operand proofs.
Thus it cannot be transplanted as a raw reference-history verifier.

Main's reconciled actual-context composition (`71ccb10`, ADR-0091) already
preserves four source-byte writer identities separately from its IMEM sink and
keeps unknown ancestry. A new deterministic negative control rejects replacing
all scoped producers, including their primitive metadata, with BREAK contexts.
That strengthens the regression record without claiming a new sensing boundary.

Disposition: reviewed model-only counterexample. Retain the research branch and
its projection result; do not import the model or branch workflow as production
architecture. Its suggested lossless ancestry requirement is covered by the
reconciled finite copy contract. Actual fetch/consumption and complete executable
lifetime/source histories remain separate, unproved obligations. No hardware,
whole-ROM, native or progress milestone changes.
