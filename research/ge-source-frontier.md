# GoldenEye source frontier after ADR-0281

Research-only continuation based on main `4507fce0`. Nothing in this note or its
experiment authorizes a production source, target set or native-completeness claim.
No ROM bytes, instruction trace, firmware, save or framebuffer assets enter git.

## Unverified affine-source probe

The ignored `target/ge_source_probe.py` tests the observed loader relation without
shipping it as a rule. It is deliberately unverified and never used by native.py.
Four source-expansion rounds produce these residual obligations:

| Added pages | Blocks | Missing direct targets | Unmapped targets | All blockers |
| ---: | ---: | ---: | ---: | ---: |
| 71 | 22069 | 355 | 167 | 1518 |
| 41 | 29868 | 202 | 124 | 1981 |
| 18 | 34579 | 130 | 94 | 2147 |
| 6 | 35407 | 126 | 92 | 2207 |

More source coverage exposes many table and indirect obligations. Applying the
existing production first-use data repair to the last research map lowers invalid
table entries787->32 and total blockers2207->1076, but exposes more code. Its
remaining classes are direct225, unmapped162, indirect567, invalid tables32,
load-straddles39, unsupported slots26, runtime-body conflicts7, callbacks7,
table immutability5, table identity5 and TLBWR1. These are experimental dependency
counts, not production measurements or a prepared integration candidate.

## Letting guest refill code recover unvisited sources

The next hypothesis avoids extrapolating a cartridge offset: after a normal reset
reaches a caller-supplied authenticated anchor, explicitly replace PC once with a
requested missing target. The pinned reference then performs its own exception,
refill, DMA and first fetch. This is a counterfactual compiler-time root, not an
observation that neutral input reaches the target. No guest instruction semantics
are implemented by the adapter and nothing is linked into a native artifact.

Reusable research harness (canonical user-local .z64 only):

```
python experiments/mapped-refill-probe/run.py "<local ROM>" <anchor> <target>...
```

All root addresses are explicit arguments. The generated adapter stays in ignored
target/, uses the existing pinned ares builder and refuses an unauthenticated
anchor. It records the PC alteration in stderr, uses fresh reset for each target
and repeat, checks deterministic repeated rows, and reports raw-ROM byte proposals
from PI-request overlap plus exact payload equality. Equal bytes/request overlap
are not promoted to causal provenance. It never writes a loads file or ProgramMap.

On the GoldenEye USA hash recorded in `ge-blockers.md`, neutral exact replay of
7f010290 and7f08fe74 reaches its100M-call budget at VI136 with both unvisited.
The exploratory roots use natural anchor7f000000 at step67137997/Status2000ff01.
Both forced targets reach first fetch at step67291778/VI103; the guest handler
runs before that first target instruction. Fresh repeats are byte-identical.

| Target | Captured virtual page | Physical page | Size | Raw-ROM byte proposal |
| --- | --- | --- | ---: | --- |
| 7f010290 | 7f010000 | 002fc000 | 4096 | 44b30 |
| 7f08fe74 | 7f08f000 | 002fd000 | 4096 | c3b30 |

Payload SHA-256 respectively:
`0df9f217d79538965c374190550b35f1f3c3c44ecfcae023dfd62d8a4f852f97`,
`4358892947752640be28266f5d70ad899dc1516e5042b305c365022b2a76962f`.
Shifting either proposal by4 bytes fails equality. Initial private probe build
takes77.343s; fresh target probes take2.547/2.078s; neutral replay3.119s (3.297s
wrapper). These are different workloads, not a speedup comparison.

The private first experiment/verification are retained at `target/ge-refill-probe`;
the reusable harness writes `target/mapped-refill-probe/<ROM hash>`. Sources and
ISC license at pinned ares9408cb43 are read only; no upstream body is copied into
production. No shared reference/shim rebuild or runtime decoder is involved.

## Integration still required

Production needs an explicit versioned counterfactual-root contract, independent
synthetic exception/refill/source tests, malformed/unaligned/missing-root refusal,
source/generation/alias/cache negatives and native content/lifetime verification.
Ordinary neutral replay and its source certificates must never silently consume
counterfactual rows. Anchor selection, batching and state/observer restoration
need their own invariants; repeated deterministic probes do not prove closure.
After source recovery, cross-page slots/continuations, native refill/exception
delivery and table/callback obligations remain. GoldenEye still has no accepted
executable or native VI/logo/title milestone.
