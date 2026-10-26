# Rogue Squadron name entry and mission continuation (ADR-0280)

Worker `rs-name-entry-dfe42999`, prepared base `afaae4c2`.
Direct integration authorized; no children, README edits or shared reference writes.
All game windows visible with SDL dummy audio. Ignored evidence lives under
`target/receipts/rs-name-entry`; complete FPR bits and framebuffer RDRAM are retained.

## Reproduction and hypotheses

Unchanged ADR-0279 executable, privately copied saves/bridge: 65-second request
stops at VI1271, fault11, PC80013408 (993 graphics,1229 audio tasks).
Prefix Start600/1000/1200/1500/1800/2000, then A2200/2300/2400/2500/2600/
2800/3000/3200/3400, each4VIs. It stops before the later inputs.
The instruction is SWC1 f26,0x24(s2), live Status2400ff01/FR1; generated
code uses a checked FR0 default when intra-function data flow is unknown.

Competing hypotheses: missing interprocedural FR facts select a fixed layout;
incorrect FPR alias semantics; missing executable entry. Compare the actual
one-instruction state and a synthetic shared helper called in FR1/FR0/FR1
against pinned ares9408cb43 before changing production. UNKNOWN stays unknown;
no snapshot or game address will seed compilation.

Validation and continuation are in progress; no mission or landing claim yet.

## General fix and first verification

Pinned ares accepts the captured e65a0024 store at80013408 in Status2400ff01,
writing00000000 at physical0010fcd0. All32 canonical FPRs, all GPRs, HI/LO,
FCSR and PC+4 match; this is a one-instruction cold-cache check, not historical
cache replay. Its ISC license and exact pinned FPR accessor/Status code were
read only; no implementation body is copied into production.

A shared synthetic helper called in FR1/FR0/FR1 reaches exit in ares while
both fixed native map layouts fault11. Unknown entry/call/join facts now emit
both existing checked native layouts, selected by live Status, then fr_mode,
then the declared bare-harness default when neither receipt exists. Proven
intra-function facts retain their layout checks. BC1 uses CU1, not FPR layout.
No runtime guest decoder, interpreter, JIT, discovered-target seed or game key.

`python runtime/test_call_fr.py`:4 complete ares/native matches across both
map defaults and SDK/plain contexts (all GPR/FPR/PC/HI/LO/FCSR/Status/64KiB RAM),
callee FR changes, odd loads/stores/arithmetic/conversions, comparisons and
ordinary/likely branch slots.10 Status/mode/default precedence cases pass;
CU1 refusal preserves the whole state; map-only mutations fault11 in both
defaults. Existing dynamic-FR verifier:12 full-state matches, both join paths
now use the correct live layout; inverted inferred guard still killed.
`cargo test --locked -p plaid-lower` passes. Final gate/controls still pending.

## PC-relative shared-tail calls on mission selection

The FR candidate reaches the Ambush at Mos Eisley level-selection image, then
VI2520/fault3/80091d88 (2100 graphics,2462 audio). JALR t3 asks for80091e0c.
The caller's untaken BLTZAL zero at80091c74 still sets RA80091c7c; ADDIU
t3,ra,0190 builds80091e0c. Nearby paths likewise construct80091e24/80091e34.
These are decoded integer helpers with a shared suffix, not missing overlays.
Pinned ares interpreter-ipu.cpp writes RA before testing the branch condition.

Address-pointer discovery now seeds PC+8 from only statically untaken linked
branches and follows the existing bounded decoded CFG to ADDIU/ORI. Explicit
and implicit link-register writes kill the source; likely annulment and slot
architectural PCs are preserved. Explicit PC-relative roots may name an
internal shared tail after CPU-body validation. Solver dispatch rederives
those roots from decoded source bytes; map membership alone cannot authorize
one. No target from a capture is a compiler input or closed-set certificate.

The synthetic ordinary/likely-link fixture is red on retained baseline
(fault3 at its second indirect call), and green on the candidate with all
GPR/FPR/PC/HI/LO/FCSR/output RAM equal to pinned ares. Removing its discovered
shared-tail dispatch entry faults3. Unit negatives cover overwritten RA,
unknown-condition links, annulled slots, invalid CPU bodies and packed slots.
Fresh RS discovery from ROM/id/inferred loads recovers all three entries;
47904->47918 blocks, residual solve remains accepted with16 sites and
native_complete:false. Subsequent native continuation and final gate pending.

