# RSP IMEM executable provenance

Date: 2026-10-08

Status: **VALIDATED (bounded controlled scope)**

## Conclusion

For pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, a controlled
identity-mapped RDRAM -> RSP IMEM transfer can carry an exact byte-origin witness
through to a later interpreter RSP fetch when the chronology contains both the
successful backing RDRAM transaction and the completed IMEM write. The witness
must be latest-writer/generation sensitive.

The experiment rejects three tempting shortcuts:

1. Existing RDRAM burst instrumentation is sufficient for SP DMA. It is not:
   ares SP DMA uses ordinary templated RDRAM reads, not `readBurst`.
2. `IMEM address + content hash` is a lifetime/provenance identity. It is not:
   byte-identical code loaded into the same IMEM address from a different RDRAM
   address has a distinct latest-writer generation and origin.
3. An IMEM destination write plus a requested DRAM address proves a successful
   backing read. It does not: the out-of-range fixture writes zero into IMEM but
   has no successful RDRAM read witness, so the fetched zero remains
   source-unknown.

A content hash is still useful for microcode recognition and native-body
content deduplication after the bytes are proved. It must not be overloaded into
an origin or residency-lifetime certificate.

## Falsifiable hypothesis

For the pinned ares revision, controlled identity-mapped RDRAM -> RSP IMEM DMA can
produce an exact byte-origin witness if and only if Plaid observes both the
successful backing RDRAM read and the completed IMEM write in one chronology.
Each completed IMEM write creates a new resident generation even when the bytes
are identical to the previous generation. A fetch may inherit origin only from
the latest generation covering all fetched bytes. Direct IMEM writes replace that
lineage, DMEM transfers cannot explain IMEM fetches, and an IMEM write caused by
an unsuccessful/out-of-bounds RDRAM read must remain source-unknown.

Result: **VALIDATED for the declared fixture scope.**

## Exact upstream source map

Pinned ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

- `ares/n64/rsp/dma.cpp::RSP::dmaTransferStep`: IMEM DMA reads a `Dual` from
  `rdram.ram.read<Dual>(..., RBusDevice::SP_DMA)` and writes that exact value to
  `imem.write<Dual>(...)`. DMEM DMA instead performs two 32-bit RDRAM reads and
  two DMEM writes.
- `ares/n64/rsp/rsp.cpp`: interpreter execution fetches from
  `imem.read<Word>(ipu.pc)` (and may fetch `ipu.pc + 4` for dual issue); the
  observer is called only after the fetched word has already been assigned to
  the pipeline in the existing prologue path.
- `ares/n64/rsp/io.cpp::RSP::writeWord`: direct writes targeting the IMEM half of
  SP memory invalidate the RSP recompiler range and write the supplied word into
  IMEM independently of SP DMA.
- `ares/n64/rdram/rdram.hpp::RDRAM::Writable::read`: in identity mode, an
  out-of-range access returns zero before the underlying `Memory::Writable::read`.
  Therefore a DMA-side destination write alone cannot prove a successful backing
  transaction.

Existing `spikes/016-ares-rdram-bursts` does not cover this path: SP DMA uses the
ordinary templated RDRAM `read`, not `readBurst`.

Independent source corroboration was also checked at the pinned Gopher64 revision
`e96debac941a26ba4961e5145056c0821d3a56f7`, in
`src/device/rsp_interface.rs`: RDRAM -> SP DMA updates the IMEM-backed decoded
instruction entries when the IMEM half is selected; direct SP-memory writes do
the same; count/length/skip advance the source blocks explicitly. This is an
independent source check, not an executed second-oracle result.

## Why the current ProgramMap shape is insufficient by itself

At the branch base, `Microcode` contains only `sha256`, `imem_start`, `size` and
`evidence`. That is a useful content description but cannot encode the lifetime
counterexamples below. Plaid already uses generation-aware identities for CPU
code; RSP executable identity needs the same conceptual separation between
content and residency/provenance rather than treating a microcode hash as proof
of how the resident IMEM bytes got there.

## Experiment

`spikes/018-ares-rsp-imem-provenance/` builds an untouched baseline using the
existing spike-003 headless recipe, then a separately generated observer build.
Both CPU and RSP recompilers are disabled. The observer records only already
completed/existing values:

