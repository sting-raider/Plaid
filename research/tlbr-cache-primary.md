# Primary harvest: guest TLBR/cache reactivation

2026-10-11. Finite source behavior reconciled under spike 054; lifetime stays OPEN.

Reviewed complete note/driver/runner/model/source guard/README/workflow and
closeout 6090347415 at `research/tlbr-icache-lifetime-gpt56sol` exact final head
`a625e4ac88482b6947c018dabf464073e58187bc`, plus the referenced TLBP/TLBR and
EntryHi context findings. Successful Actions 37999435843 executed code head
`dd84b71880cff84e1173b1950fe90bee38be8965`; final head adds documentation only.
Artifact 11648388498 result SHA-256
`3624aea92b6c3f77c455c4342ab967cc0fd3c56eb7044bc6f24bf9fe61e28d67`
was authenticated. Fresh measured facts match it exactly and stdout repeats.

The original ISC driver is unchanged except its shared include path. Actual
decoded TLBR switches EntryHi ASID while installed entries and serialized cache
tag/index/words remain unchanged. Returning A executes stale 0x1111 with misses
2 -> 2 after direct debugger backing mutation. Equal old payload at PA 0x5000
causes replacement (2 -> 3); returning A then refills 0x4444 (3 -> 4). Actual
TLBP, same-value TLBR, out-of-range index 63, global fetch and unmatched-ASID
fault controls remain. Direct Index staging, TLBWI setup and exception resets
limit the writer-history claim. Internal context-step checks are selected
snapshots, not complete machine state or an emitted generation history.

Exact decoder, TLBR/TLBP handler, ASID matching and cache hit/fill paths inspected.
Eight source Git objects are checked. ares, Gopher and n64-systemtest require
clean pinned checkouts; Mupen's pinned HEAD and selected TLB file/index are checked
without reverting its existing instrumented files. Its inspected LUT lacks the
active-ASID predicate, while Gopher uses a physical cache index. Preserve those
disagreements; independent sources/systemtest are not executed hardware oracles.
Only project-owned fixture/guard code is shared. Generated ares ISC/SLJIT BSD
implementation/notices/results remain ignored, with no upstream code in native
mode or research workflow imported into canonical CI.

Replaying the old assertions accepts +100 to every miss counter, cleared valid
tag bits and a fabricated cache digest. Main checks all 34 typed report leaves,
exact schema, counters, valid tags and digest; all 38 measured mutations reject.
Four synthetic contracts also retain missing-counter and integer-boolean cases.
Full plaid-core, fmt check and strict locked workspace/all-target Clippy pass.
Prior canonical EntryHi CI 38146002739 passes at exact
`c1d4e72524f287984f62f161818eeaad5f8f554b`.

Fresh stdout SHA-256:
`a1c1df687d3afdb2a8e06922297fc06c5b0286d1cb3a2c0f23706836b6724f3e`.
Primary schema-0 result SHA-256:
`88f0db8ab53b6cf5caeafd6aa40fc6e05b74d87fb7ddb800d6203162ffb0e9ac`.
Reproduce with `python spikes/054-ares-tlbr-cache-lifetime/run.py`.

Separately replayed the existing 50k-history model: 13,153 fetches, 4,467 faults,
3,434 same-value successful TLBRs, 3,583 invalid TLBRs, 5,016 probes, 3,231
current-backing counterexamples and 938 equal-payload/different-PA transitions.
Digest `73f3a67c9cf0c83e213f083db2eb996056779edc63ff1c3de5a582129c3c540f`
matches closeout. Seven "rejections" compare forged dictionaries/scalars to
precomputed expected values; they do not authenticate measured histories. The
model's entry subset is not a complete installed-slot TLBR contract. No model
or generation certificate is promoted.

Disposition source_contract_reconciled; original report validator superseded.
Successful context loading, instruction occurrence, installed mapping storage,
backing and resident history remain separate obligations. Internal snapshot
equality cannot reconstruct same-value operations. Mutation census, hardware
policy, privilege/region/reset/restore/cache-operation composition, complete
lifetimes and whole-ROM/native closure remain OPEN. No progress milestone change.
