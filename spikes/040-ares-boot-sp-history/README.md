# Observed CPU SP backing in bounded boot chronology

Hypothesis: actual completed SP Word reads can join uncached CPU fetch contexts
in the boot ledger while preserving every prior source byte and machine state.
Normalized CPU/SP-DMA storage effects must remain separate from ultimate origin.

Run `python spikes/040-ares-boot-sp-history/run.py --budget 10000` with the existing
ignored homebrew ROM/firmware. Use `--budget 610000` for the longer retained
prefix, or `--verify-existing` to recheck complete saved sources. Generated
licensed reference shadows and raw artifacts stay under ignored `target/`;
the exact clean ares pin and both disabled recompilers remain mandatory.

## Verdict: VALIDATED for the 10,000-call composition

The original optional sensor emits access-history v3. Its strict projection
removes only SP rows, renumbers raw fetch contexts and preserves exact complete
v2/v1/v0/v5 validation. The new fields are actual SP Word read/write address,
bank, modulo-bank aligned offset, normalized width/payload and CPU caller; DMA
stores retain actual RAM-side address, width/payload and selected backing.
No callback performs a guest access, translation or clock step.

The 10,000-call capture has 39,862 records, including 9857 SP Word events and
7945 exact SP-backed fetches. The remaining 2055 fetches are PIF. Prior complete
v2/v5 bytes, messages and all unchanged-reference/disabled/enabled/repeated
reported checkpoints agree. Repeated raw history is byte-identical.

Raw v3 SHA-256:
`68bca462a34e1e0511e82b09ff939c5b1f5ff601eba1389f6fefddf4a3a03f2e`.
Independent Python report SHA-256:
`af63ce040b13753a441d895048d8e79c5e8a64a5ccf1491fc4dabd04fa27f8e5`.
Eleven synthetic forgeries fail; missing, duplicate, foreign and cached reads
stay unknown. DMA receipts cannot cross intervening unrelated events, and
missing or ambiguous source receipts stay unbound.

## Constraints and surprises

A bank read identifies current backing, not firmware/ROM producer lineage. CPU
DMEM execution can encounter ordinary RSP DMEM mutations outside these callback
points. Sample endpoints are observations, not continuous lifetimes. Source
coverage, reset/restore, DMA request identity and general hardware behavior remain
separate from this fixed NTSC/6102/8-MiB/deterministic/PIF-HLE prefix.

## Recommendation

Recheck the full retained prefix and expose a strict original Rust consumer with
the complete nested source report. Keep ProgramMap/solver behavior and every
mutation-coverage/lifetime/native flag unchanged. Compose actual PIF reads and
SP producer history next.