- successful identity-mapped ordinary RDRAM reads whose requester is `SP_DMA`;
- completed RDRAM -> IMEM DMA writes;
- direct IMEM word writes;
- interpreter words already fetched into the RSP pipeline.

It issues no extra guest memory/bus accesses and does not modify the pinned ares
checkout. A Python reducer maintains a 4096-byte latest-writer table. An IMEM DMA
write receives RDRAM origin only when the immediately associated successful read
has the same DRAM address, width and payload. Every completed IMEM/direct write
creates a new fragment generation. A fetched word resolves only if all four
resident bytes agree with the fetched value and form a compatible generation and
source.

Command:

```bash
python3 spikes/018-ares-rsp-imem-provenance/run.py
```

## Executed environment and reproducibility

Successful provenance-manifest run:

- Plaid research head: `5f94f8fd4bbd18ba5876bce1ce2c559e0e97434d`
- GitHub Actions run: `37800346437`, job `113390548335`
- runner: Ubuntu 24.04.5, image `20261004.327.1`
- compiler: `g++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`
- Python: `3.12.3`
- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- fixture driver SHA-256:
  `4446fe3af95a759609d42e2b07089ccf83c42d535895e815f0370dde57b196a7`
- runner SHA-256:
  `b200638379c7a9b1030cc94e03bc01c86dfb7da066007ac91e9cd1f99a5d306f`
- `results.json` SHA-256:
  `78ecaa90be8bfd3c1cf317d74b95dac4e131f828082ede8b9c8ccb8a3c6abc39`
- generated-observer manifest SHA-256:
  `416da6c0cf414bded0c69557e19703b6509d320592f50e4af893dab027f9ac54`
- uploaded artifact ZIP SHA-256:
  `109536504e4bfdb52474468731c8ea8d49c9d269ed18f23c531595922b15a829`

Generated observer hashes recorded by that run:

- `include/n64/rdram/rdram.hpp`:
  `e3a73b9e415f821bb3d615794ac97f04eb3ea38b019b7c47b613923f807f8988`
- `rsp_dma.cpp`:
  `4049c8282d36f78a3f9152fd50e699bc9489c0ed2985652f7977d6974b24b86d`
- `rsp_io.cpp`:
  `7ce000e8924582c9594d2a233ce4f825021c9dfe1f1770206394212f788f1e4c`
- `rsp.cpp`:
  `4bc628e35a93948116f08615b2ffb5773a8f97e361447025cf545941dac4098c`
- generated `n64.cpp`:
  `07161f59ca3466cf19f731141b60db9d13b55cd86209f9b8bdde9aa10a0acaf2`

The same semantic fixture also passed the two preceding clean workflow runs. The
manifest run is the authoritative checkpoint because it hashes the generated
observer sources explicitly.

## Deterministic observations

Baseline state and observer state were exactly equal for the recorded state
projection, and two observer executions produced byte-identical JSON.
`neutrality=true` and `repeat_deterministic=true`.

Behavior checkpoints were:

```text
[1, 2, 1, 9, 4, 5, 7, 0]
```

Final state hashes:

- IMEM: `73b2a6ca4a8883f9ed1d367e058e8e836594091b497f74de157b738126a00cc4`
- DMEM: `062dfba3f94d3bbcf3ce2255002e0a60fbab92e4ad7d6299da7a5ccfbb989643`
- RDRAM: `463ed9c33193cb7f7be80cf8e6a79af95fb902fbf3114c51fc9213a6593f0f16`

Resolved fetches:

| Fetch PC | Word | Resolution | Fragment generation |
| --- | --- | --- | ---: |
| `0x000` | `0x24010001` | RDRAM `0x1000` | 1 |
| `0x004` | `0x24020002` | RDRAM `0x1004` | 1 |
| `0x000` | `0x24010001` | RDRAM `0x2000` after byte-identical reload | 3 |
| `0x000` | `0x24010009` | RDRAM `0x3000` after changed reload | 5 |
| `0x020` | `0x24030004` | RDRAM `0x4000` | 7 |
| `0x028` | `0x24040005` | RDRAM `0x4010`; poison at `0x4008` skipped | 8 |
| `0x000` | `0x24010007` | direct CPU IMEM write | 9 |
| `0x060` | `0x00000000` | unknown; OOB source read did not succeed | 10 |

