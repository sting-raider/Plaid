# Ares TLBWI mapping-generation completeness

Status: **VALIDATED** for the bounded exact-pinned-reference question described below.

## Scope and exact revisions

- Plaid integration base inspected before the claim: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256` (`main`).
- Exact ares revision from `refs.lock.toml`: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.
- Independent source comparison: Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`.
- Isolated branch: `research/tlbwi-mapping-generation-gpt56sol`.
- Executable spike: `spikes/045-ares-tlbwi-mapping-generation/`.
- Exact-reference Actions run: `37919492589`, job `113783720157`, SUCCESS.
- Uploaded result artifact: `11610618838`; artifact ZIP SHA-256 `523d1b61b654d7827bb9362a324fdaffbcd35cb2b467bc06e42bd6b2bce17e32`.
- `results.json` SHA-256: `6ef416a44a0fb533a1e291b8adab42b158f0eb581ec81a9174509b3d6ab606e0`.
- Repeated executable stdout SHA-256: `3f4cb59ab36e9f12713002684e65e6c6d38d3591fdc286a2e6549131abd2ae33`.

## Falsifiable hypothesis

A legal interpreted VR4300 `TLBWI` reaches a concrete selected-slot write boundary even when the staged normalized TLB entry is byte-for-byte identical to the entry already in that slot. Therefore a pre/post TLB snapshot diff is not a complete census of TLB write operations. A complete ordered mapping-mutation history for closure/provenance must preserve same-value legal `TLBWI` operations at their actual selected-slot boundary. Out-of-range Index and privilege/COP0 failure controls must not fabricate such a write event.

This is intentionally narrower than TLB translation semantics, TLBP/TLBR behavior, TLBWR random selection, or cached fetch lifetime.

## Exact source contract

`source_guard.py` requires a clean exact ares pin and checks the interpreted `TLBWI` path in `ares/n64/cpu/interpreter-scc.cpp` plus decoder dispatch. The guarded order is:

1. privilege/COP0 eligibility check;
2. `scc.index.tlbEntry >= TLB::Entries` early return;
3. `devirtualizeCache = {}`;
4. `tlb.entry[scc.index.tlbEntry] = scc.tlb`;
5. selected entry `synchronize()`;
6. `debugger.tlbWrite(scc.index.tlbEntry)`.

The decoder guard requires opcode function `0x02` to dispatch `TLBWI`.

This ordering matters: an in-range same-value write traverses the write/synchronize/debugger path even though comparing TLB state before and after the instruction cannot reveal that the operation happened. Conversely, an out-of-range Index returns before the cache clear and slot write.

At pinned Gopher64, `cop0.rs::tlbwi` independently passes CP0 Index to `tlb::write`. The pinned `tlb.rs::write` returns only for `index > 31`; otherwise it unmaps the selected entry, reconstructs it from staged CP0 registers, and maps it again. There is no equality short-circuit in the inspected path. This is useful independent source support for treating legal TLBWI as an operation rather than inferring it from value inequality, but it is not a hardware oracle and was not dynamically executed in this worker.

## Executable fixture

`driver.cpp` embeds the ordinary exact-pinned ares component fixture with CPU/RSP recompilers disabled and executes actual encoded `TLBWI` instructions (`0x42000002`). No ares CPU/TLB instrumentation or upstream patch is used.

The matrix contains four adversarial cases:

1. **Changed-value legal write.** Slot 7 is preloaded with an entry equal to the staged payload while CP0 Index is 5. Real TLBWI changes exactly slot 5, retains Index 5, and clears the devirtualization cache. Slots 5 and 7 then contain equal mapping payloads, proving payload equality cannot identify the selected slot.
2. **Same-value legal rewrite.** Slot 5 already contains the staged normalized entry. Real TLBWI executes again and clears the devirtualization cache, but the complete 32-entry pre/post snapshot has zero changed slots.
3. **Out-of-range Index.** Index 63 executes the real decoded opcode in kernel mode. No TLB slot changes and the pre-armed devirtualization-cache sentinel is preserved, matching the guarded early-return boundary.
4. **Privilege/COP0 failure.** A global uncached TLB entry maps user VA `0x4000` to the real opcode at physical `0x2000`; user mode with CU0 disabled fetches the opcode successfully, raises Coprocessor Unusable (ExcCode 11), and changes zero TLB slots.

