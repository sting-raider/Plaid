# Plaid launcher

A desktop game library for Plaid. You point it at your N64 ROM folder; it lists the
games with box art, recompiles a game into a native executable with live progress,
and launches it.

It is a Tauri 2 app: a Rust backend (`src-tauri/`) and a React + TypeScript UI (`src/`).
It is its own Cargo workspace, so the recompiler's gate does not build Tauri.

## Run it

Needs Node 20+, Rust, and a working Plaid checkout (see `CONTRIBUTIONS.md`: Python,
GCC, `.refs`, and the RT64 library for game windows).

```bash
cd apps/plaid-launcher
npm install
npm run tauri dev      # development window
npm run tauri build    # installer under src-tauri/target/release/bundle
cd src-tauri && cargo test
```

## How it works

- **Library:** scans the ROM folder (two levels deep) for `.z64`, `.v64` and `.n64`
  files and reads each header. Byte-swapped ROMs are converted to `.z64` copies in
  the app's data folder; the originals are only read.
- **Box art:** matched by title against
  [libretro-thumbnails](https://github.com/libretro-thumbnails/Nintendo_-_Nintendo_64)
  and cached in the app's data folder.
- **Compile:** runs `python scripts/native.py <rom> --rt64 --seconds N` in the Plaid
  folder and maps its output to pipeline phases (`src-tauri/src/progress.rs`).
  Builds land in `target/native/<name>/` and `target/rt64-shim/Release/<name>-rt64.exe`.
- **Play:** starts the window build with the game's save files
  (`target/native/<name>/<name>.eep|.sra|.fla`).
- **Settings:** controller bindings, graphics and experimental options, per game or
  as global defaults, are stored as JSON in the app's config folder. The native
  runtime does not read them yet; it still uses its built-in keyboard layout and a
  4:3 picture.
- **Updates:** at startup it runs `git fetch` in the Plaid folder and shows how far
  the checkout is behind `origin/main`.
