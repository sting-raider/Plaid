# Primary harvest review: standalone CPU DMEM-to-IMEM copy

2026-10-11. Older verifier rejected; its causal shape is already reconciled.

Reviewed `research/cpu-sp-dmem-imem-copy-gpt56sol` at
`5c13859e536bf42fcfae9e56b9104f5ff6292590`, its complete note, fixture, observer,
shadow recipe and verifier, and the
[closeout](https://github.com/sting-raider/Plaid/issues/4#issuecomment-6078882544).
Authenticated Actions `37915831346` artifact JSON SHA-256
`45f3126878657b9c084572a7e943a024ca05dad6c5c47a3cfa1e0cc7ab18a39c`.
Its three controls and eight stated adversaries reproduce.

Three additional histories retain all three copy certificates:

- change both before/after `t0` high bits during the intervening `LW t1`;
- give the claimed store and sink a nonsequential PC;
- disconnect the sink PC from its supposed producer instruction.

Unlike the weaker composition verifier, this verifier checks exact source-register
bits at load and final store, local tracked-register effects and decoded uncached
physical addresses. It still does not check continuity through every intervening
instruction, bind storage PCs to producers, or authenticate actual decoded
instruction windows. Only four GPRs are captured. A caller phase label cannot
fill those gaps.

Main's shared actual decoder/SP callbacks and full GPR chronology in
`spikes/047-ares-rsp-cpu-imem-compose/` already reconcile the bounded non-adjacent
LW/decoy/SW shape. Retain a separate negative control for the temporary high-bit
jump through a decoy instruction, supplementing immediate load/store continuity
tests. The source-byte and sink generations stay separate; unscoped sinks remain
unattributed and same-value ADDU cuts the prior definition.

Disposition: reviewed superseded source design. Reject the old verifier and
duplicate build/workflow scaffolding. Do not claim the standalone fifteen-phase
reference fixture was freshly executed or that every original case was ported;
the actual mixed-source composition and its stronger checkpoints are the primary
receipt. Initial-byte ancestry, complete attempts/census, general dataflow,
cache/TLB paths and eventual executable consumption/lifetime remain OPEN.
No new production certificate, hardware or native milestone is asserted.