Exact output facts from run `37919492589`:

```json
{
  "first_cache_cleared": true,
  "first_changed_slot": 5,
  "oob_cache_preserved": true,
  "oob_changed_count": 0,
  "privilege_changed_count": 0,
  "privilege_exception": 11,
  "same_cache_cleared": true,
  "same_value_changed_count": 0,
  "slot5_equals_slot7": true
}
```

The executable is run twice and the runner requires byte-identical stdout before accepting the evidence.

## Independent adversarial reducer

`model.py` does not use ares code. With deterministic seed `362056669001`, it generated 20,000 histories over 32 slots plus legal/out-of-range Index values:

- 10,035 legal TLBWI operations;
- 9,965 out-of-range attempts;
- 2,654 same-value legal writes;
- exactly 2,654 snapshot-diff false negatives;
- 3,262 legal operations whose staged payload existed in more than one final slot;
- 1,636 cases where choosing the first equal-payload slot selected the wrong slot;
- four fixed forged histories rejected: missing same-value boundary, stolen equal-payload decoy slot, fabricated out-of-range generation, and wrong legal slot.

Model SHA-256: `8c0350d8f1604b6935fcf68b0a148bb7688aaf1629355490b56816a7e7dee868`.

## Reproduction

With `.refs/ares` checked out cleanly at the exact pin:

```sh
python3 -m py_compile spikes/045-ares-tlbwi-mapping-generation/{run.py,source_guard.py,model.py}
python3 spikes/045-ares-tlbwi-mapping-generation/model.py
python3 spikes/045-ares-tlbwi-mapping-generation/source_guard.py
python3 spikes/045-ares-tlbwi-mapping-generation/run.py
sha256sum target/ares-tlbwi-mapping-generation/results.json
```

The branch workflow performs the fresh pinned checkout and the same checks.

## Result

**VALIDATED**, within the exact-pinned-emulator scope: snapshot inequality is not a complete witness for legal `TLBWI` operations. A same-value legal TLBWI reaches the same guarded selected-slot write/synchronize/debugger path as a changed-value write, while an out-of-range Index and CU0-disabled user attempt do not reach that mutation path.

For a complete TLB mutation/provenance stream, retain an ordered event at the actual legal TLBWI selected-slot write boundary, carrying at minimum operation kind, selected slot, staged/normalized entry identity, and capture epoch. Do not recover the event from pre/post snapshot differences, matching mapping payloads, or later translation/fetch observations. Same-value operations are distinct operation generations even though they do **not** imply a different translation mapping or a new executable lifetime by themselves.

## Limitations and explicit non-proofs

This result does **not** prove physical N64 hardware behavior, guest reachability, or whole-ROM closure. It does not claim that a same-value TLBWI changes architectural translation content. It does not settle overlapping-entry behavior, large PageMask/64-bit regions, ASID/global corner cases, reset/save-restore epochs, recompiler execution, TLBP/TLBR semantics, TLBWR selection, I-cache residency, or translation lifetime. It does not prove that emulator consensus equals hardware truth.

The ares devirtualization cache is an emulator-internal side effect used only as a deterministic witness that the legal function path passed the bounds check; production Plaid should observe/record the actual mapping-operation boundary rather than depending on that internal cache. Gopher64 evidence here is source-derived only.

## Integration recommendation

**ADOPT** the event-model requirement: for TLB mapping-history completeness, legal TLBWI must be represented from the actual selected-slot operation boundary, including same-value writes; invalid/failed attempts must not mint events. Keep mapping content identity separate from operation-generation identity, and keep both separate from executable I-cache lifetime.
