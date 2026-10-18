# BK Status ABI and first native execution

Prepared against main `a5e3eb9abf393748259f4324370e5459dfc28d84`.
This note records the current candidate and verification boundary. Native
gameplay/audio acceptance is still pending; scoped closure is not whole-ROM
completion, and no assumption is retired.

## Status boundary

Identification now recognizes three specific n64sym SDK profiles, by complete
relocation-normalized signature identity, never by game identity or address:

| SDK function | Size | normalized CRC32 |
| --- | --- | --- |
| osCreateThread | 0x144 | 525164f9 |
| osSetIntMask | 0xa0 | a5f9c656 |
| osInitialize | 0x28c | a26e9830 |

The verified scalar __OSGlobalIntMask binding is unique within each supplied
SDK namespace. Optional `status_global` fields carry that ABI binding through
identification, declaration parsing, the typed RuntimeFunction and lowering.
Addresses must be aligned direct-mapped guest RAM. Each selected thread/mask
copy and each present initializer must be supported before __osGetSR is
admitted. Unknown variants retain the guest Status-read obligation. Removing a
required binding or the FR=0 declaration makes the solver OPEN. The gate
applies whenever any Status binding is present, not only when __osGetSR is
declared, because the bindings alone change the lowered thread and COP1 code. A reference map
alone cannot supply this profile evidence. The runtime ABI remains an explicit
assumption, including identification by CRC signatures.

Native wrappers pass each copy's global address as a guest address. The
initializer selects the SDK namespace whose exception vectors are installed;
dispatch therefore uses the current kernel binding even for an older thread.
Thread creation initializes the verified saved SR ff03 and six MI preferences;
dispatch applies global inhibition and ERET's EXL clear. Complete live Status
is known only in a supported thread context. No boot Status word is guessed.
__osGetSR returns the sign-extended represented word; an unknown boot context,
incompatible saved mode or PRENMI delivery faults explicitly. This is a cold
start SDK model, not arbitrary CP0 instruction or reset-handler support.

Disable/restore changes IE without replacing the other fields. SetIntMask
preserves IE, replaces CPU IM through the selected global, and updates all six
effective MI enables. Its old-mask result reconstructs inhibited logical bits,
with the SDK's zero-effective-MI special case. Save reconstructs MI preferences
using the previous saved preference under global inhibition; it does not turn
every inhibited bit on. Saved and live Status are separate. Explicit SDK
blocking/yield saves an internally disabled context and restores the caller's
previous IE by OR on resume; interrupt preemption preserves its live IE.

Native COP1 operations acquire CU1 under the declared lazy-FPU SDK ABI, with a
guarded guest `fp` flag write and an FR check. osInitialize's CU1/FPCSR effects
are represented separately; enabling CU1 there does not invent a lazy-trap
flag update. A small inline fast path calls an exported acquisition helper only
when needed, including across separately compiled guest translation units.

Pending SP/SI/AI/VI/PI/DP delivery requires IE, EXL/ERL clear, CPU RCP mask and
the corresponding MI enable. Timers require the CPU Count mask. Deferred PI
completion messages share the eligibility gate. The all-blocked HLE idle pump
has an explicit accepting policy and does not overwrite blocked contexts.
This does not establish cycle-exact interrupt timing, device coalescing or a
full hardware exception handler.

## Retained contracts

`runtime/test_status.py` checks 256 CPU/MI/global combinations against
independently assembled COP0 and MI operations on pinned ares. A separate
30-word context sequence compares save, dispatch, ERET, global namespace
changes, zero-effective-MI preferences, CU1 and initializer effects. Native C
checks pending events, Count masking, deferred PI messages, idle behavior,
unknown Status refusal and incompatible FR. A real two-thread native fixture
checks disabled creation, independent child IE, blocked saved state,
resume/restore and COP1 acquisition in both single and multipart builds.
The public CLI contract retains separate typed bindings and rejects invalid
addresses. The solver rejects a removed required binding.

The oracle previously checked exit PC and exception code alone. Interrupt
exceptions have code zero, so an active EXL state could reach a synthetic exit
without being rejected. The native-slice driver now rejects EXL and ERL too;
retained negative sequences check both. All reference drivers are checked
against their exact source hashes and the locked ares revision.

## Native bootstrap findings

The normal ROM-only infer/identify/discover/harvest/solve pipeline reached
scoped CLOSED with zero blockers. No additional executable edge was hidden.
The first build then exposed missing osPiGetStatus and motor wrapper exports,
and a missing Status helper definition at the multipart link seam. The getter
uses the existing modeled PI register; motor wrappers share the existing
no-accessory policy. The multipart native fixture retains their linkage and
the floating-point helper seam.

