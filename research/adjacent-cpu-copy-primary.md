# Primary adjacent CPU-copy reconciliation

Hypothesis: exact completed uncached Word effects plus adjacent interpreted
LW/LWU and SW instruction/GPR histories can establish a bounded observed copy
without selecting a source by equal values. Architectural continuity must be
checked between the captured instructions.

Reviewed `research/ares-cpu-copy-dataflow-gpt56sol` at
`7079fe6d46b6a7ec5a0bc34cf52049e1b5d7385c`, including its fixture, callback,
source-shadow generator and verifier. Its successful experiment commit is
`c1d57fd0d2e028feaf9fe0a9962ed6f6497091bf`; Actions run `37915748860`
retains synthetic `results.json` with SHA-256
`0a10e68ebe27bac70cf6d3d2233f1ee2eab0e67caa50e9e7f49b118e948d9b2e`.
The primary downloaded and authenticated that artifact and reproduced the two
intended certificates before changing the contract.

Three additional forged histories were accepted by the branch verifier:

- changing high GPR bits between load-end and store-begin while preserving the
  low Word stored;
- moving both captured store PCs and its scalar-effect PC by 0x100;
- changing the destination base to KSEG0 while retaining an uncached transaction
  claim at the same physical address.

Each still emitted the phase-1 `0x1000 -> 0x2000` LW certificate. This is a
research verifier defect, not a previously deployed production copy certificate.
The unmodified verifier is rejected. The primary finite-history verifier retains
both valid artifact certificates and rejects twelve adversaries, including the
three research adversaries and these additional counterexamples.

The reconciled fixture at `spikes/044-ares-cpu-copy-dataflow` preserves all six
phases: LW, LWU, an equal-valued competing load, a same-value ORI clobber, a NOP
gap and a failed misaligned load. Only the first two phases can certify a copy.
It checks strict field sets and integer/bool types, all 32 GPRs, complete scoped
scalar effects, canonical aligned KSEG1 addresses in controlled identity RDRAM,
load sign/zero extension, unchanged store registers and sequential adjacent
captured contexts. A load into zero cannot define a causal register writer.
Foreign scalar effects cannot silently disappear from the history.

At exact ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, CPU instruction
callbacks bracket decoder execution after prologue and before pipeline end.
The existing scalar callback observes completed backing effects. The original
fixture now adds per-instruction independent reference/disabled/enabled/repeated
reported-state checkpoints rather than relying only on selected final facts.
Generated shadows compose through the existing shared builder; worker-specific
manual compiler/workflow scaffolding is excluded.

Fresh primary reproduction passes: fourteen original/disabled/enabled/repeated
instruction checkpoints agree, 28 boundary records and eleven scalar effects
produce exactly the two adjacent certificates, and twelve measured forgeries
fail. The nearest-equal-value reducer still selects the wrong phase-3 source
and admits the ORI clobber/NOP gap. Seven separate synthetic contract tests pass,
including a real-read/zero-register case that emits no causal certificate.
Result SHA-256: `a0903ba3ae1e2f05144a1968a065348edd344debb7ded9fac450bfdd1427fa6a`.
Full locked workspace, fmt, strict workspace Clippy and synthetic CLI checks
pass. The branch's controlled fixture/validator is superseded by this bounded
reconciliation; its unproved general-dataflow obligations remain open.

The captured instruction callback does not cover every early-return interrupt,
NMI, frozen-bus or fetch-failure attempt. Fixture call counts and interpreter
settings bound this controlled run; callback absence cannot establish a general
execution census. The reported machine digest is also not every CPU/FPU/COP0/
cache/queue state bit. General source authentication, interrupts/branches/delay
slots, non-adjacent dataflow, cached copies, transforms, executable consumption,
lifetime and hardware truth remain unproved. No production ProgramMap or solver
copy certificate is installed, and native-complete flags remain false.

These are project-owned ISC fixtures/observers. Pinned ares core ISC / SLJIT BSD
notices remain with generated ignored reference builds. No upstream implementation,
firmware or ROM data is copied into production or Git.
