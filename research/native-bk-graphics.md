# BK startup-memory graphics divergence

Primary continuation, 2026-10-18; prepared on `analysis/bk-status-model`
after 7b638f0. Final integration validation is pending.

## Observation and falsifiable hypotheses

BK runs to the title with audio but loses the sky and parts of the Nintendo
opening. A successful timed run does not establish correct rendering.
Candidate causes were missing display-list/asset data, invalid CPU-generated
transforms, and renderer depth/framebuffer handling. Capturing a complete task
and comparing its inputs with pinned ares distinguishes those seams.

Ignored `target/bk-sky/probe.py` recompiles only the runtime and a diagnostic
CPU part, preserving generated native CPU/RSP code and a visible RT64 window.
It captures RDRAM at graphics tasks 50, 300, 500, 700, 900 and 1100. The
unmodified-path 60-second diagnostic run exits 0: VI 3572, 1269 graphics tasks,
1781 audio tasks, fault 0. Captured frames contain the sky display list and
cyan/blue vertex colors; missing asset bytes are not its first divergence.

An independent analysis-only ares adapter boots the same local ROM from PIF,
with neutral controller input plus the scheduled Start/A presses, and captures
RDRAM at task entry. Task counters/VI times differ between the two schedulers;
these are matching rendering components, not claimed cycle-identical frames.
At tasks 50 and 300 ares's projection matrix has depth terms approximately
`-0.5003204345703125`, `-0.5`, `-5.0016632080078125`. Native tasks 50 and 700
instead have `-2`, `-0.5`, `-1875`; the resulting sky vertices lie outside the
far clip plane. Horizontal/vertical projection scales agree.

The compiled setter receives the intended clip distances. The subsequent
guest projection routine reads an uncached word at physical 0x1d8 and takes a
fallback branch when it differs from the IPL3-written instruction it expects.
Ares retains the boot-written RAM prefix; native startup had zeroed it.
The fallback uses distances 1500 and 2500 instead of 5 and 15000. No camera,
check instruction, expected game value or per-ROM exception is changed.

A separate current-tree `--rsp-gfx` probe faults at IMEM 0xffc on the first
graphics task. Therefore this continuation does not rely on the older
handoff's claim that both renderer paths independently rule out microcode.
That native-RSP run needs a separate successful verification.

## Bounded correction and verification

Extend the existing analysis-time startup capture at the first game-entry
instruction to include physical RDRAM `[0, 0x400)`, alongside SP DMEM/IMEM.
The default native builder emits this bounded payload and an ignored receipt
with input provenance and payload hashes. It rejects a missing entry, an
overlapping base entry, invalid lengths and non-byte values. The runtime
copies the prefix before installing its executable image and running guest
code. Generated game bytes remain ignored build outputs.

This is a declared startup-data assumption, not a proof of all post-IPL
RDRAM, cache/register/device state or executable-root completeness. Higher
RDRAM remains outside this correction. Native mode still contains no guest
instruction interpreter or JIT. Existing scoped closure is not promoted to
whole-ROM closure and no assumption is retired.

The retained synthetic ares test seeds distinct startup bytes, overwrites the
prefix later from guest code, and checks that the capture retains entry-time
bytes. Native synthetic tests sample both KSEG aliases, verify a later write
and neighboring guards, and check that the executable image loads separately.
Removing startup-prefix initialization kills the native test; restoring it
passes. Header tests reject missing, short, out-of-range and boolean payloads,
wrong entries, and an entry overlapping the prefix.

The normal ROM-only pipeline now passes its visible 60-second audio-required
run: scoped CLOSED/0, 80,850 blocks, 41 ROM-derived RSP texts, VI 3578,
1270 graphics tasks, 1785 audio tasks, 3750 PI transfers, fault 0 and PCM peak
32767. End-to-end wall time was 376.854 seconds, including discovery and
cached build steps; this is not an isolated performance comparison. A separate
visible verification confirms the blue Nintendo-opening background, sun and
lens flare, and the previously missing forest/waterfall backdrop behind Banjo.
Screenshots are ignored `target/bk-sky/fixed-opening.png` and `fixed-intro.png`.
This is finite visual verification, not a pixel-perfect or full-playthrough
claim. Audio clipping/mixing correctness is not established by a nonzero peak.
The separate 180-second visible inspection also reaches its time limit with
fault 0: VI 10769, 4562 graphics tasks, 5380 audio tasks and 16738 PI transfers.

## Independent control

The SM64 ROM-only OPEN/23 result predates the VI change. A bounded independent
comparison of 515ccae and 7b638f0 reproduces identical blocker records: 20
unsupported scope effects, two unresolved computed jumps and one unsupported
instruction, in exception/TLB paths. The current map adds 141 blocks and 222
edges without changing those blocker identities. This is not a new VI
regression; SM64's documented configured build is a different input contract.
Commands, hashes and timings are in ignored `target/sm64-regression/Handoff.md`.

## References and local evidence

Ares is exactly `9408cb43d4948fc3ea6e152a307a34348df3fe04`; all reference
execution remains analysis-only. The adapter and synthetic fixtures are
project-owned; no game instructions/assets or upstream implementation were
copied into tracked code. `target/bk-sky/` holds the local captures, diagnostic
scripts, reference build manifest, mutation probe and native pipeline logs.
