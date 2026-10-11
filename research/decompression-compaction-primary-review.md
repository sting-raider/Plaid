# Primary harvest: compact decompression ancestry model

2026-10-11. Reviewed model-only; no production transform schema adopted.

Reviewed complete note, both scripts, both workflows and issue #4 closeout
6096787689 at `research/decompression-ancestry-compaction-gpt56sol` exact head
`7b7f2fb0e5faa802c38f403e559c4a87012cec5f`. Default Linux replay reproduces
5,000 programs, 675,151 byte writes, 47,068 nodes, 19,665 unsplit overlapping
backreferences and 556 in-place programs. All 18,000 declared forgeries reject;
the weak control accepts the 12,000 ancestry-only forgeries. Semantic digest:
`d5fffb1bd106f35f4431458bdad89740c729d111b56408111c1037402a497b1a`.

Direct construction independently reproduces 2,000 programs, 275,903 writes,
18,703 nodes, 7,951 overlapping nodes and 223 in-place cases; receipts equal
byte-history compaction and expand to the same writes. Equivalence digest:
`a14624c47caedec6b27c5e0d1576009ab3b1581b8cd5c28c4f81fbebe6889a80`.
Script SHA-256 values are respectively
`e5e41d6c222c30ac042cf75f1a857994460fed9af10e0336328ae5272b10397f` and
`6b2fb045b6c3ac16e2508e8dd52a3cfd6557b91ad521a8a86368bdb50a72835c`.
Actions 38046586892 / artifact 11667835598 and Actions 38046586945 / artifact
11667995491 succeeded at code head
`75206c7cef33b9c9cb1f02796e574420af2850da`. Both hosted stable reports match
primary replay. All six direct-builder size rows agree; timing/RSS vary.

Retain the representation result: authenticated sequential-copy semantics can
rederive self-feeding ancestry inside one operation node. Splitting at every
new byte generation is unnecessary in this algebra. At 100,000 writes, the
two-node compact receipt is 726 bytes versus 15,699,782 bytes explicit. The
10,000 one-byte-literal case is larger compact (1,838,140 versus 1,338,141
bytes). Replay and generation-bearing live memory still scale with output
bytes; this is neither a universal size win nor a comparable speed benchmark.

Primary boundary probes expose assumptions outside the declared valid corpus:

- A literal at offset 1 with declared source size 1 is accepted if memory also
  contains source base + 1 and the supplied causal digest names that cell.
  `execute_byte` and the weak control reject that out-of-range operation.
- Backreferences with length 0 or -1, and an unknown operation with length 0,
  accept canonical empty node/output digests. Validation inside the per-byte
  loop never runs. `execute_byte` rejects all three.
- Replaying the same valid receipt against its prior output memory with the
  same invocation ID accepts and reuses its writer tokens, as in the earlier
  explicit-receipt review. Invocation freshness is supplied externally.
- Changing node `op_index=0` to `False` accepts through Python equality.
  Dataclass annotations do not establish a strict serialized input schema.

These are verifier/model boundary findings, not a false-CLOSED production path.
The experiment explicitly assumes separately authenticated operation semantics;
its randomized valid corpus does not exercise malformed streams. Preserve that
precondition rather than adopting this verifier as untrusted proof validation.

To reproduce the first boundary on the exact script, initialize `b'AB'` at
0x1000, but declare source size 1. Use `Op.literal(1)`, a single `ByteWrite`
`(0,0x4000,66,0x1001,memory[0x1001].token,'O:audit:0')`, and a node committing
`sha256(write_canonical(write))`. Header hashes are `values_sha(b'A')`,
`ops_sha((op,))` and `values_sha(b'B')`. Strict compact replay accepts while
explicit execution rejects. For each empty-operation probe, create one node
with matching operation fields, length equal to `op.b`, sequence/index 0 and
destination 0x4000; both causal/output digests are SHA-256 of empty bytes.
Use the valid one-byte source header. Compact replay accepts with no writes.
For the remaining probes use `(literal(0),backref(1,2))`, source `b'A'`, output
0x4000 and ID `same`; compact the explicit receipt, verify against its final
memory, then replace the first node ordinal with `False` and verify against
initial memory. Both accept.

Disposition: retain the branch, deterministic equivalence corpus, size baseline
and adversarial shapes as model evidence. No Python model, research workflow,
guest recognizer or new production proof object merged. Actual guest operation
discovery, typed/fresh invocation receipts, successful effects, mapping/cache
and executable lifetime joins, complete mutation census and whole-ROM/native
closure remain OPEN. No production architecture or progress milestone changes.
