# Primary review: reverse SP DMA and cached RSP provenance

2026-10-11. Reviewed abstract composition; no unified reference history adopted.

Reviewed full note/model/source guard/README and issue #4 closeout 6090940545 at
`research/rsp-spdma-icache-compose-gpt56sol` exact head
`823efc196f88d3dad0fb36815df65af12f61334b`. The 24-event model and seven declared
forgeries reproduce stdout SHA-256
`0e44da1f703fff536c3bb4e593bfe8b654d5eb96afdff61d0a33d77811f70c6d`,
trace SHA-256
`6a9e0bea95160957ff404b1fabaec599c90399778068134ae57a1ed59d29435d`,
and report payload SHA-256
`82a5137174bef25a914010c8e3d4cdca4be5f5871f2fb47c1b894e37d0027b1a`.

Final-head Actions 38004011125 artifact 11650401821 supplies two byte-identical
model JSON files matching the primary stdout hash. All five source hashes match
exact pinned Git objects.

Retain the distinct per-byte source writer, DMA sink, backing fill and resident
identities. Same-value post-fill backing writes cannot refresh old residents;
pre-fill writers replace earlier roots. An equal restored tuple without causal
restore/fill evidence remains unknown. Those are useful abstract counterexamples,
not newly captured combined RSP/SP-DMA/cache execution.

Primary relabeling of the second same-value RSP writer context 2 as context 1,
with dependent abstract `rsp:2:*` labels consistently replaced, is accepted.
Both writes then name the same writer generation despite different event
ordinals. The model does not enforce unique decoded instruction contexts.
Adding `decoded_word=13` (BREAK) to its RSP-store dictionaries is also ignored;
the vocabulary supplies a store operation rather than authenticating an
instruction/operand source. This does not imply a real BREAK stores bytes.
Main's actual finite RSP/CPU composition rejects a reused producer context and
already rejects BREAK producer evidence; eleven synthetic contracts pass. The
same context-reuse mutation also rejects in the retained actual instrumented
reference capture, independently of synthetic fixture construction.

The inspected exact ares reverse-DMA source reads two DMEM Words and writes two
SP_DMA RDRAM Words per eight-byte row, while this abstraction uses individual
four-byte DMA events. It is not a measured row/request/count/skip/wrap lifecycle
or completed callback join. Source formulas and prior independently executed
primitives do not authenticate a new combined chronology. The branch source
guard checks HEAD and snippets without a worktree-clean gate; primary inspection
uses exact Git source objects, preserving the historical five source hashes.

Disposition: reviewed model-only, retain its branch/specification evidence and
the new canonical context-reuse regression; do not import the model or branch
workflow as a certificate. Existing main sensors supply finite source behavior,
but the actual reverse-DMA-to-cache composition, ultimate RSP input ancestry,
source census, cache/mapping/lifetime, restore and native/whole-ROM closure stay
OPEN. No production architecture or progress milestone changes.
