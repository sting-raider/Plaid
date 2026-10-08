# Unified cache/backing/fetch order spike

Verdict: **PARTIAL**.

Base Plaid commit: `3cf45dc323cbcd9e6463ccc781d3de093a433097`  
Pinned ares revision: `9408cb43d4948fc3ea6e152a307a34348df3fe04`

## Hypothesis

The existing completed identity-RDRAM burst, I-cache fill, CACHE-operation and
instruction-fetch hooks can be placed on one monotonic sequence without changing
guest state, and that sequence is sufficient to witness the backing transaction
before each measured fill/writeback/fetch in the controlled spike-015 fixture.

The first half is supported for cached fills/writebacks. The second half is false
for the fixture's final uncached instruction fetch: the current RAM hook observes
only `readBurst`/`writeBurst`, while uncached instruction fetch uses an ordinary
word read.

## Exact source-order evidence

At the pin, the interpreter path is synchronous:

- cached miss: `CPU::fetch` -> `InstructionCache::fetch` -> `Line::fill` ->
  `busReadBurst<ICache>` -> MI RDRAM burst -> `RDRAM::Writable::readBurst`;
  the existing RAM callback is after the returned words, and the fill callback is
  after `busReadBurst`. `CPU::instructionPrologue`, which drives the fetch tracer,
  is called only after `CPU::fetch` returns. Therefore the controlled path orders
  **RAM burst read < fill completion < fetch observation**.
- CACHE fill (`0x14`) calls `Line::fill` before the generated completed-operation
  callback, so **RAM burst read < fill completion < CACHE-op completion**.
- CACHE hit writeback (`0x18`) calls `Line::writeBack` -> `busWriteBurst<ICache>`;
  the existing RAM write callback is after the data stores and hidden-RAM update,
  and the CACHE-op callback occurs only after the handler completes. Therefore
  **RAM burst write < CACHE-op completion**.
- uncached `CPU::fetch` returns `busRead<Word>(paddr)`. For identity RDRAM that
  reaches `RDRAM::Writable::read<Word>`. Spike 016's generated RAM hook has no
  ordinary-read callback, so the final uncached fetch has **no backing event** to
  order, even though source control flow places the read before the tracer.

Relevant pinned Git blobs checked during this experiment:

- `ares/n64/cpu/cpu.cpp` `41964d49c8983ae9a97b25625174cd4c4316c4a8`
- `ares/n64/cpu/memory.cpp` `f362ef67ab41ccf57330bbedd6f614e07a61dd17`
- `ares/n64/cpu/interpreter-ipu.cpp` `938ccbd0af1f127439d9859c1fd6be2bbd5222a3`
- `ares/n64/memory/bus.hpp` `367308207719c1048daa1bbf7ffca635ca0c97d5`
- `ares/n64/mi/bus.hpp` `2d61fa47b6ae568390df421036df4ffefd23b4e5`
- `ares/n64/rdram/rdram.hpp` `c718ec2e9b2a78610353562cbc81dd973b278ee2`

## Experiment

Run:

```bash
python spikes/018-ares-cache-order/run.py
python spikes/018-ares-cache-order/source_guard.py
```

`run.py` is an executable ambiguity/call-order model, not an N64 CPU oracle. It
exhaustively enumerates total orders admitted by the current separate sensor
families, then applies only the pinned synchronous source constraints. Results:

- one cached miss represented as separate RAM/fill/fetch arrays admits 6 total
  cross-family orders; exactly 1 obeys the pinned call order;
- one burst write plus completed CACHE op admits 2 cross-family orders; exactly 1
  obeys the pinned call order;
- two equal-address/equal-payload refills admit 6 cross-family interleavings, so
  payload equality cannot substitute for chronology;
- a shared monotonic sequence removes that serialization ambiguity without
  changing the modelled RAM/cache state;
- the final uncached fetch still has no RAM backing event, proving that an ordinal
  cannot repair missing provenance.

Local result digest from this worker:
`5246474a8eda3d950d3d5212740c0676213d97457700e66e049b2be142fd4940`.

`source_guard.py` is intended to run from a normal Plaid checkout with the pinned
`.refs/ares` present. It asserts the exact pin is clean, the relevant call-order
markers still occur exactly once, and the Plaid builder still has burst-only RAM
callbacks. This worker's sandbox had neither a mounted `.refs/ares` checkout nor
working direct GitHub DNS, so only Python syntax compilation of that guard was run
here. Existing spikes 015/016 remain the full-core neutrality evidence for the
individual hooks; this experiment does **not** pretend to have rerun that core.

## What this disproves

Do not treat the existing independent arrays, fill IDs, matching payloads or the
source-level knowledge that an uncached read occurs as a complete chronological
backing witness. A source proof can explain expected callback nesting, but a
portable trace intended for later rechecking needs the event chronology itself,
and provenance still requires the backing event to exist.

## Recommendation

**INVESTIGATE**, with a narrow next implementation:

1. introduce one capture-wide monotonic sequence shared by raw fetch, completed
   fill, completed CACHE-operation and actual RAM transaction events;
2. extend the actual identity-RDRAM transaction sensor to successful ordinary
   reads/writes needed by uncached instruction access, retaining requestor, width,
   address and returned/stored bytes;
3. rerun spikes 015, 016 and 017 with plain/traced/repeated checkpoint equality;
4. only then design production lifetime joins. Unsupported translated/degraded,
   reset/restore, DMA/copy and mutation paths must remain unknown.

This result does not establish hardware timing, an executable generation, cache
lifetime, ROM origin, retirement or closed-world completeness.
