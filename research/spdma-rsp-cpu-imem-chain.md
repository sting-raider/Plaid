# SP-DMA -> RSP transform -> CPU copy -> IMEM provenance composition

Date: 2026-10-10

Status: **VALIDATED (bounded composition proof)**

Worker: `gpt56sol-spdma-rsp-cpu-imem-chain-20261010`

Claim: issue #4 comment `6091049299`.

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`.

Research branch: `research/spdma-rsp-cpu-imem-chain-gpt56sol`.

## Question

Can Plaid carry **ultimate executable-byte provenance** across the full bounded chain

```text
successful RDRAM source read
  -> forward SP-DMA DMEM sink generation
  -> RSP scalar DMEM load / live GPR generation / scalar store
  -> CPU DMEM LW / live GPR generation / IMEM SW
  -> RSP executable fetch
```

without laundering distinct producer generations through equal payloads, or silently repairing missing ancestry from later values?

This is a composition question, not a new emulator-behavior claim. Every primitive edge below was already established by separately executed exact-pin research. The experiment source-guards those artifacts and attacks only the joins between them.

## Exact prior contracts

The branch verifies these exact Git objects before running:

- forward SP-DMA RDRAM -> DMEM ingress:
  - commit `7041402beb2ce63a43336ae627372098af50ff0f`
  - `research/sp-dma-dmem-ingress.md` blob `1d80c92dc22542039494bd606c886a7cafa1d234`
  - `spikes/043-ares-sp-dma-dmem-ingress/run.py` blob `03fe4653abfe75576337dc001ffaf23f7da3d3ba`
- RSP scalar load -> GPR -> store lineage:
  - commit `3c89a579aef404dba01aab2353ac2f8723750907`
  - `research/rsp-scalar-load-store-lineage.md` blob `f81500f36a8ccb438cfaee412cab1cfd33c95aee`
- mixed-origin DMEM -> CPU Word copy -> IMEM -> RSP fetch composition:
  - commit `537f230bc85788c4ff573a716a42acb7809f4989`
  - `research/rsp-dmem-cpu-copy-imem-fetch.md` blob `41935dd029d85ce51f3834f6e242e627ddd900f4`
  - `experiments/rsp-dmem-cpu-copy-imem-fetch/model.py` blob `6c88a109ba8ce1664139e431ce2714643c39209f`
- `refs.lock.toml` still pins ares at `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

The composed proof therefore depends on the exact scopes and limitations of those prior results. It does not elevate one emulator's incidental callback ordering to hardware truth.

## Executable composition model

`experiments/spdma-rsp-cpu-imem-chain/model.py` replays a deterministic 34-event history. It keeps separate state for:

- current DMEM byte value;
- current DMEM storage-writer generation;
- ultimate byte origin, which may be UNKNOWN;
- RSP GPR definition generation and attached byte ancestry;
- CPU GPR definition generation and attached byte ancestry;
- IMEM resident generation;
- ultimate byte origin visible at each RSP fetch.

That separation is essential. Storage generation, register generation and ultimate origin are related causal facts, not interchangeable identities.

The positive chain is intentionally adversarial:

1. SP-DMA installs one Word from RDRAM `0x1000` into DMEM;
2. a byte-identical SP-DMA reload from RDRAM `0x2000` installs a fresh DMEM writer generation and new backing ancestry;
3. an unrelated successful equal-valued RDRAM read at `0x3000` exists as a provenance decoy;
4. decoded RSP `LW` consumes the exact current DMEM byte generations;
5. decoded RSP `SW` creates a fresh DMEM storage generation while preserving the proven upstream byte origins;
6. CPU `LW t0` consumes that Word, while an equal-valued later `LW t1` from another DMEM Word is retained as a decoy;
7. CPU `SW t0` installs a new IMEM resident generation with the exact inherited byte ancestry;
8. RSP fetch observes that executable Word.

Additional phases then attack same-value generations, partial overwrite, missing source evidence and register-definition cuts.

## Result

**VALIDATED for this bounded composition model.**

The first executable fetch has ultimate origins:

```text
rdram:3:00002000
rdram:3:00002001
rdram:3:00002002
rdram:3:00002003
```

The older equal-valued DMA from `0x1000` and the later equal-valued read from `0x3000` do not steal ancestry. The exact successful source transaction joined to the current DMA sink does.

A second same-value RSP store creates a fresh destination writer (`rsp-store:13` instead of `rsp-store:8`) while retaining the same proven ultimate RDRAM origins. This demonstrates again that **storage generation may change while ultimate producer ancestry remains causally preserved**. Those facts must not be collapsed.

A same-value CPU overwrite of only source byte 2 changes the later executable origin vector to:

```text
rdram:3:00002000
rdram:3:00002001
cpu-dmem:cpu-patch:17
rdram:3:00002003
```

The untouched bytes retain their older DMA ancestry. Before/after value equality cannot erase the intervening write.

A completed DMA sink with no successful backing-read witness has known zero content but UNKNOWN origin. After RSP `LW -> SW`, CPU `LW -> SW` and IMEM execution, all four origins remain UNKNOWN. The later transforms do not manufacture a source from the value.

Likewise, an RSP `LW` followed by a same-value whole-GPR writer and then `SW` produces a content-valid downstream chain whose ultimate origin is UNKNOWN. The bounded RSP lineage contract says that an unproved whole-GPR transform replaces the load generation even if the numeric value is unchanged.

## Projection-collision counterexample

The strongest falsifier constructs two entirely valid histories:

- history A uses the active same-value DMA source at RDRAM `0x2000`;
- history B uses the active same-value DMA source at RDRAM `0x4000`.

Both histories have identical:

- RSP store writer identities and ordinals;
- CPU IMEM-copy resident generations and ordinals;
- RSP fetch PCs and instruction values;
- IMEM resident-generation vectors.

Yet their ultimate executable origins differ:

```text
A: rdram:3:00002000 .. 00002003
B: rdram:3:00004000 .. 00004003
```

Therefore the downstream projection cannot reconstruct upstream DMA ancestry after it has been discarded. Equal payload, equal downstream storage generations, equal control chronology and equal fetch state are still insufficient. The ancestry has to cross the seam losslessly when the causal edge is established.

## Forged-history attacks

Strict replay rejects all eight deliberate forgeries:

1. substitute the older same-value DMA source read;
2. substitute a later equal-valued decoy source read;
3. drift the DMA source address while retaining the value;
4. delete the successful source read and renumber the history;
5. let the equal-valued CPU decoy load clobber the true source register;
6. delete the same-value RSP GPR clobber;
7. move the one-byte CPU overwrite to the wrong lane;
8. make the RSP store consume the wrong live register generation.

These attacks cover value equality, missing evidence, reordered/deleted events, wrong generation and partial-byte provenance substitution.

## Reproduction and receipt

Files:

- `experiments/spdma-rsp-cpu-imem-chain/model.py`
- `experiments/spdma-rsp-cpu-imem-chain/source_guard.py`
- `experiments/spdma-rsp-cpu-imem-chain/README.md`
- `.github/workflows/research-spdma-rsp-cpu-imem-chain.yml`

Run:

```sh
python3 experiments/spdma-rsp-cpu-imem-chain/source_guard.py
python3 experiments/spdma-rsp-cpu-imem-chain/model.py
```

Validated executable-evidence head:

- commit `240f2463f970023c1a64d1de6c5ff83d3a8e4d15`
- Actions run `38005241210`
- job `114072392499`
- Ubuntu `24.04.5`, runner image `20261004.327.1`
- exact model result SHA-256 `a7305b902d39d1963a98c33106f5009aac33898f8860bbe248f7f5e8721e75b3`
- artifact ID `11650309410`
- uploaded artifact ZIP SHA-256 `d3a95d72d65a356f2b29d4d6abda8291c3059127fc056fe15e3789347eb4a011`

The run fetched the exact prior commits, passed all five Git-object guards and the ares pin guard, compiled the Python files, replayed the model twice with byte-identical output, checked the exact result digest, passed `git diff --check`, and uploaded both replay receipts.

## Composed or challenged prior research

This result composes rather than supersedes:

- the SP-DMA ingress proof that completed DMEM sinks need exact successful source-transaction identity and mint fresh writer generations even for equal payloads;
- the RSP scalar load/store proof that a live GPR generation, not matching numeric value, carries source-byte ancestry across the transform;
- the CPU DMEM -> IMEM proof that a destination resident generation is separate from the inherited per-byte origin vector.

It challenges two tempting shortcuts:

1. **"the latest equal value is probably the producer"** — concretely false at the DMA, RSP-register and CPU-register seams;
2. **"downstream storage generations plus final bytes are enough to recover source provenance later"** — falsified by the two-valid-history projection collision.

## Closed-world impact

A future Plaid executable-provenance certificate can compose this class of chain, but only if each boundary retains two logically separate things:

1. the new local generation created by the effect, such as a DMEM sink, RSP/CPU register definition, or IMEM resident generation;
2. a lossless mapping from the affected destination bytes/ranges to the exact upstream origins justified at that boundary.

A practical implementation may compress adjacent byte origins into intervals, but it may not collapse distinct origins merely because they share value, hash, copy request, Word operation or destination generation.

UNKNOWN must be an explicit hard cut. A later copy or transform may carry UNKNOWN forward; it cannot repair it from equal bytes. Provenance can only become known again from an independent causal witness that actually establishes a new origin.

This closes one higher-order information-loss uncertainty for the evidence model. It does **not** make `WholeRom` closed or establish native completeness.

## Remaining gaps

This bounded result does not establish:

- a new hardware/emulator behavior beyond the exact guarded primitive research;
- a primitive successful RSP DMEM-read callback; the scalar load proof still reconstructs the source from decoded execution plus replayed DMEM state;
- vector-register transforms or general provenance-preserving arithmetic/logical RSP transforms;
- CPU byte/half/unaligned/64-bit copy forms, D-cache-delayed copies or translated aliases;
- asynchronous scheduler/interrupt races across these component operations;
- complete CPU/RSP/DMA mutation coverage;
- save/restore/reset/NMI/debugger lifetime boundaries;
- RSP task/microcode activation and retirement completeness;
- exhaustive execution roots/indirect targets;
- whole-ROM future-execution closure.

Those unresolved obligations remain OPEN.

## Integration recommendation

**ADOPT the provenance-composition invariant, not this standalone model as production architecture.**

The production evidence graph should retain local generation identity separately from ultimate ancestry and carry ancestry losslessly through each proven copy/transform. Same-value writes and reloads mint new local generations. A transform may preserve upstream ancestry only when its exact causal input generation and transform semantics are proved. Missing source evidence or an unproved intervening definition cuts ancestry to UNKNOWN. Never reconstruct discarded ancestry from final values, hashes, addresses or downstream generation equality.

No merge to `main` was performed.
