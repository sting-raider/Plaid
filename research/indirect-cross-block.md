# Restricted cross-block constants

2026-10-08. Hypothesis: a constant target can survive direct block boundaries
without requiring an ABI assumption, a call summary or a whole-program abstract
interpreter.

Implementation walks at most 128 unique predecessors in a CFG rebuilt from
pinned Rabbitizer decoding; source images above 65,536 words are outside this
pass's budget. Each chain starts with unknown registers except zero. A scalar
nontrapping subset updates values. Branch-likely fallthrough excludes the slot;
taken and ordinary branch paths include it. JR/JALR captures its source before
link/slot writes. Entries and candidate/observed incoming indirect targets stop
backward propagation. Joins, calls, unsupported effects and cycles remain unknown.

Certificates retain block/edge identities and the traversed word hash. Verifiers
reconstruct the graph from bytes and check the supplied map's relevant facts.
Tests cover slot-produced constants across jumps, likely versus ordinary branches,
changed bytes, new entries, candidate re-entry, joins with deleted incoming edges,
calls, stores and pipeline/solver integration. Removing a required edge reopens
the solver even when the certificate payload remains in provenance.

Result: restricted cross-block discovery and declared immutable integer-scope
closure pass. General joins/loops, pointer tables, mutable code and whole-ROM
coverage remain outstanding. No speed or compatibility claim follows.
