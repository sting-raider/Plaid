# ERET target provenance experiment

This bounded experiment asks whether Plaid may treat `ERET` as returning only to a PC previously captured by exception/NMI entry, or whether CP0 return-register writes make `ERET` an independently programmable control transfer.

## Exact scope

Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Reference pins from `refs.lock.toml`:

- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`
- Mupen64Plus Core `ba95bab92a76744753bfe61470823a4937850ab0`
- n64-systemtest `196f5421173220eb2f63a7a99c64795dc0ea0698`

## Reproduce the adversarial replay

```bash
python3 -m py_compile experiments/eret-target-provenance/model.py
python3 experiments/eret-target-provenance/model.py
```

The local repeated run used Python 3 and produced byte-identical stdout twice.

Expected durable hashes for this version:

- `model.py` SHA-256: `23350e13ccfa6df122aa25a829471ce688c4dd1afbc3556fe7e2aae0ab2189b1`
- complete stdout SHA-256: `7d94d6f6c7692ef39ff288b2656123d7678e1a7eb3f7e6fea883cb5fcc8a462e`
- canonical report SHA-256: `994d5fa3a83c7ced1ad2ebc40c4fbf9b1c95f1b298fe2f4d94b243a41969b530`

The deterministic 100,000-history common-EPC fuzz produced 624,838 `ERET` events. A deliberately unsound capture-only policy produced 136,420 wrong targets, 127,590 missing targets, and 67,605 same-value provenance substitutions. The generation-aware policy retained 396,023 known current-register targets and failed closed for 228,815 unknown selected-register states.

## Exact-source guards

`verify_sources.py` is intended to run against clean checkouts at the exact pins above. It asserts the specific source contracts used by the note, including the important negative result that pinned Mupen's pure interpreter stops on `ERET` while ERL is set rather than jumping to ErrorEPC.

Example:

```bash
python3 experiments/eret-target-provenance/verify_sources.py \
  --plaid . \
  --ares /tmp/refs/ares \
  --gopher64 /tmp/refs/gopher64 \
  --mupen /tmp/refs/mupen64plus-core \
  --systemtest /tmp/refs/n64-systemtest
```

The branch-only workflow clones those exact pins and executes both the source guards and the replay model.

## Result shape

The common EPC claim is supported independently: all three pinned emulator sources permit guest writes to EPC and route ordinary `ERET` through the current EPC, while the pinned n64-systemtest privilege harness explicitly writes an arbitrary entry to CP0 EPC (`$14`) immediately before `ERET`.

The ErrorEPC/ERL subclaim is **not** cross-reference consensus. Exact pinned ares and Gopher64 select ErrorEPC when ERL is set; exact pinned Mupen instead logs `error in ERET` and stops. Plaid therefore must not promote the ares/Gopher behavior into a platform-wide invariant from emulator agreement alone.

No ROM, firmware, copyrighted asset, or generated trace is stored here.
