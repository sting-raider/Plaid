# Word-aligned RSP overlay descriptors and scalar prefixes

The retained RE2 (USA Rev 1) diagnostic stopped at VI 387 on graphics task
10. The RSP copied 384 bytes from physical `0x1c758` into IMEM starting at
zero, then dispatched to `0x090`. All transferred bytes match the image
composed from pinned ares replay and the native IMEM capture. The scalar
prefix jumps from `0x09c` to an SP-register read at `0x1a4`, beyond the
overwritten range.

The resident microcode adds the task's ucode base to four descriptor source
words in DMEM. Its loader reads the source with LW and the length and
destination with LHU. The CPU-computed root of the data window is
`0x800bb680`. The descriptors start at root + `0x304` and have an eight-byte
stride. The original scan skipped those addresses. With the alignment
change alone, the descriptor identifies the right span and the content
filter still rejects it for having only scalar instructions.

The scan requires adjacent complete entries within the rooted window at
the new alignment. The prefix filter requires a span of supported words
crossing IMEM `0x80`, an in-span jump and delay slot, and a supported RSP
operation at its destination in the untouched resident suffix. Prefixes
admitted this way enter the live dispatch registry only. Startup matching
continues to use the resident task and boot candidates. The per-fetch live
word and delay-slot checks still govern execution.

| Diagnostic | RSP texts | Last VI | Graphics tasks | Stop |
|---|---:|---:|---:|---|
| Previous registry | 300 | 387 | 10 | Unlowered IMEM `0x090` |
| Word-aligned descriptors | 387 | | | Exact prefix still absent |
| Both changes | 395 | 899 | 1,894 | 15-second time limit, fault 0 |

Three alternating runs of the registry command took a median 2.021 s on
the previous build and 2.087 s with both changes. All 300 previous C
sources match byte for byte. The 208 previous startup equivalence groups
remain represented, with 17 representatives replaced by equivalent
longer texts. The newly recognized word-aligned descriptors add 51
startup groups through the existing content filters.

The emitted prefix is 384 bytes, has zero fault stubs and matches the live
DMA span by SHA-256
`975565d63b0e4e3212e41ea37b903e2a603877de7e90d157e7f57f2ad4847c57`.
The run used visible RT64 with lowered graphics microcode. The synthetic
tests cover isolated or truncated descriptors, data holes, out-of-IMEM
spans, overwritten targets and missing or invalid delay slots.

The local gate passed formatting, Clippy, workspace tests, CLI tests,
progress validation, all 82 runtime checks and seven visible 30-second ROM
controls. Each control reached VI 1798 with fault 0.

The RE2 run uses the retained replay-authenticated replacement catalog
and experimental SDK Status declarations. Automatic admission and binding
are still open. The build reports `native_complete: false`.
