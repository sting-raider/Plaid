# BEV=1 32-bit TLB-refill root requires in-context PIF backing provenance

Status: **VALIDATED** for the bounded exact-pinned-ares interpreter experiment below.

## Question

Earlier Plaid work independently established two facts:

1. a true TLB load/store miss with `EXL=0` in 32-bit kernel context selects the refill
   root at exception base `+0x000`, hence `0xffffffffbfc00200` when `BEV=1`; and
2. an uncached CPU fetch may be assigned supplied-PIF origin only when the exact active
   fetch contains the successful `PIF::readInt -> rom.read<Word>` backing operation.

The completed BEV=1 general-vector composition joined those facts for
`0xffffffffbfc00380`, but explicitly left the 32-bit refill root open. This experiment
tests that missing root directly rather than assuming the general-vector receipt
generalizes by address similarity.

## Result

The root composes cleanly in exact pinned ares.

The fixture executes a real `LW a0,0(v1)` (`0x8c640000`) from uncached KSEG1
`0xffffffffa0004000`, with `v1=0x4000`, no matching TLB translation, `EXL=0`,
`BEV=1`, kernel privilege and UX/SX/KX disabled. The resulting true TLB load miss has
exception code 2, `BadVAddr=0x4000`, EPC `0xffffffffa0004000`, 32-bit context, and
lands at `0xffffffffbfc00200`.

A synthetic 1,984-byte PIF image places `ADDIU v0,zero,7` (`0x24020007`) at PIF
offset `0x200`. The next CPU instruction fetch is uncached physical `0x1fc00200`.
In the normal case, the active-fetch sensor records exactly one successful PIF-ROM
backing read from offset `0x200` returning the same word, and executing it leaves
`v0=7`.

The adversarial controls falsify value/address-only provenance:

- **SI busy latch:** after architectural transfer but before the root fetch, the fixture
  sets the SI latch to the same `0x24020007`. The same root address returns the same
  word and executes `v0=7`, but there is no PIF-ROM backing read and the root witness is
  null.
- **ROM lockout:** the same root fetch returns zero, with no backing read/witness.
- **Equal-value different offset:** an unrelated read from PIF offset `0x208` returns
  the same handler word before the exception. That read is unattributed; the actual root
  fetch still receives its unique offset-`0x200` witness.
- **Masked mirror:** an unrelated `pif.readInt(0xa00)` is masked by pinned ares to
  `0x200` and returns the same word. It remains unattributed; the later root fetch gets a
  separate active witness.

Thus neither vector address, returned bytes, a prior equal read, nor masked-offset
equality proves supplied-PIF provenance.

## Exact executable evidence

Plaid canonical base at claim time:
`211176e7a489fecf8331d02915ee982cd279cb62`.

Exact ares pin from `refs.lock.toml`:
`9408cb43d4948fc3ea6e152a307a34348df3fe04`.

Research branch:
`research/bev1-tlbrefill-pif-root-gpt56sol`.

Initial complete executable Actions receipt:

- run `38005941825`
- job `114074634950`
- executable branch head `919de5c6500d3061fbfe6dc6581f6b1dec80b1cd`
- artifact `11651865299`
- uploaded ZIP SHA-256:
  `4670510c22b6c52e7eef0092ca4c11951b3f5f6c1b205990c85ddb894f25ad09`

Evidence hashes:

- instrumented canonical evidence:
  `019cc80354b1c91b6a919be0bd32de754c73aaa88889b039f1f3ae53c0bbdeac`
- complete `results.json`:
  `de12fb3706ad4a63633a97a3acdd2d4bf2c3f0174f840a20d7d460f4a30b353e`
- adversarial model result:
  `5f9a16daa1debd267ff6eb621607be64d239042e9c87a0a297eb87383d98e6ea`
- each complete model stdout:
  `c721787755df18f3736065b3d9d9aedc29b8f69a4f4cca6d41eb82413fe8e54e`
- exact-pin runner stdout:
  `d9388bd00376cbfa292cfcadaa9703f05345e75e03be816adfd3984f1276b122`

The uninstrumented and instrumented guest-machine checkpoints match in all five
modes. The second instrumented execution equals the first exactly. The workflow uses
`set -o pipefail`, so a failed Python assertion cannot be hidden by `tee`.

## Root events

All instrumented runs first fetch the faulting `LW` from uncached physical RDRAM
`0x00004000`, then fetch root event ID 2 at the refill vector.

- `normal`: root VA `0xffffffffbfc00200`, physical `0x1fc00200`, returned
  `0x24020007`, witness `{kind:pif_rom, offset:0x200, word:0x24020007}`.
