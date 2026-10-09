# MTC0 EntryHi ASID is a translation-context mutation

Date: 2026-10-09

Result: **VALIDATED for the bounded exact-pinned ares scope**.

Integration recommendation: **ADOPT** a translation-context generation/event distinct from installed TLB-entry generations. At minimum, active EntryHi/ASID changes that can affect non-global matching must participate in executable-mapping lifetime reasoning. Do not infer this context history from TLBWI/TLBWR generations, current installed entries, payload equality, or state diffs alone.

Canonical Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`.
Primary reference: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`.
Independent source comparison: n64-systemtest `196f5421173220eb2f63a7a99c64795dc0ea0698`.

## Question

Can Plaid reconstruct TLB-visible executable lifetimes from installed-entry generations alone, or can guest `MTC0 EntryHi` change which already-installed non-global mapping supplies a later instruction fetch without changing a single TLB entry?

## Hypothesis

An interpreted `MTC0 EntryHi` can change the active ASID consumed by non-global TLB matching. Consequently the same mapped virtual PC may resolve to a different physical executable backing after an EntryHi write even if all installed entries are byte-for-byte unchanged. Global mappings must ignore this ASID change. A repeated same-value EntryHi write is still an ordered context write even though snapshot-diff observes no state delta.

The bounded hypothesis is **validated** by exact pinned execution.

## Exact pinned source basis

At the pinned ares revision, `CPU::MTC0` calls `setControlRegister(rd, rt.u64)`. Control register 10 writes `scc.tlb.addressSpaceID`, EntryHi VPN bits, and region. Separately, `TLB::load` rejects a non-global entry when `entry.addressSpaceID != self.scc.tlb.addressSpaceID` before selecting its physical address. Installed-entry mutation and synchronization occur in `TLBWI`/`TLBWR`; the EntryHi setter itself does not write `tlb.entry[]`.

The branch source guard also checks that this exact EntryHi setter does not perform the installed-entry cache-clear/write sequence used by `TLBWI`; the executable fixture, rather than that source fact alone, establishes the result.

Pinned n64-systemtest independently treats EntryHi ASID as live matching state. Its `TLBUseTestReadMatchViaASID` installs a non-global mapping with ASID 1, executes `set_entry_hi(1)`, and reads through that mapping; its global controls deliberately set a different ASID while expecting global mappings to remain usable. That corpus was source-inspected at the exact pin in this session, not executed on physical hardware here.

## Executable fixture

`experiments/mtc0-entryhi-asid/driver.cpp` installs three non-global mappings for the same VA `0x4000`:

- ASID `0x11` -> PA `0x1000`, instruction `ORI t1,zero,0x1111`;
- ASID `0x22` -> PA `0x3000`, instruction `ORI t1,zero,0x2222`;
- ASID `0x33` -> PA `0x5000`, the **same instruction bytes** as the ASID `0x11` page.

A fourth mapping at VA `0x8000` is global and backed by PA `0x7000`.

Every context transition executes real opcode `0x40885000` (`MTC0 t0,EntryHi`) through the interpreter with CPU/RSP recompilers disabled. The fixture semantically serializes all installed TLB entries before the matrix and rejects any change after every context write. It then executes a real instruction fetch through the mapped VA and records the physical address selected by the real TLB path plus the resulting GPR value.

## Deterministic observations

Exact pinned ares produced:

```text
ASID 0x11, VA 0x4000 -> PA 0x1000 -> t1 = 0x1111
ASID 0x22, VA 0x4000 -> PA 0x3000 -> t1 = 0x2222
ASID 0x33, VA 0x4000 -> PA 0x5000 -> t1 = 0x1111
```

All installed TLB entries remained semantically unchanged across those `MTC0 EntryHi` transitions. The `0x11` and `0x33` cases deliberately have identical fetched instruction bytes but different physical backing, so `(virtual PC, payload)` is not a mapping identity.

The fixture then executes the exact same EntryHi value for ASID `0x33` a second time. The staged EntryHi value is unchanged before/after and all installed entries remain unchanged, yet a second guest `MTC0` instruction has executed. Therefore snapshot diff cannot reconstruct complete context-writer history. This does **not** mean a same-value write changes translation; it means an ordered provenance stream cannot recover writer identity by observing only state inequality.

The global control yields PA `0x7000` and `t2 = 0x7777` under both active ASID `0x22` and `0x11`. An unmatched active ASID `0x44` produces TLB-load exception code 2 at VA `0x4000` rather than reusing a stale prior resolution.

