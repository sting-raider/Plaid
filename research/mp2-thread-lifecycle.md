# Parked SDK thread recreation (ADR-0268)

Base: `3be12c018058f1e31609a00eb403444f3e7341e7`.
Lane: `mp2-thread-deadlock-7206d280`; issue #4 carries claim and closeout.

## Reproduction and exact sequence

The requested bare `python scripts/native.py <local MP2> --rt64 --seconds 30`
was attempted first, with silent audio and bounded native execution. Analysis
stops before launch: `copy-call map has stale load declarations; rediscover
first` (193.591 s). ADR-0267 trims replay text in discovery; infer-call-loads
still compares the map to untrimmed declarations. This separate pipeline
problem remains explicit. The runtime bug is reproduced with ADR-0267's
diagnostic-free artifact and a new synthetic lowered program.

At the 30-second debugger observation the baseline is black, VI 520,
graphics 504/audio 515, PI 48, fault 0, fault_pc 00000000, pc 00000000,
RA 80016174. External watchdog termination is necessary. Thread 3 is in
rt_osCreateThread -> pthread_join while holding big. The old host is in
wait_for_baton -> pthread_cond_wait. Its slot is T_DEAD, generation 9,
contexts 1, priority 110, ID 0, entry 800161d4, OSThread 800d7920, previous
wait queue 800d7b08. This old context is a root, not a live coroutine;
thread 3 independently owns four contexts.

A separate breakpoint trace records:

- VI 4: thread 3 creates 800d7920, ID 0, entry 800161d4, RA 80016174.
- VI 521: thread 3 destroys 800d7920, RA 800161ac.
- VI 523: thread 3 recreates the same object/entry, RA 80016174, and hangs.

Breakpoint overhead shifts VI slightly; the uninstrumented stop is VI 520.
External destroy only marks the slot dead, leaving its host parked. Joining
it while big is held prevents both host retirement and event-pump progress.

The SDK [create/destroy reference](https://ultra64.ca/files/documentation/online-manuals/man/n64man/os/osCreateThread.html)
defines stopped-context initialization and removal from scheduling/message
queues. A destroyed context cannot complete an old receive. Ordinary stop/start
preserves its continuation; creation replaces it. Pinned N64ModernRuntime
`cdf5abbd5026fef5c364c676e4667c45e42b6863`, ultramodern/src/threads.cpp,
independently checks context replacement before guest execution on wake.
COPYING is GPL-3.0; no reference code was copied.

## Lifetime invariant and deterministic tests

Each SDK thread lists every root/coroutine context. Teardown removes wait/run
eligibility and invalidates saved buffers. Parked hosts wake only to unpin
their owned lowered frames, unlink/free their contexts and acknowledge exit.
The caller's condition wait releases big while retaining its guest baton.
Creation waits for all acknowledgements before reinitializing the slot.
Root hosts are detached and receive their immutable context pointer at
launch. Normal entry return and self-destroy use the same retirement path,
including a live coroutine's suspended root. No pthread_join is needed.

`python runtime/test_thread_lifecycle.py` covers four cases: stopped root or
blocked live coroutine, directly recreated or destroyed then created. Each
runs 140 iterations, crossing the 256-context cap if abandoned stacks leak.
It checks priority/ID, reset next/queue fields, new argument delivery, FIFO
messages, old-body sentinels, self-destruction (also from a live coroutine),
and released text pins by overwriting the old root/coroutine body. Native
invocations have 10-second timeouts. Before the fix, stopped-root recreation
times out at 10 seconds. Afterwards all variants pass. A private runtime
copy disables the retirement guard and must time out at two seconds;
production sources are not mutated. The full runtime gate includes it.

Retained coroutine tests still compare all GPR/FPR/PC/HI/LO/FCSR and 64 KiB
RAM to pinned ares, plus foreign-owner pin/unwind behavior. Foreign, expired,
incompatible and stale-generation continuations remain refused. The old
live-destroy refusal is superseded by positive tests; running-thread
self-reinitialization remains refused.

## Native observations and validation

Every game window is visible; SDL_AUDIODRIVER=dummy applies to every native
run. Process timeouts/watchdogs bound all runs. No shared shim rebuild,
reference refetch or protected-junction removal occurred. ROMs, saves and
copyrighted captures remain ignored.

Runtime rebuild: 57.690 s. First fixed run: 31.867 wall seconds under local
compilation, VI 1748, graphics 2914/audio 1741, fault 0/fault_pc 00000000.
A quieter 30-second visual run reaches VI 1797, graphics 3048/audio 1789,
fault 0, showing Toad's theater intro and Mario Land. Baseline cannot finish
its 30-second time limit: it stalls after about 8.7 seconds of guest retraces.

Start/A run:

```
--seconds 30 --press 0x1000@600:4 --press 0x1000@1250:4
--press 0x8000@1360:4 --press 0x8000@1440:4 --press 0x8000@1520:4
--press 0x8000@1600:4 --press 0x8000@1680:4 --press 0x8000@1760:4
```

It reaches destination selection with Toad asking to choose a destination,
and completes at VI 1798, graphics 2351/audio 1788, PI 2133, fault 0,
fault_pc 00000000, RA 8007c104. A prior press run reaches title/Press Start,
VI 1798, fault 0. Board gameplay and complete closure are not established.

The native.py discovery/build/run also completes with the previously inferred
ROM-derived `--loads X:/Plaid/target/win-oracle/target/native/marioparty2usa/loads.json`:
218.879 s total, VI 1767, fault 0/fault_pc 00000000, eight residual sites.
Generated CPU/RSP bytes are compared before reusing their unchanged objects;
current runtime objects are rebuilt. This records iteration cost, not a
controlled compiler speedup. The bare pipeline's stale-load refusal remains.

Five 30-second PM/BK/MM/SF64/OoT controls and the 60-second OoT save-load
sequence use regenerated, byte-verified CPU/RSP sources, current runtime,
unchanged shared shim and process watchdogs. OoT uses the retained local SRAM
save with Start@1200 and A@1400/1550/1700/1850, each four retraces.

Ignored evidence under `target/receipts/mp2-thread/`: before-state.log,
sequence.log, baseline.log, test-before.log, lifecycle-final-focused.log,
mp2-visual.log, mp2-menu.log, mp2-menu-28.png, pipeline-after.log,
controls.json, oot-save.json and final-gate.json. Final-gate records the
validated base/tree, exact command exits and timings. Issue #4 records
final outcomes and the canonical SHA.

Full exact-tree local gate:

```
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace
python scripts/test_cli.py
python runtime/test_runtime.py
python tools/progress.py --check
```

The artifact remains native_complete:false. Copied/incompatible jump buffers
and running-thread self-create remain refused. Teardown invalidates an SDK
lifetime; it does not prove liveness of abandoned buffers inside a still-live
generation. Existing 4096 jump-address tombstones and the 256-context cap
remain, preserving stale-generation refusal. Broader gameplay, indefinite
resource use and other host ABIs remain unverified.
