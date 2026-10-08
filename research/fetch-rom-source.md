# Finite cartridge fetch source witnesses

2026-10-08. Hypothesis: actual returned ROM-device halfwords can establish finite
canonical byte sources without inferring images, code generations or lifetimes.

Spike 006 delegates each original PI ROM-device operation once, clears its read
ledger before each interpreter instruction call and samples it at the existing
pre-decoder prologue. Uncached effective address, consecutive source offsets and
the exact returned word must agree. Original/plain/traced/repeated CPU/Count/PI
states match. Direct, TLB and reverse-endian fetches gain sources; an identical
PI latch word, unmapped file tail and prior data reads remain unknown. No extra
guest read or translation occurs. Reads after the prologue cannot be carried into
the next instruction's source window. Both recompilers stay disabled.

Spike 007 extends this to the untouched pinned homebrew's declared SP-entry
prefix. Of 4,999,998 fetches, 1,852 actual ROM reads cover 65 canonical offsets;
4,998,146 sources stay unknown. Every source word agrees with canonical bytes,
physical address/cache policy and the pin's 2,742,280-byte mapped capacity. The
entire v1 projection and previous CPU/Count/RAM/SP/message checkpoints match.
Repeated v2 files are exact: 768,248,958 bytes, SHA-256
`40d8d029cd66fb5ecfcdc3d77bdbc570dd13ce62684d47e7704cbe375008d204`.

The v2 importer requires explicit source policy and either unknown or cartridge
source on every fetch. Cartridge claims must match canonical words, mapped bounds
and uncached physical access. Missing/extra/null fields, policy/version mismatch,
forged words, invalid offsets and cache claims fail. A strict empty-struct unknown
variant avoids Serde's unit-variant acceptance of extra fields. Full-source
rechecking regenerates every fact and provenance record. Source variants remain
distinct even for identical PCs/words/accesses. Legacy fields default/omit and
both earlier map hashes stay unchanged. No reference CPU code enters Plaid core.

After spike 007, run `python scripts/test_fetch_corpus.py --source`. Its 53,037
facts (65 known-source, 52,972 unknown-source) account for every fetch, verify
against the complete raw file and self-merge byte-identically. The map is
27,016,450 bytes. One Windows/Rust debug import under concurrent verification took
51.8 seconds and peaked at 75,792,384 bytes process working set. This is one host's
cost record, not throughput, optimization or scalability evidence.

All reports stay OPEN/native_complete=false. Even a map containing only known
ROM-source fetches retains the independent unknown-execution-identity blocker.
Source at one fetch does not prove retirement, immutability, full coverage,
executable lifetimes or contextual image identity. The synthetic entry, missing
PIF/IPL2 provenance and StartupTest Config mismatch remain visible. Next establish
boot/mode and mutation/cache/copy lineage before constructing executable images.
