# Contributing to Plaid

Plaid turns an untouched N64 ROM into a native program with no emulator inside
(see `README.md`). Contributions from people and from AI agents are both welcome,
under the same rules. This file is the whole path from a fresh clone to a landed
change. The project rules live in [`AGENTS.md`](AGENTS.md); read it before your
first change.

There are two ways in:

| You are | You can push to `main`? | How your work lands |
| --- | --- | --- |
| A maintainer worker (on the project's own machines) | yes | exact-head CAS, see `AGENTS.md` and `ORCHESTRATION.md` |
| Anyone else: a person, or an agent working elsewhere | no | fork + pull request, described below |

## 1. Set up (about 15 minutes, plus the first build)

You need:

- Rust: the version in `rust-toolchain.toml` (`rustup` installs it automatically
  the first time you run `cargo` in the checkout).
- Python 3.11 or newer.
- GCC/G++ 15.2: MinGW-w64 on Windows (for example via MSYS2), the system GCC on Linux.
  The native build, runtime tests and reference oracles compile C/C++ with it.
- Git. WSL is not needed on Windows.

```bash
git clone https://github.com/<you>/Plaid && cd Plaid      # your fork
python scripts/fetch_refs.py                               # pinned reference repos into .refs/
python scripts/gate.py --doctor                            # checks the tools above
python scripts/gate.py --quick                             # fmt + clippy + Rust tests
```

If `--doctor` reports something missing, install it with your normal package manager
and run it again. If you truly cannot install something (no shell, no network), say so
in your pull request instead of skipping the check silently.

### Running a game (optional, needs your own ROM)

ROMs are never in this repository and must never be committed. Game runs use `--rt64`,
which links the RT64 renderer as `target/rt64-shim/Release/plaid_rt64.dll`. Build it once
(Windows: Visual Studio 2022 with C++, CMake 3.20+, and a
[DirectX-Headers](https://github.com/microsoft/DirectX-Headers) checkout; RT64 itself
comes from `.refs/rt64`):

```bash
cmake -S runtime/rt64 -B target/rt64-shim -G "Visual Studio 17 2022" -A x64 -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DCMAKE_CXX_STANDARD_INCLUDE_DIRECTORIES="<DirectX-Headers>/include/directx;<DirectX-Headers>/include"
cmake --build target/rt64-shim --config Release --target plaid_rt64
```

(Details and the contract test are in `runtime/README.md`.) Then, if you own a
cartridge dump:

```bash
SDL_AUDIODRIVER=dummy python scripts/native.py "<path to rom>.z64" --rt64 --seconds 30
```

The last line beginning `{"stop"` is the result: `vi` is the number of frames
(about 60 per second, so ~1798 for a 30 s run), `fault` is 0 for a clean run, and a
nonzero `fault` with `fault_pc` says where Plaid refused to continue. To find out why,
grep for `plaid_fault(` with that code in `runtime/plaid_rt.c` and
`crates/plaid-lower/src/lib.rs`; the stop line's `"stop"` text names the check that
failed.

## 2. Find something to work on

- **The current frontier:** the newest section at the top of `docs/NEXT.md`, and the
  "Next gap" column of the README's status table.
- **What is already true:** `docs/STATUS.md` (newest first) and the ADRs in
  `docs/DECISIONS.md` (newest last).
- **Code map:** `docs/ARCHITECTURE.md`; build and CLI details in `docs/DEVELOPMENT.md`.
- **Good first contributions:** build- or test-speed improvements with before/after
  timings (`AGENTS.md` invariant 8), clearer docs for one subsystem, a deterministic
  test for existing behaviour that has none, or a fault you can reproduce on a ROM you
  own, reported with its stop line (use the "Game fault" issue template).

Before starting anything larger than a day, comment on
[issue #4](https://github.com/sting-raider/Plaid/issues/4) with what you plan to change
and which paths you will touch, so nobody duplicates it. A claim with no visible
progress for a while is considered free again.

## 3. Rules that every change must follow

These are summaries; `AGENTS.md` is authoritative.

1. **No emulation in the native build.** No interpreter or JIT for guest code may be
   linked into a native artifact. Emulators are only for analysis and as test oracles.
2. **Correctness comes from tests and reference behaviour**, never from a model's or a
   person's confidence. Compare against the pinned references in `refs.lock.toml`
   (ares, Mupen64Plus, N64Recomp and others) when semantics matter.
3. **No game-specific hacks.** Fix the general capability, with a deterministic test
   that does not need a ROM. A truly unavoidable exception must be documented,
   isolated and justified in an ADR.
4. **No ROMs or copyrighted game data in git**, including captures, saves, screenshots
   of large framebuffers and extracted assets. Use synthetic inputs, hashes or metadata.
5. **Check licenses before copying code** from another project, and record the reuse
   in `docs/DECISIONS.md`.
6. **Speed matters.** If you make something faster, record before/after timings and
   keep outputs identical (or covered by the same tests).
7. **Do not edit the README's progress tables**; a maintainer updates them after each
   landing.

## 4. Validate

Run the gate on your final tree:

```bash
python scripts/gate.py                   # fmt, clippy, all tests, CLI and progress checks
python scripts/gate.py --roms <dir>      # adds the 30 s game controls (needs your ROMs)
```

`gate.py` runs the runtime suite (`runtime/test_runtime.py`, several minutes)
automatically when your branch touches `runtime/` or `crates/plaid-lower/`;
`--runtime` forces it and `--no-runtime` skips it. The individual commands it runs are
listed in `AGENTS.md` under "Local validation".

The game controls need specific ROMs (see `scripts/gate.py`). If you do not have them,
say which ones you could not run; a maintainer runs them before landing. Never claim a
run you did not do, and paste the `{"stop"` lines exactly as printed.

## 5. Open a pull request

One coherent change per PR. Fill in the template; it asks for:

- **What and why:** the problem, the root cause, and the fix in plain words.
- **Evidence:** gate output, the before/after stop lines or timings, and any
  differential test against a reference.
- **ADR:** if the change alters behaviour, architecture or a measured result, add an
  entry at the end of `docs/DECISIONS.md` titled `## ADR-XXXX: <title>` and a short
  paragraph at the top of `docs/STATUS.md`. Leave the number as `XXXX`: workers land in
  parallel, so the maintainer assigns the next free number when landing.
- **Who made it:** if an AI agent wrote or ran the change, name the agent and model in
  the PR description. Agents must not invent results; "not run" is an acceptable answer.

### How a PR lands

`main` only moves by fast-forward after the full gate passes on the exact tree being
landed. A maintainer worker takes your PR, rebases it onto the current `main`, assigns
the ADR number, reruns the full gate including the game controls, and pushes. Your
commits keep your authorship. The PR is then closed with a note saying which commit it
landed in (GitHub may show "closed" rather than "merged"; that is expected). If the
rebase or the gate fails, you will get the failing output back on the PR.

## 6. Repository map

| Path | What it holds |
| --- | --- |
| `crates/plaid-core` | ROM analysis: decoding, discovery, solving, proofs, map formats |
| `crates/plaid-lower` | lowering of proven code to C (CPU and RSP) |
| `apps/plaid` | the `plaid` command-line tool |
| `runtime/` | the C runtime linked into native builds, and its tests |
| `scripts/` | the native pipeline (`native.py`), the gate, oracles and test drivers |
| `tools/progress.py` | progress charts and badges (`--check` in the gate) |
| `docs/` | status, next steps, decisions (ADRs), architecture, development guide |
| `research/` | measurements and investigation notes behind decisions |
| `spikes/`, `experiments/`, `instruments/` | retained experiments and reference-lab tooling; older ones are historical |
| `refs.lock.toml` | pinned reference implementations (fetched into `.refs/`, never committed) |

## 7. License

Plaid is dual-licensed under MIT or Apache-2.0 (`LICENSE-MIT`, `LICENSE-APACHE`).
By submitting a contribution you agree that it is licensed under the same terms.
