# Bounded boot access chronology

2026-10-08. Pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, x64 WSL
Ubuntu/G++ 15.2. Original sensors extend the measured controlled chronology to
the existing NTSC/6102/8-MiB/deterministic/reference-PIF-HLE/checksum power-entry
prefix, retaining actual ignored firmware and homebrew inputs. Generated ISC/BSD
reference shadows stay ignored and separately compiled with upstream notices.

Commands:

```powershell
python spikes/011-ares-cache-fetch/run.py
python spikes/027-ares-boot-history/run.py
python spikes/027-ares-boot-history/run.py --verify-existing
python spikes/027-ares-boot-history/test_verifier.py
```

The first sidecar attempt exceeded the legacy 180-second limit. The explicit
600-second override completes plain/enabled/repeated runs. A test expectation
requiring positive uncached RAM fetches was corrected after inspecting the prior
corpus: 2,055 uncached PIF fetches, 596,991 uncached SP fetches and 400,954 cached
RAM fetches. Completed sensor streams were then fully rechecked without CPU
reexecution; no generated observer changed during that validation correction.
The entire v5 stream and reported machine checkpoint equal the prior goldens
and a freshly reproduced default build, including Count 6,784,366 and the full
RAM/SP/I-cache hashes. Traced/repeated history and guest messages agree exactly.

| Completed record class | Count |
| --- | ---: |
| Fetch begin / end / pre-decoder prologue | 1,000,000 each |
| Successful identity-RAM scalar access | 2,050,501 |
| Successful identity-RAM burst | 44 |
| Completed instruction-cache fill | 32 |
| Selected completed guest CACHE operation | 512 |
| Total ordered records | 5,051,089 |

All 32 fills join adjacent successful RAM read bursts in their fetch contexts
and match every resident word in the paired v5 snapshot. Nineteen ordinary
uncached CPU data reads stay outside fetch contexts. Zero uncached RAM fetch
witnesses is the correct result for this prefix. The controlled direct-fetch
fixture remains positive evidence for that path. The scalar write census includes
411,646 SP-DMA dualword writes and 1,638,808 PI-DMA byte writes; counts do not prove
which source bytes supplied each transfer or when a microcode/image was installed.

Raw receipts:

- V5: 210,032,160 bytes,
  `c0dcae4870aaec1b30097d7fd95f2b6214f043e2ac1dea6366b1814655ce4ce9`.
- Ordered sidecar: 859,502,085 bytes,
  `f4ee931e8536026a5a42581092e5be40aa43cfc91b6dc330d557314834edb842`.
- Outputs: ignored `target/ares-boot-history-spike/1000000/`.

The observer performs no extra guest accesses, translations or clocks and holds
constant sidecar state. The Python verifier streams all rows, validates complete
headers/footers/unique contiguous ordinals/paired contexts and every v5 fetch,
and treats multiple eligible scalar reads as ambiguity. Its synthetic tests
exercise a data-read decoy plus eleven malformed/duplicate/truncated cases.

This validates bounded callback chronology and immediate RAM-backed fills, not
reference hardware equivalence, all mutation paths, cache/restore lifetimes,
RSP installations, copy dataflow, exhaustive reachability or full guest-suite
completion. The next separate decision is an original Rust complete-source
inspection/rechecker that records these finite witnesses without creating
ProgramMap images/generations or weakening OPEN whole-ROM gating.

## Original Rust inspection receipt

`inspect_boot_history` and `verify_boot_history_report` now reproduce every
corpus count and both raw hashes above. The report is 877 bytes with SHA-256
`8eb7007dd08de872c34969a69ca6ed77911f8f9b6745b160b4cbbdb778d478d8`.
Five Rust tests cover data-read ambiguity, complete resident-lane agreement,
malformed/duplicate/truncated/oversized records, supplied-input/report tampering
and a paired source changing between validation and replay. The corpus passes
complete report reconstruction. All 81 Rust tests, formatting and strict Clippy
pass. No ProgramMap identity or source/lifetime certificate is changed.

The public CLI uses `inspect-boot-history <rom> <firmware> <fetch.ndjson>
<history.ndjson> <report.json>` and `verify-boot-history` with the same inputs.
The corpus receipt above was generated and fully reconstructed through these
commands. `python scripts/test_history.py` separately tests all canonical ROM
orders, report/source/input tampering, truncation and input-overwrite protection.
