# R4300 exception-vector executable roots in pinned ares

Status: **VALIDATED**

Date: 2026-10-08

## Question

For the exact ares revision pinned by Plaid, which virtual PCs can the tested
classes of guest-triggered R4300 exceptions select as their first handler
instruction? The purpose is executable-root enumeration, not a claim that an
exception path is reachable in every ROM.

## Pins

- Plaid branch base: `3cf45dc323cbcd9e6463ccc781d3de093a433097`
- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64 source cross-check: `e96debac941a26ba4961e5145056c0821d3a56f7`
- n64-systemtest source/test cross-check: `196f5421173220eb2f63a7a99c64795dc0ea0698`

## Falsifiable hypothesis

For ordinary exceptions and TLB-invalid faults, pinned ares selects the general
vector `base + 0x180`. For true TLB misses with EXL clear, it selects `base + 0`
in 32-bit kernel mode and `base + 0x80` in 64-bit kernel mode. BEV selects base
`0xffffffff80000000` versus `0xffffffffbfc00200`. EXL already set forces the
general vector and preserves pre-existing EPC/BD. A fault in a branch delay slot
changes EPC/BD but not the selected vector.

## Upstream source map

In pinned ares, `ares/n64/cpu/exceptions.cpp` initializes the offset to `0x180`,
switches true TLB misses with EXL clear to `0x000` or `0x080` according to
`context.bits`, and distinguishes miss wrappers from invalid/modification
wrappers. The same function updates EPC/BD only when EXL was clear. `context.cpp`
derives 32/64-bit kernel context from Status KX, and `tlb.cpp` distinguishes no
matching entry (miss) from a matching invalid entry.

This distinction matters to Plaid because treating all TLB exception code 2/3
entries as refill-vector roots is wrong: exception code alone does not determine
which handler PC was selected.

## Experiment

`spikes/019-ares-exception-vectors/` uses the existing spike-003 headless pinned
ares build helper without patching CPU implementation sources. It executes a
matrix of 28 guest-triggered cases, each twice with byte-identical JSON required:

- SYSCALL as an ordinary general-vector control;
- TLB load miss, store miss, and instruction-fetch miss;
- a matching but invalid TLB entry as the adversarial non-refill case;
- BEV 0/1;
- 32/64-bit kernel addressing;
- EXL clear/set for a true TLB load miss;
- SYSCALL and TLB-miss faults in branch delay slots.

The instruction-fetch case starts the guest PC in mapped space with no matching
TLB entry, so the exception is raised by normal instruction devirtualization.
The load/store cases execute actual guest LW/SW instructions against mapped
virtual address `0x4000`. The invalid case installs a matching invalid entry.

Execution: GitHub Actions run `37798306997`, job `113383466662`, on Ubuntu 24.04 at branch head `435db22532671c844745273705bb531c46f79375`. The build and all assertions passed. The runner printed `PASS: 28 guest-triggered cases match the pinned ares exception-vector truth table; every case repeated byte-identically`. SHA-256 of the generated `results.json` was `9e9aff42c258177daa94f9de8be296c816735b67c2a4d0c04fdb89501d322de7`.

## Resulting root table for tested classes

| Condition | BEV=0 | BEV=1 |
| --- | --- | --- |
| General exception / TLB invalid / true TLB miss with initial EXL=1 | `ffffffff80000180` | `ffffffffbfc00380` |
| True TLB miss, EXL=0, 32-bit kernel context | `ffffffff80000000` | `ffffffffbfc00200` |
| True TLB miss, EXL=0, 64-bit kernel context | `ffffffff80000080` | `ffffffffbfc00280` |

For EXL=0 delay-slot faults, the vector category is unchanged while BD becomes 1
and EPC points at the branch. With initial EXL=1, the preset EPC and BD survive
nested entry while the exception code is updated.

## Independent cross-checks and disagreement

Pinned `n64-systemtest` installs distinct handlers at `0x80000000`, `0x80000080`
and `0x80000180`. Its 64-bit TLB exception tests explicitly expect
`0xffffffff80000080` for a true TLB miss and `0xffffffff80000180` for an address
error. Its ordinary TLB invalid tests expect the general `0xffffffff80000180`
vector. This independently supports the distinction exercised here; it is source
from hardware-oriented tests, not a hardware run performed by this worker.

Pinned Gopher64 agrees on BEV and the general-vs-refill distinction, but its
`src/device/exceptions.rs` only selects offset `0` for refill misses and has no
64-bit `0x80` XTLB-vector branch. Therefore Gopher64 at this pin is **not** an
independent oracle for the 64-bit XTLB vector. Plaid must not turn that source
disagreement into false consensus.

## What this proves

For the tested synthetic post-initialization scope, the pinned ares executable
entry roots are mode-sensitive and require at least the three vector offsets
`0x000`, `0x080`, and `0x180`, under both BEV bases. A ProgramMap root model that
only seeds the general vector, or that collapses 32-bit and 64-bit refill vectors,
can miss executable code.

## What this does not prove

- It does not establish reachability of any exception in an arbitrary ROM.
- It does not cover reset, NMI, cache-error vectors, interrupts, watch exceptions,
  arbitrary TLB page configurations, user/supervisor modes, or boot/PIF/CIC flow.
- It does not establish instruction-byte provenance for the handler bytes.
- It does not run the n64-systemtest cases on physical hardware in this session.
- It does not make Gopher64 authoritative where its source disagrees with the
  hardware-oriented 64-bit vector expectation.

## Integration recommendation

**ADOPT**, narrowly: when exception roots enter the executable-universe model,
represent vector selection as a mode-sensitive root rule rather than one fixed
exception address. Seed/permit `base+0x000`, `base+0x080`, and `base+0x180` as
appropriate to the proven exception class and Status state. Keep reachability and
handler-byte provenance as separate obligations.

## Primary-checkout reproduction

2026-10-08, x64 WSL Ubuntu/G++ 15.2: The 28 guest-triggered cases each repeat byte-identically and match the mode-sensitive truth table. The complete results file SHA-256 is `9e9aff42c258177daa94f9de8be296c816735b67c2a4d0c04fdb89501d322de7`. This does not supply handler bytes or arbitrary-ROM reachability.