## Recovery review in `t3/rs-name-entry-r2`

Recovered all three interrupted milestones on `afaae4c2`, with no child agents.
The first reproduction used a different copied EEPROM and reached an idle name
screen without the expected fault; it is excluded from the matching-input claim.
With the prior worker's EEPROM, the retained baseline again stops at VI1271,
fault11/80013408 (983 graphics/1219 audio). Full stop state and RDRAM are retained
under this worktree's `target/receipts/rs-name-entry`; the initial EEPROM is
preserved privately at `target/inputs/rs.eep`. Saves and bridge/executable inputs
are hashed in every new run receipt. Review and fresh gate remain in progress.

## Recovered native continuation

Fresh candidate with the matched EEPROM passes the old FR refusal. Start600/
1000/1200/1500 (four VIs each),24s, ends VI1436/fault0/PC00000000 with SELECT
GAME in the RDRAM PNG. Explicit new-pilot route: Start600/1000, D-right1200,
Start1500,32s ends VI1918/fault0/PC00000000 with ENTER NAME and the alphabet.
A completely fresh EEPROM takes different logo/intro timing; the retained
menu sequence is not claimed for that startup state.

The full prior existing-pilot prefix,65s, reaches Chapter I's crawl at
VI3886/fault0/PC00000000. Extending A presses through VI8000,150s reaches
VI8978/fault0/PC00000000 and an X-wing flyover over the first mission's desert.
This is a first-mission cinematic checkpoint; HUD/interactive verification and
the new-pilot continuation are still being checked, rather than inferred from it.

Fresh ROM/id/inferred-load discovery with the final CLI exactly reproduces the
recovered candidate map:47918 blocks,16 residual sites,native_complete:false.
A new deterministic solver regression changes only the pointer source's delay
slot to overwrite RA; its unchanged map/shared-tail body no longer authorizes
address-taken dispatch. This supplements the reference and entry-removal tests.

## New pilot to playable first mission

The final extended new-pilot drive ends at205s, VI12284, fault0, PC00000000,
5027 graphics/8281 audio tasks. `rs-new-pilot-play-r2.png` shows the X-wing,
reticle, radar and weapon counter over the first mission desert. All PNGs are
VI-derived RDRAM/framebuffer readbacks, not desktop captures. No additional
production blocker was encountered through this finite checkpoint. Completion
of the mission and later content remain unverified.

Working retained-EEPROM sequence (every press held4VIs):

- Start:600,1000
- D-right (`0x0100`):1200
- Start:1500
- A:1800,1900,2000
- Start:2200
- A:2400,2600,2800,3000,3200,3400
- B (`0x4000`):4000,4400,4800,5200
- A:6000,6500,7000,7500,8000,8500,9000,9500,10000,11000

Start=`0x1000`, A=`0x8000`; flags use `--press <mask>@<VI>:4` and `--seconds 205`.
The exact command, input hashes, complete stop state and framebuffer are in
`target/receipts/rs-name-entry/rs-new-pilot-play-r2.{json,rdram,png}`. The new-pilot
run enters a previously empty second slot. The same prefix without the later
A/B inputs gives ENTER NAME at32s/VI1918. A150s run without B remains in the
opening cinematic; do not treat cinematic images alone as interactive gameplay.

Build verification: default GCC15.2 CPU-O1/RSP-O2 flags. Every CPU source was
freshly regenerated from its retained ROM-bound map; copied RSP source/object
bytes and original normal compiler/header/flag keys were independently checked.
The unchanged ADR0279 private production bridge is copied locally and hashed;
shared .refs, RT64 patches/bridge and Release DLLs are untouched. No shim ctest
or shared rebuild is needed for this compiler-only change.

Local gate commands, exit codes and timings are machine-readable in
`gate-r2.json` and `runtime-gate-r2.json`, with individual logs in the ignored
receipt directory. Quiet30s old/candidate RS and PM/BK/MM/SF64/OoT controls,
the full MP2 destination list and OoT60s save-load receipts are retained there.
VI/fault/PC always come from stop JSON. Save inputs are copied privately and
hashed. Any final integration SHA/tree/base is recorded in `integration.json`.
