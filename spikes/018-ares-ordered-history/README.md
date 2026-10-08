# Ordered controlled transaction/cache/fetch history

Hypothesis: one callback ledger can join the existing actual RAM bursts,
completed fills, completed CACHE operations, pre-decoder fetches and explicitly
declared fixture writes without extra guest accesses or clocks.

Run `python spikes/018-ares-ordered-history/run.py`.

## Verdict: VALIDATED for the controlled callback chronology

### Evidence

All 43 ordered records reference each payload exactly once: nine declared fixture
writes, five RAM bursts, four fills, seventeen fetches and eight CACHE completions.
RAM reads precede their fills and cached fetches. Explicit CACHE fill occurs after
that instruction's fetch and before operation completion. Successful writeback
occurs after the instruction fetch and before operation completion. A stale
resident word survives the declared backing mutation and is then written back.
The complete prior spike-016 projection retains SHA-256
`0eac15edb2d40ecbcd85b5302c12fc25b24f9980a6c83b2d9b6291f3cbeaed8a`.
A separately built baseline without transaction/cache hooks, observer-disabled
and repeated traced runs have equal CPU/COP0/timing/RAM/cache checkpoints.
Five reordered/missing/forged history or payload variants are rejected.

### Constraints and surprises

The ledger covers only the declared fixture. Fixture writes are labelled as host
setup/mutation, not guest copy provenance. Fetches are pre-decoder observations;
they supply no retirement certificate. The final uncached fetch has no scalar
RAM read event because the existing observer covers bursts only. Tag stores retain
historical fill data under a different effective page. Neither one event sequence
nor an unchanged payload proves general absence of mutation/reset/restore.

### Recommendation

Join source-specific transactions with explicit operation context before broader
capture. Use the remote research on scalar reads, reset/restore and byte mutations;
keep ordinary writes, device copies and executable lifetimes unknown until covered.
