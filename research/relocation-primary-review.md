# Primary harvest: runtime relocation ancestry model

2026-10-11. Retained fail-closed regression; no relocation certificate adopted.

Reviewed complete note/model/workflow and issue #4 closeout 6090962492 from
`research/runtime-relocation-provenance-gpt56sol`, exact final head
`253acfae6542e8bb65a42ae041c1115c301f4dcf`. Retrieved exact N64Recomp
`ffb39cdad1da5de07eaaa48bd1db4a89a7986771` objects and inspected the surrounding
non-relocatable reference-section patch path and HI16/LO16 macros. The source
guards match blobs `0768f16bf58ce09824cfe6ddec9eb5fcf9251ed7` and
`73f3e73d7fc6cd6ccf37637f579fc389b554d8c3`. Its MIT license was inspected;
source-only comparison, with no reference implementation copied or linked.

Full source-guarded replay reproduces 250,000 HI16 formula comparisons and
100,000 cases on each of three generation/pairing axes. Strict checks preserve
the same-value generation advances and reject the declared source-generation
and cross-load pair attacks. The equal-payload control collapses/accepts all
three axes. Report digest:
`78ad10aa9533dca441c81b4063bff87fd98da3d00ef933d7d883f46488deb87f`.
Script SHA-256:
`78d133c07b85fc352c1659190e5ac7eb0c6cff977a6ae36e52a011dedf269615`.
Primary stdout, normalized only CRLF to LF, matches
`585f33160ed068c5cac7541017e592c0b5924f5289e2f78b82e5dbb01ce97836`.
Successful final-head Actions 38004157335 / artifact 11650661506 and prior
code-head Actions 38004080089 contain the same JSON; both final outputs match
that LF hash exactly.

The concrete erased-preimage example remains useful: 0x3c081111 and 0x3c082222
both patch to 0x3c088041 for target 0x80408000. Thus site/kind/target/postimage
cannot identify the input storage/load generation. The inspected source is a
static mod-tool ROM patcher, not a captured guest runtime relocation loop or
hardware oracle. The model supplies those runtime events and labels itself.

Primary probes show that `strict_receipt` accepts changing only the relocation
`event_id` while keeping its write identity, assigning any mutually matching
post-generation label different from the input, and changing sequence 10 to
boolean `False` before write sequence 11. The model does not authenticate the
relocation event against an external chronology or prove global freshness from
local inequality. Same-load/target/ordered HI16 and LO16 are necessary checks in
this reducer, not independent proof of a guest symbolic pair or addend semantics.

Reproduce those probes with source `StorageGeneration('input:1','load:1',
0x3c080000)` and `make_receipt(event_id='event:1',seq=10,site=0x80001000,
kind='R_MIPS_HI16',target=0x80408000,source=source)`. Replace only relocation
`event_id` with `unrelated`; or replace both `output_generation` and
`post_generation` with `some-prior-generation`; or replace relocation `seq`
with `False`. Each separately passes `strict_receipt`. These are boundaries
outside its declared corpus, not evidence of a production solver defect.

Current main independently adds `unverified_relocation` for every retained
typed relocation. Added a canonical regression: an otherwise CLOSED finite
self-loop stays OPEN for HI16, LO16 and unknown relocation facts after importer
diagnostics are cleared, despite reused valid CFG evidence and an equal site/
target. The relocation-free control remains CLOSED only in declared-static
scope; WholeRom and native completeness remain OPEN. Full core tests, fmt and
strict workspace Clippy validate this regression.

Disposition: reviewed model-only with retained canonical solver regression.
No raw branch/model/workflow merge, mutation certificate, pairing recognizer,
cache/lifetime integration or production architecture change. Keep descriptive
relocation facts fail-closed. Guest writer/dataflow, actual event identity,
fresh generation census, addends/formats, executable consumption and whole-ROM
closure remain unresolved. No progress milestone change.
