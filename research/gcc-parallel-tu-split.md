# Generated-C → gcc → link wall time (candidate analysis, WIP)

Cluster: native build wall time after ADR-0307, for the MP2 pipeline
(~490 s total) and one further large game.
Branch: `oc/gcc-parallel` (direct-integration worker, exact-head CAS).
Host: Windows, native only, 20 hardware threads, gcc 15.2, rustc 1.99.1.

**Status: PRELIMINARY — source reading only. No native build was run on this
tree, so every number below is either quoted from an existing receipt or read
out of the code, none of it is a new measurement.** The measurements the task
asks for (TU count, per-TU compile time, realised parallelism, link time) have
*not* been taken yet. This note records the diagnosis so the next worker does
not have to re-derive it, and states the experiments to run first.

## Where the time actually goes (code reading)

`scripts/native.py` lowers the CPU program with `plaid lower-map ... --parts 16`
and then compiles it in three parallel-ish groups:

| phase | code | wall cost (ADR-0307 receipt, MP2, cold) |
| --- | --- | --- |
| `lower` | `plaid lower-map`, 16 parts | 23.2 s |
| `gcc` | parts, `ThreadPoolExecutor(min(4, cpu_count))` | 224 s |
| `gcc-runtime` | one runtime TU, serial | 1.4 s |
| `gcc-window` | one RT64 runtime TU, serial | ~0 s |
| `gcc-rsp` | RSP texts, `ThreadPoolExecutor(min(4, cpu_count))` | 45.4 s |
| `link` / `link-window` | one `gcc` invocation each | 0.8 s |
| `validation` | 30 s run | 30 s |

Total 489.6 s with 111.4 s of analysis, so the compile group
(`gcc` + `gcc-rsp`) is ~270 s — 55 % of the pipeline — against 224 s for the
CPU parts alone. The two candidate causes named in the task both look real:

1. **The compile pool is capped at 4 workers, not at the hardware thread
   count.** `min(4, os.cpu_count() or 1)` at `native.py:314` (parts) and
   `native.py:335` (RSP). On a 20-thread host that is 5 % of the available
   parallelism; 16 TUs over 4 workers is a 4-deep pipeline where the longest
   part runs last. The ~8 `cc1` processes observed during a build are exactly
   the 4 part workers plus the 4 RSP workers (they are two separate
   `ThreadPoolExecutor` blocks that do not overlap in time, but both are
   capped at 4 and each leaves 16 threads idle).
2. **The split is by bytes, into a fixed 16 parts, and it is contiguous.**
   `lower_c_units` (`crates/plaid-lower/src/lib.rs:2953`) computes
   `share = total_len / (parts - 1) + 1` and greedily fills parts in map order,
   so the parts are balanced in *bytes* of generated C, not in compile *cost*,
   and the part count is fixed by the `--parts` flag rather than by the size
   of the program. A 60 MB part and a 1 MB part both exist in a 16-way
   byte-balanced split of a program whose functions differ by 4 orders of
   magnitude. Cost differs from bytes mainly because each part re-emits the
   shared prelude/`HELPERS`/dispatch text and because gcc's own cost per
   function is not linear in its byte count.

## What is already in place

* **Content-keyed object cache.** `compile_source` (`native.py:146`) stores
  `<source>.o` plus a `.sha256` stamp of (source bytes + `gcc --version` +
  dependency bytes + flags) beside it in `target/native/<name>/`. An unchanged
  generated TU therefore compiles once and is skipped afterwards; the cache is
  keyed by content, so re-lowering into a *different* number of parts, or a
  different split, invalidates exactly the parts whose bytes changed and not
  the rest. Re-running the same split is free. This already satisfies the
  "avoid re-compiling unchanged TUs" half of the task; the second half
  (unchanged TUs after a split change) is what needs care.
* **Function bodies do not depend on the split.** `lower_c_units` emits each
  function body once (`lowered`), and the split only decides how many TUs
  `format!("/* part {} of {parts} */\n{shared}", ..)` prefixes wrap them in.
  With `parts > 1` guest functions get external linkage and each part gets the
  same `shared` declaration block; with `parts == 1` they are `static` and all
  bodies stay in the main unit. So a different part count changes the *file
  layout* only — the concatenated set of function bodies is identical, and the
  link result is the same program. That is the invariant the task wants proved,
  and it can be proved directly: for fixed inputs the emitted function bodies
  (names + bodies) are a pure function of the map, so hashing the concatenated
  bodies in a canonical (entry-address-sorted) order must be invariant under
  any `--parts` value. Note this check must extract bodies only, not whole
  files, since the `shared` prefixes and the `static`/extern linkage of the
  part > 1 case differ.
