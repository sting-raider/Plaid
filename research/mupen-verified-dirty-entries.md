# Verified dirty-entry snapshots

2026-10-08. Hypothesis under test: the pinned `get_dirty` path can report the
exact existing compilation unit and entry whose saved instruction bytes passed
`verify_dirty`. This may explain pending indirect targets after invalidation;
it must not turn cache metadata into a complete executable lifecycle proof.

The pinned verifier compares the complete saved unit against current RDRAM/SP
memory or a checked contiguous TLB mapping. The successful lookup returns that
entry only after the comparison and expiry checks. Carry a trace-local unit ID
on linked-list entries, preserving it when `clean_blocks` copies metadata. Emit
saved words only after successful dirty lookup. The words must equal the unit's
earlier capture, and the entry/mask must have been installed for that unit.

Import should retain these typed snapshot observations separately from loads and
compilations. A verification may explain a pending target in the same epoch; it
must not explain observations across invalidation, establish a new DMA copy, or
claim execution merely because a lookup verified an entry. Competing target
identities remain ambiguous. Legacy traces without this sensor remain unresolved.

Acceptance: original store-stress return gets snapshot-backed target identity;
all CPU modes still agree, reruns remain deterministic, changed/incomplete or
uninstalled unit claims are rejected, missing verification keeps the blocker,
and whole-ROM reports stay OPEN. Other restore/cache-hit paths remain unsensed.

Results: all acceptance checks pass. The store-stress return at 80000544 now
joins generation 9 to its original generation-8 entry at 80000490, retaining
both the indirect event and the byte-verification event as provenance. One
verification increases that deterministic trace from 48 to 49 events. The other
five sessions remain 43/83/82/82/34. All GPR/HI/LO/PC values agree across pure,
traced and untraced engines, with byte-identical reruns. Whole-ROM remains OPEN.

62 Rust integration tests cover exact/changed/truncated captures, unit/mask/entry
validation, absent/future verification, intervening invalidation, competing
current-generation snapshots, raw fact roundtrips and merge idempotence. Strict
Clippy, formatting, CLI, C99 exporter, four-unit compile-only harness, eight CPU
scenarios, six full-core sessions and the spimdisasm fixture comparison pass.
The portable exporter explicitly calls the helper while disabled; its 10-event
stream stays unchanged. Patch application against the clean pinned index passes.

The hook is GPL research instrumentation. It skips predecessor-dependent
pagespan delay-slot entries; ordinary restricted entries retain their mask and
existing modeling blockers. `clean_blocks` only preserves unit metadata; it does
not emit a speculative execution claim. Cache-hit/expiry, exception/interruption
and other host coverage still need separate analysis. No lifecycle certificate
or native artifact is produced.
