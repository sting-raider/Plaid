# Per-copy SDK scalar address evidence (ADR-0194)

Prepared base: `b6006cb6595ce181428e1ad4ce843ad7b05bf4cf`.

The next interrupt-mask boundary needs each SDK copy's own global-mask
address. Identification already used signature data relocations to reject
lookalikes but discarded them from its result. Preserve conservative address
evidence before connecting any new runtime behavior.

## Artifact contract

`Identification.data_bindings` maps selected function entries to ordered
symbol/address maps. `plaid identify` emits each nonempty map as an optional
`data_bindings` object in its `plaid-runtime-functions-v0` function record;
values use the existing hexadecimal guest-address notation. Existing fields,
function selection and ordering retain their meanings. Original declaration
consumers accept the extra field and currently ignore it. This milestone does
not carry bindings into ProgramMap, native lowering or the runtime.

Only adjacent LUI plus ADDIU, ORI, LW or SW pairs are supported. Validate the
opcodes, nonzero LUI destination, low operand's base register, readable
instruction bytes and checked offsets. An arithmetic low instruction writing
zero supplies no materialized pointer. ADDIU and memory offsets are signed;
ORI is unsigned. Every recorded use must form a supported pair and resolve to
the same address. Every surviving signature variant must supply that same
binding. Duplicate, missing, indexed, nonadjacent, excluded-data and
contradictory references supply no binding. Reconciliation disagreement drops
binding evidence while preserving an otherwise agreed function declaration;
conflicting function selection drops its associated bindings too. Reference
map names alone supply no new bindings.

The artifact describes constant address references. It does not establish
global value immutability, layout, boot initialization, effective masks or
equivalent SDK variants. Future mask implementations must require their
verified variant and binding explicitly; this optional metadata cannot justify
guessing a mask or admitting `__osGetSR`.

## Verification and references

Three new Rust regressions cover signed versus unsigned lows, LW/SW, all-use
and all-variant agreement, clobbered/zero register refusal, nonadjacent pairs,
excluded data, missing lows and duplicates. Existing identification regressions
now assert independent globals in disjoint SDK copies, reconciliation conflict
and reference-map conflict. A retained public CLI fixture identifies two
synthetic copies with distinct globals and feeds the JSON to the original
declaration consumer. It runs within `scripts/test_cli.py`.

The extractor first failed its positive tests; the CLI test first failed on
missing `data_bindings`. The completed focused signature suite passes all 15
tests. Removing all-use agreement makes the contradictory-use regression fail;
the original source bytes were restored afterward. Native/runtime instructions
are unchanged, so this artifact transformation has no new register, memory,
exception or timing semantics. Existing full native/runtime contracts remain
part of local validation.

The n64sym reference is exactly the locked
`ccf4600f3389f1a84bde23339225cf372fdf7712`. Existing signature-format metadata
is an input; no upstream implementation, SDK bytes, ROM-derived code or game
assets were copied. The extractor and synthetic fixtures are project-owned.

Local evidence is retained under ignored `target/sdk-bindings/`: focused
counterexamples, mutation log, old/new compiler identification comparison,
control maps and committed-tree gate logs. Control identification comparisons
remove only the new optional field before checking every original field.
Map comparisons use the exact original declaration bytes to retain the exact
original evidence digest; newly enriched JSON intentionally changes that
digest and is not claimed byte-identical. Tests also exercise new JSON with
the existing declaration consumer.

BK's identified osSetIntMask copies at 80003a30 and 80264220 retain distinct
__OSGlobalIntMask references at 800050f0 and 80275f80. No production address
constant or global value was added. Old/new identification agrees after
removing only the optional field, and discovery with the accepted declaration
bytes produces the identical map: scoped OPEN/1. Nine other ROM controls
(RS, SF64, MK64, PM, GE, SM64, MM, F-Zero X and OoT), plus the separately
configured SM64 control, preserve every original identification field and
their exact original-declaration maps. Solver outcomes are unchanged.

The three-thread control sweep took 98.818 s. BK identification measured
13.302 s with the pre-change compiler and 8.482 s with the new compiler, in
that order with shared analysis caches; these are not controlled performance
comparisons. No optimization is attributed to the metadata change.

Full integration validation runs fmt, strict locked workspace/all-target
Clippy, locked workspace tests, CLI contracts and runtime contracts on the
committed tree. Final command timings and the exact candidate hash belong in
the issue #4 closeout and commit-bound local gate receipt. This is a correctness
and metadata milestone, with no performance improvement or retired assumption
claimed. BK's Status, interrupt masks, saved/live thread state and event
eligibility remain the next implementation boundary.
