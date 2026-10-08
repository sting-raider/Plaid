# PIF ROM backing provenance experiment

Result: **MODEL_VALIDATED / overall PARTIAL**

This experiment attacks one narrow question: when an ares VR4300 instruction fetch
returns a word from the physical PIF window, what evidence is sufficient to say
that the word actually came from the supplied PIF ROM bytes?

It does **not** model general N64 execution, timing, boot equivalence, cache state,
or PIF-HLE correctness. It is an independent executable model of the exact
routing/source predicates inspected at pinned ares revision
`9408cb43d4948fc3ea6e152a307a34348df3fe04`.

## Falsifiable hypothesis

A firmware-origin witness is sound for this bounded path only when a CPU fetch
context is active and the same access reaches the successful unlocked PIF ROM
backing read. Physical address, returned value, current firmware contents, or a
prior PIF read are insufficient substitutes.

The hypothesis is falsified if any modeled path emits a firmware witness for:

- SI `ioBusy` / `busLatch` return;
- PIF ROM lockout;
- PIF RAM;
- cached non-RDRAM fetch rejection;
- an address outside the SI/PIF window;

or if a genuine mirrored PIF ROM read cannot identify its actual masked firmware
offset.

## Pinned source map

At the pinned ares revision:

1. `ares/n64/cpu/cpu.cpp`: the interpreter resolves `PhysAccess`, then calls
   `fetch(access)`. Only after `fetch` returns does it call
   `instructionPrologue(ipu.pc, *data)` / the existing debugger observer.
2. `ares/n64/cpu/memory.cpp`: uncached fetches use `busRead<Word>(paddr)`;
   cached fetches use `icache.fetch`. Reverse-endian mode may alter `paddr`
   before either path.
3. `ares/n64/memory/bus.hpp`: ordinary N64 bus reads route physical
   `0x1fc00000..0x1fcfffff` through SI. Non-Aleck64 cache-line burst reads accept
   RDRAM only, so cached PIF fetches are rejected rather than delegated to PIF.
4. `ares/n64/si/io.cpp`: SI returns `io.busLatch` early when `io.ioBusy`; only
   the non-busy path calls `pif.read<Word>(address)`.
5. `ares/n64/pif/io.cpp`: `PIF::readWord` performs `intA(Read, Size4)` and then
   `readInt`; `readInt` masks `address &= 0x7ff`. Offsets `0..0x7bf` read ROM
   unless `romLockout`, which returns zero. Offsets `0x7c0..0x7ff` read PIF RAM.
6. `ares/n64/pif/pif.cpp`: PIF ROM allocation is `0x7c0` bytes and power loads
   the region-specific PIF ROM into that backing object.

These facts imply that `physical - 0x1fc00000` is not the firmware offset for
all valid PIF reads. For example, `0x1fc00800` and `0x1fcff800` both mask to ROM
offset zero.

## Harness

`witness_model.py` uses no ares code and no firmware bytes. With no `--firmware`
argument it creates a synthetic 1,984-byte fixture containing deliberate equal-
value collisions and a zero word. It models only the source-selection conditions
above and creates a witness **only** on the modeled successful PIF ROM backing
read.

The optional `--firmware` argument accepts a local PIF ROM only if it is exactly
1,984 bytes and has SHA-256:

`fa7b09795ef1e54461e59f6f2d902368133e3f1cd980e34383e6a780d74beffd`

The firmware is never copied into output.

Run:

```sh
python3 experiments/pif-rom-backing/witness_model.py --fuzz 1000000 \
  > /tmp/pif-rom-backing.json
python3 -m py_compile experiments/pif-rom-backing/witness_model.py
```

Deterministic synthetic run, seed `0x504946`:

- iterations: 1,000,000
- positive ROM witnesses: 92,583
- negative/non-ROM cases: 907,417
- positive reads using mirrored physical addresses: 92,426
- predicate violations: 0 (assertions would terminate the run)
- harness SHA-256: `4b35066e8bfc6e2bfc9064bba38e2ecb6ec4a199ca6bf112f6fc63677eaab036`
- JSON output SHA-256: `0fc0d77daa8b3c745eba67d40954a7ec7a7b253370527c55f98abf1270f09476`

Targeted adversarial cases cover:

- natural power-entry physical address `0x1fc00000`;
- final PIF ROM word at masked offset `0x7bc`;
- two mirrored addresses mapping to firmware offset zero;
- PIF RAM returning the same 32-bit value as firmware offset zero;
- SI busy latch returning the same value as firmware offset zero;
- ROM lockout returning zero while real unlocked firmware offset four also holds
  zero;
- cached PIF access rejection;
- both sides of the SI/PIF bus-window boundary;
- prevention of witness carry-over from an earlier real PIF read into a later
  same-value latch return.

Two intentionally bad policies are tested and rejected:

- infer firmware source by matching the returned value against firmware contents;
- infer firmware offset as `paddr - 0x1fc00000`.

## Minimum event needed by a future ares sensor

A trustworthy fetch-source join needs a temporary per-fetch context opened before
`CPU::fetch(access)`, because the existing instruction observer executes after the
backing read. A successful PIF ROM event should be emitted only on the
`rom.read<Word>` branch after masking and lockout checks, and should include at
least:

- fetch/context ID;
- guest PC / access identity;
- actual physical address supplied to the bus after endian handling;
- masked PIF ROM offset;
- returned 32-bit word;
- explicit source kind identifying PIF ROM backing.

The context must not be reused for DMA/HLE reads that also reach `PIF::readInt`.
SI-latch, lockout, PIF-RAM, failed/cached paths produce no firmware-origin event.
A later importer must still verify the offset/word against the explicitly supplied
firmware hash and bytes.

## Why overall result is PARTIAL

The source predicate and adversarial model are validated, but this worker did not
rebuild and run an instrumented full pinned ares binary. Therefore instrumentation
neutrality, exact event plumbing through the existing boot observer, and an actual
supplied-firmware capture remain unverified in this branch. Existing Plaid boot
spikes already establish the uninstrumented/traced CPU-state baseline and supplied
firmware identity; they do not establish this new backing-read event.

No production identity, image generation, lifetime, or closed-world certificate
should be promoted from this experiment alone.
