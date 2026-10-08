# Finite instruction-cache context

2026-10-08. Hypothesis: the existing pre-decoder prologue can retain the selected
instruction-cache line without extra guest reads, translation or clocks. This
fills a gap in the effective physical/cache metadata: physical RAM can change
while a cached instruction still uses old resident bytes.

The pinned CPU::InstructionCache selects slot `(vaddr >> 5) & 0x1ff`. Its line
holds tag/valid bits, a page offset index and eight words. On a successful cached
fetch, the prologue samples those existing fields and verifies the exact word
using `(effective_physical >> 2) & 7`, after reverse-endian selection. It never
calls the coherence helper, which would perform another guest bus read.

Spike 010 checks twelve original fetches against the separately built ISC
reference, with both recompilers disabled. Plain/traced/repeated CPU/COP0/
exception/Count and complete RAM/instruction-cache hashes match. Repeat JSON is
identical. Cases cover stale words, uncached access, invalidation, eviction/reload,
cached TLB remapping, reverse endian, nonzero index and virtual-bank aliases.
Eleven snapshots are present; the uncached fetch has none. Final s0=8, Count=444,
hits=2, misses=9. RAM hash:
`fdaa4712ad0c382090e5e8db1065b8c4632c1d0fcea6c888ae656b454fc766e1`.
Cache hash: `9073f41420302efa4f6ec1880d421f17ebd37dd8f16e7280ea5408540c97c3ef`;
explicit fields are serialized in fixed slot order and big-endian byte order,
excluding padding and host pointers.

Two boundaries matter: identical snapshots recur after eviction, and different
slots (129/1) can hold identical tag/index/words. Retain slot and exact event
provenance; neither payload equality nor tag equality establishes a cache lifetime
or generation. Resident words do not establish their RAM/ROM origin or that every
word executed. Broader boot capture, source verification, fill/mutation/copy
lineage and contextual image construction remain separate work. No production
data handling, native output or whole-ROM closure is promoted.

Spike 011 extends the sensor to the unchanged homebrew's CPU power-entry prefix.
Research v5 retains the explicit v4 boot inputs and declares
selected_icache_line_at_prologue. One million fetches include 400,954 cached
snapshots at 32 distinct slot/tag/index/data tuples; uncached fetches have none.
Virtual slot and page index, effective physical page/index/lane and exact word
are checked. Complete v3/v4 projections and previous checkpoint goldens match,
as do plain/traced/repeated CPU/device/timing/RAM/SP and complete cache hashes.
The additional cache hash serializes explicit fields without padding/pointers.
Raw size: 210,032,160 bytes; SHA-256
`c0dcae4870aaec1b30097d7fd95f2b6214f043e2ac1dea6366b1814655ce4ce9`.
Full cache hash:
`eb0abce6ce91d78b5c335be4cb364a7d10744af865a758b9026f9c653c474892`.
Production rejects this unsupported cache policy without output. Longer-prefix
and legacy checks are pending. Counts describe finite observations/payloads, not
fills, epochs or immutable images; backing and lifecycle joins remain unresolved.
