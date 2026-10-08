# Bounded homebrew cartridge source witnesses

Hypothesis: the validated delegating-ROM-device observer can capture actual source
offsets on the untouched homebrew while preserving the whole v1 physical stream,
full CPU/Count/RAM/SP checkpoints and guest messages. Clear returned-halfword
metadata before every interpreter call and consume it only at the pre-decoder
prologue. No extra guest reads or translations; CPU/RSP recompilers remain off.

Research v2 records an explicit fetch-window source policy and either unknown
source or cartridge_rom with the offset supplied by actual consecutive reads.
Check every source word against canonical ROM bytes and actual mapped capacity.
Preserve unknown image generations, retirement, copies and executable lifetimes.

Run `python spikes/007-ares-rom-fetch/run.py` after building the pinned homebrew.
Windows uses WSL Ubuntu/G++ C++20. Raw captures/generated references and upstream
LICENSE remain under ignored `target/ares-rom-fetch-spike/`.

## Verdict: VALIDATED

### Evidence

Of 4,999,998 fetches, 1,852 actual ROM-source reads cover 65 canonical offsets.
Their words match canonical bytes and mapped capacity; the other 4,998,146
fetches retain unknown source. The complete physical/PC/word/slot projection has
the exact v1 hash `c14917d5dd2037cb93c02039bff2f488cf3d60aa841152c43f31c5e3a4ba22d1`.
Plain/traced/repeated CPU/Count/RAM/SP checkpoints and guest messages agree with
the previous capture. Repeated v2 files are byte-identical: 768,248,958 bytes,
SHA-256 `40d8d029cd66fb5ecfcdc3d77bdbc570dd13ce62684d47e7704cbe375008d204`.
The existing v0/v1 observers and the six source-boundary fixtures also pass after
the shared driver extension.

### Constraints and surprises

The observer delegates the actual device operations once and samples returned
halves before the decoder. No additional guest memory access or translation is
introduced. Reads after the prologue belong to opcode/device execution and cannot
be reused by the next fetch. CPU/RSP recompilation remains disabled. Synthetic
SP entry, missing PIF/IPL2 provenance, StartupTest's Config mismatch and the budget
stop retain their earlier limits. Source witnesses do not establish retirement,
image generation, immutability, complete coverage or executable lifetime.

Concurrent regression runs initially rewrote another probe's message file while
it was being compared. Fixed canonical checkpoint/message hashes now provide
stable comparisons without cross-run file dependencies.

### Recommendation

Promote conservative project-owned source data through a separate decision,
requiring explicit policy, mapped capacity, physical access, canonical bytes and
full raw-source rechecking. Preserve unknowns and legacy serialization. Keep the
solver's independent identity gate; source offsets cannot create image lifetimes.
