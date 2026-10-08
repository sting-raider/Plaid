# Executed controlled callback chronology

2026-10-08. ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, x64 WSL
Ubuntu/G++ 15.2. Related worker findings: `research/icache-rdram-chronology.md`
and `research/unified-cache-ordering.md` on their isolated research branches.

Hypothesis: the existing callbacks can preserve one measured order without extra
guest accesses or clocks. Spike 018 extends the unchanged spike-016 fixture with
an original ledger referencing each independently retained payload once. Hooks
copy existing callback data; declared host writes append only after the fixture's
existing identity-mapped in-range Word store. The reference pin stays unchanged.

`python spikes/018-ares-ordered-history/run.py` passes. Its 43 records comprise
nine fixture writes, five actual RAM bursts, four fills, seventeen pre-decoder
fetches and eight completed CACHE operations. Normal misses measure RAM read ->
fill -> fetch. Explicit guest fill measures instruction fetch -> RAM read ->
fill -> CACHE completion. Hit writeback measures instruction fetch -> completed
RAM write -> CACHE completion. Miss operations supply no backing transactions.
The deliberate RAM word-8 mutation precedes writing back resident word 9; the
later uncached fetch returns 9. Retagged hits retain historical fill words even
though their current effective page differs from that fill's burst page.

A separately compiled no-hook baseline, instrumented plain and repeated traced
runs have equal complete reported CPU/COP0/timing/RAM/cache state. Count=257,
hits=5, misses=4, writebacks=1. The complete spike-016 JSON projection retains
SHA-256 `0eac15edb2d40ecbcd85b5302c12fc25b24f9980a6c83b2d9b6291f3cbeaed8a`.
Five variants with reordered/missing records, invalid references, changed read
data or false CPU attribution of a fixture write fail verification.

This closes the shared-order reference-execution gap for this controlled scope.
It does not turn the worker chronology model into a production certificate.
The final uncached fetch still lacks an ordinary scalar-RAM witness. Explicit
fetch/fill contexts, nested/reentrant paths, reset/restores, general byte writes,
CPU/PI/SP copies and broader backing policies remain separate obligations.
Current tags and historical data origin remain distinct; a conservative model
that clears active witness state after retagging must not erase the prior fill
record itself. No ProgramMap image, generation, lifetime or closure is promoted.
