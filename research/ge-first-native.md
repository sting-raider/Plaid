# First GoldenEye native emission (ADRs 0289–0292)

## Claim and limits

The verified 227-engine-page source frontier can now produce and link a
residual-dispatch executable. The manifest remains `native_complete: false` and
lists five transfer sites: 80801ba8, 808103c0, 80810a7c, 80961000, 80acf00c.
It contains native compiled instruction bodies and faults on an unlisted target;
there is no runtime guest decoder, interpreter or JIT fallback.

The first silent, visible run stops with VI=0, fault=3, PC=800004b4, before
graphics/audio tasks or VI register initialization. All fourteen VI registers
and the framebuffer origin are zero. The ignored RDRAM readback PNG represents
that uninitialized state, not a logo. There is no logo/title/gameplay claim.
The next obligation is the mapped source binding at the boot register tail.

## Bounded TLBWR (ADR-0289)

The unchanged ADR-0288 map has 49,241 blocks and one static blocker, TLBWR at
analysis 80801b94 / virtual 70001b94. A native TLBWR now accepts only known
Wired=31, the singleton Random replacement domain. It shares TLBWI's staging,
global mapping, page mask, generation and source-lifetime checks, uses entry31,
and preserves Index even when Index is unknown. Unsupported state faults12
before mutation. This removes the static blocker (1 -> 0); the five residual
sites remain. It does not establish that GoldenEye's Wired=2 refill can run.

NEC U10504EJ7V0UM00 sections5.4.2/5.4.4 describe a decrementing Random register:
https://hack64.net/docs/VR43XX.pdf. Pinned ares9408cb43 interpreter-scc.cpp samples
the replacement index instead. Only the singleton domain is independent of
that timing distinction. Context, general Random timing and exception delivery
remain unsupported; no index is guessed. References were read, not copied.

The full-state pinned-ares fixture covers eight COP0/TLB forms, both ordinary
mapping and actual memory effects through the singleton mapping. It compares
all GPR/FPR, PC, HI/LO, FCSR, output RAM, staging and all32 TLB entries. Native
checks cover every other six-bit Wired value, unknown Wired/staging/Status,
invalid committed state, generation changes and Index independence. Removing
the domain guard makes the refusal test fail. Earlier unsupported-instruction
unit examples now use SYSCALL, whose exception delivery remains unsupported.

## Fixed-load tag capacity (ADR-0290)

Emission then exposed the arbitrary 64 fixed-load limit. GoldenEye's input has
134 fixed declarations and229 relocatable sources; only fixed loads consume
these tags. Expand load_ok to251 entries, the exact available tag domain2..252;
253..255 retain their proof/fixed-revocation/overlay meanings. A252nd fixed load
still rejects before tag collision. Source verification and revocation remain
unchanged. This is a general capacity correction, not a ROM exception.

Synthetic65- and251-load programs execute the final load and match complete
pinned-ares state. Tests verify its highest tag, revoke its content witness,
corrupt the bytes and require atomic source refusal. The252-load negative
verifies the boundary. All native control CPU/runtime objects must be rebuilt
because the state layout changed; retained CPU binaries cannot validate this.

## Mapped register tails (ADR-0291)

Emission next rejected a proven fixed-to-mapped JR and then a local virtual
label in a mapped fragment. Proven non-linking cross-source transfers now bind
native source entries through the existing virtual dispatcher, preserving the
entering RA. The body partitioner resolves same-identity virtual targets to
their supplied source labels; general return certificates remain unchanged.
Legacy tail-cell promotion and local table labels retain their behavior.

Three synthetic fixed/mapped/local virtual-target programs match full ares
state. Corrupt destination bytes refuse before entry. Retained old compilers
fail both fixed-source emission and local-label emission; green receipts use
the same synthetic inputs. This changes emission, not static target closure.

## Advertised native ABI symbols (ADR-0292)

The final link exposed osDpSetNextBuffer as advertised but unprovided. A check
against actual compiled runtime symbols found four such defaults:
osDpSetNextBuffer, osPiReadIo, osSetCount and osSetTLBASID. Remove those defaults
so their guest bodies stay on the native instruction path. All101 remaining
default names now link against the actual runtime in a deterministic test.
The retained105-name registry fails that same linker test. No no-op host
implementation is added. Existing signature attribution/notices are retained.

The production rediscovery with the corrected default registry has49,250 blocks
(nine newly retained guest blocks), zero ordinary blockers and five residual
sites. Generated C and native objects are ignored local artifacts.

## Receipts and integration

Focused producing receipts are target/tlbwr-strengthened.log,
target/load-capacity-focused.log, target/mapped-tail-green.log and
target/default-abi-red-green.log in target/delay-worktree. The first build log
is target/ge-build-only.log. Stop JSON, full RDRAM and PNG are under
target/receipts/ge-first-native. Runtime reporting adds state fields only; the
CPU/RSP bodies are the generated production objects, using GCC15.2.

Exact-tree fmt/clippy/workspace/CLI/runtime/progress gates, rebuilt native
controls and release discover/solve measurements are retained in that receipt
directory before the canonical write. Timings from different profiles or
concurrent workloads do not establish an optimization. RT64 bridge/patches and
README are unchanged. MM's clean-main standalone30s run gave1797VIs/fault0;
the earlier1612VI observation was not reproduced.
