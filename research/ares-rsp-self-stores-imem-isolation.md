# RSP-originated stores do not alias IMEM in pinned ares

Status: **VALIDATED** for the bounded scope below.

Worker claim: `gpt56sol-rsp-self-store-imem-20261008`.

## Question

Can an architecturally executed RSP scalar or vector store instruction mutate RSP IMEM, including by setting address bit 12 or by crossing the 4 KiB DMEM boundary?

This matters because `research/rsp-imem-provenance.md` intentionally left RSP-originated stores unclassified. If ordinary RSP stores can reach IMEM, Plaid needs another executable-mutation source. If they cannot, that mutation class can be excluded while CPU/SP-memory writes, SP DMA, reset, restore/debugger and other non-instruction paths remain separate obligations.

## Hypothesis

All ordinary RSP scalar/vector store opcodes target only the RSP's 4 KiB DMEM address domain. Address overflow wraps inside DMEM and does not select IMEM. Therefore an executed store at `0x1000` or across `0x0fff -> 0x0000` must never modify resident IMEM bytes.

Falsifier: any audited handler or decoded exact-pinned execution that writes IMEM.

## Exact references

- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64: `e96debac941a26ba4961e5145056c0821d3a56f7`
- n64-systemtest: `196f5421173220eb2f63a7a99c64795dc0ea0698`

No reference source was patched or instrumented for the executable fixture.

## Source result

### ares

Pinned ares has separate RSP memory objects:

- `ares/n64/rsp/rsp.hpp`: RSP-specific `Writable dmem{*this}` plus separate `Memory::Writable imem`.
- `ares/n64/rsp/rsp.cpp`: both allocate exactly 4 KiB; instruction fetch reads `imem.read<Word>(ipu.pc)`.
- `ares/n64/rsp/interpreter-ipu.cpp`: scalar `SB`, `SH`, and `SW` write only through `dmem`; `SH`/`SW` use the RSP unaligned helpers.
- `ares/n64/rsp/interpreter-vpu.cpp`: all twelve architectural vector-store families discovered by the verifier (`SBV`, `SSV`, `SLV`, `SDV`, `SQV`, `SRV`, `SPV`, `SUV`, `SHV`, `SFV`, `SWV`, `STV`) sink through `dmem.write<Byte>` and contain no IMEM sink.
- the RSP `Writable` byte sink indexes `data[address & maskByte]`; the underlying 4 KiB allocation yields a `0x0fff` byte mask. Multi-byte unaligned stores decompose to byte stores, so crossing `0x0fff` wraps to DMEM `0x0000` rather than escaping the object.

One useful edge case fell out of execution rather than being assumed away: aligned `SRV` stores zero bytes because pinned ares computes `end = start + (address & 15)`. At address `0x1000`, `address & 15 == 0`; this is an architectural zero-length case in the pinned implementation, not evidence of an unexecuted opcode.

### Gopher64 independent source oracle

Pinned Gopher64 represents SP memory as one 8 KiB array and therefore provides a structurally independent check. Its CPU/SP interface treats bit `0x1000` as the IMEM selector, but RSP scalar and vector store implementations mask their data addresses with `0xFFF`. Thus RSP-originated stores remain in the lower 4 KiB DMEM half even though the backing representation could have exposed IMEM if the store path retained bit 12.

### n64-systemtest hardware-oriented corpus

Pinned n64-systemtest source independently encodes the same address-domain expectations:

- `src/tests/rsp/op_sw.rs` explicitly tests unaligned RSP `SW` at the top of DMEM and expects wraparound to DMEM `0x000`.
- `src/tests/rsp/op_vector_stores.rs` masks expected vector-store destination addresses with `& 0xFFF`; eleven store-family tests include a literal `0x1000` base, while `STV` uses a separate offset/register/element matrix.
- `src/rsp/rsp_assembler.rs` independently supplied the decoded SWC2 encoding used by this spike: major opcode 58 and subtypes `B=0,S=1,L=2,D=3,Q=4,R=5,P=6,U=7,H=8,F=9,W=10,T=11`.

This worker source-audited those hardware-test expectations but did **not** execute the suite on physical N64 hardware.

## Executable experiment

Durable fixture: `spikes/026-ares-rsp-self-stores/`.

`driver.cpp` builds against exact pinned ares with CPU and RSP recompilers disabled. For every probe it:

1. initializes DMEM and vector/scalar register state;
2. places the actual store instruction at IMEM `0x000` and `BREAK` at `0x004`;
3. snapshots all 4096 IMEM bytes and all 4096 DMEM bytes;
4. executes through `rsp.instruction()` until `BREAK` halts the RSP;
5. aborts if any IMEM byte differs;
6. verifies the expected DMEM effect and records the resulting DMEM hash.

The matrix has 29 decoded probes:

- scalar `SB @ 0x1000`, `SH @ 0x0fff`, `SW @ 0x0ffe`, and `SW @ 0x1000`;
- every one of the 12 SWC2 vector store families at base `0x1000`;
- every one of the 12 vector store families at base `0x0fff`;
- an additional `SRV @ 0x100f` to force SRV's nonzero write path while bit 12 is set.

