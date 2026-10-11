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
same DMEM backing; initial bytes have unknown writers. This original fixture
still excludes unscoped low-level DMEM sinks and retains its exact result hash.

The extended nineteen-phase fixture reconciles the broader swarm cases with
the same independent checkpoint gate. It retains 78 records, fifteen scoped
RSP byte effects, two CPU Word effects, three foreign sinks and ten CPU backing
reads. Neighboring equal-valued writes cannot steal origin. Scalar SB and
vector SBV change only their measured bytes. An unmatched same-value foreign
sink makes its byte writer unknown; a later decoded same-value SB reestablishes
an observed writer. A same-value CPU overwrite replaces all four writers.
Seventeen forged histories fail; a deliberately weaker payload-only replay
accepts three causal forgeries. Extended result SHA-256:
`d7973dcd198a5b4e281f0c5719789e40863a905b0cce70e66c9d4a9b8af303e6`.

Both fixtures run by default. Contracts validate exact fields/types, instruction
contexts, ordered primitive effects and byte histories for these controlled
sequences. No complete mutation census, ultimate ROM source, continuous
lifetime, hardware equivalence or native closure is inferred.
