# Actual cartridge read source

Hypothesis: delegating the actual selected ROM device's halfword reads can supply
finite fetch-source witnesses without extra guest reads or translations. Clear
the observer before each interpreter instruction call; sample its two returned
halves at the existing pre-decoder prologue. Require an uncached effective address,
matching consecutive ROM offsets and the actual fetched word. A PI busy latch or
unmapped tail must remain unknown even when its word matches canonical ROM.

Use the pinned ISC/BSD ares core separately, preserve upstream notices and disable
CPU/RSP recompilation. The project-owned delegating PI device forwards every
original operation once; compare original-device, plain observer and repeated
traced CPU/PI checkpoints. Synthetic state excludes boot and whole-ROM proof.

Run `python spikes/006-ares-rom-source/run.py` with the pinned ares checkout and
Linux G++ C++20 (Windows uses WSL Ubuntu). Outputs and preserved upstream LICENSE
remain under ignored `target/ares-rom-source-spike/`.

## Verdict: VALIDATED

### Evidence

Six original fetches yield three ROM witnesses and three unknown sources. A
direct ROM read, a TLB-mapped ROM read and reverse-endian lane selection each
produce two actual consecutive halfword reads and the expected source offset.
The identical-word PI latch produces zero reads and stays unknown. The final
four file bytes are unmapped, yield a different open-bus word and stay unknown.
Prior data reads are cleared before the next fetch and cannot supply its source.

Original-device/plain-wrapper/traced/repeated checkpoints agree in every GPR,
HI/LO/PC/Count, exception/EPC and PI latch/busy/address state. Count is 2,196,
s0=2, PC=0x4004, exception=0, PI busy=0 and mapped ROM size=8,192. Repeated
source records match exactly. No ROM assets or binaries enter git.

### Constraints and surprises

The fetch window depends on the pinned interpreter's single-instruction call
and pre-decoder prologue. Events after the prologue belong to opcode execution
or synchronization; clear the ledger before the next call. This is not a runtime
JIT observer. CPU/RSP recompilation stays disabled. The wrapper forwards every
original device operation once and supplies no extra reads/translations.

Only returned ROM halfwords qualify. A physical cartridge range or equal word
does not qualify. Source at one fetch proves neither retirement, immutability,
complete execution coverage nor an executable image's lifetime. Synthetic state
excludes authentic boot and hardware-wide acceptance.

### Recommendation

Extend the observer to the bounded homebrew capture and verify canonical source
bytes plus complete raw provenance before promoting a production data adapter.
Keep unknowns explicit and preserve the independent solver identity blocker.
Do not construct generations, overlays or native readiness from source offsets.
