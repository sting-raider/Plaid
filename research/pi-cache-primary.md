# Primary harvest: PI copy versus cache visibility

2026-10-11. Reconcile a finite reference regression, preserve production boundaries.

Reviewed complete note, fixture, baseline wrapper, runner, source guard, model,
README and issue #4 closeout 6091150954 from exact branch head
`b7d78e3372a1077f1cf75c0558a7b63a4222ed82`. Hypothesis: PI lifecycle completion
is independent of completed byte writes and instruction-cache visibility.
Current main `pi_history.rs` already reports returned copies without observed
status and leaves `transfer_completion_certified=false`; this is not a new core
bug or justification for a production lifecycle policy change.

Downloaded successful Actions 38005081724 evidence. Its exact actual result
SHA-256 is `219467974727280a8584c156297133fb82d9663225d4b4d60e20e734ec16dd73`.
Final-head Actions 38005405806 artifact 11650429606 independently contains the
same exact result hash.
The original runner accepts three primary measured-record forgeries: changing
the second source halfword to 0xffff, moving destination byte 0x4004 to 0x4040,
and changing a fetch's translated physical address to 0x8000. It checks the first
source halfword/four destination bytes and selected payloads, but not the full
byte/address/context chain. Reject it as written for causal source validation.

The original abstract model and seven declared negatives reproduce report hash
`351370142ac05174fb44582bb8e374fcf42fcc4477d71520035b393c34989cb1`
and trace hash
`c8d1858b784f29fb6ce97b0a7cf01b711e559186593f70ffea901062a175633f`.
Its same-value writer and unbound restore examples are useful specification
evidence, but are not events executed by this actual two-transfer fixture.
The model supplies abstract copy/writer/token identities rather than joining
an authenticated source-bound measured history, and is not imported.

Primary spike 050 qualifies only two fixture queue names, shares the current
003 builder/observers and independently declares the finite expected chronology.
All sixteen source halfwords and thirty-two destination bytes per transfer are
checked, together with exact full-line burst/fill payloads, slot/physical/index,
fetch addresses, callback kinds and contiguous ordinals. No missing primitive
or extra field may be repaired from a checkpoint or matching bits. Eleven
synthetic tests retain full tail/address/type/order/census failures. Ten forged
measured records supplement them in the reference runner.

Source inspection covers exact PI MMIO request/copy/completion, fixed queue
insertion rejection, CPU queue dispatch and cache/fetch backing routing. The
existing boot PI source scope ends at copy return rather than status completion.
No upstream implementation, branch workflow or branch-only source-generation
scaffold enters production; generated core ISC / SLJIT BSD builds stay ignored.

Fresh main unmodified/disabled/enabled reported checkpoints agree, and repeated
enabled stdout reproduces historical trace SHA-256
`4b6a39c3a46a729a173d404a9a7d9b1a9f3d402d5d8540a8622d8f96b05a8f9f`.
All ten measured forgeries reject. Final schema-0 primary result SHA-256 is
`32b6f52e18c4fd3427d8374921e9103da8771452938208336a8577022a27645c`.
Full locked plaid-core, formatting and strict locked workspace Clippy pass.
All 53 synthetic copy/transform/SP/cache contracts also pass together.

The fixture's observer tracks the latest pending copy solely to label its one
controlled completion. It is not an exact queue-container insertion identity
or general overlapping/canceled-request proof. Eight checkpoint observations
plus final PC/Count/exception/t0/RAM/PI state are selected fields, not the full
architectural state. Real PI MMIO and guest CACHE run in the interpreted pinned
fixture, but hardware timing, general writers, aliases, replacement/restore,
complete attempts/mutations, executable lifetimes and whole-ROM/native closure
remain OPEN. No progress-map milestone changes.
