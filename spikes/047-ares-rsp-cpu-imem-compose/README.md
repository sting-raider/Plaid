# Actual RSP DMEM -> CPU register -> IMEM composition

Reconciles the sixteen-phase fixture from
`research/rsp-producer-cpu-imem-compose-gpt56sol`. Use main's shared generated
SP/RSP/CPU decoder observers rather than caller-only CPU instruction metadata.
Capture full CPU GPRs, RSP scalar operands and the exercised SBV source byte.
Normalize initial/final memory through guest byte accessors.

```sh
python spikes/047-ares-rsp-cpu-imem-compose/test_verify.py
python spikes/047-ares-rsp-cpu-imem-compose/run.py
```

The second command requires clean pinned ares in `.refs/ares`; Windows delegates
to WSL Ubuntu. Generated sources, binaries and versioned receipts stay in ignored
`target/ares-rsp-cpu-imem-primary/`. It compares sixteen reported machine/timing/
exception checkpoints, full caller step snapshots and final backing states across
unchanged-reference, callback-disabled, enabled and repeated enabled runs.

The finite independent census and semantic replay require actual LW definitions,
full GPR continuity, decoded addresses, exact bank/offset and completed SW sinks.
Each copy keeps four source-byte generations separately from its IMEM sink.
Repeated identical RSP stores advance generation. A mixed CPU/unknown/vector/
scalar source keeps its unknown byte. An equal-valued decoy load cannot replace
the true source; same-valued ADDU cuts the old definition. An unscoped sink has
no instruction source. Deliberate captured-history forgeries must fail.

This is a controlled reference contract, not a production ProgramMap certificate.
Writer identity does not prove the ultimate origin of scalar/vector register
inputs. The CPU callback excludes early interrupt/NMI/frozen/fetch-failure
attempts. No complete mutation census, asynchronous interleaving, DMA ancestry,
cache/TLB scope, IMEM consumption/lifetime, hardware truth or native closure is
established. Reported checkpoints cover a subset of emulator state.