- `equal_offset_decoy`: one unattributed prior backing read at `0x208`, followed by
  the exact root witness at `0x200`.
- `mirror_decoy`: one unattributed prior read through masked address `0xa00`, followed
  by the exact root witness at `0x200`.
- `busy_latch`: same root VA/physical address and same returned `0x24020007`, but
  witness null and zero backing reads; handler still leaves `v0=7`.
- `lockout`: same root VA/physical address, returned zero, witness null and zero
  backing reads.

## Adversarial replay

`experiments/bev1-tlbrefill-pif-root/model.py` retains root fetch identity, successful
backing-read ordinal, PIF offset, returned word, and declared firmware identity as
separate fields.

It rejects eight explicit forgeries:

1. deleted backing event;
2. wrong active fetch ID;
3. equal-valued wrong PIF offset;
4. wrong backing word;
5. equal-valued wrong declared firmware identity;
6. forged physical mirror;
7. wrong/general vector substitution;
8. duplicate backing ordinal.

Deliberately unsound address-only/latest-equal policies produce false positives for
seven histories, including the SI-latch case, ROM lockout, wrong fetch context,
wrong offset, wrong firmware identity, a forged physical mirror, and reuse of the
completed general-vector receipt for the refill root.

## Source composition

This experiment composes, rather than redefines:

1. `research/exception-vector-roots-gpt56sol`, which executed the 32-bit/64-bit
   true-miss vector matrix and established the 32-bit `BEV=1` root at
   `0xffffffffbfc00200`;
2. `research/pif-rom-backing-ares-gpt56sol`, which established the exact active-fetch
   backing witness and SI-latch/lockout/mirror counterexamples; and
3. `research/bev1-exception-pif-root-gpt56sol`, which proved the same composition for
   the **general** BEV=1 vector and explicitly left refill/XTLB roots open.

At the pinned ares revision, `CPU::Exception::trigger` uses base
`(s32)0xbfc0'0200`; when `tlbMiss && !EXL && context.bits == 32`, it selects
offset `0x0000`. PIF `readInt` masks its address with `0x7ff` and reaches
`rom.read<Word>` only for unlocked PIF-ROM addresses. The executable fixture joins
those source-level facts through one actual guest miss and subsequent handler fetch.

No disagreement is erased here. Prior research already records that pinned Gopher64
does not independently implement the 64-bit `+0x080` XTLB distinction, while
n64-systemtest does. This experiment makes no new 64-bit-vector claim.

## Closed-world impact

A BEV=1 **32-bit refill-root** certificate may assign supplied-PIF byte provenance
only when all of the following are causally joined:

- true-miss/root-selection identity and exact BEV/mode/EXL state;
- selected refill vector VA;
- exact translated/physical CPU fetch;
- SI/PIF selection state;
- one successful backing event inside that exact fetch context;
- declared PIF input identity/generation and masked source offset; and
- fetched executable value.

The general-vector receipt is not a wildcard certificate for all bootstrap roots.
Likewise, current PIF bytes, equal returned words, a prior backing read, or masked
address equality cannot reconstruct a missing root-specific causal join. Missing or
ambiguous same-fetch backing provenance stays UNKNOWN and therefore OPEN.

## Remaining gap

This is not a hardware proof or a complete bootstrap-root census. The bounded result
covers exact pinned ares interpreter execution, synthetic PIF input, a 32-bit kernel
true TLB **load** miss, and the first refill-handler fetch.

Still OPEN include:

- the BEV=1 64-bit XTLB root at `0xffffffffbfc00280`;
- reset/NMI and cache-error/bootstrap roots not already composed to source bytes;
- store/fetch true-miss variants as independent end-to-end source receipts if required
  rather than relying on the already-validated common root-selection primitive;
- recompiler paths;
- arbitrary SI timing and supplied-firmware lifetime/authenticity;
- hardware corroboration; and
- production ProgramMap/certificate import of this causal root-source contract.

## Integration recommendation

**ADOPT the certificate obligation, not the emulator instrumentation.**

For the already-established 32-bit BEV=1 true-miss class, production evidence should
bind the architectural root selection to the exact subsequent CPU fetch and then to a
unique successful PIF-ROM backing read carrying the declared input identity and masked
offset. Keep virtual/physical fetch identity, PIF source identity, backing operation,
and fetched value distinct.

Do not infer PIF provenance from bootstrap vector arithmetic or reuse the general-vector
receipt. Keep XTLB and reset/NMI source composition OPEN until independently joined.
