# Native execution through TLB-backed code

The hypothesis is that raw executable files can retain their architectural
virtual addresses while discovery stores their alternatives separately. This
needs independent identities for the source file, executing virtual address,
physical backing and winning TLB entry. A physical copy alone cannot establish
an executable virtual mapping.

`tlb_raw` declares unchanged source bytes and a bounded text extent. It requires
a content-bound slot and an entirely mapped virtual range. It applies no
guessed MIPS relocations. J/JAL derives the target region from the architectural
PC, then resolves an internal target to the same analysis alternative. Direct
and register calls discover supplied text alternatives before return analysis;
their return continuations retain the executing virtual PC.

Native entry compares source text at the translated physical backing. It
requires one winning global TLB entry and contiguous RDRAM throughout text and
protected dispatch data, probing every 4 KiB boundary and the last byte. The
binding records the virtual delta separately from its physical backing delta,
entry index and generation. Every modeled TLB write, including an equal
rewrite, advances that entry's generation. Inactive affected bindings are
revoked and must be verified again. A rewrite, unmap or earlier-entry shadow
that would invalidate an active native frame fails before changing mappings or
bindings. Generation overflow also fails before mutation.

Writes through physical aliases revoke inactive text bindings; writes into
active mapped text fail. Noncontiguous dispatch cells are compared on entry
and protected alongside text without freezing unrelated module data. A tail
across a binding boundary enters the destination's native function wrapper,
retaining the original continuation. Native body discovery stops at that
boundary; return analysis retains the complete tail graph.

The reference is ares at
`9408cb43d4948fc3ea6e152a307a34348df3fe04`: VR4300 J/JAL region and link behavior
in `ares/n64/cpu/interpreter-ipu.cpp`, and first-match/global/page translation
in `ares/n64/cpu/tlb.cpp`. These are semantic references; no implementation
code was copied. The existing global-only mapped-data and cache restrictions
remain explicit limits. This does not model arbitrary guest TLBWI execution,
ASID scheduling, runtime guest decoding or a fallback execution engine.

Retained authored contracts cover unchanged source words, virtual jump regions,
internal case identity, linked-call alternative discovery, return continuations,
native body partitions and invalid virtual/text bounds. `runtime/test_tlb_execution.py` checks native register state and RAM checkpoints
against pinned ares, including a virtual-module JAL followed by a tail through a
protected data cell into base code. Active remaps/unmaps, physical alias writes,
invalid/global/page conditions, same-value rewrites and generation overflow are
retained contracts. Mutating either the active-remap preflight or data-cell
write guard kills this authored contract. The SDK indexed-unmap test retains an
independent mapping. Its invalid EntryLo pair makes PageMask irrelevant to all
supported mapped accesses; arbitrary guest CP0/TLB register observations remain
outside this SDK boundary.

The first candidate scan discovers 128 mapped source files in 11.503 s; discovery
takes 68.497 s with the larger source universe (the preceding 34-load run took
55.778 s). Indexed CFG lookups and helper-shape caching avoid repeated whole-map
scans. Release compilation took 163.474 s and remains an iteration cost. Exact
integration gate results are recorded after final local validation.
Paper Mario remains unaccepted until its automatic closure and visible native
validation succeed.
