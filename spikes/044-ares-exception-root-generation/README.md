# Spike 044: exception-root executable generation

## Hypothesis

For the cached BEV=0 general VR4300 exception root, the architectural vector
address alone does not identify the executable handler generation.  If backing
RDRAM at physical `0x180` is replaced while an older valid I-cache line remains
resident, a subsequent exception can transfer to virtual `0xffffffff80000180`
and still execute the older resident handler.  Only a causally observed cache
transition/refill can bind later cached handler fetches to the new backing
generation.

This is a composition experiment.  It builds on the validated exception-vector
fixture in `spikes/019-ares-exception-vectors` and the validated cached-code
visibility fixture on `research/cached-code-patch-visibility-sol`.

## Exact dynamic case

`driver.cpp` uses exact pinned ares with both recompilers disabled and identity
RDRAM.  It:

1. installs `ADDIU v0,zero,1` at physical `0x180` and executes the cached BEV=0
   vector once to create resident generation A;
2. replaces backing `0x180` with `ADDIU v0,zero,2` without invalidating I-cache;
3. executes a guest `SYSCALL` from an uncached direct segment and checks the
   architectural next PC is still exactly `0xffffffff80000180`;
4. executes the handler and requires `v0 == 1`, proving the exception root used
   stale resident generation A while current backing already contains B;
5. executes guest `CACHE 0x10` hit-invalidate from uncached helper code;
6. triggers another guest `SYSCALL`, then requires the vector miss/refill to
   execute generation B (`v0 == 2`).

The runner executes the fixture twice and requires byte-identical JSON output.
It also source-guards the pinned revision and relevant exception/cache/memory
Git blobs.

## Adversarial reducer

`../../experiments/exception_root_generation.py` separates backing and resident
generations and covers changed replacement, same-value replacement, refill before
replacement, refill after replacement, uncached BEV control, and missing resident
evidence.  It deliberately rejects a certificate that substitutes current backing
for a cached root fetch.

## Reproduction

With `.refs/ares` at the revision in `refs.lock.toml`:

```sh
python3 experiments/exception_root_generation.py
python3 spikes/044-ares-exception-root-generation/run.py
```

The branch-only workflow `research-exception-root-generation.yml` performs a
fresh exact-revision checkout before running both.

## Scope

This does not prove hardware timing, mutation completeness, handler reachability
beyond the exercised general exception, TLB-mapped vector aliases, NMI/reset
roots, or whole-ROM closure.  It tests one proof-composition rule: cached root
identity must include resident/fetch generation evidence instead of equating a
vector address with current backing bytes.
