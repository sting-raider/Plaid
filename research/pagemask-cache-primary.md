# Primary harvest: PageMask and cache remap

2026-10-11. Retain finite unmodified-reference behavior; no production certificate.

Reviewed complete note, driver, model, source guard, runner, README and issue #4
closeout 6090876288 at exact branch head
`9679c4b9bd658d53e14932f62b6ffa6d78148f84`. Reviewed its source research notes
for PageMask translation, TLBWI operation generations and cacheable synonyms.
Hypothesis: large-page translations require their actual selected physical
address; mapping/context operations cannot automatically end instruction-cache
residency, and equal instruction payloads cannot preserve physical-tag identity.

The branch's deterministic model and six hit-witness negatives reproduce report
SHA-256 `922c54f8c09f6f330cea4b1307c059b68423be6faaeb81c79dbe0db1bc671327`.
Its 50,000-case sweep reproduces 46,065 fixed-4K address/tag disagreements and
25,028 bit-12 half-selection disagreements. These are abstract source-formula
comparisons, not guest reachability measurements. A primary extra adversary
changes a miss witness to resident generation 999, backing generation 999 and
word 0xdeadbeef. `verify(..., resident=None, witness=forged)` accepts it because
the miss path returns `not witness.hit` after translation/slot/tag checks. It
does not validate a completed fill or backing writer. Reject this verifier as a
production certificate; preserve its useful hit-side counterexamples as research.

Final-head Actions 38003361050 artifact 11649979946 contains result SHA-256
`7d0116e2a31c186951ebb248ac81b78df2fcb342ccbb005f6aa88e2fd44c0f86`.
Its behavior fields independently agree with spike 049's strict expectations.
The primary adapts only the original project-owned ISC driver to the shared 003
builder and runs it without reference callbacks or TLB/cache patches. It retains
explicit false ancestry/census/lifetime/native flags rather than deriving
generation certificates from the model or final-state hash.

Source inspection covers exact ares PageMask normalization, selected-half/offset,
ASID checks, direct TLBWI slot synchronization, fetch routing and instruction-
cache resident/fill logic. Exact source blobs bind the executed builder. Gopher
cache source and systemtest PageMask source match the historical LF SHA-256
receipts, respectively
`45fad688563424d08d8db0e2ce52c588f65cb8f114f14648e190dee6090af177` and
`221bc0f3239ddbb1f9e4d16b2910edf007db34997915db7b2d4703f5683d88f4`.
No Gopher or physical N64 execution is claimed. Gopher indexes I-cache physically;
ares indexes virtually. Preserve that disagreement, and avoid a universal
indexing rule. No GPL implementation or upstream source enters Plaid production.

The fixture directly calls `CPU::TLBWI()` after staging entries and directly
stages ASIDs; it cannot authenticate guest writer instruction/operand histories.
Debugger-side RDRAM writes isolate cache behavior rather than producer ancestry.
Repeated selected facts and cache-state digest are not full-machine checkpoints,
measured fill chronology, observer neutrality or a complete lifetime census.
Only finite 16-KiB/64-KiB big-endian identity-RDRAM interpreted paths are exercised.

Primary unmodified executions reproduce every historical behavior field and the
I-cache digest. Compact facts SHA-256 is
`4227e340a3000607b70cde96339a379737ea46167a7cf10573fe7aba093050fd`;
schema-0 primary result SHA-256 is
`d884a8ce86b01192750afd9f7539e2a618f5a0dcb72c54f777134c9561fe8a35`.
Six strict synthetic contracts, full locked plaid-core, formatting and strict
locked workspace Clippy pass. Source guards, model generations and branch-only
CI scaffolding are not imported as production evidence.

Disposition: preserve the executable regression under spike 049 and supersede
the branch runner/workflow. Do not adopt its miss verifier, abstract generation
IDs or ares indexing into production. Unified measured mapping/context/cache/
backing history, producer identity, guest writer semantics, larger pages,
overlapping/undefined mappings, reset/restore, hardware validation, whole-ROM and
native completeness remain OPEN. No progress-map milestone changes.
