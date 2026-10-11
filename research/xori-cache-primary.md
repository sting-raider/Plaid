# Primary harvest: XORI through cache visibility

2026-10-11. Executed behavior retained; abstract generation model not promoted.

Reviewed complete note, fixture, runner, model and issue #4 closeout
6091158618 from `research/xori-cache-fetch-compose-gpt56sol` exact head
`20c342f6255ac93c7c0e04a066124313d4dfb42e`. Hypothesis: actual transformed
cached stores require successful writeback and a later instruction-cache refill
before their changed bits become executable; current backing cannot replace
resident instruction identity.

The primary unmodified exact-ares run in spike 048 reproduces all four scenarios
and the original compact evidence SHA-256
`707e06fecb81975e8e611b13cfc55f6cdc28ab1916975f8ab105eaf083e51910`.
Two executions report identical selected facts. Normal XORI 0x00ff transforms
0x240200fd into 0x24020002; cached store and completed writeback both still
execute resident 0x24020001. Only later invalidate/refill executes new bits.
Refill before writeback continues executing old bits after backing becomes new.
XORI zero executes a distinct instruction with identical source/output bits.
A later uncached same-value writer produces the same final instruction payload.

Downloaded final-head Actions 38005565416 artifact
`xori-cache-fetch-compose-evidence` (11650409967). Its evidence JSON SHA-256
`9f7f571b9eb0229d27cd9af76b9e8445b6060170ad5bc8f7645b2322494fc068`
matches the primary parsed facts; model report SHA-256
`4908c05d000b056b151359ebdc3c4ddfdb19d20de91272f63c2f9fbb34fb2836`
also matches. The branch's eight forged-history rejections reproduce, with
compact model report SHA-256
`d49f6730ae0d81bfe7dd38476e97419a174fbfb8e354d7f098080e89c069b2a4`.

The replay supplies abstract loads, register generations, cache stores,
writebacks and fills. It is useful as a proof-shape example: foreign same-value
writers cut the transform chain, early fills retain old backing, and XORI zero
needs an explicit transform generation. It does not measure those generation
edges in the executed fixture. Its low-32-bit arithmetic accepts `imm += 2**32`
in both normal and identity histories, preserving the same final chains despite
an impossible decoded u16 operand. There are no decoded words, full GPR histories,
exact cache slot/transaction spans or source-bound event census in this model.
This is a model vocabulary limitation, not an ares instruction bug. Main's
actual XORI contract rejects the corresponding oversized captured word; a new
deterministic regression retains that boundary.

Reviewed exact ares CPU CACHE 0x19/0x10, instruction-cache fetch/fill/read, D-cache
write/fill/writeback, memory routing, LW/XORI/SW and RDRAM source contracts.
Spike 048 checks the five exact relied-on Git source blobs and uses the shared
builder's clean exact-head gate. No reference callback or instruction/cache patch
is applied. Full locked plaid-core, formatting and strict locked workspace Clippy
pass, along with four visibility and seven actual-XORI synthetic tests.

Disposition: reconcile the original behavior fixture on main and supersede its
branch runner/workflow. Keep the branch model as reviewed abstract specification
evidence. Do not import it as an authenticated ancestry verifier or port its
synthetic generation IDs into ProgramMap. No full-state observer-neutrality
comparison applies to this uninstrumented fixture. Unified measured chronology,
complete attempts/mutations, mapping/cache lifetimes, general transforms,
independent hardware behavior, whole-ROM and native completeness remain OPEN.
