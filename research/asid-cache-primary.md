# Primary harvest: guest EntryHi and stale resident reactivation

2026-10-11. Source behavior reconciled under spike 053; lifetime stays OPEN.

Reviewed complete note/driver/runner/model/source guard/workflow and ledger
closeout 6086361454 at `research/asid-icache-lifetime-gpt56sol` exact final head
`a23c432ebc11ad2efdda8a33db7b5af6b9401896`. Successful Actions 37969367332
executed code head `9071d5471fe85eca0c17fb9626492616036449a1`; final note-only
head has no separate workflow run. Artifact 11635555459 results SHA-256
`448051784104daca1c2ec2c079a60afcd18ace1b71b708a3bcf815c74196714d`
was authenticated and all fresh measured facts match it.

Unmodified pinned ares executes actual guest MTC0 EntryHi plus three NOPs through
an uncached helper. It selects already-installed non-global mappings for VA
0x4000. ASID 0x11 fills PA 0x1000 with ORI immediate 0x1111. While ASID 0x22 is
active, direct debugger writes change that backing to immediate 0x4444. The
same-value context write preserves its snapshot; global code at a different
cache index does not replace the line. Unmatched ASID 0x44 faults with exception
2 and BadVAddr 0x4000 without a fill. Returning to 0x11 hits the stale resident
value with misses 2 -> 2. ASID 0x33 selects equal payload at PA 0x5000 and misses
2 -> 3, changing tags 0x1001 -> 0x5001. Returning to 0x11 then misses 3 -> 4 and
executes fresh 0x4444. Full installed-entry semantic snapshots are internally
compared throughout; output reports equality flags. Final digest covers cache
tag/index/words, not complete machine state. CPU/RSP recompilers are disabled.

Exact MTC0/setControlRegister, TLB matching/translation and I-cache hit/fill
source objects were inspected. Four ares blobs and the Gopher cache blob are
guarded at clean pins. The original absence-of-mutation guard selected the
getter's first EntryHi case; main isolates the setter instead. Gopher's physical
index remains an explicit source disagreement with ares's virtual index. No
reference implementation is copied or linked into native mode; original ISC
fixture/guards are reused, while reference code/notices/results remain ignored.

The old runner's original assertions accept offsetting every miss counter by
100, clearing both tag valid bits, and replacing the cache digest. Main checks
all 32 exact typed report leaves and exact schema; those cases and every leaf
mutation reject (36 total). Four synthetic contracts also preserve missing
counter and integer-for-boolean rejection. Two actual runs are byte-identical.
Full plaid-core, fmt check and strict locked workspace/all-target Clippy pass.

Fresh stdout SHA-256:
`103bcf603e8d4a70bac74c07c99d1d1ee6993db92295563e2921db3d5a520d55`.
Primary schema-0 result SHA-256:
`006b56b14509eb4392f53a50f356a780fccc0a9692d9a05f316b6b8796cde224`.
Reproduce with `python spikes/053-ares-asid-cache-lifetime/run.py`.

Separately replayed the abstract 50k-history model: 14,873 fetches, 5,246 faults,
4,373 same-value context writes, 3,597 stale/current-backing counterexamples and
1,144 equal-payload different-PA cases. Report digest
`97228e1e17f1810806795d40e346e5a7832d77a5441ef609c66aaf1f708ebd8f`
matches closeout. Its four rejected dictionaries are comparisons against
precomputed expected identities, not authentication of a measured writer
history. Preserve the counterexample; do not promote that model as a verifier.

Disposition: retain finite behavior and reject the old report validator.
Temporary context inactivity alone cannot retire resident code. Direct TLBWI
setup, debugger backing mutation and exception resets do not establish a guest
writer census. Generation histories, backing/fill ancestry, other mutation and
reset/restore paths, privilege/region/cache geometry, hardware index policy,
complete executable lifetimes and whole-ROM/native closure remain OPEN. No new
architecture or progress milestone and no branch-only CI workflow imported.
