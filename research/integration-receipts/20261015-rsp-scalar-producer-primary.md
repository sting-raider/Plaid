# Primary integration: executable IMEM reads feed rooted scalar producers

Base: c9e1bc994275b8fbd9976b5d1f90f78b5901d500. Claim: 6175047611.
Reuse canonical spike060/rsp_cpu_imem ORI/ADDU expression logic, spike091 exact
read/performed identities and the existing original-clock SP/PI consumers.
The shared child module extracts the old expression implementation without
changing controlled-profile results. No independent production consumer, new
expression policy, native backend or raw research-branch merge is introduced.

Strict raw v9 admits explicit opaque operand roots and exactly 32 GPR values on
each performed begin/end. Roots must advance epoch identity and cut held parents,
even if snapshots are equal. Supported scalar instructions verify the complete
register transition with the existing semantics; unsupported producers stay
opaque and cut all scalar candidate parents. Logical PC, returned code-read ID,
begin/end context and operand-root epoch remain separate. Equal redefinitions
select the new context. Architectural zero remains explicit; captured root/input
values are not authenticated producer ancestry. Root cuts cannot rewrite frozen
code-read parents. Every complete occurrence is hashed; at most 64 producer
samples are retained. The containing SP report is v5. Legacy policies reject
roots/operand fields and retain old serialized shapes when unselected.

Focused synthetic complete-source graphs link ROM/PI/RAM/IMEM code consumption
to ORI and held definitions consumed by ADDU. The ADDU's separately opaque code
writer stays unknown rather than borrowing the earlier instruction's PI bytes.
Fresh roots with equal registers restore captured-input opacity. Equal ORI
redefinition changes the later ADDU parent. Both existing consumers and independent
replay/digest agree. Missing/reused/nested roots, missing/short/nonzero-zero or
incorrect/foreign snapshots, PC discontinuities, legacy admission and forged/
deleted producer reports reject. The shared Rust tests retain unknown-instruction
cuts, full-register checks and explicit boundary requirements.

Fresh pinned ISC ares 9408cb43d4948fc3ea6e152a307a34348df3fe04 reference
controls contain 356 events, 40 complete machine/backing checkpoints, 14 explicit
opaque host operand roots, 42 performed instructions, 20 ORI/ADDU definitions and
22 opaque instructions. Native read words/offsets agree with each definition;
baseline/disabled/enabled/repeat complete state and source controls agree. All
154 captured root/read/instruction observations also replay through the shared
Rust engine, with the independent ordered-producer digest agreeing exactly.
The portable regression is original synthetic numeric observation data; no ROM,
firmware, upstream implementation or game asset is committed. Its code byte
origins are marked unknown; the complete native capture remains separately
externally authenticated under ignored target/.

Actual source SHA256:
c3f2c2865fcbf788b0a54e404a785589435549bb7eafa3fac7845dd9b3fa8610.
Reference receipt SHA256:
6c56b4b22e872bf6d9c17ebf0108c0030500ba999f81a1564da55cdfd7ed6ae6.
Ordered producers:
10e6cad59bb4f3ddc8065f799f5a4087dc86c409433d37df23283a95024769d7.
Build/executable/control hashes are retained in the receipt. The initial harness
looked for an absent outer native_complete/source wrapper; corrected it to the
actual states/events schema and rechecked the retained outputs, without rebuilding
or changing guest behavior/assertions. All certification flags remain false.

Actual supplied 100k v9 capture retains all 436,756 previous body records byte-
for-byte; only header policy/version changes. Complete baseline/checkpoint/fetch/
repeat controls agree. Canonical/independent replay agrees on 100k fetches, zero
PI chains/contradictions and the preserved ordered fetch digest. This early prefix
has zero operand roots/producer instructions; positive producers are the separate
actual reference control graph and synthetic end-to-end code-parent graph.
History SHA256:
a262549bab180fb53ae4fb9391d310161a11234af168b43c810bc6052a7fd59a.
Capture receipt SHA256:
fac53d95347da96ae49e7c1d23e9bbcf2be935e1dc1bb25f5cdd3f542875c2c7.
Canonical report SHA256:
1c77c7a7e08bbd364f3d817144b0cc1e048ab46440edf7cf1d785394263ef94f.
Independent report SHA256:
ddf6ae2182bfe49da3bbb31b7411da9b449e7a7cd392670100b00fbf5d7179b6.

The boot adapter emits only the first opaque initial operand root. Later task/PC/
GPR discontinuities without a declared root reject. Host fixture roots are not
relabelled guest task/control/reset evidence. General instruction/vector producers,
DMEM/RAM sink composition, source/backend/writer completeness, execution epochs/
lifetimes, hardware consensus and whole-ROM/native closure remain OPEN. All broad
proof flags remain false. Earlier authenticated 20M paths remain unselected and
are not rerun or claimed as new producer coverage.

Validation: focused CLI and independent graphs/digests, actual reference controls,
portable native golden through Rust, shared controlled-profile regressions,
old IMEM/RSP/default-source recipe contracts, complete canonical/independent 100k
replay and exact prior-body comparison. Final local locked workspace/CLI, strict
workspace/all-target Clippy, fmt, progress and whitespace gates pass before CAS.
No Actions or gate waiver. Only the bounded scalar/code-read progress milestone
is added; existing broad partial/open milestones are not promoted.
