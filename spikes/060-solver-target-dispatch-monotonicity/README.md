# Target-dispatch monotonicity spike

Current-main baseline is Actions run `37998865273` / job `114051729785`.

The importer-origin `TargetLookup` and `RuntimeLink` cases are OPEN before editing, but become CLOSED after deleting only `uncorrelated_target`; the no-event control remains CLOSED. The trace provenance records remain present.

Candidate invariant: source-uncorrelated target-dispatch primitives must survive independently of derived diagnostics. Retain target, import generation, event kind (`TargetLookup` including `delay_slot_entry`, or `RuntimeLink`), and exact trace provenance in a typed ProgramMap collection. The solver must independently keep such facts OPEN until a future verifier can correlate or otherwise discharge them. PC equality with a decoded target is not correlation.
