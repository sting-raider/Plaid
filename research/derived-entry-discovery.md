# Inferred decode entries retain their incoming edges (ADR-0208)

Base: `9d199143c4b810e24ab94a5a1f347f301eff763e`.
Prepared semantic candidate: `86549b518252ebbdccf5ae6ccf7ad79977497172`.

The address-taken discovery loop previously carried all prior map entries as
fresh external roots. It discarded the earlier indirect candidates. An authored
two-case switch loop demonstrated both failures: case backedges prevented a
preheader base proof, and another address-taken round lost the candidate set.

`ProgramMap.derived_entries` now distinguishes decoder roots introduced solely
by non-linking indirect candidates. Each nonempty source set must name current
same-image/generation candidate relations. Missing classification remains an
unknown-state entry. JSON without the optional field retains its old meaning.
Merging unions source sets; an ordinary entry on either side wins in either
merge order. Address-taken functions cannot have a derived classification.

The classification also needs independent entry evidence. Each internal seed
has a content-addressed derivation witness naming that entry and its sources;
the union of its entry witnesses must exactly match the classification. Any
ordinary entry evidence remains an unknown-state origin, even if a valid
candidate source is added to the editable tag. This matters after merging a
map that knew the switch candidates with a map declaring one case externally:
the retained counterexample originally bypassed the barrier by restoring only
the tag. Original explicit entry facts must survive that operation.

Discovery retains candidates and evidence before each analysis pass, including
outer address-taken rounds. Explicit inputs, linked-call roots and proven SDK
callbacks remain external. A newly computed table certificate is still checked
against the complete current candidate set, observations, CFG and source bytes;
old candidates cannot disappear just because a replacement proof disagrees.

The backward table proof follows every known incoming indirect edge, including
observations absent from the candidate set. Each source must be a canonical
non-return JR in the same executable identity and placed-slot binding; its
delay-slot transfer must preserve the pending predicate. Calls, returns,
unknown entries and unsupported paths remain barriers. Full-state loop
induction still needs a concrete initializer on every non-cycle path. No ABI
preservation assumption is added for guest callees. Derived metadata alone
does not certify closure. Current SDK callback targets are recomputed so an
edited origin tag cannot turn a callback into an internal case label.

Authored contracts cover legacy JSON, malformed relations, merge order,
explicit entries, missing/foreign origins, address-taken and callback entries,
additional candidate/observed incoming JRs, changed case/delay-slot words and
slot rebinding. Temporarily skipping the incoming-JR walk makes the retained
unknown-state predecessor test fail (exit 101); the original bytes were
restored. An authored native loop dispatches input indices 0 and 1, exits at 2,
and produces 11. Its full registers, PC, FPU state and RAM checkpoints match
pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

Fresh ROM-only Paper Mario discovery remains OPEN/16 with 56,799 blocks and
162 loads. Five previously empty sites now retain 84 candidate edges in total:
7, 56, 5, 4 and 12 targets respectively. Their proofs still reject the remaining
paths. Candidate recovery is not closure and no native Paper Mario artifact or
run is accepted. Receipts and source-qualified diagnostics remain ignored in
`target/paper-mario/0208/`.

The first optimized discovery took 56.234 seconds and solve 110.129 seconds
while the laptop encountered severe memory pressure. These are operational
receipts, not a controlled performance comparison. A repeated solve timing
after memory became available took 18.360 seconds (8.109 CPU seconds) and
produced identical output after line-ending normalization. Required canonical
validation remains fmt, locked workspace/all-target Clippy, workspace tests,
CLI, runtime and pinned-ares checks on the exact final committed tree.
