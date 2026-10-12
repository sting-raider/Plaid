# PI writer/fill/consumption on the complete SP source clock

Base: ea250c8e1f1f8fab7d8d33ddef2e5ed796b6132e. Claim: 6121583474.

Reuse canonical pi_fetch_lineage's observed ROM writer -> RAM backing -> full
I-cache fill/resident bytes -> discrete fetch engine. Extend admission to the
complete v3 SP/PI source after the existing canonical nested validator; no new
sensor, guest operation or architecture lane. Require independently preserved
raw v3/v5 hashes, then rehash both complete inputs on replay. Preserve raw v3
ordinals rather than substituting the renumbered v2 projection. SP observations
are validated/hashed but provide no invented RAM origins. The typed outer report
retains the entire SP/queue/PI/access/fetch projection. Default v2 public report
type/schema stays compatible.

Positive synthetic contracts cover successful canonical-ROM-byte writers through
both unambiguous uncached consumption and witnessed complete32-byte cached fills.
An inserted SP event shifts raw identities while leaving old projection semantics
intact. Writer/fill/read occurrences are checked against actual raw rows. Source
receipt mismatches, forged nested reports/raw writer IDs/unknown fields/proof
flags, malformed raw ordinals and either input changing between validation and
replay all reject. Even an otherwise unused SP row changes the full source hash.
Existing equal-store/burst cuts, resident-vs-backing, invalidation/retag/unknown
fills, contradictions and ambiguous-read adversaries remain in the full gate.

All22 focused PI-history tests pass. Full local fmt, strict locked workspace/
all-target Clippy, locked workspace, canonical CLI and diff checks pass. Extended
synthetic CLI checks reject overwriting any source, wrong independent digests
and forged chain counts. No Actions or branch-only CI scaffolding.

The retained610000-fetch v2 report fully rechecks unchanged against the current
refactor:10954 full PI-chain observations,185 samples, ordered chain SHA256
67158997c3fbec624afaea75cd8b255ef59c863258345a89ca80cda1bb3da5c7.
No reference rebuild; exact pinned ares9408cb43d4948fc3ea6e152a307a34348df3fe04
source contracts and existing licensed sensor inputs remain authoritative.

Actual retained100k v3 import and independent Python replay agree on every
count/sample/ordered digest:100000 fetches,0 PI-compatible chains,0 samples,
ordered SHA256 bf9653cea12e9546e33724f4c32603455b467324554bdcbfcdbabf3cf5ff1ad8.
Raw v5ce66498314c58b448fc95ecd4ef8adbd795e83c60c9ac5e49189e4406f8039a4;
v3e2732d22c99bf4fd5a41446bfdf69c2d054d4fd3b94159dbfa16d7e30c577090.
The independent checker preserves v2 behavior while admitting v3 and its extra
nested projection; all SP events still contribute to the raw source digest.

Current-tree larger20m chain inspection is ongoing on the authenticated source
pair from the local PI-entry receipt. That outcome is not certified by this
integration. Primitive completion/entry observation is already retained, while
full installed consumption candidates require the new replay result.

Chains remain finite recorded compatibility, not ultimate ancestry. Equal unseen
mutations, unsupported producers, cache/TLB/mapping lifetime, restore/reset/NMI
and a complete executable/writer census stay unresolved. Discrete endpoints never
define continuous image lifetimes. All census/lifetime/native flags remain false;
no ProgramMap/solver promotion, whole-ROM CLOSED claim or progress milestone.
Copyrighted raw words, ROM, firmware, reports and sources stay ignored/external.
