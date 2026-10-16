# Primary integration: the boot image and its segments come from the ROM alone

Base: 0a8047e. Milestone 5. Worker: Claude co-integrator, user-authorized on main.

**ADR-0184:**
- `RomHeader.boot_address` applies the CIC-6103/6106 entry offset, with
  the CIC identified by n64sym's IPL3 CRC32.
- `CanonicalRom::boot_image_size` takes the main image's size from the
  entry stub's BSS clear.
- Without a file table, `infer-loads` takes candidate files from ROM
  ranges whose start and end the code builds a few words apart.

| Local ROM | Before | After |
|---|---|---|
| F-Zero X (USA), no decomp | entry 0x80267000 (wrong), 10 blocks, 1 blocker | 0x80067000, 0x71030-byte image + 3 inferred segments, 11,398 blocks, 20 blockers (all overlay-slot calls) |
| SM64 loads | 2 by hand | engine segment inferred exactly; goddard not found (level script) |
| OoT + overlays, `native.py` window | 1 MiB | 0x6960: same loads, 155,770 blocks, CLOSED |
| MM + overlays, `native.py` window | 1 MiB | 0x19500: same loads, 214,963 blocks, CLOSED |

Gate on the exact tree, all passing:

| Check | Notes |
|---|---|
| `cargo fmt --all -- --check` | |
| `cargo clippy --locked --workspace --all-targets -- -D warnings` | |
| `cargo test --locked --workspace` | 706 passed; new: boot-image bound, CIC default, table-free range |
| `python scripts/test_cli.py` | |
| `python runtime/test_runtime.py` | |
| spike096 | unchanged lowering |
| `tools/progress.py --record` and `--check` | |
| whole gate | 151 s plus spike096 |

ROMs, maps and loads stay local. Actions were not used. `native_complete`
stays false.