The runner executes the exact fixture twice and requires byte-identical JSON stdout.

## Executed result

Authoritative run:

- GitHub Actions run: `37851625324`
- job: `113565651961`
- branch head: `f1ada1d9658976802f9e569ba8950c20b77aef7c`
- conclusion: `SUCCESS`
- driver SHA-256: `e5d254099f953106fd105f7bb377334542c15676ba74a82bccdb12e71ac74135`
- result artifact: `rsp-self-store-results`, artifact id `11582206386`
- artifact ZIP SHA-256: `9a88d68ff7ad262e95d3279eb111ece4febd6c022ce068dcecfe7f287912f554`
- repeated exact-pinned stdout: identical (`repeat_deterministic=true`)
- probe count: 29

Every probe completed without any change to its 4096-byte IMEM snapshot.

Representative concrete effects:

| Probe | DMEM bytes changed | IMEM bytes changed | Meaning |
| --- | ---: | ---: | --- |
| `SB @ 0x1000` | 1 | 0 | bit 12 does not select IMEM |
| `SH @ 0x0fff` | 2 | 0 | halfword wraps within DMEM |
| `SW @ 0x0ffe` | 4 | 0 | word crosses `0xfff -> 0x000` in DMEM |
| `SW @ 0x1000` | 4 | 0 | scalar bit-12 adversary remains DMEM |
| `SQV @ 0x1000` | 16 | 0 | full 16-byte vector write remains DMEM |
| `SQV @ 0x0fff` | 1 | 0 | quad-vector boundary semantics stay in DMEM |
| `SRV @ 0x1000` | 0 | 0 | expected aligned zero-length SRV case |
| `SRV @ 0x0fff` | 15 | 0 | reverse-vector boundary write remains DMEM |
| `SRV @ 0x100f` | 15 | 0 | real SRV write with bit 12 set remains DMEM |
| `STV @ 0x1000` | 16 | 0 | transpose-vector bit-12 adversary remains DMEM |

All other nonzero-length probes likewise changed DMEM and zero IMEM bytes. The final probe's DMEM SHA-256 was `7e8ad5017488ba03437fc1a7a4ecb000dfa5991c2fe7b2a0e0f3a80bbbdb7813`; its resident IMEM SHA-256 after execution was `c1619ab7b21bad6173af7b104d9d381ad21e724c499e8ad2ff850b005da775bc` and matched the pre-execution snapshot by direct byte comparison.

## Failed attempts and why they do not weaken the result

The branch history intentionally preserves three harness failures:

1. The first fixture called templated vector handlers directly from a separate translation unit and failed to link because those templates live in ares's unity source. It was replaced by a stronger decoded-opcode fixture.
2. An early source guard incorrectly required `STV`'s n64-systemtest block to use the same literal `0x1000` fixture shape as the other families. The corpus actually uses a separate `TEST_OFFSETS` matrix for STV; the assertion was narrowed to the evidence the corpus really contains.
3. The decoded fixture initially required every vector probe to change DMEM. Exact execution falsified that test assumption for aligned `SRV @ 0x1000`; the final fixture preserves the zero-length case and adds `SRV @ 0x100f` to exercise SRV's real write path.

These were harness/test-model defects, not observed IMEM mutations.

## Conclusion

**VALIDATED, bounded:** in exact pinned ares interpreter execution, ordinary architecturally executed RSP scalar stores and all twelve vector-store families do not provide an RSP-instruction path to IMEM. Bit 12 is not an IMEM selector for the RSP's own data-store domain, and multi-byte/vector boundary behavior remains inside 4 KiB DMEM.

Plaid may therefore exclude ordinary RSP-originated scalar/vector store instructions from the **RSP IMEM executable-mutation source set** for this pinned-reference contract.

That exclusion is not a blanket IMEM-lifetime proof.

## Remaining gaps

Still separate and not discharged here:

- CPU writes through the SP memory window into IMEM;
- SP DMA into IMEM and its request/lifecycle semantics;
- reset/NMI, debugger, save-state restore, frontend mutation or other out-of-band IMEM replacement paths;
- real-hardware execution of the cited n64-systemtest cases;
- separate execution of ares's RSP recompiler/fast paths. The source audit found the interpreter handlers used by recompiler slow paths, but this fixture deliberately disabled recompilers so it does not claim fast-path behavioral equivalence.

Those mutation classes must remain in the executable-lifetime proof until independently classified.

## Reproduction

From this branch with clean exact checkouts at the revisions above:

```bash
python3 -m py_compile spikes/026-ares-rsp-self-stores/run.py
python3 spikes/026-ares-rsp-self-stores/run.py
```

The runner source-guards all three pins, builds exact pinned ares through the existing spike-003 builder, executes the decoded matrix twice, and writes the ignored local result to `target/ares-rsp-self-store-spike/results.json`.

## Integration recommendation

**ADOPT.** Treat ordinary architectural RSP scalar/vector stores as DMEM-only and exclude them from IMEM executable-mutation provenance. Preserve CPU/SP-window writes, SP DMA, restore/reset/debugger and other out-of-band paths as independent IMEM mutation obligations.
