# Code-built PI descriptor overlays

Worker: `rs-descriptor-overlays-a7051c14`. Prepared base:
`c8a0bf5ff912e624907fb1d8bf1ae58d074e5d82`. ADR-0264.

## Claim and scope

Ordered stores of a PI address, RAM, size and matching RAM end can name raw
load candidates without a file table or title-specific addresses. They do
not prove executable sections, reachability, load order or native completeness.
The earlier uncommitted candidate in worktree `t3-46e7409d` was inspected
read-only, recovered onto current main, hardened for possible aliasing
stores and given additional bounds/CLI tests. Its original files and ignored
evidence were preserved. No child agents were used.

`descriptor_loads::infer` requires all four fields through one unchanged
base, in source/RAM/size/end order, within 64 instructions of each store.
The relative offsets are 0/0x20/0x40/0x64; neither SP nor absolute descriptor
offsets are special. Source must be a `0xb0000000 | ROM` cartridge alias.
Source/destination/size must be word-aligned, size nonzero, ROM end bounded,
RAM within 8 MiB and nonwrapping RAM + size equal to the stored end. Constant
and store knowledge is cut at transfers, clobbers and possible overwrites.
Unmodeled paths or layouts remain unrecognized, never guessed.

The CLI emits raw slot declarations and source evidence; `discover --overlays`
also recognizes the construction in its composed image and emits hashed raw
catalog overlays. Existing catalog superseding/deduplication preserves valid
formats (ADR-0263). Catalog files are always slots, even a singleton, because
they use bounded catalog layouts rather than relocation footers. Normal
content verification, binding ambiguity, writes and missing targets still
fail closed. Data-first payloads retain the raw-slot candidate text fallback;
no new entry root or invented section boundary is supplied.

## Rogue Squadron reproduction

Local user-supplied Star Wars - Rogue Squadron (USA) (Rev 1), `.z64` under
`C:/Users/aliza/Documents/ROMs/N64`. No ROM bytes, assets or traces are stored
in git. Canonical ROM SHA-256:
`4813551d01d3a3474df3a51f84c31059cd2a9d1eeae7885dda51a88ee6b9f88d`.
Exact command before and after:

```powershell
$env:SDL_AUDIODRIVER = 'dummy'
python scripts/native.py <rom> --rt64 --seconds 30
```

Recognized files (all linked at `0x800960e0`):

| ROM range | Size | RAM end | Completing store in base image |
| --- | --- | --- | --- |
| `0x96ce0..0xfdec0` | `0x671e0` | `0x800fd2c0` | `+0xf54` |
| `0xfdec0..0x126660` | `0x287a0` | `0x800be880` | `+0xf90` |
| `0x126660..0x131ea0` | `0xb840` | `0x800a1920` | `+0xfd0` |

| Measurement | Main before | Candidate after |
| --- | --- | --- |
| Inferred descriptors / content-bound overlays | 0 / 0 | 3 / 3 |
| Decoded blocks | 39,550 | 50,862 |
| Address-taken blockers | 15 | 28 |
| Residual blockers / sites | 5 / 10 | 13 / 15 |
| Native artifact / 30 s gameplay | refused / unavailable | refused / unavailable |
| VI / fault / runtime PC | unavailable | unavailable |
| Pipeline wall seconds | 41.681 | 40.650 |

Those timings include different compilation/cache states, so they are receipts,
not a speedup claim. Initial clean-checkout compilation and a recovered-source
build took longer; only clean-main and restored-guard runs support these results.
Local build units were reused for controls; native.py still checks content,
compiler and flags before reusing any object. Shared `.refs` and the RT64 shim
were accessed through junctions, never refetched or rebuilt. Junction targets
were never removed.

The original five residual blockers persist:

- Data `0x7677696e` at `0x80096d50`: invalid instruction and unsupported effect.
- An unmapped target, unresolved direct call and unsupported delay slot from
  data decoded at `0x80091a48`. The actual target in this ROM is `0x8334b334`
  (the task's `0x8334b034` does not occur in either solve).

The eight additional blockers are invalid/unsupported pairs at `0x80806d50`,
`0x80876d50`, `0x808b1148` and `0x808b12b8`. The first two are the first and
second alternates' copies of linked `0x80096d50`; both are data, while the
third alternate has a CPU function at that offset. The latter two are
float-valued data reached in the third alternate. All files are data-first;
their first word is not an executable entry. Merely recognizing them cannot
prove internal sections or which alternate any particular call requires.

Independent false-path evidence: ROM `0x925bc` / RAM `0x800919bc` contains
`BLTZAL $zero, 0x80091a48` (`0x04100022`), a get-PC idiom that writes RA but
never takes its branch. Discovery currently follows both paths and decodes
the target's data word `0x0ccd2ccd` as JAL to `0x8334b334`. Pinned ares
`9408cb43d4948fc3ea6e152a307a34348df3fe04`,
`ares/n64/cpu/interpreter-ipu.cpp:89`, writes RA then branches only for a
negative source. This was read as reference evidence; no code was copied,
and this change does not alter branch semantics or prune those blockers.

## Synthetic verification

Six unit tests cover exact recognition, moved descriptor offsets/base,
signed ADDIU low halves and computed end, optional tail fields, wrong end,
wrong PI alias, ROM/RAM bounds, alignment, zero size, constant/base clobbers,
control-flow cuts, unknown/partial/aliasing stores and expiration. A catalog
composition test checks derived slot text/data and `verify_slots`.
Self-review also reproduced descriptors incorrectly joined across ERET,
SYSCALL and BREAK; these now cut tracking, with retained regressions.
Overlapping word stores discard the affected recorded fields too.
The CLI contract checks infer-loads plus discovery with and without supplied
declarations, two alternate call entries, no descriptor-start entry roots,
deduplication and rejection of mismatching ends.

Mutation: replace `ram.checked_add(size) == Some(value)` with an overflow-only
test. The exact inconsistent-end test fails on its rejection assertion;
the mutation was killed in 32.745 s and the original source restored.
These are discovery changes; no ISA lowering or runtime implementation changes.
The final CLI also rejects each ERET/SYSCALL/BREAK synthetic probe that the
pre-hardening implementation had accepted.

`infer-loads` output for all six control ROMs is byte-identical between the
clean-main binary and the final candidate. The new descriptor recognizer
adds no inferred declaration to those controls. The comparison fixtures and
per-command wall timings are ignored under
`target/receipts/inference-comparison/`.

## Local acceptance receipt

All commands exited 0, repeated on the final proposed tree before integration:

```text
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace
python scripts/test_cli.py
python tools/progress.py --check
```

Rust: 937 tests passed, one pre-existing test ignored. The runtime suite was
not required: neither `runtime/` nor `plaid-lower` production code changed.
All diagnostic instrumentation below stays under ignored `target/`.

Visible native controls used `--rt64 --seconds 30` and
`SDL_AUDIODRIVER=dummy`. Fault PC 0 means no fault, not an observed executing PC.

| Control | VI | Fault | Fault PC | Pipeline seconds |
| --- | --- | --- | --- | --- |
| Paper Mario | 1797 | 0 | `00000000` | 381.766 |
| Mario Party 2 | 8 | 8 | `80102800` | 529.061 |
| Banjo-Kazooie | 1773 | 0 | `00000000` | 225.968 |
| Majora's Mask | 1681 | 0 | `00000000` | 522.095 |
| Star Fox 64 | 1762 | 0 | `00000000` | 88.619 |
| Ocarina of Time | 1766 | 0 | `00000000` | 301.091 |

MP2 matches the requested stop (audio 3, PI 17). OoT passed first time;
the microcode-ambiguity retry was not needed. These check fault/control-flow
regressions, not visual correctness. Rogue Squadron remains an analysis result,
not an accepted native game run. Logs, maps, timing JSON and synthetic probes
remain under ignored `target/receipts/`.

## Separate SF64 rendering defect: reproduces on current main

The user reported tiled blue/white garbage around the starfield intro's
borders, with fading centered text. This is a real rendering failure.
Rogue Squadron emitted no executable; the window was SF64. The attachment's
original VI counter is unknown, so the measurements below belong to the
explicitly reproduced baseline frame, not a guessed counter for the attachment.

A visible silent baseline diagnostic was built from exact `origin/main`
`c8a0bf5ff912e624907fb1d8bf1ae58d074e5d82` runtime source and its existing
SF64 generated C/objects, with observation-only VI logging and frame capture.
It linked the same shared RT64 DLL; the shim was not rebuilt. SF64's main
generated C and all 16 CPU parts are byte-identical to the candidate's.
The 32 s baseline run exited 0, and the VI 600 image shows the same border
garbage around a starfield and fading `I N` text. VI 1740 also shows it around
the ship scene. Thus this is pre-existing on current main, not caused by
descriptor recognition. No renderer behavior was changed to hide it.

At reproduced frame VI 600 (hex register values passed to the renderer):

```text
framebuffer physical origin = 0x003daa80; width = 320 pixels
STATUS=0000300e ORIGIN=003daa80 WIDTH=00000140 INTR=00000002
CURRENT=00000000 BURST=03e52239 V_SYNC=0000020d H_SYNC=00000c15
LEAP=0c150c15 H_VIDEO=006c02ec V_VIDEO=002501ff V_BURST=000e0204
X_SCALE=00000200 Y_SCALE=00000400
```

The scanout origin switches between the game's buffers; it must be read
from the per-frame log rather than inferred from the earlier control's final
summary. `CURRENT` is the array supplied to RT64; the guest's dynamically
computed VI-line read is a separate runtime operation. Framebuffer
origin/width here are the VI scanout values, not a claim about an
independently traced RDP SetColorImage command.

Evidence is preserved locally, never committed as game assets:

- `target/receipts/sf64-render/sf64-main-screen-vi-600.bmp`, SHA-256
  `88c3b73c19a73fa45a55c76dc3548660210ca2977873b1b081d4aa1ebabb85c3`.
- `target/receipts/sf64-render/sf64-main-screen-vi-1740.bmp`, SHA-256
  `21471e706f6b1e276965d617e2dccdb76db5d14fdf902e70c9c20341e5a95a6c`.
- `target/receipts/sf64-render/vi.jsonl`, SHA-256
  `6319691ffbc8b1424b130561d7509b4cec3575d105f36070ff26fd000cdaa31e`.
- Diagnostic source, compile/run driver and logs in that same directory.

The ordinary desktop-capture helper was unavailable (native-pipe error);
own-process diagnostic capture recovered the evidence. An initial window-DC
capture was black and is not used as rendering evidence. The retained
`*-screen-*` images capture the displayed client region instead.

Separate follow-up: compare VI origin/width and H/V/X/Y scaling against RDP
color-image dimensions and scissor/clear bounds, then trace texture/TMEM
addresses if needed. The root cause is not established by this reproduction.
Do not classify the visual result as accepted merely because fault is 0.