Additional negative checks:

- DMEM transfer produced successful SP-DMA backing reads at RDRAM `0x5000` and
  `0x5004`, but no IMEM write event and no IMEM mutation.
- The out-of-range request at RDRAM `0x800000` produced an IMEM zero write but no
  successful backing-read event at that address.
- The pinned ares checkout remained clean after instrumentation/build.

## Architectural requirements supported by this result

For the tested path, Plaid should model RSP executable provenance with separate
concepts for content and residency/lifetime:

1. Record the successful backing transaction, including requester, physical
   source span, width/payload and chronology identity.
2. Record the completed IMEM write and join it to that exact backing transaction,
   not merely to the programmed DRAM address.
3. Create/replace latest-writer generation state for every IMEM byte written,
   including byte-identical reloads.
4. Treat direct IMEM writes as first-class provenance/mutation events that
   supersede only the bytes they cover.
5. Keep DMEM and IMEM destination provenance separate.
6. Fail closed when backing success is missing or cannot be joined exactly.
7. Group low-level 8-byte write fragments under a higher-level SP-DMA transfer
   identity before describing a complete installed microcode image; length,
   count and skip belong to that transfer record.
8. Permit content hashes/signatures to identify equal byte sequences, but never
   infer equal origin or equal lifetime from hash equality alone.
9. Chain RDRAM provenance further backward when available. This spike proves
   `RDRAM address -> IMEM resident byte` for controlled successful transactions;
   it does not prove where those RDRAM bytes originally came from.

## Limitations / remaining unknowns

This result is deliberately narrower than an N64-wide closure claim:

- RDRAM is forced into the controlled identity-mapped path. Translated/degraded
  RDRAM modes were not executed here.
- The fixture drives the real SP DMA engine directly in a headless component
  setup; it does not prove full-game DMA FIFO/interrupt/scheduler ordering or
  adversarial interleaving with CPU writes during a multi-block transfer.
- Only the RDRAM -> SP direction is used for executable provenance. Reverse SP ->
  RDRAM DMA is not an executable-origin proof.
- The direct-write counterexample is a CPU word write. Byte/halfword forms,
  RSP-originated stores, debugger/save-state restoration, reset and unusual
  mutation paths remain unclassified.
- The `origin_cpu` observer discriminator is sufficient for the controlled CPU
  caller fixture, not a production-quality requester taxonomy.
- IMEM wraparound edge cases were not exercised.
- RSP interpreter execution is tested; RSP recompilation is disabled. This is
  appropriate for a compile-time/reference discovery oracle but says nothing
  about an ares RSP JIT execution path.
- The reducer's generation is per completed write fragment. Defining a complete
  microcode-installation lifetime across all fragments still requires a transfer
  identity and completion boundary.
- Dynamic fetch observations remain observations, not exhaustive reachability of
  the RSP execution universe. Whole-ROM closure still needs roots/task discovery
  and proof that all relevant microcode generations are represented.
- Gopher64 was inspected as an independent implementation source; it was not
  executed as a second behavioral oracle in this spike.

## Recommendation

**ADOPT** the provenance/lifetime invariant and observer requirements above.
Do not merge the experimental ares-generated instrumentation wholesale into
production. The primary integrator should transplant the semantics into the
project's unified chronology/provenance model, retain the spike as a reproducible
oracle, and decide the final ProgramMap representation after reconciling it with
other active backing-transaction/cache/copy research.

## Primary-checkout reproduction

2026-10-08, x64 WSL Ubuntu/G++ 15.2: The independent uninstrumented baseline and repeated observer runs agree on the reported state. All eight resolved fetches, the distinct equal-byte reload generations, count/skip selection, DMEM exclusion and OOB unknown source pass. IMEM, DMEM and RAM hashes match the worker receipt. The local results file SHA-256 is `53e321a2dedcd226df2e1109de18c0e1112db9ddc07ad3bc091f5fd687144a05`; driver line endings make this file receipt host-specific. The clean-pin guard now handles the Windows checkout through `core.autocrlf=true`. These comparisons cover the reported checkpoints, not every CPU/RSP register or scheduler state.
