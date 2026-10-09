# Gopher64 `SDC1` -> SP executable sink width

Status: **VALIDATED**

Date: 2026-10-09

Plaid base commit: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Research branch: `research/gopher-sdc1-sp-exec-gpt56sol`

Pinned Gopher64 revision: `e96debac941a26ba4961e5145056c0821d3a56f7`

Compared pinned ares revision: `9408cb43d4948fc3ea6e152a307a34348df3fe04`

## Question

Does the exact pinned Gopher64 interpreter actually execute a CPU `SDC1` targeting CPU-visible SP DMEM/IMEM as two completed four-byte SP writes, mutating eight adjacent bytes, as its source suggests? This closes the source-only side of the disagreement found by `research/cop1-sp-sink.md`, where exact pinned ares was already executed and produced only one four-byte SP effect for the same instruction family.

## Hypothesis

For an aligned direct-mapped SP target with COP1 enabled, Gopher64 `cop1::sdc1` will call `memory::data_write` at `phys_address` and `phys_address + 4`; both writes will route through the SP memory map to `rsp_interface::write_mem`, producing two completed four-byte storage effects and eight changed bytes. `SWC1` is a one-write control. With CU1 disabled, `SDC1` produces no SP write.

## Exact source guard

`spikes/044-gopher-sdc1-sp-exec/run.py` refuses to run unless the Gopher checkout is exactly `e96debac941a26ba4961e5145056c0821d3a56f7`. It then guards the specific topology used by the experiment:

- `cop1::sdc1` contains exactly two `device::memory::data_write` calls;
- the second target is `phys_address + 4`;
- both 32-bit halves are extracted from the selected 64-bit FPR value;
- the SP memory-map entry is `device::rsp_interface::write_mem`;
- `write_mem` copies four big-endian bytes into `device.rsp.mem`.

The deterministic source-topology record hashes to:

`72d1f99165af25bf8a0e7529cbcd30bed3cbdea1bcfd782af471d23e69965467`

## Instrumentation and neutrality

The runner adds only a `#[cfg(test)]` module to the exact pinned checkout. It does not replace the COP1 handler, address translation, memory dispatcher, or SP primitive sink under test.

The observed path replaces only the SP memory-map function pointer with a wrapper that records `(physical_address, value, mask)` and immediately delegates to the original `rsp_interface::write_mem`. Every successful scenario is also run on a separately constructed unobserved device, and the complete 8 KiB `rsp.mem` arrays are asserted equal between observer-off and observer-on executions before the event count is trusted.

The fixture calls Gopher's real `Device::new(false)`, `memory::init`, `rsp_interface::init`, COP0 status handling, FPR helpers, COP1 `sdc1`/`swc1`, memory-map dispatch, and SP sink. This is an executable interpreter-path experiment, not a source simulation.

## Fixture cases and deterministic observations

Successful GitHub Actions run: `37918544801`, job `113780583011`, branch head `7576c5b2a1a973589f35baed76b1df8f535caf49`.

The runner executes the complete six-case suite twice in the same clean job and requires the normalized observations to match exactly.

| Scenario | Observed completed SP writes | Final target bytes | Adjacent sentinel |
|---|---:|---|---|
| `sdc1_dmem_fr1` @ `0x04000020` | 2: `0x04000020=0x11223344`, `0x04000024=0x55667788` | `1122334455667788` | unchanged `a8a9aaab` |
| `sdc1_imem_fr1` @ `0x04001020` | 2: `0x04001020=0x01234567`, `0x04001024=0x89abcdef` | `0123456789abcdef` | unchanged `a8a9aaab` |
| `sdc1_dmem_fr0_odd` @ `0x04000040` | 2: `0x04000040=0x10203040`, `0x04000044=0x50607080` | `1020304050607080` | unchanged `a8a9aaab` |
| `swc1_dmem_control` @ `0x04000060` | 1: `0x04000060=0xdeadbeef` | `deadbeef` | next word unchanged |
| `swc1_imem_control` @ `0x04001060` | 1: `0x04001060=0x13579bdf` | `13579bdf` | next word unchanged |
| `sdc1_cu1_disabled` | 0 | seeded bytes unchanged | unchanged |