## Adversarial reducer

`model.py` runs 20,000 deterministic histories against a deliberately unsound reducer that retains a VA->PA resolution until an installed TLB entry changes.

Recorded receipt:

```text
generated fetches:                              114315
naive entry-only wrong-backing decisions:        47742
same-value EntryHi writes:                       26379
same-value writes invisible to state diff:       26379
equal-payload/different-backing context switches:13232
global ASID-independence checks:                114315
model digest: 18574a58aaf6ff2f5fe8067906901f4a6b38a9cec46063689eeabe843ab29c00
```

The model is not an emulator oracle; it is an adversarial proof that the proposed evidence reduction loses information once the executable fixture establishes that active ASID is an independent mapping selector.

## Exact run receipts

GitHub Actions exact-pin run:

```text
run:                    37921437352
job:                    113790049129
executed source head:   172e4c471e6ae33626aeae0283aa4a594d24b5d5
ares pin:               9408cb43d4948fc3ea6e152a307a34348df3fe04
result JSON SHA-256:    0076568ee8d519d6a0faf2028fbbf40edd556dffa8e51f8896d372422c8bae09
repeat stdout SHA-256:  91477d420c26debce34de7e6a945dbcb26b17e06cf7232bd642c0c2d462f8a16
artifact id:            11612276842
artifact digest:        sha256:c10fb5b988169f18c0081fa12ff1492711a21da72a1e6ac5cf2a8d1af3dc7bd4
```

The job fetched the exact ares pin, passed Python syntax checks, the deterministic adversarial model, and exact-source guards, built the unmodified pinned ares headless oracle, executed the fixture twice byte-for-byte identically, hashed the result payload, and uploaded it.

Source-guard hashes from the receipt:

```text
interpreter-scc.cpp SHA-256: df7252d14f532e9fa44a39147be05afeb9851196a7d5249ab325900cee2aa722
tlb.cpp SHA-256:             93722177331f1df2cd7cbf313909bf20a148183d8cbd73db928b7cf0bff506d1
```

No emulator instrumentation was needed, so there is no observer-neutrality delta to prove. The tested executable is the ordinary pinned ares build produced by the existing Plaid oracle builder.

## Safe integration contract

For executable mapping/lifetime reasoning, keep at least two distinct ordered state families:

1. **installed-entry generations**: actual TLBWI/TLBWR/reset/restore changes to TLB slots;
2. **translation-context generations**: active matching context such as EntryHi ASID, including guest `MTC0 EntryHi` and other proven mutation sources such as successful TLBR.

A later mapped executable fetch must be interpreted against both the installed-entry state and the active translation context at that point in chronology. Do not cache a virtual-to-physical executable identity merely until the next TLB entry write.

If exact writer lineage for CP0 state is part of the proof, record same-value context writes at the actual instruction/mutation boundary; before/after inequality is insufficient to recover that history.

## What this does not prove

- It does not characterize physical-N64 timing or CP0 hazard latency; the independent n64-systemtest source is supporting evidence, not a hardware run performed here.
- It does not solve TLBWI/TLBWR generation identity, PageMask geometry, cacheable I-cache synonyms, TLBR semantics, save/restore/reset epochs, 64-bit region/address modes, privilege transitions, or overlapping-entry hardware corner cases.
- It does not prove that every EntryHi field besides ASID has the same closure significance. This fixture isolates ASID matching.
- It does not prove arbitrary-ROM reachability or whole-ROM closure.
- It does not promote one emulator implementation into a platform-wide invariant where references disagree.

Within those limits, an installed-entry-only mapping history is **rejected**: real interpreted `MTC0 EntryHi` can switch executable backing while installed TLB entries remain unchanged.

## Reproduce

With `.refs/ares` at the exact pinned revision:

```sh
python3 -m py_compile experiments/mtc0-entryhi-asid/{run.py,source_guard.py,model.py}
python3 experiments/mtc0-entryhi-asid/model.py
python3 experiments/mtc0-entryhi-asid/source_guard.py
python3 experiments/mtc0-entryhi-asid/run.py
sha256sum target/ares-mtc0-entryhi-asid/results.json
```

Expected result SHA-256:

```text
0076568ee8d519d6a0faf2028fbbf40edd556dffa8e51f8896d372422c8bae09
```
