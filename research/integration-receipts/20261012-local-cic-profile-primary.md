# Explicit local CIC profile and canonical boot-fetch composition

Base: b1d1c313b633584897852b32413c516d19f3696a. Claim: 6118288053.

The independently diagnosed supplied ROM is CIC-NUS-6105, not the existing
reference driver's hardcoded 6102. Add an explicit optional CIC argument only
to profiled PIF boot captures. Cartridge configuration and metadata share it;
6102 remains the exact default. The importer admits only those two declared
NTSC profiles and retains source/firmware/identity gates. No game hash whitelist.

Exact ares pin: 9408cb43d4948fc3ea6e152a307a34348df3fe04. Clean canonical
source objects:
- cic/cic.cpp: 94bbdd7400585495a66862097fbaf7c80a667f19b76bfe64e21638cd5f295148
- cic/commands.cpp: 3a56e261ccde4dedccc4e12401141e6c87165535c7be4174f36829cf76ce2e73
- pif/hle.cpp: 4b7546a07b765e1cb825ab6ce060dbfcc652c0042f7a28dcfb4756c0b2b61442
- mia/medium/nintendo-64.cpp: 78dd779ccf6d7adcfc3fdcbf7dbf6016093b20b5390ce18c573f6773e8b73d4d

CIC configuration is seed 0x91/checksum 8618a45bc2d3/RealChallenge. The retained
standalone pinned-mia diagnostic selected the same CIC from local IPL3 bytes.
Firmware: 1984 bytes, SHA256
fa7b09795ef1e54461e59f6f2d902368133e3f1cd980e34383e6a780d74beffd.
ROM: 33554432 bytes, canonical SHA256
49acd3885f13b0730119b78fb970911cc8aba614fe383368015c21565983368d.
Neither input nor captured words/maps are committed.

One necessary updated profiled observer build captures 10,000 actual fetches:
2,055 PIF, 7,945 SP, zero RAM/cartridge fetches. Disabled/repeated full existing
machine checkpoints and messages agree; repeated trace bytes are identical.
Trace SHA256: c401d0df6dae791d99c6e5aa5f0872ad64e2c06c9fb4404db0bf08e4ecdf7de6.
Checkpoint: b6292f2b3341574b7c9432609fe512ad8d3d9478af6b4d22a8327e1b0e8003b5.
Canonical import retains 305 summaries; source/firmware recheck passes. Whole-ROM
solve stays OPEN with eight blockers, including unknown execution identity.
Final PC is ffffffffa4001568; this is not a boot-completion claim.

Reuse that exact compatible build for the homebrew 6102 control. Default and
explicit 6102 traces/checkpoints match; full trace, checkpoint and messages are
byte-identical to the retained spike-040 v5 projection. No second reference build.
6102 trace: 4c21103a606df872aa13b61fc58c7838d124b9ff66c924dde7f66fff8f84e8ca.
6102 checkpoint: 51bf289ab95d381bea8a6fd302ff6aa0bab3af23b1410b35c767e2d4c6547ce7.

Focused 14-test fetch suite passes, including source substitution and unchanged
OPEN status; actual unsupported CIC, wrong firmware and supported-CIC source
substitution adversaries reject. Full local fmt, strict locked workspace/all-target
Clippy, locked workspace tests, CLI and diff gates pass. The recipe's reused-build
output-directory defect was caught and fixed before landing; both recipe paths
and retained replay now pass. No Actions execution or proof waiver.

Driver: c5a8f75cf1e11165714c5201fdf6aeb7baa30b3c10854ae1f6544aef9764546b.
Selector: 3ab4620ab17ed332fa2a41d7c2608735d0ccd736c6192bd9d92dcd330b1468e9.
Ignored controls/build/source receipts: target/local-boot-primary/.
All CIC identity/hardware boot/census/native flags remain false. No progress
milestone change. Next compose actual RAM/PI/SP producer/lifetime chronology.
