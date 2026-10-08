# Buffered PI byte origins

Primary receipt, 2026-10-08. Hypothesis: actual ROM half-read results must pass
through the consumed PI buffer lane and a successful RAM write before identifying
a destination byte. Read/write adjacency or equal payloads cannot establish this.

`python spikes/028-ares-pi-buffered-copy/run.py` passes on ares
`9408cb43d4948fc3ea6e152a307a34348df3fe04`, WSL Ubuntu x64, G++ 15.2, both
recompilers disabled. Original project sensors observe existing fields/results
without guest accesses or clocks. Reference sources stay ignored and separately
compiled with ISC/BSD notices. The eight fixtures call real DMA and completion
components directly; no guest MMIO setup, queue/scheduler duration or hardware
agreement is claimed.

| Case | Successful writes | Canonical origin |
| --- | ---: | --- |
| Aligned 16-byte copy | 16 | ROM 1000–100f |
| Identical reload from different offset | 16 | ROM 2000–200f |
| Changed reload | 16 | ROM 3000–300f |
| Misaligned destination 1102, length 16 | 14 | ROM 1000–100d |
| Odd length 15 | 15 | ROM 1000–100e |
| Row boundary 17fe, length 20 | 18 | ROM 1002–1013, destination 1800–1811 |
| Destination outside 8-MiB RAM | 0 | No successful destination witness |
| Unmapped/open-bus source | 8 | Unknown, despite successful RAM writes |

All ranges are hexadecimal. The 479-record ledger contains 111 write attempts,
103 successful effects and 95 known byte origins. First-block row alignment can
discard every byte of a two-byte read. All block reads precede writes; joins must
retain consumed lane identity. Byte writes complete before the separately invoked
busy/interrupt transition. Identical reloads retain distinct transfer IDs;
changed writes supersede previous backing writers.

An independently compiled original-PI baseline, disabled callbacks and repeated
enabled traces preserve reported PC, all GPRs, Count/exception, full RAM/hidden
hashes and every PI cursor/status/window checkpoint. Count and exception remain
zero because this fixture executes components, not CPU instructions. Final RAM
SHA-256 `dcb5f3d844e7053fe4e2924cf11013cc0da0fb1dee2e8ffef957f0b9cff4ee56`;
hidden `62e209f5e0b4b6889519617d34626b05b465394f13ea8256b7ed8b543ba8b487`.
Complete result SHA-256
`ec467fd50f91c42354172079e9548196f24eabb308619743ff2debbead81dca7`.

Four forged write/completion/order histories fail. Substituting an equal-byte ROM
offset removes the corresponding two-byte origin instead of borrowing it.
Opt-in enabled/disabled/enabled recipe checks and the six prior shared recipe
cases pass. Recipe tests are generation checks, not CPU evidence.

This validates finite buffered transfer provenance under identity RAM. General
translated/degraded memory, mutation completeness, resident cache provenance,
executable installations/lifetimes and whole-ROM closure remain open. Compose
actual fetch/fill observations with these writers next; current RAM bytes cannot
replace historical resident cache bytes.
