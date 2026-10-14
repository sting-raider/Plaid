# Primary integration: PI RAM parents through SP DMA to CPU SP consumption

Base:54846e6b0da984391140787c572de464ec48f3b6. Claim:6167806761.
The canonical reproduction retained a uniquely compatible SP DMA writer but
reported zero PI-attributed CPU SP fetches. The prepared composition uses the
existing validated `dma_store_receipts` rather than another read-selection rule.

The PI state freezes each needed RAM byte parent at the selected source read.
SP installation retains its independent occurrence, byte lane and exact read
ordinal. Shared `sp_history::WriterLineage` supplies writer selection, equal-write
replacement and permanent contradiction cuts. Actual same-fetch CPU backing
reads select only parents whose installation matches the current SP writer.
Partial or absent parents stay partial/unknown; later RAM writes cannot change a
previously captured read. Cached SP execution is not newly attributed.

The independent Python model agrees on identity/physical PI graphs and fourteen
controls:
equal RAM cuts before/after the read and after installation, equal SP overwrite,
duplicate/missing/wrong-PC reads, wrong bank/offset/payload, store before read,
duplicate CPU read, non-CPU read and permanent contradiction. Three forged
installation/read identity edits reject. Existing27 PI Rust regressions, two
physical-storage graphs, six storage/cache graphs and legacy SP writer controls
remain applicable. All broad proof flags remain false.

The actual pinned ISC ares9408cb43d4948fc3ea6e152a307a34348df3fe04 fixture executes
PI I/O requests, actual Dual RAM reads, SP DMA installation and decoded CPU
execution from IMEM. Identity and translated physical PI destinations both feed
the chain. Its116 events and twelve checkpoints agree across baseline, disabled,
enabled and repeat, with full ordinary/hidden RAM and SP backing hashes plus
selected GPR/PC/CP0/PI state. Host mapping/descriptor setup and explicit DMA
component stepping remain opaque controls. No RSP execution, guest-MMIO ancestry,
scheduler or hardware timing claim follows.

Actual source SHA-256:
fd256b5e97e861529925f30909b52bc0738dd31b73606afdfe47b03f281ee804.
Baseline/disabled SHA-256:
d00bea5b7bce1dab5600d55c4a4dde1e1b128e60c4061b7cfdd28c71b84ebe9e.
Reference receipt SHA-256:
1374cdb69ba206f2c3436ad1fbaec9ba4252354155f8275dc8169c79bbe7d64c.
Baseline build SHA-256:
c1c941b484b992c96e70fab85a008b3ddba2aa5e4ba9e55a01369797cdcac66a.
Sensor build SHA-256:
dc4d97a4be4d9a59d513cfac956ce3077f04e42f59b3bccbf9b92b079c84aa7d.
Executable hashes are also retained in the receipt under ignored
target/pi-sp-consumption-primary. Upstream implementation/notices stay in ignored
reference builds; no upstream code is linked into production/native gameplay.

Consumed SP parents add optional `sp_writer` and select SP/PI report-v1. Unused
paths retain the old report shape and digest; no new standalone consumer or proof
waiver is introduced. The retained full commercial-prefix source is reused for
canonical/independent replay, without ROM recapture or an equivalent reference
rebuild. Its complete source/fetch receipts remain:
41f88d484ba0d274ac3613c748fdce6b5b8276370cb579da8facccedc423551d and
d0e2cf0ade942c4c4cf266bf9f8d6f4309ce0186e425fbadbcb1724b6f7889f1.

Fresh complete canonical and independent replays agree on all20M fetches and
69,513,732 source records:2,472,203 full chains, zero partial/contradicted backing
bytes and172 samples. Both complete reports stay byte-for-byte identical to their
earlier authenticated versions; the added SP path supplies no new parent in this
commercial prefix. Ordered chains retain
c028756ec8f5562b2870299357ff91c2fb02b46f81016ab679709ab3805a3a04.
Canonical report SHA-256:
a8a235230e4bf45045163d39a58ed31eb56dd6acf967525cc0d8a290ec10d53d.
Independent report SHA-256:
aa1df966f4563dc50ab3653a3c96ceadd2f3cd8e46d4785ff88ec6bd3e4f486e.
Final paired replay receipt SHA-256:
c557701cc0b1b89fe6f3dddd60528255ab998ad048e87f34fddc3942b514d147.
The independent computation was retained before the canonical run finished;
exact-integer comparison and both full source hashes were checked afterward.

The complete locked workspace gate, strict all-target Clippy, fmt and CLI pass,
including the outer fixed-point deletion regression. Focused and actual reference
controls pass without waivers. The final expected-head CAS and fetched verification
belong in the canonical closeout. STATUS/NEXT/DEVELOPMENT/ADR0124 describe the finite production
composition. Progress stays unchanged. No raw research branch, CI scaffolding,
ROM or game assets are imported. General mutation/mapping/cache/root/epoch
coverage, RSP task ancestry, whole-ROM closure and native execution remain OPEN.
