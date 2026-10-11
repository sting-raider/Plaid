# Primary harvest: bounded decompression receipt model

2026-10-11. Reviewed model-only; no guest transform verifier adopted.

Reviewed complete note/model/workflow scope and issue #4 closeout 6091116524 from
`research/decompression-lineage-receipt-gpt56sol` exact head
`e3cf98a5414ba49afa695cbd890f98786d0ddc2c`. The complete default corpus reproduces
20,000 positive programs, 880,132 writes, 19,916 self-feeding programs and 2,858
source/output overlaps. Eight axes of 10,000 forgeries each reject under strict
receipt replay; the content-only and value/shape controls accept 80,000 and
70,000 respectively. Semantic report SHA-256 reproduces
`336443e2a109033f0aad3c43ffdb7d6f94c8c8ea2a820b7be25ac516047d0a24`.

Exact script SHA-256 is
`4b33a3ada5d3347bc93099a576e7c8e98a63bcbaa4a1fc1759033205d5577835`.
Windows primary stdout normalized only from CRLF to LF matches historical hash
`15e2bcf5e8d5ff16f8d735e15729d4ed4981a9def48a33ff1480c6ac6d4383db`.
Final-head Actions 38005286772 artifact 11650732363 contains two outputs with
that same hash. Counts and report contents independently agree.

Retain exact current literal parents, sequential output-to-output backreference
parents and read-before-clobber chronology. Hashes authenticate bits, not the
observed storage generations. The model demonstrates these distinctions once
its operation stream, starting memory and invocation identity are supplied.

Two primary boundary probes limit promotion. Running the same operations twice
with the same supplied transform ID produces identical `O:<id>:<seq>` writer
tokens, and strict replay accepts the second receipt against its current memory.
Invocation freshness must therefore come from an external authenticated census;
the model does not allocate or enforce it across runs. Replacing the first
receipt's integer `seq=0` with boolean `False` also passes dataclass equality.
Annotations are not a strict serialized schema. These probes do not invalidate
the eight declared corpus axes, which supply distinct invocation IDs and typed
memory/operations; they rule out importing this Python verifier as production
proof input validation.

Reproduce the invocation probe with `initial_memory(b'\x07\x07',0x1000,1)`,
operations `(Op.literal(0),Op.backref(1,2))`, output base 0x4000 and ID `same`.
Call `execute` twice, passing the first final memory into the second run with
the same ID; `strict_verify` accepts and both writer-token lists match.
`dataclasses.replace` on the first write with `seq=False` supplies the type probe.

Fetched and inspected exact N64ModernRuntime
`cdf5abbd5026fef5c364c676e4667c45e42b6863` Git objects under ignored output.
`librecomp/include/librecomp/game.hpp` matches blob
`a4cf7e861c678931dc9916ab84dcf0b8e68ba6e3`; the compressed-code callback and
its `mods.cpp` invocation expose host decompressed bytes for mod loading, not
guest causal ancestry. Its COPYING was inspected; this is source-only context,
with no runtime implementation copied or linked into Plaid.

Disposition: reviewed model-only, retain branch/corpus/specification evidence.
No MIO0/Yay0/Yaz0/guest code recognizer, production transform receipt, authenticated
operation stream, complete effects or execution lifetime is established. Compact
ancestry is a separate existing research cluster. Hardware behavior, producer
census, cache/mapping/lifetime and whole-ROM/native closure remain OPEN. No
architecture/progress-map changes or raw branch/model/workflow merge.
