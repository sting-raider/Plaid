# Bounded homebrew fetch observer

Hypothesis: the pinned ares interpreter's existing debugger callback can capture
exact fetched CPU words and delay-slot context from the untouched, reproducibly
built n64-systemtest ROM, including cartridge-resident code, without changing
instruction semantics or inferring RAM copies by byte similarity.

The probe begins at the cartridge's open-source IPL3 entry in SP memory, with
ROM bytes copied into SP and declared initial registers. Proprietary PIF ROM and
IPL2 execution are excluded. Boot provenance and whole-ROM closure stay open.
The reference hardware handles subsequent PI/RAM/CPU/RSP activity. Rendering,
full suite completion and universal CPU correctness are outside this question.

Compare traced/untraced state after the same instruction-call budget; repeat the
raw fetch stream exactly. Verify cartridge fetches against canonical ROM bytes.
Use a separate research JSON format, not fabricated dynarec compilation events.

Reproduce after the source build documented in spike 002:

```text
python spikes/004-ares-fetch/run.py
```

Linux needs GCC/G++ C++20 and the two pinned source checkouts; Windows uses WSL
Ubuntu. The default fixed budget is 5,000,000 CPU instruction calls. On Linux,
`PLAID_FETCH_BUDGET` may select 1..10,000,000 for investigation. Each traced run
has a roughly 466-MB raw stream at the default; two streams remain under ignored
`target/ares-fetch-spike/`. Verification streams records and compares files in
chunks, without loading the full event list into memory.

## Verdict: VALIDATED

### Evidence

- The untouched 2,742,284-byte guest ROM retains SHA-256
  `629f908c200bbf21013dcd1d331d4ddedd08a6c9d7ae1f528421564238056e8a`.
- At 5,000,000 instruction calls, 4,999,998 fetch events cover 52,424 distinct
  RAM, 548 SP and 65 cartridge addresses. Each direct cartridge fetch word equals
  the canonical ROM word at the architectural physical offset.
- Plain/traced/repeat checkpoints agree on all GPRs, HI/LO, PC, Count, exception/
  EPC, RAM and SP-memory SHA-256, PIF state and RDRAM configuration. Guest message
  bytes and repeated complete fetch streams agree exactly. The 465,553,451-byte
  research stream's SHA-256 is
  `2657fb26ab09059050e6d2a23e6c7e984f3ece26544db994c7fcf3a9a5abb78c`.
- The 100,000-call trial remains in IPL3 (434 SP addresses); 1,000,000 calls
  reach RAM (185 RAM/533 SP addresses); the larger budget reaches guest tests,
  exception paths, cartridge reads/writes and DMA cases. These intermediate
  trials explain the budget choice, not a coverage or performance claim.

### Constraints and surprises

- The core debugger passes the exact fetched word into its disassembler before
  opcode execution. The field is private, so a generated header adds one const
  accessor; no fields, object layout or instruction semantics change. Disable
  tracer mask/history suppression and CPU/RSP recompilation. No extra guest
  memory read or TLB translation is performed by the observer.
- A fetch may precede a trapping instruction; it is not proof of retirement.
  Interrupts/fetch errors can make instruction calls differ from fetch count.
  The full 64-bit guest PC and current delay-slot flag are retained.
- This synthetic SP entry copies the guest's open IPL3 bytes, supplies r22=0x3f
  and otherwise uses reference power state. Proprietary PIF/IPL2 execution is
  absent; PIF remains WaitLockout. StartupTest reports one initial COP0 Config
  mismatch (`7006e460` vs `7006e463`). Preserve that failure; do not patch guest
  expectations or claim authentic boot/full-suite correctness.
- The footer says instruction-call budget, never guest completion. This is a
  separate research format, not dynarec trace v0. No compilation, installed
  entry, DMA provenance, overlay generation, immutable RAM or closed targets
  are inferred from fetched words or byte similarity.
- Reference core, notices and outputs stay separate and ignored. The generated
  non-Vulkan guard and harness-owned hidden RAM follow spike 003's constraints.

### Recommendation

Add a separately decided production fetch-observation schema/import path with
64-bit PCs, raw byte/slot facts and provenance. Preserve changing words at one
PC and unknown RAM source/lifetime; establish typed cartridge backing only with
explicit mapping and canonical-byte verification. Keep whole-ROM closure OPEN
while boot, exceptions, executable copies/writes, overlays and RSP remain open.
