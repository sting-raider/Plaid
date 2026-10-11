# Primary harvest review: AI interrupt policy disagreement

2026-10-11. Source/model evidence retained; no production timing rule adopted.

Reviewed newly discovered `research/ai-interrupt-root-compose-gpt56sol` at
`8015de2443c2105c5caa7b664b9e8edb2f41eddd`, its complete note/model/source guard,
and [closeout](https://github.com/sting-raider/Plaid/issues/4#issuecomment-6108958858).
Authenticated final Actions `38138860190` artifact `11702173256`:
`results.txt` SHA-256
`35381f952177a5c9412ae05bc3db9254b3ade57cf92a366d4fa5e7fe89491bc9`.
The reproduced model result is
`80e140879adbb3b2fd5741d46fcbd0c7fc385623940541fc8549449404fad395`,
with 192,000 abstract operations per policy and 64 initial/final divergence
probes each. These are model operations, not executed reference instructions.

The branch guard checks HEAD and source needles, not complete source equality.
Primary review additionally compared all ten relied-on files with exact pinned
Git blobs after newline normalization, and inspected the actual AI functions.
The existing authorized Mupen instrumentation does not alter those AI/MI files.

| Pinned reference | Initial nonzero buffer | Lone final completion after an early acknowledgement | Two-buffer handoff assertion |
|---|---|---|---|
| ares `9408cb4` | asserts AI | no unconditional reassert | newly promoted buffer |
| Gopher64 `e96deba` | asserts AI | no separate reassert | newly promoted buffer |
| Mupen64Plus `ba95bab` | schedules completion | asserts AI | completed prior buffer |

In ares, AI_LENGTH raises when the accepted FIFO was empty; AI::sample raises
only when a queued second entry is promoted. In Gopher, do_dma schedules and
raises, and dma_event pops/promotes. In Mupen, do_dma schedules without raising,
and ai_end_of_dma_event pops then raises. AI_STATUS clears in all three. The
inspected ares LENGTH path also lacks the other references' nonzero guard.

Equal pending bits at a handoff therefore conceal different causes. This is
enough to reject a universal start/completion provenance rule across these
references; it does not identify physical N64 behavior. AI assertion, MI masked
contribution, competing sources, CPU gate and handler identity remain separate
proof inputs. An aggregate IP2 snapshot cannot select an AI producer.

Do not promote the model into a producer certificate. It generates and checks
its own abstract state; it is not an external-history forgery verifier or a
joint reference-system execution. Its boundary method changes EXL without a
new status generation, and root records omit some requested generation fields.
Its full-FIFO rejection is an abstraction: the inspected Gopher/Mupen fifo_push
paths overwrite the queued slot when busy, whereas ares guards dmaCount < 2.
The worker explicitly leaves FIFO overwrite, reset/restore and cycle timing
outside its scope. Retain those limits rather than reading randomized operation
counts as a complete device contract.

Disposition: reviewed reference disagreement. Preserve the branch/artifact as
evidence and the conflict in this primary note. No source policy, model, branch
workflow or upstream implementation is integrated into production. GPL Mupen/
Gopher sources were inspected only; no implementation was copied. Hardware
timing, full-system causal sensing and handler-byte/lifetime composition remain
OPEN. There is no whole-ROM/native or progress-map milestone change.
