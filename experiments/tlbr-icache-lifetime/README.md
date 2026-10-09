# TLBR + I-cache executable-lifetime composition

This bounded experiment composes two already-validated Plaid findings against exact pinned ares:

1. `TLBR` can load a different EntryHi ASID and thereby change translation reachability without replacing any installed TLB entry.
2. A cacheable mapped instruction can remain resident after its mapping becomes temporarily inactive, so later ASID reactivation may execute stale resident bytes rather than current backing.

The fixture asks whether those facts actually compose when **TLBR itself** is the context-changing instruction.

## Exact references

From `refs.lock.toml`:

- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`
- Mupen64Plus Core `ba95bab92a76744753bfe61470823a4937850ab0`
- n64-systemtest `196f5421173220eb2f63a7a99c64795dc0ea0698`

The exact executable oracle is pinned ares with CPU/RSP recompilers disabled. Gopher64 and Mupen are disagreement guards, not hardware truth; n64-systemtest provides hardware-oriented ASID test-source evidence.

## Adversarial sequence

The fixture installs three non-global mappings for VA `0x4000`:

- slot 0 / ASID `0x11` -> PA `0x1000`, old word `ORI t1,zero,0x1111`
- slot 1 / ASID `0x22` -> PA `0x3000`, word `ORI t1,zero,0x2222`
- slot 2 / ASID `0x33` -> PA `0x5000`, **equal old payload** `ORI t1,zero,0x1111`

It also installs a global control at VA `0x6000` and an unrelated slot whose only purpose is to let real TLBR load unmatched ASID `0x44`.

The key history is:

1. real guest `TLBR` slot 0 activates ASID A;
2. fetch VA `0x4000` and fill A's I-cache resident line from PA `0x1000`;
3. execute real `TLBP` control and require EntryHi context/cache state unchanged;
4. real guest `TLBR` slot 1 activates B without changing installed entries or I-cache state;
5. mutate A backing to `ORI ... 0x4444` while A is inactive;
6. execute a same-value TLBR of slot 1 and preserve it as a distinct ordered operation despite equal CP0 values;
7. execute out-of-range TLBR index 63 and require an exact-pinned no-op;
8. TLBR an unrelated slot to load ASID `0x44`; VA `0x4000` must fault without refilling/replacing A's resident line;
9. TLBR slot 0 again, then fetch VA `0x4000`;
10. require a **cache hit of stale `0x1111`** even though current PA `0x1000` backing contains `0x4444`;
11. TLBR slot 2 and fetch the equal-payload word at PA `0x5000`; require a physical-tag miss/replacement despite equal bytes;
12. TLBR slot 0 again; because C replaced A's resident slot, require a miss and execute fresh `0x4444`.

Every TLBR/TLBP control snapshots installed entries and serialized I-cache contents around the instruction. The helper opcodes execute from uncached KSEG1 so they do not perturb the cacheable test slot.

## Reducer

`model.py` deliberately keeps separate:

- TLBR instruction-operation generation;
- successful translation-context generation;
- installed-entry generation;
- backing-storage generation;
- resident-fill generation.

It rejects forged histories based on current backing, equal payloads, treating TLBP as a context write, treating out-of-range TLBR as a successful context write, or pretending TLBR replaced the installed mapping.

## Reproduce

With the exact refs checked out under `.refs/`:

```bash
python3 -m py_compile experiments/tlbr-icache-lifetime/{source_guard.py,model.py,run.py}
python3 experiments/tlbr-icache-lifetime/source_guard.py
python3 experiments/tlbr-icache-lifetime/model.py
python3 experiments/tlbr-icache-lifetime/run.py
```

GitHub Actions workflow: `.github/workflows/research-tlbr-icache-lifetime.yml`.
