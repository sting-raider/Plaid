# BEV=1 exception roots require in-context PIF backing provenance

Status: **VALIDATED** for the bounded exact-pinned-ares interpreter experiment described below.

## Question

The architectural exception-vector work already proved that a BEV=1 general exception transfers to `0xffffffffbfc00380`. Separately, the PIF provenance work proved that a CPU fetch may be assigned supplied-PIF origin only at the successful, active `PIF::readInt -> rom.read<Word>` backing branch.

The missing composition question was: does a **real guest exception entry** to the BEV=1 general vector traverse that ordinary PIF fetch path, and can vector address or equal returned bytes fabricate PIF origin when it does not?

## Result

Yes, the normal root fetch traverses the ordinary uncached path in exact pinned ares, and no, the vector/value are not enough.

A synthetic PIF image places `ADDIU v0,zero,7` (`0x24020007`) at PIF offset `0x380`. A real guest `SYSCALL` executes from uncached RDRAM with Status.BEV=1. Pinned ares transfers to `0xffffffffbfc00380`; the next instruction fetch is uncached physical `0x1fc00380` and, in the normal case, the active-fetch PIF sensor records exactly one successful backing read from offset `0x380` carrying the same word. The handler executes and leaves `v0 == 7`.

The crucial counterexample is `busy_latch`: after the exception transfer but before the handler fetch, the fixture sets SI `ioBusy` and its bus latch to the **same** `0x24020007`. The root fetch still occurs at the same virtual/physical address and executes the same instruction (`v0 == 7`), but there is **no PIF-ROM backing read and no PIF witness**. Thus `(BEV=1 vector address, returned instruction bytes)` does not prove supplied-PIF provenance.

`lockout` gives a second negative: the same root fetch returns zero under PIF ROM lockout and records no PIF witness. Two positive-decoy cases perform an unrelated successful PIF read before the exception root: one reads a different offset containing the same payload, the other uses address `0xb80`, which PIF masks to the same backing offset `0x380`. In both cases the prior read remains unattributed while the later root fetch gets its own active witness. Temporal/fetch identity, not payload or masked-offset equality, is what joins the origin.

## Exact executable evidence

Plaid canonical base at claim time: `211176e7a489fecf8331d02915ee982cd279cb62`.
Exact ares pin from `refs.lock.toml`: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.
Research branch: `research/bev1-exception-pif-root-gpt56sol`.

Fail-closed GitHub Actions run: `38004246774`, job `114069254414`, branch head `37c88e57cf4a5e3c5e65b919b31936fee2990ddf`.
Artifact: `11651185304`, archive digest `sha256:ecdadd884f158142a6d07ad1d1ea5deae8cffc5ef69e3856d942f8bbb620fe62`.

Evidence hashes:

- instrumented canonical evidence: `014521b49d3fe5bda2433d5328624af8e0d2284320df6b341c3d85e2ac662bf0`;
- complete generated `results.json`: `27ae59f4f372e19b5d62150be3895412a23351ba2c45eb0d30c09952b7341853`;
- adversarial model result: `5c08b240f42b970105354d53206871f4deeaacf1ccc94cc9e7bfc9e177517d16`.

For every mode, baseline and instrumented guest-machine checkpoints matched, and the second instrumented execution matched the first exactly. The workflow explicitly uses `set -o pipefail`; an earlier run exposed that piping through `tee` without pipefail could cosmetically green a failed Python command, so that harness defect was fixed before accepting this receipt.

Key instrumented root events:

- `normal`: `vaddr=0xffffffffbfc00380`, `physical=0x1fc00380`, returned `0x24020007`, witness `{kind:pif_rom, offset:0x380, word:0x24020007}`;
- `busy_latch`: same address and same returned `0x24020007`, **witness null**, zero backing reads, handler still executes `v0=7`;
- `lockout`: same address, returned zero, **witness null**, zero backing reads;
- equal-value decoy: one unattributed prior backing read plus the unique root witness;
- same-offset mirror decoy: one unattributed prior backing read plus the unique root witness.

## Adversarial replay

`experiments/bev1-exception-pif-root/model.py` independently replays seven histories and deliberately compares the strict causal rule against unsound address-only and latest-equal-value policies.

It produces five naive false-positive histories: SI-latch equal payload, ROM lockout, wrong fetch context, equal payload at another PIF offset, and a forged physical mirror. It also rejects six explicit forgeries: deleted backing event, wrong fetch ID, wrong offset, wrong word, wrong physical address, and wrong vector address. Two executions were byte-identical in CI.

## Source composition

This experiment composes, rather than replaces, two previous validated results:

1. `research/exception-root-generation-gpt56sol` proved a real BEV=0 cached general-exception root and explicitly left BEV=1 only as an abstract uncached control.
2. `research/pif-rom-backing-ares-gpt56sol` proved the active-fetch PIF backing witness and its SI-latch/lockout/mirror counterexamples, but did not join it to an architectural exception transfer.

At the exact ares pin, `CPU::Exception::trigger` chooses base `(s32)0xbfc0'0200` when BEV is set and general offset `0x0180`, then calls `pipeline.setPc(vectorBase + vectorOffset)`. PIF `readInt` masks delegated addresses with `0x7ff`, rejects ROM origin under lockout, and only the unlocked ROM branch executes `rom.read<Word>(address)`. The executable fixture joins those source facts in one real exception/fetch chronology.

## Closed-world impact

For BEV=1 roots, Plaid must keep separate:

- architectural root selection (exception kind, BEV/mode state, vector VA);
- translated/physical fetch identity;
- SI/PIF selection state;
- the successful backing event, if any;
- PIF input identity/digest and masked byte offset; and
- the fetched executable value.

A root can execute the same instruction bytes from SI latch state while having no PIF-ROM provenance at all. Therefore a whole-ROM certificate must not infer a supplied-PIF source from vector address, current PIF bytes, a matching earlier read, masked-offset equality, or returned-value equality. Missing same-fetch backing evidence remains UNKNOWN/OPEN.

## Remaining gap

This is not a hardware proof or complete BEV=1 root census. It covers exact pinned ares interpreter execution, synthetic PIF input, identity RDRAM for the trigger, and the **general** BEV=1 exception vector only. It does not execute the BEV=1 32-bit TLB refill (`0xffffffffbfc00200`) or 64-bit XTLB (`0xffffffffbfc00280`) roots, NMI/reset, recompiler paths, arbitrary SI timing, real licensed firmware, PIF input lifetime/authenticity, or a whole-ROM certificate importer. Those obligations stay OPEN.

## Integration recommendation

**ADOPT the invariant, not the research instrumentation wholesale.** A BEV=1 exception root may receive supplied-PIF provenance only from a uniquely joined successful backing read inside that exact CPU fetch context, retaining both physical address and masked PIF offset plus declared input identity. SI latch, ROM lockout, prior unrelated reads, mirrors and equal payloads must not be promoted to PIF origin. Extend the rule to refill/XTLB roots only after reproducing their actual fetch/source chronology or proving the generic path with equivalent evidence.