The first executable stopped at an unsupported raw PI DMA register write in a
signature-matched SDK osPiRawStartDma body. Its native boundary supports aligned
eight-byte ROM reads, honors protected RAM and cache visibility, exposes PI
interrupt status and acknowledgment, and refuses unsupported directions,
alignment and bounds. A retained independent ares DMA test compares complete
RAM, guard bytes, preserved ABI registers/HI/LO, return, PC and interrupt
status/acknowledgment. There is no runtime guest instruction execution.

The next stop was __osPfsGetStatus's raw SI presence query. The native platform
has one gamepad and no Controller/Rumble Pak. Its private SDK query returns
PFS_ERR_NOPACK, including disconnected ports, consistently with the matched
SDK path. Gamepad query status now reports the absent-Pak bit as pinned ares
does. A native fixture checks type/status/error bytes, disconnected ports,
bounded output writes and PFS/motor outcomes. __osEepStatus supplies the
existing 4 Kbit EEPROM's idle identity/status, consistently with osEepromProbe.
The cartridge model's immediate EEPROM policy is unchanged.

BK then completed 18 PI transfers and reached audio bank relocation. RAM held
the correct B1 bank bytes, but the native CPU read a stale allocator header.
The pinned ares checkpoint at 803344b8 has a relocated bank pointer 80072a98
and a valid following object, while native execution retained the old cached
8023d660/80 values. The checkpoint took 67,151,947 analysis instructions / VI
139. These finite observations diagnose the transition; they prove no
whole-ROM or exhaustive execution coverage.

A trial retaining the SDK PI manager/request code as native guest code stayed
scoped CLOSED but did not remove the stale bank header. It was not adopted.
Source inspection found the actual defect: the matched SDK's small writeback
path uses CACHE Hit Writeback D (25), while requests of at least 8192 bytes and
WritebackDCacheAll use Index Writeback Invalidate D (1). The runtime had kept
the valid tags in the latter paths. The fix invalidates after the index
writebacks, preserving hit-writeback behavior for a small range. A retained
native/ares differential first failed with four old cached values instead of
the three new values following whole-cache operations, then passed after the
fix. RAM, PC and normal fault-free exit agree. No DMA coherence shortcut was
introduced.

With that correction BK progressed to 19 PI transfers / VI 8 and an EEPROM
status query through raw SI. The native SI boundary now runs the SDK's Joybus
packets for the declared one-gamepad / 4 Kbit EEPROM platform: PIF RAM DMA in
both directions, gamepad status and reads, absent channels, and EEPROM
status/read/write with a 6 ms write-busy window. Every other command or length
is refused. The HLE __osEepStatus reports the same busy window. A synthetic
contract (runtime/test_joybus.py) covers the packet subset, refusals, SI DMA
through PIF RAM and the shared busy state; compiled against the previous
always-idle status query it fails.

The visible ROM-only run (`native.py --rt64 --seconds 60 --require-audio`, the
same three presses) still reaches scoped CLOSED with zero blockers, builds, and
stops at VI 8 / 19 PI transfers with fault 4 at 8026e614: a cached LWL of the
SDK's PIF reply buffer (80284be4) after the read DMA, whose result depends on
D-cache state. A traced build showed all four buffer lines dirty, holding the
SDK's refill stores, when the invalidate after the read start discarded them.
libultra's raw SI DMA writes the read-address register and then invalidates the
buffer. Pinned ares (si/io.cpp) queues both SI DMA directions and moves the
bytes with the interrupt later, so the discarded stores never reach RAM before
the transfer. The native transfer completed at the register write, before the
invalidate, so the runtime counted the line as lost.

SI DMA now follows the ares order: the address write leaves the DMA busy, and
the transfer and interrupt complete together at SI delivery or the guest's next
SI/PIF access. runtime/test_si_order.py runs that sequence (dirty refill, read
start, hit invalidate, wait, cached read) against pinned ares on a port with no
device in either model; RAM and PC match, and the previous runtime faults 4 on
it. A trial that kept instant completion and exempted fully DMA-overwritten
dirty lines also passed BK's stop but was not adopted, because it keeps the
reversed order.

The visible run then stays scoped CLOSED and stops at VI 10 / 19 PI transfers
on BK's first audio task: "unknown or ambiguous ROM-derived RSP microcode"
(fault 0). No graphics task or gameplay has been observed.

