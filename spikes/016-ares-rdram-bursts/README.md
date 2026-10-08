# Actual identity-mapped RAM bursts

Hypothesis: existing successful identity-mapped RAM burst reads/stores can supply
backing transaction witnesses for the measured cache fills/writeback, without
another guest read or clock. Sample the existing returned/input words after the
actual read/store and hidden-memory update. Reuse spike 015's controlled cases.

Run `python spikes/016-ares-rdram-bursts/run.py`.

## Verdict: VALIDATED for successful identity-mapped bursts

### Evidence

Four completed RAM burst reads match the four fills, followed by one completed
RAM burst write at 0x4000. All five transactions retain 32 bytes/eight words and
the instruction-cache requestor; returned/stored words are exact. Out-of-bounds
zero reads and ignored writes supply no valid backing witness. Plain/traced/
repeated complete checkpoints and the prior full JSON projection match exactly.
The prior projection SHA-256 is
`63d27623769528d7147d051c8f8597ff71ffb59ad78bdffc901accdaf9d164b9`.
Count=257, with unchanged RAM/cache hashes. A fresh default-observer spike 015
rebuild also retains its goldens. A recipe-only regression separately checks
enabled/disabled/enabled directory reuse removes stale shadow headers; it stubs
compilation and makes no CPU execution claim.

### Constraints and surprises

This sensor covers successful identity-mapped bursts only. It deliberately emits
no witness for translated/degraded paths or unsuccessful accesses. Ordinary and
ebus stores, CPU/PI copies, reset/restore and unified chronology remain separate.
RAM transactions do not establish ROM origin or executable lifetime.

### Recommendation

Verify mapping/failure boundaries and unified transaction/fill/mutation/fetch
ordering before broader source/lifecycle or production handling.
