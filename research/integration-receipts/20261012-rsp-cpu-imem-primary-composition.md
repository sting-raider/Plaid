# Primary composition: decoded RSP producers through CPU definitions into IMEM

Base: 323d8649ee1b82a65bc7323be5911e172bfec0d6. Claim: 6114922248.
Source: canonical research/rsp-cpu-imem-primary.md / spike 047, source research
rsp-producer-cpu-imem-compose-gpt56sol @ 5caaabd5b96e4240dbe33e7f897f24be7b9a30c0
and closeout 6079548290. Reuse the actual single-clock source, not the rejected
branch verifier or two incompatible scalar/egress ledgers.

The prepared PR #37 represents RSP writer contexts without scalar operand
snapshots; PR #8 has richer scalar dataflow in another source. Those cannot be
joined by labels/equal values. The canonical capture already supplies full CPU/
RSP before/end snapshots, actual Byte mutations, SP Word effects, independent
CPU step snapshots and normalized initial/final memory. Production now consumes
those connected facts with a generic typed bounded decoder/effect protocol.

Production has no fixture phase/PC/payload/count tables. It checks RSP SW/SH/SB
operands and observed SBV-v2-element0 bytes, complete actual Byte effects, GPR
zero and RSP result/control boundaries. CPU LW/SW/NOP/ADDU use full snapshots,
exact direct-KSEG1 physical/bank/offset joins, LW sign extension and whole-register
definitions. Foreign CPU DMEM sinks must match decoded stores; external unknown
mutations cut only touched bytes. CPU register-specific loads survive unrelated
equal-valued loads and backing mutations; same-value ADDU cuts prior ancestry.
Unscoped writes retain content and unknown instruction attribution. Parent IDs
come from original ordinals in the containing source, not caller generation labels.

The explicit source profile permits controlled RSP reentry seeds while CPU
register/control continuity remains exact. Initial backing content and incoming
scalar/vector operands have no ultimate origin certificate. Cache/TLB/DMA/restore
interleavings and unsupported instructions/vector sources reject. This is
compiler-time receipt verification, no guest executor/native fallback. No
ProgramMap/solver/native waiver or progress-map promotion.

Authenticated actual result SHA256:
b244a6c2de930048215d10199859309fc036a719a293b3b39c911223b590aef3.
Independent unchanged-reference/disabled/instrumented/repeat controls still agree
on 16 checkpoints, complete CPU steps, reported state and normalized byte
snapshots; repeated instrumented capture is identical. Exact ares
9408cb43d4948fc3ea6e152a307a34348df3fe04 and all relied-on files are clean. Inspected
CPU LW/SW/ADDU, RSP scalar stores/SBV, SP Word bank routing and actual interpreter
boundaries. No upstream implementation copied into production.

Normalize only by copying the authenticated instrumented fields initial_dmem,
initial_imem, final_dmem, final_imem, steps and all 58 events, adding the explicit
format/profile strings. No operand, ordinal, context or primitive is synthesized.
Normalized source SHA256:
9d8b7778b0fb5ff7bea88e95d0f4b7b17ef71614236b14ea5460914d066e9a1c.
New entire report SHA256:
2dc31e222304cb1818d863bb3134eb3bf4dc76eb7885057f813899aa77005896.
All three chains agree with the prior report's actual read/write/context/byte
parents; final modeled memory hashes match independent actual snapshots. The
mixed chain uses read ordinal 45 into t0, while an equal-valued read ordinal 48
into t1 cannot steal that lineage. The final same-value ADDU/store and unscoped
write do not manufacture extra source-copy chains.

Three unit tests pass: RSP address bit12 still selects DMEM before CPU IMEM
installation, BREAK/zero-register false writer rejection, and source/report/effect
deletion. Synthetic CLI cases pass: same-value writer distinction, mixed/unknown
parents, definition cuts, wrong pointer/bank/width/context/opcode, source/report/input forgery, independent snapshot mismatch and generic phase/code-PC renaming.
All twenty retained actual-history forgeries also reject under Rust replay.

Mandatory local gate PASS: fmt check, strict locked workspace/all-target Clippy,
full locked workspace including actual outer fixed-point deletion adversary,
canonical CLI, new composition CLI, retained actual source/control comparisons
and twenty forgeries, diff check. No emulator rebuild, Actions or workflow.
Logs/inputs/reports under target/rsp-cpu-imem-rust-primary (ignored). ADR-0118;
STATUS/NEXT/DEVELOPMENT and original source note updated.

Consumed/superseded: the canonical stronger spike-047 production recommendation
and the rejected source-branch bounded copy verifier, already superseded by the
primary source reconciliation. PR #8 broader scalar-load dataflow and PR #37
DMEM-DMA egress remain pending; neither is closed/marked integrated here. The
new bridge is actual producer -> CPU definition -> executable-bank installation,
not proof of IMEM execution or RSP-universe closure.

Remaining: incoming operand/initial storage ancestry, complete producer/writer/
execution census, asynchronous/DMA/cache/mapping/restore composition, IMEM
executable consumption/lifetime, root universe and whole-ROM/native closure.
All source-ancestry/census/IMEM-execution/lifetime/native flags remain false.
