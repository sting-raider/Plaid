# RSP DMEM writes followed by CPU SP refetch

Hypothesis: actual scoped RSP byte sinks can explain a later CPU SP backing read,
while repeated same-value writes create distinct observed writer contexts and a
later CPU Word store supersedes that observed chain. IMEM remains separate.

Verdict: VALIDATED for the finite seven-phase fixture; broader composition is
PARTIAL. At pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, the unchanged
reference, disabled sensor, enabled sensor and repeated enabled run agree at
every reported machine checkpoint. Byte replay checks 31 ordered records,
eight primitive RSP byte writes, one CPU Word write and four backing-read
samples. Ten measured history forgeries are rejected.

Run `python spikes/043-ares-rsp-cpu-refetch/run.py` from the repository root
(Windows delegates to WSL Ubuntu). Generated reference shadows and results
remain under ignored `target/`; the reference checkout remains unchanged.
Result SHA-256: `542e887cd45730ab019c790caeadaa6e4eb016deaaa26bb337178a9afc920ec1`.

The repeated same-value RSP store creates four new observed byte writers. A
later CPU overwrite replaces them. An alternate SP aperture fetch reads the
same DMEM backing; initial bytes have unknown writers. This fixture excludes
unscoped low-level DMEM sinks and does not certify a complete mutation census.
Partial/vector stores and foreign-sink boundaries from the broader swarm
fixture still need reconciliation with this independent checkpoint gate.
No ultimate ROM source, continuous lifetime or native closure is inferred.
