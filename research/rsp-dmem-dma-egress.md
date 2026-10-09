# RSP DMEM producer lineage through SP write-DMA

Date: 2026-10-09

Status: **VALIDATED** for the bounded exact-pin interpreted/identity-RDRAM fixture described below.

Branch: `research/rsp-dmem-dma-egress-gpt56sol`

Plaid base selected from canonical `main`: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Executed research commit: `2a395485b3828badb8e2f68178f626008da9fa61`

Pinned ares revision: `9408cb43d4948fc3ea6e152a307a34348df3fe04`

GitHub Actions evidence run: `37917030869`

## Question

Can actual decoded RSP DMEM store effects be causally exported through a real
SP write-DMA into exact RDRAM byte mutations without relying on payload equality,
while preserving same-value writer generations, vector/partial coverage, a later
CPU overwrite boundary, multi-row skip, and 4 KiB DMEM wrap?

## Hypothesis

For exact pinned ares, a completed identity-RDRAM `RBusDevice::SP_DMA` Word
write can inherit the latest ordered DMEM writer identities for its four source
bytes when all of these are true:

1. the current SP DMA is a write transfer targeting DMEM, not IMEM;
2. the completed RDRAM-write callback occurs inside the exact current fragment;
3. source DMEM offsets are derived from the current descriptor and destination
   lane, not from matching values;
4. DMEM writer generations come from measured completed sink effects;
5. an intervening measured DMEM mutation replaces only the covered byte writers
   before the DMA export.

A same-value RSP store must still advance writer identity. Missing or
unclassified DMEM history, or an RDRAM effect that cannot be joined to the
current descriptor, must remain unknown.

## Exact source contract

The source guard pins and checks these exact files:

- `ares/n64/rsp/dma.cpp` SHA-256 `b5d8a1c4b45c2d84c487d98725caa465ac4b5fbea4761beff51ca1a1ba93d7b6`;
- `ares/n64/rsp/io.cpp` SHA-256 `60cc9b1efb2e90c127098a736c5213ea0bf77d2e3bd6e5b112e55752289af860`;
- `ares/n64/rdram/rdram.hpp` SHA-256 `6a77c2fa0bbb320ff6b2855ea6379541a67096bed6b91cc6cd2697584112b1cf`;
- `ares/n64/memory/memory.hpp` SHA-256 `673de0205f34c3da47095bce162e5706924cb24cddaac3080a2a40e0d444b6eb`;
- `ares/n64/memory/lsb/writable.hpp` SHA-256 `52565f0359450110af0836d37540a7fb8f77cb10a6e444286a5b09c14c8fd2f0`.

Pinned `rsp/dma.cpp` performs each DMEM write-DMA fragment as two
`dmem.read<Word>` calls followed immediately by two
`rdram.ram.write<Word>(..., RBusDevice::SP_DMA)` calls. It advances current
DRAM/PBUS addresses only after those completed writes. Therefore the successful
RDRAM callback can derive the exact source DMEM Word offset from the still-current
DMA descriptor. The emitted payload is checked only afterward as trace
integrity; it never selects the source origin.

Pinned N64 `memory.hpp` selects the `lsb` memory wrapper. Its Byte access maps a
guest address through `address ^ 3`, while Word access uses the aligned host
backing word. This distinction is part of the experiment contract because raw
backing byte indices are not guest logical byte addresses.

## Fixture and chronology

Durable spike: `spikes/043-ares-rsp-dmem-dma-egress/`.

The executed fixture:

1. initializes all 4096 **logical** DMEM bytes through `write<Byte>` with a
   deterministic byte pattern;
2. executes a decoded same-value scalar `SB` at logical DMEM `0x040`;
3. executes a decoded scalar `SW` at `0x044`;
4. executes a decoded vector `SDV` at `0x048`;
5. performs a fixture-known CPU-origin SP-memory Word write at `0x04c`, replacing
   four bytes of the prior vector-produced lineage;
6. executes a two-row SP write-DMA from `0x040..0x04f` to RDRAM rows `0x1000`
   and `0x1010`, with an eight-byte DRAM skip;
7. executes a decoded unaligned `SW` at `0xffe`, wrapping through `0xfff` into
   `0x000..0x001`;
8. executes a 16-byte SP write-DMA from DMEM `0xff8`, whose second fragment wraps
   its source to `0x000`, into RDRAM `0x2000..0x200f`.

The observer records ordered RSP instruction contexts, completed primitive DMEM
sink effects, the fixture-known CPU DMEM overwrite, completed identity-RDRAM
scalar writes, and current SP-DMA descriptor state. It performs no guest memory
reads or clock steps.

The replay verifier chooses each DMA source from descriptor state first, then
looks up the latest ordered per-byte DMEM writer, then checks payload equality
only as an integrity assertion. It separately models competing completed writes
into the declared RDRAM target windows so a later writer would cut resident
lineage instead of being silently ignored.

## Baseline and instrumentation neutrality

`run.py` builds both an unchanged-reference baseline and the observer-capable
exact-pin variant, then runs:

- baseline;
- observer-capable binary with callbacks disabled;
- observer enabled;
- observer enabled again.

