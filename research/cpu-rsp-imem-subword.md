# CPU SB/SH writes into RSP IMEM widen to a 32-bit sink

Status: **VALIDATED** for the bounded pinned-ares CPU-to-RSP-IMEM path. The initial payload hypothesis was **PARTIAL**: it correctly predicted a full-word sink, but incorrectly assumed the source would first be truncated to the nominal SB/SH width.

## Question

When the VR4300 writes RSP IMEM using `SB` or `SH`, can Plaid treat the nominal one/two-byte ISA store width as the executable mutation width and payload width?

No.

For the pinned ares reference, an uncached CPU `SB`/`SH` reaching SP memory through the RCP adapter replaces the complete 32-bit destination word. More surprisingly, the adapter shifts the unmasked low 32 bits of the source GPR, so bytes above the nominal store width can also become part of the written word depending on the address lane.

Pinned `n64-systemtest` encodes the same SPMEM hardware quirk, and pinned Gopher64 models the same full-word behavior. Pinned Mupen64Plus instead keeps a byte mask through to the RSP memory sink and therefore disagrees with that hardware-facing oracle.

## Exact revisions

- Plaid integration baseline at claim time: `5a24b9ccf3064d96f2f0d50fd3df1e50ee6d4862`
- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64: `e96debac941a26ba4961e5145056c0821d3a56f7`
- Mupen64Plus Core: `ba95bab92a76744753bfe61470823a4937850ab0`
- n64-systemtest: `196f5421173220eb2f63a7a99c64795dc0ea0698`

## Exact pinned-ares path

The relevant pinned ares path is:

1. `CPU::SB` calls `write<Byte>(..., rt.u32)`; `CPU::SH` calls `write<Half>(..., rt.u32)`.
2. `CPU::write` applies reverse-endian physical-address lane mapping before the bus sink: Byte XORs the physical address with `7`, Half with `6` when `context.littleEndian()` is true.
3. `Bus::write<Size>` routes physical `0x04000000..0x0407ffff` to `rsp.write<Size>`.
4. `Memory::RCP::write<Byte/Half>` does not mask `data` to 8/16 bits. It shifts the full incoming value according to the RCP lane and calls `writeWord`.
5. `RSP::writeWord` selects IMEM when address bit `0x1000` is set, invalidates the RSP recompiler line, and calls `imem.write<Word>(address, data)`.
6. `Memory::Writable::write<Word>` replaces the complete aligned 32-bit word.

No instrumentation patch is involved in the experiment. The fixture builds and executes the exact pinned ares checkout with recompilers disabled.

## Concrete sink rule

Let `p` be the physical SP-memory address *after* translation and reverse-endian lane mapping, and let `x = rt.u32`.

For normal big-endian addressing, `p` is the translated physical address. In ares reverse-endian mode:

- Byte: `p ^= 7`
- Half: `p ^= 6`

The sink word base is `w = p & ~3`.

### SB

The complete 32-bit word at `w..w+3` is replaced by:

| `p & 3` | written word |
|---:|---:|
| 0 | `(x << 24) & 0xffffffff` |
| 1 | `(x << 16) & 0xffffffff` |
| 2 | `(x << 8) & 0xffffffff` |
| 3 | `x` |

With `x = 0x12345678`, the four big-endian lane results are therefore:

`0x78000000`, `0x56780000`, `0x34567800`, `0x12345678`.

### SH

An odd virtual address raises Store Address Error before the SP-memory sink and leaves IMEM unchanged in the tested pinned-ares path.

For aligned stores, the complete 32-bit word at `w..w+3` is replaced by:

| `p & 2` | written word |
|---:|---:|
| 0 | `(x << 16) & 0xffffffff` |
| 2 | `x` |

With `x = 0x12345678`, those are `0x56780000` and `0x12345678`.

This is not merely “zero-fill around the nominal byte/halfword.” At later lanes, upper source-register bytes survive the shift and become executable IMEM bytes.

## Hardware-facing oracle

Pinned `n64-systemtest/src/tests/sp_memory/mod.rs` explicitly describes SPMEM `SH/SB` as overwriting the complete 32-bit word. Its test cases use `x = 0x12345678` and expect exactly:

- `SB` lanes 0/1/2/3: `0x78000000`, `0x56780000`, `0x34567800`, `0x12345678`
- `SH` lanes 0/2: `0x56780000`, `0x12345678`

The repository describes itself as an N64 test ROM intended to test hardware quirks and emulator correctness. This research did not execute that ROM on a physical N64; it treats the pinned expected values as the project’s hardware-facing oracle.

Pinned Gopher64 independently ignores the incoming write mask in `rsp_interface::write_mem`, applies a full `0xffffffff` mask, and contains the same explanatory `SH/SB` SPMEM quirk comment.

Pinned Mupen64Plus differs. Its `SB`/`SH` implementations construct nominal-width masks (`0xff << shift` / `0xffff << shift`), and `write_rsp_mem` calls `masked_write(..., mask)`, preserving bytes outside the nominal store. For this case, Mupen must not be treated as the independent truth oracle.

## Experiment

Durable fixture: `spikes/040-ares-cpu-rsp-imem-subword/`

