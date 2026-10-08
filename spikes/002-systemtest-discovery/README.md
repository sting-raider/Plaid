# Pinned n64-systemtest discovery spike

Hypothesis: a reproducible source build of the pinned MIT n64-systemtest can
exercise executable discovery beyond Plaid's small original fixtures, while
retaining unknown boot, copies, writes, exceptions and microcode obligations.

Pin: `196f5421173220eb2f63a7a99c64795dc0ea0698` from refs.lock.toml.
Upstream specifies Rust nightly-2022-07-10. The independently pinned MIT
packager nust64 0.4.1 includes libdragon's open-source IPL3. No ROM is committed.

Cases and acceptance:

- Build pinned guest source with its locked dependencies and exact nightly.
- Record source/tool/ROM hashes; repeat packaging deterministically.
- Attempt bounded reference boot with a declared plugin/stop policy.
- Import captured facts without ELF/symbol metadata as discovery input, checking
  byte provenance, deterministic serialization and fail-closed solver output.
- Report precise limitations; a dummy RSP/graphics setup cannot validate the
  complete test suite or rendering. Boot failure is evidence, not compatibility.

Reproduce on the verified Windows/WSL host:

```text
rustup toolchain install nightly-2022-07-10 --profile minimal --component rust-src
cargo install nust64 --version 0.4.1 --locked --root target/reference-tools/nust64
python spikes/002-systemtest-discovery/build.py
python scripts/build_mupen_core.py
python spikes/002-systemtest-discovery/probe.py
```

The pinned checkouts must exist under `.refs/`. Build outputs and logs are under
`target/systemtest-spike`. The exported manifest adds `[workspace]` solely to
isolate old Cargo from Plaid's resolver 3; guest files and Cargo.lock are unchanged.
The packager writes beside its ELF; the script copies that output and checks two
identical packaging runs. No ELF/symbol metadata is supplied to Plaid.

The probe uses a 30-second wall bound and the existing 16-MiB trace bound. The
former five-second limit stopped during integer tests under concurrent reference
build load, before the expected LLD boundary. A timeout still fails that boundary
assertion; extending the bound does not count as guest completion or CPU agreement.

## Verdict: PARTIAL

### Evidence

- Exact-nightly source build and repeated packaging pass. ROM size 2,742,284
  bytes; SHA-256 `629f908c200bbf21013dcd1d331d4ddedd08a6c9d7ae1f528421564238056e8a`.
- Pure interpreter boots and emits 410 IS64 messages, including nine upstream
  failure reports, then stops at unimplemented LLD `80163180:D0640000`. No guest
  completion is claimed. Pin `pure_interp.c` explicitly marks opcode 52 unimplemented.
- Traced dynarec exits 1 on direct cartridge execution at `B0001040`, before
  IS64 output. Its 356,124-byte, 2,874-record prefix has no footer; Plaid rejects
  it with `truncated discovery trace: missing end record`. The pin's
  `new_recompile_block_impl` exits on this unsupported address range.
- The probe confirms these negative outcomes reproducibly; it never imports the
  incomplete prefix or claims the test suite completed. The timeout/trace-size
  budget is a bound, not a deterministic guest checkpoint or CPU oracle.

### Constraints and surprises

- The production libdragon IPL3 executes cartridge-resident code, a broader
  discovery requirement than the synthetic RAM/SP fixtures exposed.
- The pin's interpreter is useful for the tested integer/control subset; these
  unaligned/LLAddr failures and absent LLD prevent treating it as a universal
  hardware oracle. Dummy plugins also exclude graphics/audio/RSP validation.
- The pin's README deprecates this test repository in favor of nemu64-test. This
  experiment intentionally keeps the existing lock rather than changing corpus.
- The first build inherited Plaid's newer workspace; isolation fixes that setup
  problem. The packager has no `--output` flag, corrected after source inspection.
- This research uses the MIT test/tool sources and bundled open-source boot code,
  with the GPL reference built separately. No ROM, ELF, toolchain or binary is
  committed or published; no production runtime linkage is introduced.

### Recommendation

Model cartridge-resident executable sources and establish a capable capture path
before broader homebrew discovery. Add a stronger independent CPU/RSP oracle for
exceptions and omitted instructions. Preserve the guest and report reference
limitations; a guest workaround or a fabricated trace footer cannot validate
automatic discovery. Promote any observer/runtime change only through a separate
decision and differential tests. Native lowering remains deferred.
