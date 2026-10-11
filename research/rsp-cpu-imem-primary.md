# Primary reconciliation: RSP DMEM through CPU copy to IMEM

2026-10-11. Bounded exact-reference contract; no production copy certificate.

Reviewed `research/rsp-producer-cpu-imem-compose-gpt56sol` at
`5caaabd5b96e4240dbe33e7f897f24be7b9a30c0` and its
[closeout](https://github.com/sting-raider/Plaid/issues/4#issuecomment-6079548290).
Read its fixture, observer, generator, replay and independent model. Reviewed
the source CPU SP copy note/verifier at
`5c13859e536bf42fcfae9e56b9104f5ff6292590` as an input, without promoting its
broader fixture or caller-only instruction ledger.

Authenticated the passing composition Actions `37920477662` artifact. Its JSON
SHA-256 is `c309038cbcf418fe343edcd520706a441aae38600beb301489a6beff7fbbb07c`.
All three controls and eight stated adversaries reproduce. Three additional
histories still receive all three certificates:

- change the high GPR bits at the store after the claimed source load;
- give the IMEM sink a different physical address while retaining bank/offset;
- claim a cached source GPR address for the supposedly uncached SP read.

Reject that verifier. Retain the useful sixteen-phase scenario and reconcile it
with main's actual decoder and completed backing callbacks in
`spikes/047-ares-rsp-cpu-imem-compose/`. Do not transplant the custom compiler,
branch workflow or independent model as production architecture.

The unified chronology captures actual CPU begin/end contexts and all 32 GPRs,
actual RSP instruction contexts with scalar operands and the exercised vector
byte, primitive DMEM effects and completed CPU SP reads/writes. The independently
declared finite census and semantic replay check full GPR continuity, LW sign
extension, exact decoded KSEG1 addresses, bank/offset and successful SW effects.
Initial/final byte snapshots use guest accessors rather than raw IMEM storage.

Each copy carries four source-byte writer generations separately from its sink
generation. Identical RSP stores create different source generations. The mixed
copy retains `[CPU writer, UNKNOWN, RSP vector writer, RSP scalar writer]`.
The last equal-valued read is ordinal 48 into `t1`, while the actual source is
ordinal 45 into `t0`. Same-valued ADDU cuts `t0`'s old memory definition even
though every register bit is unchanged. The final unscoped IMEM write retains
known content and unknown instruction attribution.

Exact clean ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` passes unchanged,
callback-disabled, enabled and repeated enabled executions. All sixteen reported
checkpoints, full independent CPU step snapshots, normalized byte snapshots and
reported final state agree. The checkpoints include the existing RSP machine
digest plus CPU Count/clock/exception/BD/EPC; they are a subset of emulator state.

The versioned receipt contains 58 records: twenty CPU boundaries, sixteen RSP
boundaries, ten scoped RSP byte effects, four CPU SP reads, six CPU SP writes and
two lower-level foreign DMEM sinks. It produces exactly three intended copy
chains. Twenty captured-history forgeries fail, and eight independent synthetic
contract tests pass. Full locked core (including the real 512-pass frontier),
formatting and strict workspace Clippy pass.

Final `results.json` SHA-256:
`b244a6c2de930048215d10199859309fc036a719a293b3b39c911223b590aef3`.
Generated sources, binaries and receipt remain ignored under
`target/ares-rsp-cpu-imem-primary/`.

Pinned CPU LW/SW/ADDU, RSP SW/SB/SBV, SP Word routing and actual interpreter
boundaries were inspected. Original project ISC fixture/observers are shared;
upstream core ISC / SLJIT BSD notices stay in generated ignored builds. No
upstream implementation enters production or the native runtime.

This supersedes the composition branch's bounded fixture/verifier, not its
unproved future obligations. Source writer identities do not prove the ultimate
origin of scalar/vector register operands. UNKNOWN is retained explicitly.
Complete execution attempts/mutation census, asynchronous interleavings,
cache/TLB paths, DMA ancestry, IMEM executable consumption/lifetime and hardware
equivalence remain OPEN. No ProgramMap/native certificate or progress milestone
changes from this reference fixture.