- `model.py`: source-derived lane/sink model; exhausts 32 endian/op/offset cases, reproduces the pinned system-test examples, then fuzzes 100,000 randomized successful stores.
- `compare_refs.py`: exact-revision/source guards for Gopher64, Mupen64Plus, and n64-systemtest; checks that the first two emulator models disagree and that Gopher matches the hardware-facing widening rule.
- `driver.cpp`: headless exact-ares component fixture. Initializes 16 nonzero IMEM sentinel bytes, executes one CPU `SB` or `SH` to uncached physical SP IMEM, and reports pre/post IMEM plus exception state.
- `run.py`: source guards, exact-pin build, repeated execution, model comparison, fault checks, deterministic hashes.
- `.github/workflows/research-cpu-rsp-imem-subword.yml`: exact-pinned CI reproduction.

The direct ares matrix is 2 endiannesses × (`SB` 8 offsets + `SH` 8 offsets) = 32 cases. Each process is run twice and byte-for-byte output equality is required. There are 24 successful cases and 8 odd-address `SH` faults.

### Useful failed model

Workflow run `37850322119` at branch commit `71623e7f48f5ab7023b13ae9dae716e257b8de57` intentionally remains useful evidence of the first wrong hypothesis. The first model truncated SB to one source byte before the RCP shift. Exact ares disproved it immediately at big-endian `SB +1`:

- source `rt.u32 = 0x55667788`
- observed IMEM word bytes: `77 88 00 00`
- a nominal-byte model would have predicted only `00 88 00 00`

That failure led to inspection of the pinned SPMEM hardware tests and the corrected unmasked-register rule.

### Passing run

GitHub Actions run `37850555562`, head `dfeeaace0d08ae737f78b2acb12e157552f6205c`:

- model: PASS, 32 exhaustive cases + pinned hardware-oracle examples + 100,000 randomized sink cases
- independent source comparison: PASS
- exact pinned ares: PASS, 32 repeated cases
- successful widened cases: `24/24`
- model SHA-256: `cbbcf1d5dcb2a148c0930c1274f441ed5c320caeca3de1059218bee23a4b72d8`
- comparison SHA-256: `6ce196f015e985dd79921ac707ab5ef546124caed5ca0f927220aab0e90fbb87`
- exact-ares results SHA-256: `2ccf7423eb9d2359119c29dea519c62f089c76902fd31c59f31c02ee06a3825e`

Pinned-source SHA-256 guards from that run:

- ares CPU IPU: `495c2589d6c5b34e144a5d2cd02cf2372771dc8642af590e9d46389a157e6152`
- ares CPU memory: `55f833718501d018d7e81e089a1ca53a9891154b8952cc2ec1b5126fda632c74`
- ares RCP adapter: `54089251052dbffddf7ae77819c3a3bb494cf7269ae874a3015a23907370a69c`
- ares RSP IO: `60cc9b1efb2e90c127098a736c5213ea0bf77d2e3bd6e5b112e55752289af860`
- ares writable memory: `29d6d71b9b92e095f34bd1809c5d3f8afb74cb16857e1f597854165d70d9df06`
- Gopher64 RSP interface: `a5864c02f742bc922284d7866bbe76fe80efda63d3a3c69af7e37c50fe661053`
- Mupen IPU definitions: `c0f7e42835386ecd8bc623fe6115bc1b2d7facd93799c0308a76bef138622a7d`
- Mupen RSP sink: `8f24582ff64748ac6164f4c468adf7d7d198a968f6c53ad6ff690469fe095b7f`
- n64-systemtest SPMEM tests: `9096a6eefc7a8a248642ca782e25be67f51d9620d81cf2a7322e9fd5254af074`

## Plaid implication

A provenance/mutation event for CPU stores cannot infer executable byte span or payload from the MIPS opcode width alone.

For SP IMEM specifically, a sound event must reflect the *post-RCP sink effect*:

- translate/alias the CPU address first;
- apply the relevant endian lane mapping;
- classify the SP-memory target;
- use the actual aligned 32-bit sink span;
- preserve the exact shifted `rt.u32` payload, including source bytes outside the nominal SB/SH width;
- emit no IMEM mutation for a faulting misaligned `SH`.

This is a concrete reason to instrument or normalize at actual backing/device transactions rather than only at CPU ISA stores. A nominal one-byte `SB` can replace an entire 32-bit RSP instruction and can source multiple bytes from the GPR.

The existing RSP IMEM provenance rule that direct writes supersede only the bytes they cover remains usable only if “cover” means the concrete device sink span, not the nominal ISA width.

## Limitations / still unknown

- The exact ares fixture uses uncached KSEG1 SP IMEM. Cached KSEG0-to-SP-memory behavior, including any D-cache writeback interaction with the RCP bus, is outside this claim.
- Reverse-endian lane behavior was executed in pinned ares by forcing the CPU context endian mode and is source-derived from `reverseEndianPaddr`; this session did not run a physical-N64 reverse-endian SPMEM test.
- The pinned n64-systemtest examples target SPMEM at the DMEM base. Extending the same hardware bus quirk to IMEM is strongly supported by the common SP-memory bus model and by exact ares/Gopher routing, but this session did not run a physical-N64 IMEM-specific SB/SH test.
- RSP-originated stores to IMEM are a separate claimed research lane and are intentionally excluded.
- DMA, debugger/save-state restoration, reset paths, and other IMEM mutation sources are outside this claim.

## Recommendation

**ADOPT** the sink-width result into Plaid's executable-mutation model: CPU `SB`/`SH` reaching SP IMEM must not be represented as one/two-byte mutations merely because of opcode width. Normalize from the actual SP-memory sink semantics, including unmasked `rt.u32` lane leakage. Treat pinned Mupen's masked behavior as a known conflicting oracle for this case, not as grounds to weaken the hardware-facing result.
