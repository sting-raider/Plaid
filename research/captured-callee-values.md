# Captured table values across guest calls (ADR-0213)

Base: `2342395d1783cea71914347729bfb79d4c5280f9`.
Probed prototype: `66cfc66bd10ca3d049cff66324da381978a0756e`.

The prior callee consumer handled only a pending table base after the index
and bound were matched. A captured table address and its branch flag can
also remain live across a call. The backward walk now collects its pending
address, operands, scale, base, constants, flags and unmatched index/bound
registers. A matched captured index/bound needs no earlier index value; the
callee may change that now-dead GPR while preserving the captured address.
Every still-live GPR needs the existing bounded no-write proof. Full Need
equality for loop induction is unchanged.

Source reads can now include fixed text and the explicitly current placed
alternate. A different alternate, ambiguous mapping, missing normal block,
data tail, unsupported control transfer or register write still rejects.
The caller delay slot is transferred normally. Return-site accounting,
source-word hashes, external-entry barriers and the shared 4096-read budget
remain mandatory. Each GPR currently traverses the callee separately and is
charged against that budget; this can conservatively reject larger callees.
This is a source-effect proof, not a new ABI, return-target, memory, timing,
binding-lifetime or whole-program closure assumption. All guest instructions
still execute in the final native path.

The captured pointer/flag positive failed on the preceding prototype and now
passes. Fourteen module tests and 25 focused integration tests pass, including
same-alternate calls, cross-alternate refusal, callee and caller-slot pointer
clobbers, flag clobbers and retained loop/guard/source negatives. A caller slot
that sets the flag to one only after a valid case entry is safe; ordinary
value-version tracking handles it. Deleting the pending-address obligation
causes the callee-clobber regression to fail (exit 101), and restored tests
pass again. Native valid indices zero/one loop through a callee three times,
changing the old index and temporary GPR while retaining the captured values.
Their accumulators are 3/30; invalid index three bypasses dispatch and calls.
Full register, PC, FPU and RAM checkpoints equal pinned ares. Independent Luna
xhigh review found no correctness findings and independently reran the module,
flag and native/ares tests. It did not run the full workspace gate or ROM.

The ROM-only inferred-input probe is OPEN/12, with 56,807 blocks, 4,604 indirect
sites and 162 loads. The five-word dispatch at 80aac6f0 now has a source-bound
closed proof over its four distinct targets. No blocker sites are added.
Save/restore, spill-cell provenance, index relationships and external-entry
barriers still leave twelve sites unresolved. No native Paper Mario artifact
is emitted or run.

Optimized compilation took 153.577 seconds, discovery 51.449 seconds and solve
13.863 seconds. Earlier discovery/solve took 58.089/16.182 seconds with other
control solves running concurrently; this is not a controlled speedup claim.
Ignored receipts are under target/paper-mario/0213, including the mutation.
The exact committed integration tree still requires the full local gate.