All recorded successful writes used mask `0xffffffff`. The FR=0 odd-`ft` case deliberately exercises Gopher's paired-register double-source selection rather than merely repeating the FR=1 fixture.

The two full executions produced identical normalized observations. Their record hashes to:

`1b0370798888d9e7594a00f2b8716dfb4d10ae8dc6ecf41828f98a9db325023f`

## Reproduction

The durable workflow mirrors the pinned Gopher Linux dependency set, uses Rust `1.99.0`, checks out the exact Gopher revision recursively, and isolates that nested checkout from Plaid's parent Cargo workspace before running the probe:

```bash
# on research/gopher-sdc1-sp-exec-gpt56sol
python3 -m py_compile spikes/044-gopher-sdc1-sp-exec/run.py
python3 spikes/044-gopher-sdc1-sp-exec/run.py
```

For a clean CI reproduction, manually dispatch `.github/workflows/research-gopher-sdc1-sp-exec.yml` on `research/gopher-sdc1-sp-exec-gpt56sol`. The workflow installs the native packages required by pinned Gopher and supplies the `.refs/gopher64` checkout expected by the runner.

## Harness failures retained as evidence

Three earlier runs failed before semantic execution and were used only to harden the harness:

1. `37917349772`: nested Gopher was accidentally absorbed into Plaid's Cargo workspace. Fixed by an experiment-only empty `[workspace]` table after exact-revision source guarding.
2. `37917626299`: Gopher dependencies reached compilation but `ring` could not find `llvm-ar`. Added LLVM tooling.
3. `37917785202`: SDL3 compilation required XScreenSaver development headers. The workflow was changed to mirror the pinned Gopher Linux CI dependency set rather than disable reference features.

Run `37918061178` then compiled and its Rust test passed all six semantic cases, but the outer Python parser rejected the successful output because Rust's test harness prefixed the first marker with the test name. Commit `7576c5b2a1a973589f35baed76b1df8f535caf49` made marker extraction prefix-neutral. No semantic fixture or expected result changed. Run `37918544801` subsequently completed green and executed the suite twice identically.

## Result

**VALIDATED for the tested exact pinned Gopher64 interpreter path.**

An aligned `SDC1` to CPU-visible SP DMEM or SP IMEM reaches two completed `rsp_interface::write_mem` calls and mutates all eight payload bytes. The result survives an FR=0 odd-register source case, while `SWC1` remains a one-word control and CU1-disabled `SDC1` produces no SP effect. Observer-on and observer-off complete SP memories are identical for every tested scenario.

This converts the previous ares/Gopher `SDC1` disagreement from source-only suspicion into an executable reference disagreement. Exact pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, already exercised by `spikes/043-ares-cop1-sp-sink/` in Actions run `37915480878`, produced only one four-byte SP effect for direct `SDC1` to both DMEM and IMEM. Exact pinned Gopher64 executes two four-byte effects. Plaid therefore must not promote either sink width into an N64-wide invariant from emulator behavior alone.

## Limitations and explicit non-proofs

This result does **not** establish N64 hardware truth and does not prove that Gopher64 is correct or that ares is wrong. It covers the pinned Gopher direct interpreter handler with controlled aligned KSEG1-style SP targets; it does not cover a Gopher JIT/dynarec, complete ROM execution, cached/TLB aliases, exception timing, misaligned `SDC1`, same-value writes, DMA, cache interactions, or arbitrary executable-mutation completeness.

It also does not show that all 64-bit CPU stores to SP have the same semantics, does not prove provenance beyond the controlled fixture, and does not close a whole-ROM executable universe.

## Recommendation

**INVESTIGATE.** The next useful adjudication is a minimal `n64-systemtest`/hardware experiment for aligned `SDC1` to SP DMEM and IMEM, ideally with a misalignment control. Until independent hardware-oriented evidence resolves the disagreement, provenance/mutation modeling should preserve the reference conflict rather than silently choosing either the four-byte ares effect or eight-byte Gopher effect as platform semantics.
