# Spike 033: ares PI dispatch identity sidecar

Status: **PARTIAL**

This spike models the exact binary-min-heap mutation semantics of pinned ares
`nall/nall/priority-queue.hpp` at
`9408cb43d4948fc3ea6e152a307a34348df3fe04`, while keeping provenance identity
in a parallel sidecar. It asks whether spike 032's insertion tokens can survive
heap motion far enough to join a PI scheduling request to the exact row removed
at CPU dispatch.

## Run

```sh
python3 spikes/033-ares-pi-dispatch-identity/run.py
```

The run is dependency-free and deterministic. It performs explicit adversarial
cases plus 200,000 seeded mixed insert/cancel/step/reset operations. After every
random operation, the instrumented queue's emulator-visible state is asserted
equal to an uninstrumented baseline model.

Recorded result: `result.json`.

## What it establishes

- Identical `(absolute clock, event)` rows receive distinct insertion tokens and
  those exact tokens reach removal/dispatch in order.
- Heap insertion, removal repair, compaction and slot reuse do not break a
  parallel token sidecar if every upstream heap copy is mirrored.
- `remove(event)` tombstones can be attributed to the exact token before
  invalidation; later invalid-root removal does not produce a CPU callback.
- A queue-capacity failure must produce no request-to-token association.
- Tuple-only, slot-only and pointer-to-array-slot identity are unsound.

## Counterexample

Current spike 032 treats serializer observer event `kind == 9` like reset and
clears every token regardless of serializer direction. Pinned N64
`System::serialize` serializes `queue` on both save and load. Therefore saving a
state while a PI DMA event is pending is enough to erase the token before the
future completion is removed. The deterministic counterexample records request
token `1` before save and dispatch token `0` afterward.

This means the normal-run request -> insertion -> dispatch bridge is viable, but
it is not globally sound across current savestate hooks.

## Hashes from the recorded run

- `run.py`: `9012434365634d41232dd0ba859ec7e700db7dfb9223cce77d3c3874f9918256`
- `result.json`: `5646526ba8db6d69e5ba78f8d2f3d6b2611a37f9c3a1ed7a68cbf347887f6276`
- visible-state trace SHA-256 (inside result):
  `b10f8a5d4c4f3de8e64519b9d7665d0fa360ba937a0fab465506cb9265690d79`

See `research/ares-pi-dispatch-identity.md` for the source-level join and
integration constraints.
