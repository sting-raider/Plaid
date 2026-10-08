# Reset, NMI, and restore executable lifetimes

Status: **VALIDATED (pinned ares source semantics)**

Date: 2026-10-08

Plaid base: `3cf45dc323cbcd9e6463ccc781d3de093a433097`

Reference: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`

Spike: `spikes/018-reset-cache-lifetime/`

## Result

The hypothesis that every reset-like event can be treated as one executable
lifetime boundary is rejected for the pinned ares model.

Three different transitions have three different lineage effects:

| Transition | I-cache resident bytes | RDRAM bytes / mapping | Plaid consequence |
|---|---|---|---|
| CPU NMI (`Exception::nmi`) | preserved | preserved by this path | continue both lineages |
| `System::power(true)` reset | cleared by `CPU::power` -> `icache.power` | `RDRAM::power(true)` skips RAM/chip/map reinit | end cache residency only; keep backing lineage |
| save-state restore | serialized cache can be restored | serialized RAM/map/chips can be restored | explicit chronology branch/restore epoch required |

Full power (`System::power(false)`) clears I-cache and invokes RDRAM `ram.fill()`
plus chip/mapping initialization. The exact power-on RAM entropy is not part of
this result.

## Falsifying counterexample

A cache line is filled while backing word P is `0x11110000`. Backing P is then
changed to `0x22220000`; cached fetch remains `0x11110000`. NMI changes PC/status
but not cache or RDRAM. Because NMI records the old PC in ErrorEPC and pinned ares
`ERET` returns to ErrorEPC while ERL is set, the next matching cached fetch can
still return `0x11110000` without a fill.

A system reset then preserves the `0x22220000` backing byte state but clears the
I-cache, so the next matching fetch refills and obtains `0x22220000`. After a
later `0x33330000` backing mutation, restoring a snapshot made before reset
restores both the old stale `0x11110000` cache line and the snapshot's
`0x22220000` RDRAM. The first matching fetch after restore is again a cache hit,
not a fill.

This disproves both of these tempting models:

1. `reset_like_event => terminate all byte provenance`
2. `event sequence is globally monotonic across save-state restore`

## Source evidence

Pinned ares paths checked directly:

- `ares/n64/system/system.cpp`: system power orders component `power(reset)`
  calls including RDRAM and CPU.
- `ares/n64/rdram/rdram.cpp`: only `!reset` executes `ram.fill()`, chip
  initialization, and `mapIdentity = 0`.
- `ares/n64/cpu/cpu.cpp`: CPU power always calls I-cache power.
- `ares/n64/cpu/cpu.hpp`: I-cache power clears every `tagKey` and word and does
  not branch on the reset value.
- `ares/n64/cpu/exceptions.cpp`: NMI only alters status, ErrorEPC, and PC.
- `ares/n64/cpu/interpreter-scc.cpp`: ERET returns to ErrorEPC while ERL is set.
- `ares/n64/cpu/serialization.cpp`: cache tags, indices, words, PC, ErrorEPC,
  status, and NMI state are serialized.
- `ares/n64/rdram/serialization.cpp`: RAM, identity-map flag, and all modeled
  RDRAM chip state are serialized.
- `ares/n64/system/serialization.cpp`: synchronized unserialize powers first,
  then restores serialized component state, so the serialized cache/RDRAM state
  supersedes that temporary power state.

## Plaid design implication

Executable provenance needs at least two lifetime notions:

- **backing-byte lifetime** for RDRAM/SP/PIF/etc.;
- **resident-instruction-image lifetime** for the I-cache image actually fetched.

A reset event may end one without ending the other. A restore event is stronger:
it can select an older checkpoint rather than merely advancing either lifetime.
If dynamic traces are allowed to span emulator state restore, add an explicit
restore/checkpoint event or trace-epoch identity and do not join post-restore
facts to pre-restore "latest" writers/fills solely by sequence number.

If production trace capture explicitly forbids or restarts tracing on restore,
record that as an invariant and validate it. Silent continuation across restore
is unsafe.

## Reproduction

```sh
python3 spikes/018-reset-cache-lifetime/model.py
```

Expected final line:

```text
PASS reset/cache lifetime adversarial model
```

The spike README records full deterministic cache/RAM SHA-256 checkpoints.

## Limitations

No compiled ares execution was available in this worker environment, so the
executable harness is a direct, deliberately small transcription of the pinned
source rather than an instrumented ares build. This result therefore establishes
what the pinned implementation's explicit state transitions permit, not a
hardware-level universal invariant. Other hardware reset sources, asynchronous
RCP activity during reset, and user-interface policy about when save-state
restore can occur remain outside scope.

## Recommendation

**ADOPT** the split cache-residency/backing-byte lifetime rule and require an
explicit policy for save-state restore chronology before treating event sequence
numbers as globally monotonic provenance.
