# VR4300 Watch exception root / closure obligation

Result: **PARTIAL**

Worker: `gpt56sol-watch-exception-roots-20261009`

Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Research branch: `research/watch-exception-roots-gpt56sol`

## Question

Can whole-ROM closure exclude the VR4300 Watch exception from the executable-root
model when reference-emulator traces do not show it, and what state must a future
certificate preserve?

## Hardware contract

Primary source: **VR4300 User's Manual**, `U10504EJ7V0UM00`, 7th edition.

Sections 6.3.8 and 6.4.17 establish the bounded contract used here:

- WatchLo `PAddr0` is physical-address bits 31:3, so the selected unit is an
  8-byte physical block. WatchHi bits 35:32 exist for software compatibility but
  are invalid as VR4300 physical-address bits.
- WatchLo.R enables load trapping; WatchLo.W enables store trapping.
- A matching enabled load/store raises the Watch exception. `CACHE` never does.
- EXL postpones Watch; clearing R/W disables it.
- Watch uses the common exception vector and the Watch ExcCode (`23`). EPC/BD
  identify the faulting load/store in the ordinary exception manner.
- WatchLo/WatchHi are **undefined after reset**. The manual explicitly requires
  software initialization and warns that an uninitialized Watch can occur.
- Figure 6-14 routes general-purpose exceptions to `base + 0x180`, with base
  `0xffffffff80000000` for BEV=0 or `0xffffffffbfc00200` for BEV=1.

Therefore an emulator's convenient zero-filled reset state cannot certify Watch
as disabled.

## Exact pinned reference audit

Pins are taken from `refs.lock.toml`:

- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`
- Mupen64Plus Core `ba95bab92a76744753bfe61470823a4937850ab0`
- n64-systemtest `196f5421173220eb2f63a7a99c64795dc0ea0698`

`source_guard.py` demonstrates an important ares split at that pin:

1. `WatchLo`/`WatchHi` storage exists.
2. guest CP0 writes update W, R and physical-address fields.
3. Watch state is serialized.
4. `Exception::watchAddress()` exists and maps to `trigger(23)`.
5. nevertheless, the only `watchAddress` references are its declaration and
   definition; no N64 execution call site invokes it.
6. the only lower-case `watchLo` member users are `cpu.hpp`,
   `interpreter-scc.cpp`, and `serialization.cpp`; no load/store path consumes it.

The guard also records that the pinned Gopher source has Watch register masks but
comments out the named WatchLo/WatchHi constants, pinned Mupen stores WatchLo via
MTC0 without a named Watch exception handler in the guarded audit, and pinned
n64-systemtest only names WatchLo in its CP0 register enum. This is **not** proof
that those projects can never model Watch through another mechanism; it is a
fail-closed statement about the exact audited paths.

Source-guard payload SHA-256:

`c33fe48eac49af5e39d2e4e020e95bc1e92529e1a13dac3cee3381728d8caa0b`

Selected exact-source SHA-256 values are stored in that payload.

## Executable ares probe

`driver.cpp` runs unmodified pinned ares through Plaid's existing
`spikes/003-ares-oracle` build helper. The guest executes:

1. `MTC0 $t0,$18` to program WatchLo,
2. four hazard NOPs,
3. one uncached `LW` or `SW` to a chosen physical block.

The fixture does not mutate ares and disables both recompilers. Each case executes
twice and must produce byte-identical JSON.

Fourteen cases passed:

- 6 hardware-manual immediate-Watch cases: matching read/write, BEV=0/1, and
  address `+4` within the same watched 8-byte physical block.
- 6 normal controls: disabled R/W, wrong access type, and next-block `+8`.
- 2 EXL=1 matching cases, for which the manual says Watch is postponed.

Pinned ares took **0/6** of the manual-expected immediate Watch exceptions. In
all six, the faulting access retired, PC advanced to `start+0x18`, the Cause/EPC/BD
sentinels remained unchanged, and loads/stores produced their ordinary data side
effects. All six normal controls also retired. The two EXL cases show no immediate
entry in ares, but because the implementation has no call site they do not validate
the hardware's later postponed-entry timing.

Results payload SHA-256:

`08eed307c85a39933360e1c26b3d15c1173836e5a382ea1f9d31858bad6dd422`

Successful Actions run: `37970065497`, artifact `11635706106`.
Artifact ZIP SHA-256 reported by Actions:

`3f42d653bdfb2055c3326628e998a5109025dc4d91cdc3a924461f4c28e45160`

## Adversarial certificate model

`model.py` keeps Watch register generation separate from semantic value and starts
reset with **UNKNOWN** Watch state rather than zero.

The deterministic matrix covers reset-unknown, explicit disable, R/W selection,
`+0/+4/+8` physical matching, EXL postponement, CACHE exclusion, BEV vector choice,
higher-priority preemption and a same-value WatchLo rewrite.

The model additionally ran 100,000 deterministic-seed randomized history
operations and observed 7,151 same-value register rewrites. Seven forged closure
claims are explicitly rejected:

- reset-unknown claimed disabled,
- matching read claimed normal,
- low-lane alias claimed non-match,
- CACHE claimed Watch,
- EXL-postponed case claimed ordinary normal,
- wrong BEV vector,
- same-value WatchLo rewrite coalesced into the prior register generation.

Model report SHA-256:

`ae0e2b9be0ddd9749281f6c875fb524c330e40b08e7ee09e3910aa626f6c5415`

## Hypothesis result

The root/closure half is validated, but the full claimed lane is PARTIAL because
postponed-entry timing and several priority/mode interactions still need hardware
or an independent executable oracle.

Validated:

- Watch is architecturally real on VR4300 and shares the BEV-sensitive common
  `+0x180` vector.
- It is driven by enabled load/store references to an 8-byte **physical** address
  block, not by virtual value equality.
- reset state is not a certificate of disablement; it is unknown until stronger
  evidence establishes otherwise.
- reference-emulator non-observation cannot discharge the obligation. Pinned ares
  demonstrably disagrees with the manual for six positive cases despite exposing
  guest-writable Watch state and an unused ExcCode-23 wrapper.
- a same-value WatchLo write is a distinct register-generation/history event even
  though it need not change the semantic match set.

Not validated here:

- exact hardware timing of a postponed Watch when EXL later clears,
- all exception-priority interactions around translated/failing accesses,
- branch-delay Watch on physical hardware,
- independent user/supervisor/kernel and ERL matrices,
- a physical N64/systemtest execution receipt.

## Closed-world impact

Watch does not introduce a fourth vector address beyond the already established
general `+0x180` byte root, but it adds a separate **reachability and CPU-state
obligation**. A whole-ROM certificate must not mark exception paths closed merely
because its reference trace never emitted Watch.

A future verifier should fail closed unless it can establish one of these scoped
conditions:

1. stronger hardware evidence constrains the initial Watch state, or
2. every relevant path reaches a verified WatchLo generation with R=W=0 before
   any data access for which reset-unknown state matters and never re-enables it,
   or
3. enabled Watch generations are modeled against the physical address of each
   reachable load/store, including TLB/remap aliases, with the resulting common
   exception root included.

The verifier must retain WatchLo register generations, BEV generation, EXL state,
physical translation context, and access kind. Value equality must not erase a
write event. `CACHE` is explicitly outside the Watch trigger set.

The exact semantics of EXL-postponed Watch should remain OPEN until separately
validated rather than being approximated as either a normal access or an immediate
exception.

## Integration recommendation

Do **not** integrate emulator-specific Watch behavior into Plaid production code.
Integrate the proof obligation and adversarial model semantics when whole-ROM
exception certificates are introduced:

- seed reset Watch state as unknown unless stronger platform evidence exists;
- track MTC0 WatchLo generations and R/W/PAddr0 fields;
- compose matches with trustworthy physical-translation history, not virtual
  pointer equality;
- share the already validated common-vector byte root but preserve Watch as a
  distinct reachability reason;
- refuse CLOSED when Watch is enabled/unknown and the relevant physical access or
  postponed timing cannot be proven.

A hardware-backed n64-systemtest for Watch should be the next semantic oracle,
not another emulator-majority vote.
