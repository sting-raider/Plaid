# Actual PIF-ROM backing in boot chronology

Hypothesis: only the existing completed PIF ROM bank read inside an uncached CPU
fetch interval supplies backing offset identity. SI busy-latch, PIF lockout/RAM
and cached paths must remain without that witness despite equal payloads.
Delegated write attempts to read-only ROM must remain distinct from mutations.

## Verdict: PARTIAL

The 10,000-call v4 capture preserves every prior v3/v2/v1/v0/v5 source and
independent reference/disabled/repeated checkpoint. Its 2457 PIF bank reads supply
2055 exact fetch witnesses. Thirteen actual component adversaries validate read
paths and no-effect write attempts. Full-prefix rechecking remains in progress.
See `research/bounded-boot-pif-history.md` for measurements.
Generated separately licensed exact-reference sources, binaries and supplied
ROM/firmware stay ignored. The callback consumes an existing read result or delegated
write-attempt payload and performs no guest access, translation or clock step.

## Constraints and surprises

The actual write probe falsified the initial mutable-ROM hypothesis: pinned ares
uses `Memory::Readable rom`, whose Word write is a no-op. Unlocked delegates
therefore produce write-attempt metadata; locked writes skip even that delegation.
Both preserve the backing. Current backing identity and equality to supplied
firmware remain separate facts in the presence of out-of-band mutations. A
fixed finite boot prefix is not a mutation/lifetime or whole-ROM certificate.

## Recommendation

Require complete prior v3/v2/v1/v0/v5 source equality, independent reference/
disabled/repeated checkpoints and strict source-bound read/attempt replay before
promoting this composition. Keep unknown and uncertified paths explicit.
