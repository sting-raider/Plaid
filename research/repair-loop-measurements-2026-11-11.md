# Bounded repair loop measurements, 2026-11-11

Measurement claim: compare Paper Mario's default bounded repair loop with explicit
`--deep` and retain Resident Evil 2's complete repair/admission sequence. Baseline:
`0f7e3786cb24a3176a95ca5a0ae05b57bf81a19a`, branch `t3/measure-repair-loop`.
Backend measurements only; no production changes or completeness promotion.

Windows 11, 20 logical CPUs, Cargo 1.99.1, GCC 15.2.0, Clang 22.1.0. Pinned
ares `9408cb43` and n64sym `ccf4600f` were verified. The release CLI and ares
oracle were prepared before measurement. Each case started with a unique empty
output directory, `PLAID_OBJECT_CACHE` and `PLAID_REPLAY_CACHE`; the worktree's
analysis cache had no entries for these invocations. Caches were retained between
repair rounds within a case. Thus these are cold game/object/replay builds with
a prepared toolchain/oracle, not first-install timings. Runs were sequential.

All native runs used visible RT64 windows, `SDL_AUDIODRIVER=dummy`, no presses,
and a 60-second time limit. ROMs were found by filename only in the authorized
local folder, read without modification, and never committed. Input identities:

- Paper Mario (USA), 41,943,040 bytes, SHA-256
  `9ec6d2a5c2fca81ab86312328779fd042b5f3b920bf65df9f6b87b376883cb5b`.
- Resident Evil 2 (USA) (Rev 1), 67,108,864 bytes, SHA-256
  `71f3f779613bf1f0e2050bfa600425385d2c257a647d2e40f63be1a7986e9aac`.

Reproduction: `python scripts/native.py <local-ROM> --name <case> --rt64 --seconds 60`,
adding `--deep` only for the deep case and assigning fresh cache directories via
the two environment variables above. Default cases unset `PLAID_SITE_BUDGET`
before launch, allowing the CLI's 100M budget; deep removes that override and
uses the 2-billion-instruction site budget. No loads or repair records were supplied.

| Case / output name | Wall time, s | Exit / acceptance | Last actual native stop (VI / fault / PC) |
| --- | ---: | --- | --- |
| PM default / `measure-pm-default-cold2` | 422.465 | 1 / failed in round 2 solver | 651 / 3 / `80b3e154`, target `8002ac00` |
| PM explicit deep / `measure-pm-cold-deep` | 655.551 | 0 / accepted in round 1 | 3552 / 0 / `00000000`, time limit |
| RE2 default / `measure-re2-default-cold` | 34.605 | 1 / failed in round 2 solver | 9 / 15 / `8004d348`, target `00000000` |

Wall time uses `time.perf_counter()` around the complete CLI subprocess, including
analysis, compile/link, validation, capture and repair. Summed printed harvest
phases were 18.489 s for PM default versus 237.439 s for deep; validation phases
were 12.999 s versus 61.218 s. These timings compare different acceptance outcomes,
not equivalent successful builds or a speedup. Deep retained 10 residual sites
and `native_complete: false`; it admitted no observed images.

Paper Mario printed exactly:

```text
repair round 1: fault=3 pc=80b3e154 sha256=e84a3d8dbb59bb75548c84ab69ddb15f4e44668cc34a8901a09a3caea32c551f stop=admit-and-rebuild
repair round 2: fault=none pc=none stop=build-or-validation-error
```

The default capture was inserted as observed generation 1 in the next loads/map.
Round 2 printed `solve open 29 blockers`, then `residual-dispatch solve open 4
blockers, 25 residual sites`, and refused: `not CLOSED under the address-taken
scope, even with residual dispatch: nothing is built`. The remaining four are
two `pointer_table_immutability_unproven` and two
`pointer_table_target_identity_unproven` blockers. There was no round-2 native run.
Deep printed only `repair round 1: fault=0 pc=00000000 stop=success`.

Resident Evil 2 printed exactly:

```text
repair round 1: fault=15 pc=8004d348 sha256=7daa926be0a60eb09c5c56294967b3c1bb590e8599529ac24fc7278dafcb8d79 stop=admit-and-rebuild
repair round 2: fault=none pc=none stop=build-or-validation-error
```

Round 1's stop was `guest fault`, VI 9, fault 15, PC `8004d348`, reported
`fault_target: 00000000`, zero graphics/audio tasks and one PI DMA. For fault 15,
the repair root is the fault PC itself: record target `8004d348`, not zero.
The 131,072-byte capture's SHA-256 above was independently rechecked. Round 2
inserted it as observed generation 1 in loads and the discovered map (1,951
blocks, 184 indirect sites, 66 unresolved items). Both ordinary and residual
solve stayed OPEN with 126 blockers and zero residual sites. Blocker kinds:
33 exception/unsupported instruction, 2 unmapped target, 2 unresolved direct
target, 46 unresolved indirect target, 1 unsupported delay slot, 42 unsupported
scope effect. It printed the same CLOSED refusal as PM. Admission into analysis
therefore succeeded, but executable admission did not; no second native stop,
second record/hash, fault-17 result, or later gameplay was produced.

After the loop, a separate visible 60-second invocation of the retained RE2
round-1 executable stopped after 0.800 s, exit 1, at the identical VI 9 / fault 15 /
PC `8004d348` / target `00000000`, again with zero graphics/audio tasks. This
is the final observed RE2 stop, not a run of a repaired artifact. Failed round-2
solves leave the prior executable and manifest in place; their manifests have
`native_complete: false` and no observed images and do not certify round 2.

Setup failures retained separately: a launch was canceled after 35.248 s while
waiting for the initial Rust bootstrap, before analysis. An initial cold default
PM attempt took 399.451 s and failed at RT64 linking, printing only
`repair round 1: fault=none pc=none stop=build-or-validation-error`; no native stop
occurred. The copied DLL lacked `plaid_gfx_connected`, `plaid_gfx_input_player`,
and `plaid_gfx_window_options`. The unchanged current bridge source was rebuilt
privately against the existing pinned RT64 static library; relinking and a visible
2-second PM preflight then passed (VI 28 / fault 0). The table uses a fresh cold
retry and this same rebuilt DLL for all cases. DLL SHA-256:
`0ce181d8c2360be75fd9f964e3321aabffafbe3c8414ed4e088458f9b02354b5`.

Local logs, timing JSON, cache directories, captures, full standalone RE2 stop and
post-measurement solver receipts remain ignored under
`target/receipts/repair-loop-measurements-2026-11-11/`; game outputs are under
`target/native/<case>/`. Native CLI stop lines are truncated by the existing
script to 400 characters; requested stop fields and full round lines are intact.
Documentation gate: `python scripts/test_cli.py` (result recorded in the commit).
PM default repair convergence and RE2 repaired execution remain unverified because
their round-2 solvers refused; the deep PM 60-second run completed successfully.
