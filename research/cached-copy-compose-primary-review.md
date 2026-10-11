# Primary harvest review: cached copy, writeback and uncached fetch

2026-10-11. Model-only composition retained; no production certificate adopted.

Reviewed `research/cached-copy-writeback-fetch-compose-gpt56sol` at
`14f92e2be5b01837bc2abc326921aa3734e25bcd`, its complete note/model and issue #4
closeout. The three exact prior note blobs reproduce. The twenty-event abstract
model reproduces report SHA-256
`6c74ec8c9340b0f0e1b8414c6206b1e374fb0de39639368e81c28c60e02606b8`.
No claim is made that the combined chronology was executed in pinned ares.

Retain these useful obligations:

- a source backing patch after a cached load cannot replace resident/register
  ancestry;
- the completed writeback span includes nominally clean bytes in the inspected
  pinned-ares primitive, so its dirty mask cannot stand in for mutation width;
- outgoing resident tag/generation must survive until the successful writeback,
  before slot reuse;
- a later same-value backing write replaces prior ancestry before an uncached
  read/fetch join.

The model explicitly supplies abstract load/store operations. It has no decoded
CPU instruction, actual operand snapshot or complete intervening register history.
Adding `word=0` to its load/store dictionaries is ignored and leaves the canonical
report unchanged; this is a boundary of its vocabulary, not proof that a real NOP
can copy bytes. Such a model cannot authenticate raw instruction evidence. Cache
fills and writebacks likewise have no new completed reference transaction receipt
in this combined run. Sequence IDs are monotonic rather than a complete census.

Its advertised seven rejection entries comprise six actually mutated histories
plus a logical assertion about the already-derived post-patch chain. There is no
external claimed-certificate verifier for that seventh entry. Preserve the
logical counterexample, but do not count it as a separately forged report tested
against a production verifier.

Disposition: reviewed model-only. Retain the branch and report as proof-shape
evidence. Do not import the model, branch workflow or universal dirty-width rule
into production. Main's actual uncached copy/transform contexts remain finite
contracts; they do not cover this cache composition. One combined actual-reference
history, exact source authentication, cache/mapping/lifetime, complete mutation
coverage and eventual executable consumption remain OPEN. No native, whole-ROM
or progress-map milestone changes.