That task had no boot microcode in IMEM because BK never loaded rspboot. Before
it DMAs ROM 0xb70 to 802820c0 (code near 802549c8) BK checks the SP memory
IPL3 leaves behind: DMEM word 0 = ffffffff and IMEM word 0 = 000017d7. Native
boot copied only ROM 0x40-0xfff into DMEM, so the check failed. At the game
entry pinned ares has DMEM 0x00-0x3f all ff, DMEM 0x40-0xfff 3,957 bytes away
from the ROM copy and IMEM fully written. ADR-0195: native.py now captures
DMEM/IMEM from pinned ares at the first entry fetch (the ROM's own IPL3, CIC
from its CRC32) and the runtime starts from those 8 KiB, a declared assumption.
The BK capture equals an independent ares handoff dump byte for byte.

The load then refused as "PI DMA outside the ROM": BK passes devAddr
b0000b70, and libultra's raw PI DMA addresses K1_TO_PHYS(osRomBase | devAddr),
which is 10000b70 as in ares; the HLE took devAddr as a ROM offset.
osPiRawStartDma and osPiStartDma now OR the guest's osRomBase. test_raw_pi.py
uses a base-qualified devAddr against pinned ares and the old runtime refuses it.
Native 802820c0 then holds ROM 0xb70-0xc6f, the bytes ares DMAs there.

The visible run now reaches the 60 s limit with no fault: VI 3545, 1,768
audio tasks, 20 PI transfers. It issues no graphics task and its PCM is
silent, so the window stays black and --require-audio rejects the build.
The stall was the main thread (id 6, entry 8023dbfc) waiting forever on
__osEepromTimerQ (802847b8) after BK's first EEPROM write: the runtime's
osContInit never created that queue, so the 12 ms delay's expiry was dropped.
Pinned ares with a 512-byte EEPROM attached creates it in osContInit at VI
137, completes eight delays and issues the first graphics task at VI 175.
ADR-0196 binds the queue (a split LUI/ADDIU pair) and creates it natively.

The visible run then passes the EEPROM writes (33 PI transfers) and stops at
VI 17 with fault 3: 8034b620 calls 8034c360 through t9 with a0 800b0c88. ares
makes the same call with the same a0 at VI 154, so the paths agree; 8034c360
is code inside the harvested 80277020 image that discovery never reached, a
call target outside the address-taken scope, probably via a pointer in data
BK loads at run time. That is the next barrier; graphics and PCM are still
unmeasured because the run stops before them.

ADR-0197 closes that gap: the pointer to 8034c360 is a word of the loaded
80277020 image, not of the ROM bytes, and address-taken discovery now scans
image words; jump tables missing their words are harvested at their site's
first fetch. BK closes (41 ROM-derived RSP texts) and the visible run is
accepted with audio, but issues no graphics task. ADR-0198: BK reads
__osViNext->framep through its own code, which the HLE osViSwapBuffer never
wrote, and its scheduler freezes the RDP between frames, so the DP interrupt
must wait for the thaw, as in pinned ares. The visible 60 s run now shows the
N64 and Rare logos, the intro and the title screen: 1,260 graphics tasks,
1,780 audio tasks, 3,702 PI transfers, no fault. The outdoor sky is black in
both the RT64 and --rsp-gfx paths. BK's non-audio ROM loads match ares in
order and size, and the headless build's framebuffers stay empty (the CPU
draws no sky), so the missing sky is still open.

## Sources, evidence and scope

References are exactly refs.lock.toml: ares
9408cb43d4948fc3ea6e152a307a34348df3fe04 and n64sym
ccf4600f3389f1a84bde23339225cf372fdf7712. Relevant primary behavior is in ares
cpu/interpreter-scc.cpp, cpu/dcache.cpp, pi/io.cpp,
controller/gamepad/gamepad.cpp and cartridge/joybus.cpp. Local signature-matched
SDK observations establish the supported ABI profiles. No upstream
implementation, SDK/game instructions, ROM assets or captured RAM were copied
into production code or git; reference instruction fixtures are project-owned.

Ignored `target/sdk-bindings/` retains claims, focused evidence, the oracle
checkpoint, temporary alternative-PI experiments and native attempt logs.
`target/native/bk-native-status/` contains ROM-derived generated artifacts and
the visible runtime outputs. These are local evidence, never repository inputs
or substitutes for the native content guards. The final integration requires
the full local gate on the exact candidate and expected-head CAS.