The baseline and disabled runs produced empty event histories. All four state
checkpoints were identical, and both enabled runs produced byte-for-byte
identical traces. CI summarized `neutrality: true` and
`repeat_deterministic: true`.

## Adversarial cases

The verifier mutates the measured history and requires rejection for nine forged
cases, including deletion of the same-value writer, source-offset corruption,
current-DMA PBUS corruption, relabeling/deletion of the CPU overwrite, broken RSP
instruction context, vector payload corruption, moving a DMA effect into the
skipped DRAM hole, and chronology corruption.

All 9/9 forged histories were rejected.

## Deterministic observations

Successful exact-pin run `37917030869` at commit
`2a395485b3828badb8e2f68178f626008da9fa61` reported:

- ordered events: **42**;
- completed RSP DMEM primitive sink effects: **17**;
- fixture-known CPU DMEM sink effects: **1**;
- completed SP-DMA RDRAM Word effects: **8**;
- competing completed non-SP-DMA writes in the declared RDRAM windows: **0**;
- same-value RSP sink event sequence: **2**;
- exported bytes attributed to RSP writers: **13**;
- exported bytes attributed to the later CPU overwrite: **4**;
- exported bytes retaining the initial DMEM generation: **15**;
- RDRAM backing: **8388608 bytes**;
- scoped logical destination hash:
  `4702a25853c06b1b082985076830a2e325ebc50965a68c63ce918a5065b0ac14`;
- event-history SHA-256:
  `060e97a1fa347dc1b2a928852491da320040a0dcaee6bf24dd8460de2c285060`;
- raw enabled-trace SHA-256:
  `25248a01ac69ebb9c7f5697a0fb010f632c7a852b5310475d9a7472f9b0dd927`;
- `results.json` SHA-256:
  `03d5138badc899d3b19fe24401199a672db6ce2eb2e1e00957e882bff6e54274`.

Descriptor-derived Word source chronology was exactly:

`0x040, 0x044, 0x048, 0x04c, 0xff8, 0xffc, 0x000, 0x004`.

The first DMA retained `count=1, skip=8` on the first row and `count=0` on the
second row. The second DMA demonstrated the DMEM source wrap from `0xffc` to
`0x000` without using payload matching to infer that wrap.

## Important falsification found during fixture development

Preliminary runs correctly failed the verifier because the first fixture treated
raw ares backing indices as guest logical byte addresses. Pinned N64 ares does
not have that identity for Byte accesses: the `lsb` wrapper uses `address ^ 3`.
Consequently the preliminary "same-value" setup was not semantically entitled
to call itself same-value, and raw destination-window hashes were the wrong
comparison surface.

No hypothesis result was taken from those failed runs. The corrected fixture
initializes, samples, and hashes logical guest bytes through `read<Byte>` /
`write<Byte>`. Raw full-memory hashes remain only as instrumentation-neutrality
checkpoints. The exact LSB mapping is now guarded and hashed so this mistake
cannot silently reappear at the pinned revision.

## Result

**VALIDATED**, within this declared exact-pin controlled scope.

A completed pinned-ares identity-RDRAM SP write-DMA effect can be causally joined
to the latest measured per-byte DMEM writer generation without using equal
payload values to choose provenance. The fixture specifically validates:

- same-value RSP writer generation retention;
- composition of scalar and vector-produced DMEM bytes;
- replacement of only the covered bytes by a later measured CPU-origin SP-memory
  write before DMA;
- multi-row `count/skip` source/destination chronology;
- 4 KiB DMEM source wrap;
- fail-closed rejection of nine damaged histories.

For this fixture's 32 transferred bytes, replay accounted for every byte as
13 RSP-produced, 4 CPU-overwritten, or 15 initial-generation bytes.

## Limitations and explicit non-claims

This result is reference-implementation evidence, not hardware proof. It does
**not** establish:

- hardware timing or DMA atomicity;
- exhaustive coverage of all RSP or CPU mutation forms;
- a general production classifier for CPU-origin SP writes (the CPU overwrite in
  this fixture is explicitly scoped by the harness around a known CPU call);
- IMEM-source write-DMA behavior;
- arbitrary concurrent DMA queue interactions beyond the tested descriptor
  chronology;
- RDRAM-to-executable copying, decompression, relocation, or overlay lifetime;
- instruction-cache visibility;
- reachability or whole-ROM closure.

SP -> RDRAM is only a producer-export edge. A later executable consumer still
needs its own causal join and lifetime proof.

## Reproduction

After fetching the exact ares pin into `.refs/ares`:

```bash
python3 spikes/043-ares-rsp-dmem-dma-egress/source_guard.py
python3 spikes/043-ares-rsp-dmem-dma-egress/run.py
```

The GitHub workflow `.github/workflows/research-rsp-dmem-dma-egress.yml`
performs the same source guard, baseline/disabled/enabled/repeat execution,
replay, adversarial verification, and evidence upload.

## Integration recommendation

**PRIMARY-INTEGRATOR-REVIEW.** Adopt the scoped semantic rule only after primary
reproduction: for a completed DMEM-origin SP write-DMA fragment, derive source
identity from the stable current DMA descriptor at the completed RDRAM effect,
then inherit measured per-byte DMEM writer generations. Do not infer origin from
payload equality, raw backing byte indices, request creation, or stale descriptor
snapshots.
