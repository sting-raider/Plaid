# Plaid host runtime

`plaid_rt.c` is Plaid's own libultra host runtime (ADR-0158, ADR-0159), licensed
MIT OR Apache-2.0. It implements the declared runtime functions
(`plaid_rt_<name>`) that lowered code calls.

It is built as one translation unit with a lowered program that was compiled with
`PLAID_SAFEPOINTS`:

```bash
plaid lower-map <rom.z64> <map.json> <entry> <exit> game.c
gcc -O1 -std=gnu11 -DPLAID_SAFEPOINTS -DPLAID_LOWERED='"game.c"' -I . runtime/plaid_rt.c -pthread -o game
./game --rom <rom.z64> [--stop-at gfx|none] [--gfx-tasks N] [--seconds S] [--dump <addr> <words>]
```

## Model

- **Threads.** Guest threads run on host threads, but only the holder of a
  single baton executes guest code. A handoff swaps the CPU register file.
  Scheduling follows libultra:
  - priority order, FIFO within a priority;
  - preemption when a thread is started or woken at a higher priority;
  - a yield when a thread lowers its own priority.
- **Events.** VI retrace runs at 60 Hz. Timers, SP and DP completion, SI and
  PI are posted by host sources and delivered by the baton holder at a
  runtime call or a loop-header safepoint.
- **Guest RAM writes.** All writes go through `plaid_runtime_write`, so
  executable bytes and verified declared loads stay protected.
- **Graphics and audio tasks.** For now these complete immediately. RT64 will
  consume graphics tasks in a later step.

## Tests

`python runtime/test_runtime.py` runs a synthetic multi-thread program and
checks libultra's scheduling order, including VI preemption of a spinning
thread.
