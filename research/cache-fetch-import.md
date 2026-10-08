# Finite selected-cache context import

2026-10-08. Following spikes 010/011, original Rust data handling accepts research
v5 through the explicit firmware-input path. The complete declared boot profile,
firmware identity and source policy remain required. The additional cache policy
is selected_icache_line_at_prologue; older formats cannot carry this policy or
resident snapshots. Wire null, missing, unknown and malformed fields fail closed.

Each cached fetch carries a strict snapshot: slot, tag_key, index and eight u32
words. Validate slot=(virtual PC >> 5)&0x1ff, index=(slot << 5)&0xfe0 and
index=effective physical&0xfe0, tag_key=(physical&~0xfff)|1 and the exact effective
word lane (physical >> 2)&7. Uncached fetches omit snapshots. These checks encode
the pinned observer's declared constraints; they do not independently certify
hardware behavior or raw sensor truth.
The pre-decoder sample supplies no retirement certificate for the selected lane.

The summary key includes the entire resident tuple, effective access and source.
Different virtual cache banks and changed unfetched lanes remain distinct;
identical tuples recurring after eviction remain finite observations, with no
continuous-lifetime claim. Full-source verification regenerates every fact,
metadata field and provenance, including all resident words. Mutation of an
unfetched lane may pass structural checks but fails the raw-source rechecker.
Snapshots create no regions, blocks, entries, copies, images or generations; the
unknown-execution solver gate remains OPEN/native_complete=false.

Original unit and CLI cases check slots 129/1, resident payload changes, recurrent
observations, invalid slot/tag/index/lane/array shapes, missing/null/version
metadata, uncached snapshots, firmware input and full-source tampering. The
one-million ignored corpus accounts for every fetch in 1,155 facts and self-
merges byte-identically. Map size: 644,693 bytes; SHA-256
`07f650865d122d13059c6f862e68303aa82527173d87f08b37e2d0e90108156f`.
A single Windows debug import took 14.01 seconds and peaked at 11,907,072 bytes
of working memory under concurrent checks. This is one-host cost evidence, not
an optimization or scalability claim. Complete longer and legacy corpus checks
remain separate verification milestones. Fill/copy/mutation lineage and
contextual executable identities are still required.
