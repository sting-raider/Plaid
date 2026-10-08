# ares VR4300 SB/SH executable-byte mutation semantics

Status: **VALIDATED** for the bounded exact-reference scope below.

Plaid base inspected: `codex/executable-discovery` at `5a24b9ccf3064d96f2f0d50fd3df1e50ee6d4862`.

Reference: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` from `refs.lock.toml`.

Independent checked-in oracle: n64-systemtest `196f5421173220eb2f63a7a99c64795dc0ea0698`.

Research branch: `research/sb-sh-mutation-gpt56`.

Executable experiment: `spikes/033-ares-sb-sh-stores-gpt56/`.

## Question and hypothesis

Plaid's historical CPU executable-store sensing started from a narrow aligned-`SW` case. The bounded question here is whether ordinary `SB` and `SH` are independently capable of materializing or patching executable bytes, and which post-translation/cache facts must be preserved so their byte effects can be attributed soundly.

Starting hypothesis:

1. `SB` and `SH` are real mutation classes missed by an aligned-`SW`-only observer.
2. Successful uncached identity-RDRAM stores synchronously change backing at the post-endian physical lane, while cacheable stores initially change D-cache residency only.
3. Reverse-endian operation changes the physical sink (`Byte: paddr ^ 7`, `Half: paddr ^ 6`), so guest virtual address plus payload is insufficient to name the backing bytes.
4. Odd-address `SH` and failed translation reject the store before any cache/backing mutation.

All four claims are validated for the exact pinned ares path and fixture matrix below.

## Exact pinned source map

### Instruction handlers

`ares/n64/cpu/interpreter-ipu.cpp`

- `CPU::SB` performs one `write<Byte>(rs + imm, rt)`.
- `CPU::SH` performs one `write<Half>(rs + imm, rt)`.

Unlike `SWL`/`SWR` or `SDL`/`SDR`, these instructions do not decompose into multiple subwrites in pinned ares.

### Translation, endian transform, and sink routing

`ares/n64/cpu/memory.cpp`

- alignment/address validation happens in `devirtualize` before the concrete sink;
- `reverseEndianPaddr<Byte>` is `paddr ^ 7`;
- `reverseEndianPaddr<Half>` is `paddr ^ 6`;
- after translation/endian mapping, cacheable writes route to `dcache.write`;
- uncached writes route synchronously to `busWrite`.

Therefore the useful destination identity for provenance is the translated **post-endian physical sink**, not merely the original guest effective address.

### D-cache behavior

`ares/n64/cpu/dcache.cpp`

- a cacheable store fills/hits the selected line, then updates resident bytes and dirty state;
- raw RDRAM backing is changed later by writeback, not by the immediate store;
- for these naturally aligned one-write `SB`/`SH` cases, the observed dirty mask matched the exact post-endian touched lanes in every tested cached case.

That last statement is intentionally narrow. Separate `SWL`/`SWR` research already found byte-mask counterexamples in pinned ares, so `DataCache::Line::dirty` must **not** be promoted to a universal byte-provenance oracle.

### RDRAM byte layout

`ares/n64/memory/msb/writable.hpp`

- byte writes address one backing byte directly;
- half writes naturally align and store the low 16-bit payload MSB-first;
- the experiment reads raw RDRAM separately from guest CPU reads so reverse-endian address presentation cannot hide the actual physical sink.

## Independent reverse-endian oracle

Pinned n64-systemtest `src/tests/endian_re/mod.rs` contains a real reverse-endian **user-mode** store matrix. It includes both `SB` (`0x81`) and `SH` (`0x92a3`), runs cached and uncached TLB mappings in 32- and 64-bit user modes, writes back cached data before checking backing, and computes the expected physical destination with the same width-dependent transforms:

- 1 byte: `vaddr ^ 7`;
- 2 bytes: `vaddr ^ 6`.

The test then compares backing bytes with the big-endian byte representation of the stored value. This is independent checked-in expected-value evidence for architecturally legal RE operation. This session did **not** execute n64-systemtest on physical N64 hardware, so it is not presented as a new hardware measurement.

## Executable experiment

The Plaid spike contains:

- `model.py`: independent lane/effect model;
- `driver.cpp`: headless exact-pinned ares execution with CPU and RSP recompilers disabled;
- `run.py`: exact-reference build, repeated execution, byte/cache/fault assertions, deterministic result hash;
- branch-only GitHub Actions workflow `.github/workflows/research-sb-sh-stores.yml`.

No ares CPU/memory source is patched or instrumented for this experiment. The driver directly invokes the original pinned handlers, so an instrumented-vs-uninstrumented neutrality comparison is unnecessary. Every logical case is nevertheless executed twice and byte-for-byte JSON equality is required.

Independent model command:

```text
python3 spikes/033-ares-sb-sh-stores-gpt56/model.py
```

Result:

```text
PASS: 32 SB/SH lane cases + two construction families
model_sha256=f26ef0dbd888a8d45cbf32a4edb8499386537a01182da649c94737f0387b42e3
```

Exact-reference command:

```text
python3 spikes/033-ares-sb-sh-stores-gpt56/run.py
```

GitHub Actions run `37849726717`, job `113559360729`, tested branch commit `6cbd2e09b8404fda8339541a2bae87b27e8200fc` against exact ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` and reported:

```text
PASS: 100 repeated pinned-ares SB/SH cases
results_sha256=d3a96c83470d7c0a69dc28877dac5338492c792886c4fba9513503a08b5d3bae
```

The 100 logical cases are:

- 2 endian contexts;
- 2 store opcodes;
- 8 offsets;
- 3 destination/failure modes (`uncached`, `cached`, `tlbmiss`) = 96 cases;
- plus four arbitrary-word construction cases (`SB` x4 and `SH` x2 in both endian contexts).

A prior workflow run `37849695140`, job `113559256181`, independently produced the same model and exact-reference hashes.

## Findings

### 1. Aligned `SW` observation is insufficient even without partial-word stores

One `SB` changes one executable byte. One aligned `SH` changes two executable bytes. More strongly, the exact pinned-reference construction fixture materializes guest word `0x11223344` using either:

- four `SB` instructions; or
- two aligned `SH` instructions.

No `SW`, `SWL`, `SWR`, `SD`, `SDL`, or `SDR` is involved. Therefore executable immutability cannot be inferred from the absence of aligned word stores.

### 2. Reverse endian moves the physical byte origin/sink

For the identity-RDRAM fixture, successful big-endian stores target the translated physical address directly. In the controlled little-endian handler context:

- `SB` offset `o` targets raw lane `o ^ 7` within the 8-byte window;
- aligned `SH` offset `o` targets raw lanes starting at `o ^ 6`.

All corresponding exact ares cases matched the independent model. The pinned n64-systemtest RE matrix independently encodes the same transforms for real user-mode execution.

A provenance witness that records only source PC, opcode, guest virtual address and payload can therefore name the wrong backing bytes. Preserve the post-endian physical sink (or enough context to reproduce it exactly).

### 3. Cached mutation and backing mutation are different chronological facts

For every successful uncached case, raw RDRAM changed synchronously at the expected physical lanes and the uncached architectural read returned the new value.

For every successful cached case, the cached read returned the new value and the expected D-cache dirty bits were set, while raw RDRAM remained unchanged and the uncached alias still returned its pre-store value at the immediate checkpoint.

Thus an architectural `SB`/`SH` completion is not automatically an RDRAM backing-write witness. Cached executable-byte provenance still requires a later verified D-cache writeback join.

### 4. Tested alignment/TLB failures mutate nothing

- odd-address `SH` raises Address Error Store (`Cause.ExcCode = 5`) before raw RDRAM or D-cache dirty state changes;
- aligned `SH` to the unmapped test address raises TLB Store Miss (`3`) before mutation;
- every `SB` TLB-miss case likewise raises `3` before mutation;
- odd `SH` in the TLB-miss mode still reports the alignment error first, matching the source ordering.

No tested failure left a partial mutation because `SB`/`SH` each contain only one concrete typed write after successful validation.

## Plaid implication

The existing executable-mutation abstraction should be generalized around successful byte effects rather than extended with another opcode-specific flag. For CPU stores, a useful normalized event should preserve at least:

```text
observer chronology key
source CPU PC / architectural store identity
guest virtual effective address
translated pre-endian physical address (if useful diagnostically)
post-endian physical sink address
width and payload bytes
cacheable vs uncached route
sink identity: D-cache residency vs backing bus/RDRAM
cache-line identity/generation for cached residency when available
later backing-writeback join when the actual backing transaction occurs
```

The `SB`/`SH` result composes with the already integrated SWL/SWR and SD/SDL/SDR results: the correct direction is a general byte-range mutation/provenance model, not a growing list of special-case opcode booleans.

## Limitations / remaining unknowns

- The exact ares little-endian cases directly set the CPU context endian field while using direct KSEG aliases. They are controlled handler/memory semantic probes, not a claim that little-endian kernel KSEG operation is normal N64 software. The pinned n64-systemtest source supplies the independent architecturally legal reverse-endian user/TLB oracle.
- This scope does not cover `SC`/`SCD`, COP1 stores, RSP stores, arbitrary MMIO/device sinks, arbitrary TLB histories/address modes, asynchronous cache-state changes, DMA/copy/decompression provenance, instruction-cache visibility, or later executable lifetime closure.
- The fixture uses identity-mapped RDRAM backing and a bounded 8-byte lane window. It does not prove every device/bus target has equivalent failure or write-completion semantics.
- The exactness of D-cache dirty bits observed here must not be generalized beyond naturally aligned `SB`/`SH`; existing SWR counterexamples already disprove that broader assumption.
- No physical N64 hardware was newly measured in this session.

## Recommendation

**ADOPT** the semantic requirement: executable-write observation must cover `SB`/`SH` through a general byte-effect event that distinguishes guest intent, post-endian physical sink, cache residency and backing chronology. Do not merge the research branch wholesale; transplant the event-model/test requirements into the current integrator state and compose them with the other store-family and cache-writeback results.

## Primary integration reproduction (2026-10-09)

Retained original gpt56 fixture from `6fd2107`; the independent gpt56sol fixture
is retained in `research/ares-sb-sh-executable-mutation-independent.md` and its
separate numbered directory, avoiding the workers' shared note filename.
Primary lane/construction model matches SHA-256
`f26ef0dbd888a8d45cbf32a4edb8499386537a01182da649c94737f0387b42e3`.

Primary exact-reference execution also passes all 100 repeated cases, including
both instruction-word construction families, with exact worker result SHA-256
`d3a96c83470d7c0a69dc28877dac5338492c792886c4fba9513503a08b5d3bae`.
The initial local attempt collided with the independent runner's same ignored
output directory (ETXTBSY); this runner now uses a distinct `gpt56` output root.
The isolated replay establishes the semantic receipt independently of that
integration defect. No prior ignored evidence is deleted.
