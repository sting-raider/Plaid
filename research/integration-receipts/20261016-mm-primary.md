# Primary integration: ROM in, native out; Majora's Mask runs its intro natively

Base: 3cd1b2b. Milestone 5. Worker: Claude co-integrator, user-authorized on main.

**ADR-0183:**
- `plaid infer-loads` declares the reset stub and the file-table files
  that code places at fixed addresses. A file's destination is where its
  own calls begin functions.
- `scripts/native.py <rom>` runs the whole pipeline. It builds nothing
  unless the address-taken scope is CLOSED.
- Identification and closure fixes, all general:
  - 8-byte signatures must start a plausible function;
  - `osFlash*` leaves the runtime set and `osGetIntMask` joins it;
  - `andi`-masked `jr` tables, with a limit of 1024 entries;
  - padding after a working delay slot;
  - CFG-walk constant pairing.
- Runtime:
  - `__osInitialize_common`;
  - no VRU;
  - threads start at `sp - 16`;
  - 8 MiB (Expansion Pak);
  - the first VI comes a frame after boot;
  - an exact VR4300 D-cache model;
  - FlashRAM as ares;
  - the stop report gains its GPRs.

Measured with `plaid solve <rom> <map> [scope]` on the exact tree.
SM64 uses its curated identification; OoT and MM use inferred loads:

| Image | Blocks | Sites | `--address-taken` | `--guarded-ram` | Whole ROM |
|---|---|---|---|---|---|
| SM64 | 45,419 | 4,385 | CLOSED, 15 assumptions | 91 blockers | 4,820 blockers |
| OoT, fixed image | 29,613 | 2,574 | CLOSED, 13 assumptions | 122 blockers | 3,120 blockers |
| OoT + 468 overlays | 155,770 | 14,869 | CLOSED, 14 assumptions | 711 blockers | 16,338 blockers |
| MM + overlays | 214,963 | 19,138 | CLOSED, 14 assumptions | 891 blockers | 21,313 blockers |

| MM USA, local | Before | After |
|---|---|---|
| hand-written inputs | boot/code loads, curated identification | none (`scripts/native.py`) |
| closure | — | CLOSED, address-taken scope |
| native, headless | — | 3,181 VIs, 1,125 gfx / 3,167 audio tasks, 6,169 PI DMAs; fault 3 at a call to heap overlay 0x805665e0 |
| native, RT64 | — | mask intro, Happy Mask Salesman, Clock Town attract scene (screenshots taken locally) |
| discover + solve, all four images (release) | — | 3 min 0 s |

Gate on the exact tree, all passing:

| Check | Notes |
|---|---|
| `cargo fmt --all -- --check` | |
| `cargo clippy --locked --workspace --all-targets -- -D warnings` | |
| `cargo test --locked --workspace` | new: load inference, masked tables, slot padding, far-hoisted constant |
| `python scripts/test_cli.py` | identify fixture widened to 12 bytes |
| `python runtime/test_runtime.py` | the sched check raced the t=0 VI; the first VI now comes a frame after boot |
| spike096 | new: `clean_uncached`, `evicted_uncached`, `stale_cached`, `stale_overwritten` (43 s) |
| `tools/progress.py --record` and `--check` | |

ROMs, maps, saves, lowered C and RSP snapshots stay local. Actions were
not used. `native_complete` stays false.
