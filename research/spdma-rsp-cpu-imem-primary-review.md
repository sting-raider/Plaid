# Primary review: forward DMA through RSP and CPU to IMEM

2026-10-11. Reviewed model-only; no unified actual-history certificate adopted.

Reviewed complete note/model/source guard/README/workflow and closeout 6091126619
at research/spdma-rsp-cpu-imem-chain-gpt56sol exact head
`ef95b423647f3f03cee3026ea7f1d22815d80532`. All five exact prior Git-object
checks and the ares pin guard pass on current main. Two primary model runs
reproduce the 34-event fixture, eight declared rejections and two-valid-history
projection collision. Report payload digest is
`a7305b902d39d1963a98c33106f5009aac33898f8860bbe248f7f5e8721e75b3`;
stdout normalized only CRLF to LF matches
`2475db3f978e18e14da9563871cda1225ac614e388b722b15a2865c8baeac688`.
Successful final-head Actions 38005379732 / artifact 11651056811 supplies two
outputs with exactly those LF bytes. Model script SHA-256:
`919242c130b5e329e6f8e86c503946c023e9d505f089da9a2d1198d2f07d71fb`.

Retain the projection collision: changing the active equal-valued DMA source
from 0x2000 to 0x4000 keeps downstream writer/resident/fetch projections identical
while changing four upstream byte origins. Downstream identity cannot recreate
ancestry discarded earlier. Fresh local storage/register generations and inherited
origins are separate facts. Missing ingress or unproved whole-GPR definitions
propagate UNKNOWN rather than repairing it from equal payloads.

The modeled operations are supplied as `rsp_lw`, `rsp_sw`, `cpu_lw` and
`cpu_sw_imem` dictionaries. This replay does not authenticate decoded guest
instructions, operands, successful read callbacks or a combined scheduler.
Additional primary probes accept ordinal 1 replaced by boolean True and
successful-read True replaced by integer 1. Adding decoded_word=13 (BREAK) to
both RSP load/store events is ignored: operation vocabulary is authoritative.
These probes do not invalidate the declared abstract projection collision;
they rule out importing the model as a production instruction/source verifier.

Reproduce with the exact model: start from history(); separately change
history[0]['ordinal']=True, history[0]['success']=1, or add
history[6]['decoded_word']=history[7]['decoded_word']=13. Each passes
verify(replay(history)). Main's actual RSP/CPU fixture already rejects a BREAK
producer and strict serialized finite fixtures reject boolean integer fields.

The guarded prior notes were reviewed: forward DMA ingress captures actual
paired Word source/sinks; scalar RSP load ancestry reconstructs DMEM sources
from decoded instructions and replay state rather than a primitive read callback;
the guarded older CPU/RSP composition was superseded by main's stricter actual
composition fixture. Hashing that older note/model authenticates their contents,
not their promotion or a new combined execution. Main's new finite ingress
fixture and existing RSP/CPU fixture remain separate measured histories.

Disposition: reviewed model-only; branch retained as specification/counterexample
evidence, not declared obsolete. No raw branch, Python model, workflow or new
production architecture merged. The actual combined ingress/scalar RSP/CPU/fetch
history, ultimate RDRAM storage ancestry, complete writer census and execution
lifetime remain OPEN. No progress milestone change.
