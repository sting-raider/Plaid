# Primary integration: lower IMEM storage cuts compose with executable reads

Base: 91b24c6480d70b625abeb1dd123467452018ee3b. Claim: 6172781852,
originally prepared against b7144340d584ff87987965ba6ab0cf2895752320.
Sources: canonical spike086 generic Memory::Writable mutation sensing, spike090
DMEM cuts, spike091 exact read/performed-RSP receipts and shared SP writer state.
No raw research branch is merged or represented as wholly superseded.

Strict raw history v8 admits exact completed lower IMEM Byte/Half/Word effects
and whole-bank fill/load cuts. Domain selection uses the actual IMEM object,
without serializing host pointers. The same shared SP writer selection revokes
only the affected lanes, including equal values. Both SP and PI/SP consumers use
this cut; neither constructs producer ancestry from a mutation sink. Previously
captured CPU/RSP read receipts keep their parents frozen. Lower DMA writes occur
before a separately captured higher installation; the install selects a fresh
writer rather than reviving an ended one. V8's containing SP projection is v4.
Old source policies reject the new record and preserve their prior wire shapes
when unselected. Restore/retirement rejects without execution-epoch evidence.

Retained pinned ISC ares 9408cb43d4948fc3ea6e152a307a34348df3fe04 controls
contain actual identity/translated PI copying, RAM-to-IMEM DMA, equal writes,
whole fill, short-file load, CPU SP execution and performed RSP instructions.
All baseline/disabled/enabled/repeat full machine/backing checkpoints agree:
342 records, 40 checkpoints, 42 effects, 56 IMEM reads, 42 performed instructions.
Each DMA installation is preceded by its actual two lower Word effects and
frozen RAM source read. Fixture descriptor/mapping/seed/step controls remain
opaque. Source SHA256:
59333bd2a5521eea0584726e7e62316f1070f2b93ee826dbf05067d653eece04.
Reference receipt SHA256:
47d96b18c51e24d76ac20a79704dd5fb48098214f48cef332a5a26c5117866a6.
All declared build/executable/control hashes and fixture source hashes were
rechecked from the migrated retained artifacts; no reference rebuild was needed.

Actual supplied 100k v8 prefix contains 436,756 body records, adding 12,096 IMEM
effects. The complete 424,660-record v7 body is preserved after normalizing only
header version/policy and shifted ordinal/context/fetch-context/read references.
The initial projection check omitted fetch_context normalization and was corrected;
no source event or production behavior changed. Complete canonical/independent
replay agrees on 100k fetches, zero full/partial PI ancestry, zero contradictions
and ordered chains bf9653cea12e9546e33724f4c32603455b467324554bdcbfcdbabf3cf5ff1ad8.
This early prefix has no performed RSP consumption; the positive consumption
control graph is separate. Fetch/checkpoint and complete repeat controls agree.
History SHA256:
a20ad2333d484c7ef8c701b53d8f1a1f32d65a92bb0e644fda213a5e2302a959.
Capture receipt SHA256:
e8b311da2e226532d5120e519c7f85958bb85859b427869db8b744e1f04020f6.
Final canonical report SHA256:
1ef2498fbfb00c3bf37a580e9d6f67cfcd4f801f99dbc255c8a3e92ef1c1ce22.
Final independent report SHA256:
ddf6ae2182bfe49da3bbb31b7411da9b449e7a7cd392670100b00fbf5d7179b6.
The retained 20M v5 evidence is reused only on the unchanged unselected source
path; no new 20M capture or RSP coverage is claimed.

Post-migration default-source recheck initially failed only on old C: include
prefixes. The portable comparison obtains the recorded root from the retained
pinned decoder include, normalizes source/output prefixes and compares every
remaining byte of generated source exactly. Historical receipts are unchanged.
The default shadows and exactly two original instruction-read sites pass.

Validation: focused malformed/legacy/equal/scalar/bulk/frozen/partial/reinstall
regressions, both consumers plus independent model, predecessor spike089/090/091
contracts, authenticated exact-pin controls, complete canonical/independent 100k
replay and prior-body projection. Full local locked workspace tests (including
outer-limit deletion), strict workspace/all-target Clippy, fmt, CLI, progress
regeneration and whitespace checks pass on the final candidate. No Actions.

The progress atlas gains only the bounded IMEM revocation milestone. Producer/
register/task ancestry, raw-pointer/hidden backend coverage, complete mutation
census, epochs/lifetimes, hardware consensus, first commercial CLOSED scope,
whole-ROM and native completion remain OPEN; every broad proof flag stays false.