* **Link is negligible** (0.768 s, one `gcc` invocation) so it is not a target
  for optimisation; only `gcc` and `gcc-rsp` are.

## Experiments to run first (in this order, all silent)

Each run is `python scripts/native.py <rom> --rt64 --seconds 30` with
`SDL_AUDIODRIVER=dummy` (the pipeline already sets that for the validation
run; the build phases are silent anyway).

1. **Baseline on this tree.** Both MP2 and one further large game (OOT or BK,
   whichever's ROM is present), cold `target/native/<name>/`, then repeated
   warm runs (the analysis memo cache plus the object cache make repeats
   cheap) to get the spread of the `gcc`/`gcc-rsp`/`link` phases. Record wall
   *and* CPU: the host swings 2x wall, so use process `TotalProcessorTime` as
   in ADR-0307's receipt.
2. **Per-TU cost.** Instrument the `gcc` phase to report per-TU seconds and
   bytes, so the byte/cost correlation and the longest part are known, not
   assumed. This is diagnostic only (like the ADR-0307 per-phase timings).
3. **Parallelism experiment, no split change.** Raise the part/RSP pools to the
   hardware thread count (with a floor/ceiling so a small ROM does not launch
   20 gccs) and measure. If `gcc` drops by close to the ratio 4 → 16 workers,
   the pool was the dominant limit and the split change is optional.
4. **Split experiment.** Measure per-TU cost at a finer granularity (more
   parts, balanced by measured bytes) and take whichever is better. Prefer the
   change that is provably layout-only.

## Checklist the final candidate must satisfy

* generated function bodies identical under any split (deterministic body-hash
  check, added as a Rust test over `lower_c_parts` at two part counts);
* `map.json` and the manifest untouched; controls unchanged (PM/BK/MM/SF64/OOT/RS
  at ~1798 VIs, fault 0, and MP2 reaching destination/rules under the required
  press list);
* full local gate on the exact final tree, before/after timings as
  wall + CPU with repeated runs, recorded in this note.

## 2026-11-10 measured baseline (WIP)

Base `ab2aea580e2a84277a9f3119c161fc8cefc5f6cb`, gcc 15.2, Windows, 20 logical CPUs, 16 GiB RAM, other work active. The 30-second silent visible MP2 baseline reported VI 1798, fault 0, PC 00000000. Its cold pipeline phase walls were: generated C 212.932 s, RSP 39.435 s, links 0.775 + 0.749 s, total 480.394 s.

A separate four-worker cold-object compile of the same generated CPU sources took 223.790 s wall and 866.547 sampled CPU seconds (3.87 CPU-seconds per wall second). CPU time is sampled at 0.1 s from GCC and descendant processes and is a lower bound, not exact accounting. Peak RSS is the largest sampled individual process, not the total process tree. The machine was shared and this is one observation, not a before/after speedup.

| TU | bytes | wall s | sampled CPU s | peak RSS MiB |
| --- | ---: | ---: | ---: | ---: |
| marioparty2usa.c | 21327946 | 43.50 | 43.06 | 595.9 |
| marioparty2usa.part1.c | 8960644 | 30.73 | 30.42 | 640.5 |
| marioparty2usa.part10.c | 8901754 | 53.23 | 52.61 | 969.7 |
| marioparty2usa.part11.c | 8911024 | 52.50 | 51.98 | 888.7 |
| marioparty2usa.part12.c | 8901062 | 63.46 | 62.77 | 1320.5 |
| marioparty2usa.part13.c | 8902161 | 62.52 | 61.95 | 1371.3 |
| marioparty2usa.part14.c | 8901525 | 55.72 | 55.06 | 1240.8 |
| marioparty2usa.part15.c | 8164886 | 49.73 | 49.08 | 1201.0 |
| marioparty2usa.part2.c | 8900265 | 63.47 | 62.95 | 1165.5 |
| marioparty2usa.part3.c | 8903705 | 60.73 | 60.08 | 1371.1 |
| marioparty2usa.part4.c | 9337403 | 64.80 | 64.17 | 1413.0 |
| marioparty2usa.part5.c | 8896236 | 58.62 | 57.97 | 1323.8 |
| marioparty2usa.part6.c | 8896114 | 55.48 | 54.75 | 1237.5 |
| marioparty2usa.part7.c | 8895450 | 52.47 | 51.89 | 1199.4 |
| marioparty2usa.part8.c | 8908168 | 56.94 | 56.30 | 1272.3 |
| marioparty2usa.part9.c | 8998472 | 52.05 | 51.50 | 1150.2 |

Canonical SHA-256 over sorted function-name/body-SHA-256 pairs: `31f449d0fb9acaa34825cd14ae0d1586eb6575bd522a026229f0d14ca2c2c7be` (8005 functions). This is a baseline only; no after comparison has been made.

The processes observed for individual CPU parts reached up to 1.38 GiB RSS. A 20-process trial on this shared 16 GiB machine risks severe paging or exhaustion; measure and manage memory before increasing concurrency. The two pools in the current source execute sequentially, so their limits are not additive within one pipeline.

WIP measurement tools: `python experiments/gcc-parallel/bench.py <native-output-dir> 4 <label>` (requires psutil; writes temporary objects under target/compile-bench) and `python experiments/gcc-parallel/hash-functions.py <native-output-dir>`. The latter extracts externally linked F_ definitions from multi-part output; it does not cover static single-part output or helper code. Retain its full per-function output locally to compare a later build; only the aggregate is recorded here. Do not run overlapping benchmark invocations because they share object paths.

### OoT baseline

Silent visible cold pipeline: VI 1798, fault 0, PC 00000000; total 434.856 s, lower 14.503 s, gcc 247.455 s, gcc-rsp 18.753 s, link 0.287 s. A separate cold-object four-worker compile took 230.872 s wall and 891.562 sampled CPU s (3.86 CPU-seconds per wall second); sampling caveats above apply.

| TU | bytes | wall s | sampled CPU s | peak RSS MiB |
| --- | ---: | ---: | ---: | ---: |
| legendofzeldatheocarinaoftimeuv1.c | 26264012 | 77.15 | 76.44 | 1285.2 |
| legendofzeldatheocarinaoftimeuv1.part1.c | 9077040 | 48.18 | 47.84 | 922.8 |
| legendofzeldatheocarinaoftimeuv1.part10.c | 9044026 | 46.25 | 45.84 | 819.3 |
| legendofzeldatheocarinaoftimeuv1.part11.c | 9045068 | 35.17 | 34.73 | 786.8 |
| legendofzeldatheocarinaoftimeuv1.part12.c | 9043257 | 65.27 | 64.72 | 1340.9 |
| legendofzeldatheocarinaoftimeuv1.part13.c | 9237178 | 70.01 | 69.34 | 1384.9 |
| legendofzeldatheocarinaoftimeuv1.part14.c | 9051019 | 66.85 | 66.23 | 1374.0 |
| legendofzeldatheocarinaoftimeuv1.part15.c | 8569033 | 59.37 | 58.91 | 1211.6 |
| legendofzeldatheocarinaoftimeuv1.part2.c | 9103646 | 52.56 | 51.98 | 1346.2 |
| legendofzeldatheocarinaoftimeuv1.part3.c | 9067322 | 55.97 | 55.55 | 1271.6 |
| legendofzeldatheocarinaoftimeuv1.part4.c | 9139801 | 58.86 | 58.34 | 1352.7 |
| legendofzeldatheocarinaoftimeuv1.part5.c | 9047673 | 56.17 | 55.70 | 1369.9 |
| legendofzeldatheocarinaoftimeuv1.part6.c | 9060066 | 57.66 | 57.05 | 1287.5 |
| legendofzeldatheocarinaoftimeuv1.part7.c | 9054436 | 57.17 | 56.45 | 1260.3 |
| legendofzeldatheocarinaoftimeuv1.part8.c | 9043599 | 55.74 | 55.17 | 1211.2 |
| legendofzeldatheocarinaoftimeuv1.part9.c | 9052813 | 37.85 | 37.25 | 897.5 |

Canonical sorted function-body hash `601058b05baacc1a3aa5a7e7a445c28ff73b242eba82bca7ce47f64bb3c35746` (12935 functions); baseline only.

### MP2 six-worker trial (first observation)

Same source files and flags, independent cold-object compile: 178.400 s wall, 932.516 sampled CPU s, 5.23 CPU-seconds per wall second. Free physical memory fell below 1 GiB while active on the shared host. This alone is not a reliable speedup claim; repeat and compare under similar load.

| TU | bytes | wall s | sampled CPU s | peak RSS MiB |
| --- | ---: | ---: | ---: | ---: |
| marioparty2usa.c | 21327946 | 44.70 | 44.25 | 591.4 |
| marioparty2usa.part1.c | 8960644 | 31.72 | 31.34 | 601.6 |
| marioparty2usa.part10.c | 8901754 | 57.15 | 56.44 | 1031.4 |
| marioparty2usa.part11.c | 8911024 | 57.22 | 56.67 | 885.9 |
| marioparty2usa.part12.c | 8901062 | 69.19 | 68.27 | 1319.2 |
| marioparty2usa.part13.c | 8902161 | 67.36 | 66.55 | 1364.2 |
| marioparty2usa.part14.c | 8901525 | 65.12 | 64.28 | 1238.2 |
| marioparty2usa.part15.c | 8164886 | 59.40 | 58.55 | 1196.6 |
| marioparty2usa.part2.c | 8900265 | 73.51 | 72.44 | 1112.6 |
| marioparty2usa.part3.c | 8903705 | 70.18 | 68.94 | 1370.4 |
| marioparty2usa.part4.c | 9337403 | 73.24 | 72.45 | 1230.3 |
| marioparty2usa.part5.c | 8896236 | 66.47 | 65.75 | 1319.9 |
| marioparty2usa.part6.c | 8896114 | 57.98 | 57.39 | 1236.4 |
| marioparty2usa.part7.c | 8895450 | 53.45 | 52.89 | 1200.1 |
| marioparty2usa.part8.c | 8908168 | 51.00 | 50.41 | 1270.2 |
| marioparty2usa.part9.c | 8998472 | 46.44 | 45.91 | 1146.6 |

### MP2 six-worker trial (repeat)

Same source and flags: 170.648 s wall, 884.312 sampled CPU s, 5.18 CPU-seconds per wall second. Compare with the 4-worker cold-object measurement (223.79 s / 866.55 sampled CPU s) and cold pipeline (212.932 s gcc phase; CPU not measured). The repeat includes ongoing host contention and is not a controlled isolated-host experiment.

| TU | bytes | wall s | sampled CPU s | peak RSS MiB |
| --- | ---: | ---: | ---: | ---: |
| marioparty2usa.c | 21327946 | 45.62 | 45.08 | 590.8 |
| marioparty2usa.part1.c | 8960644 | 32.48 | 32.00 | 624.7 |
| marioparty2usa.part10.c | 8901754 | 56.42 | 55.78 | 1033.1 |
| marioparty2usa.part11.c | 8911024 | 56.86 | 56.36 | 884.5 |
| marioparty2usa.part12.c | 8901062 | 65.97 | 65.23 | 1316.9 |
| marioparty2usa.part13.c | 8902161 | 65.11 | 64.39 | 1363.3 |
| marioparty2usa.part14.c | 8901525 | 58.03 | 57.50 | 1236.0 |
| marioparty2usa.part15.c | 8164886 | 52.66 | 52.05 | 1196.5 |
| marioparty2usa.part2.c | 8900265 | 67.23 | 66.42 | 1163.6 |
| marioparty2usa.part3.c | 8903705 | 63.65 | 62.94 | 1371.9 |
| marioparty2usa.part4.c | 9337403 | 67.32 | 66.62 | 1416.3 |
| marioparty2usa.part5.c | 8896236 | 61.23 | 60.61 | 1324.9 |
| marioparty2usa.part6.c | 8896114 | 55.21 | 54.59 | 1231.8 |
| marioparty2usa.part7.c | 8895450 | 50.29 | 49.78 | 1195.4 |
| marioparty2usa.part8.c | 8908168 | 50.14 | 49.72 | 1270.3 |
| marioparty2usa.part9.c | 8998472 | 45.69 | 45.23 | 1145.0 |

### OoT six-worker trial

Same source and flags: 180.723 s wall, 990.344 sampled CPU s, 5.48 CPU-seconds per wall second; one shared-host observation.

| TU | bytes | wall s | sampled CPU s | peak RSS MiB |
| --- | ---: | ---: | ---: | ---: |
| legendofzeldatheocarinaoftimeuv1.c | 26264012 | 82.81 | 82.17 | 1315.6 |
| legendofzeldatheocarinaoftimeuv1.part1.c | 9077040 | 54.51 | 53.86 | 916.0 |
| legendofzeldatheocarinaoftimeuv1.part10.c | 9044026 | 52.06 | 51.48 | 819.2 |
| legendofzeldatheocarinaoftimeuv1.part11.c | 9045068 | 39.16 | 38.56 | 786.5 |
| legendofzeldatheocarinaoftimeuv1.part12.c | 9043257 | 69.16 | 68.56 | 1336.2 |
| legendofzeldatheocarinaoftimeuv1.part13.c | 9237178 | 76.57 | 75.77 | 1388.0 |
| legendofzeldatheocarinaoftimeuv1.part14.c | 9051019 | 72.28 | 71.47 | 1372.0 |
| legendofzeldatheocarinaoftimeuv1.part15.c | 8569033 | 67.45 | 66.61 | 1210.2 |
| legendofzeldatheocarinaoftimeuv1.part2.c | 9103646 | 60.34 | 59.72 | 1340.0 |
| legendofzeldatheocarinaoftimeuv1.part3.c | 9067322 | 63.70 | 63.05 | 1265.8 |
| legendofzeldatheocarinaoftimeuv1.part4.c | 9139801 | 67.43 | 66.75 | 1351.7 |
| legendofzeldatheocarinaoftimeuv1.part5.c | 9047673 | 64.28 | 63.52 | 1365.3 |
| legendofzeldatheocarinaoftimeuv1.part6.c | 9060066 | 63.57 | 63.02 | 1288.1 |
| legendofzeldatheocarinaoftimeuv1.part7.c | 9054436 | 63.72 | 63.08 | 1261.0 |
| legendofzeldatheocarinaoftimeuv1.part8.c | 9043599 | 61.21 | 60.66 | 1205.4 |
| legendofzeldatheocarinaoftimeuv1.part9.c | 9052813 | 42.49 | 42.08 | 895.2 |

### OoT six-worker repeat

Same source and flags: 183.568 s wall, 1010.594 sampled CPU s, 5.51 CPU-seconds per wall second; shared-host conditions.

| TU | bytes | wall s | sampled CPU s | peak RSS MiB |
| --- | ---: | ---: | ---: | ---: |
| legendofzeldatheocarinaoftimeuv1.c | 26264012 | 83.52 | 82.88 | 1315.0 |
| legendofzeldatheocarinaoftimeuv1.part1.c | 9077040 | 51.96 | 51.50 | 910.5 |
| legendofzeldatheocarinaoftimeuv1.part10.c | 9044026 | 49.76 | 49.25 | 820.0 |
| legendofzeldatheocarinaoftimeuv1.part11.c | 9045068 | 37.72 | 37.27 | 786.0 |
| legendofzeldatheocarinaoftimeuv1.part12.c | 9043257 | 69.23 | 68.61 | 1344.6 |
| legendofzeldatheocarinaoftimeuv1.part13.c | 9237178 | 76.41 | 75.80 | 1392.7 |
| legendofzeldatheocarinaoftimeuv1.part14.c | 9051019 | 76.11 | 75.47 | 1371.4 |
| legendofzeldatheocarinaoftimeuv1.part15.c | 8569033 | 72.37 | 71.83 | 1210.4 |
| legendofzeldatheocarinaoftimeuv1.part2.c | 9103646 | 64.39 | 63.95 | 1340.7 |
| legendofzeldatheocarinaoftimeuv1.part3.c | 9067322 | 68.67 | 68.23 | 1268.9 |
| legendofzeldatheocarinaoftimeuv1.part4.c | 9139801 | 71.42 | 70.83 | 1353.1 |
| legendofzeldatheocarinaoftimeuv1.part5.c | 9047673 | 67.48 | 66.86 | 1365.8 |
| legendofzeldatheocarinaoftimeuv1.part6.c | 9060066 | 64.15 | 63.38 | 1290.9 |
| legendofzeldatheocarinaoftimeuv1.part7.c | 9054436 | 63.92 | 63.45 | 1279.2 |
| legendofzeldatheocarinaoftimeuv1.part8.c | 9043599 | 61.43 | 60.91 | 1208.9 |
| legendofzeldatheocarinaoftimeuv1.part9.c | 9052813 | 40.94 | 40.39 | 899.4 |

MP2 was separately lowered with `--parts 64` from the same map: the 63 emitted C units (main plus 62 parts) yielded exactly the same 8,005 function-name/body hashes as the 16-unit baseline, aggregate `31f449d0fb9acaa34825cd14ae0d1586eb6575bd522a026229f0d14ca2c2c7be`. This checks emitted function definitions only, not helpers, declarations, dispatch or runtime behavior.


### Finer split and hardware-thread trials (WIP)

MP2, unchanged function bodies, 63 units: six workers 153.61 s wall / 876.47 sampled CPU s; 12 workers 141.33 s / 1523.53 CPU s; 20 workers 154.40 s / 1858.91 CPU s and 139.44 s / 1864.30 CPU s. CPU is sampled as above. At 20 workers, observed free physical RAM dropped below 1 GiB on this shared host. This is not a production change or a full pipeline comparison. Full per-unit details are in the adjacent `gcc-parallel-mp2-64-*.json` files.

OoT 16-part versus 64-part lowering has the same 12,935 function-name/body hashes, aggregate `601058b05baacc1a3aa5a7e7a445c28ff73b242eba82bca7ce47f64bb3c35746`. This checks bodies only.

OoT 64-way request: 20 workers 152.18 s / 1901.94 sampled CPU s and 175.26 s / 1958.34 sampled CPU s; 10 workers 155.80 s / 1459.34 sampled CPU s. MP2 with 10 workers: 145.65 s / 1349.19 sampled CPU s. Per-unit observations are recorded in the adjacent JSON receipts.

Candidate MP2 pipeline (`--parts 63`, CPU and RSP pools at 20 workers, sequential): generated CPU C compile 111.061 s versus cold baseline 212.932 s; lower 8.024 s versus 7.813 s; link 2.457 s versus 0.775 s. The candidate RSP phase was cached (0.134 s) versus baseline cold 39.435 s, so those phases and total pipeline are not comparable. Scripted 50-second run stopped at VI 2997, fault 0, fault PC 00000000. The computer-use native pipe was unavailable after retries, so the screen was not independently inspected and reaching destination/rules remains unverified. The real candidate output contains exactly the 8,005 baseline function-name/body hashes, aggregate `31f449d0fb9acaa34825cd14ae0d1586eb6575bd522a026229f0d14ca2c2c7be`.

### Landed candidate (ADR-0308), same-host back-to-back

Overlay verifiers moved out of the main unit into the balanced parts (MP2 main
21.3 MB to 8.0 MB; alone-on-host gcc 64 s to 6.4 s), one pool for every C unit
largest-first, workers = CPUs capped by RAM. Cold CPU-part wall on the shared
host: MP2 304.9 s (16 parts, 4 workers; `gcc-parallel-base-mp2-4.json`) to
126.0 s (61 units, 15 workers; `experiments/gcc-parallel/pool_bench.py`);
OoT 264.3 s (`gcc-parallel-base-oot-4.json`) to 152.2 s (62 units, 11
workers). Per-unit receipt at 8 workers: `gcc-parallel-new-mp2-8.json` (234 s
wall, 1572 sampled CPU-s: total CPU, not balance, is now the floor). Function
bodies hash-identical (MP2 8,005, OoT 12,935); MP2's 116 verifier definitions
byte-identical to the pre-split main unit.

### Independent takeover measurements

On the same shared Windows host, gcc 15.2, each original 16-unit four-worker
CPU compile was immediately followed by the candidate's cold CPU compile.
MP2: 295.0 s -> 140.8 s (61 units, 12 workers); OoT: 435.9 s -> 185.7 s
(62 units, 12 workers). Baseline per-unit receipts are
`gcc-parallel-takeover-mp2-base.json` and `gcc-parallel-takeover-oot-base.json`;
candidate timings used `experiments/gcc-parallel/pool_bench.py`. Contention
from other work on this shared host can affect both measurements. These cover
CPU C units only, not the full pipeline or runtime behavior.

The takeover gate exposed an existing Windows path-with-spaces failure in the
RSP snapshot test: `rsp_texts.py` joined paths with spaces and the consumer
split on whitespace. The helper now emits one path per line and the test uses
`splitlines()`. The focused three-stage `rsp_tasks` test passes from this
worktree's path containing a space.
