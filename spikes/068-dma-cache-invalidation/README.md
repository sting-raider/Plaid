# Guest invalidation composes with fresh DMA executable parents

Original controlled extension of spike067 at exact ISC ares
9408cb43d4948fc3ea6e152a307a34348df3fe04. Run `python run.py` from this
directory; use `--verify-existing` to recheck retained controls without rebuilding.
ROM and build outputs remain ignored under `target/dma-cache-invalidation-primary`.

After the stale-resident NOP, a guest CACHE HitInvalidateI executes from that
same line. Capture its decoded effective address and completed full before/after
tuple on the same event clock. The valid bit clears without changing words.
Then a promoted DMEM DMA installs NOP again at6028; a new completed burst/fill
and cached decoder consumption must use the new RAM writer and fill identities.
DMEM parents retain their earlier ingress/RAM/RSP chain. Equal NOP bits cannot
recover the old resident parent after invalidation.

Baseline/disabled/enabled/repeat report identical CPU steps and34 complete
reported machine/cache checkpoints; each hashes all512 I-cache tuples. Enabled
sources repeat exactly. The independent model reconstructs the complete event,
bank, RAM, cache, definition and parent census and compares the Rust report.

The production profile additionally checks misses, repeated invalidation, initial
power-cleared slots, unselected words, exact operands/scope, required operation
cardinality and report forgeries. Only identity-mapped direct-KSEG0
HitInvalidateI is admitted; other cache operations remain unsupported. Explicit
host control seeds remain opaque. Complete mutation/cache/TLB/root/restore
coverage, executable lifetime and whole-ROM/native certification remain false.
