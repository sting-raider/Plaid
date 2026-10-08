# Buffered PI sources in the bounded boot chronology

Primary receipt, 2026-10-08. Hypothesis: actual boot PI ROM-half results can join
through consumed buffer lanes to successful identity-RAM byte writes, preserving
the complete previous access/fetch sources and reported reference checkpoints.

`python spikes/030-ares-boot-pi-history/run.py` passes at 610,000 instruction calls
on clean ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, WSL Ubuntu x64,
G++ 15.2, both recompilers disabled. `--verify-existing` rechecks complete retained
sources and supplied ROM/firmware without CPU execution. The declared NTSC/6102,
8-MiB, deterministic, PIF-HLE/checksum, single-run profile is unchanged. This
prefix reaches RAM execution and PI polling, not guest-suite completion.

Research history v1 adds returned buffered PI half, block, byte-attempt/return
and status records, delegated ROM half results, and PI transfer/block/lane
metadata on successful scalar writes. The original project observers sample
existing results/fields only; the ROM wrapper delegates once. Reference shadows,
ROM/firmware and streams remain ignored and separately compiled with notices.
No runtime reference dependency or production identity is added.

The 8,823,134-record stream contains 819,404 delegated ROM halves and 1,638,808
successful byte writes. Every byte has an exact canonical source through its
actual consumed lane; no failed destination or unknown PI origin occurs in this
prefix. Four synchronous copy calls return. Three busy/interrupt transitions
are observed with observer write contexts 1, 2 and 3. Context 4 has no such
transition before the cutoff; the independent final PI snapshot has busy 1.
These are observed status/context facts, **not transfer completion certificates**:
queue direction, duplicate insertion identity and guest cancellation remain
unsensed, as shown by the separate source/container contract.

Dropping only the added PI records/metadata and remapping ordinal/context
references reproduces every byte of the separately compiled original-PI v0
history: 3,881,089 records, 32 actual RAM-backed fills and 19 data reads outside
fetch contexts. The complete paired v5 stream is also byte-identical. Original
PI, disabled and repeated enabled reported CPU/COP0/PIF/PI/Count/RAM/SP/cache
checkpoints agree; enabled raw histories repeat exactly. Final Count 4,444,366,
exception 0. Final RAM/SP/cache hashes match the earlier one-million-call prefix;
the different budget has its own CPU/register checkpoint and complete sources.

| Complete artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| V1 history | 1,572,142,700 | `994d62686ff5d57a0a9a26ab6bc8454c6026d79c3bd069d1c921513431cfc7af` |
| Exact v0 projection | 656,507,083 | `2c84bd02adeb9bfef68e46dbc300df735c1c56b06240d951c36621204d43e07f` |
| Paired v5 fetches | 96,347,158 | `6213a9159efc5bca9e64c0ee2d4e5b2b866a0ba22a438626b28c84d99b1ec1c5` |

The 10,000-call preflight contains no PI copies and preserves all prior projections.
Seventeen forged/truncated/type/context/metadata protocols fail; equal-byte ROM
offset substitution removes origins. Rewriting v1 context references cannot
conceal a forged fetch association. Production v0 inspection rejects v1 through
the CLI version gate; the projected preflight v0 inspects and source-rechecks.
The default ROM-source fixture reproduces its prior known/latch/unmapped/TLB/
endian cases, with three source witnesses and three unknowns. Recipe/reuse and
prior v0 wire counterexamples also pass.
Rust v0 inspection and report source rechecking pass the complete 3,881,089-record
preserved history with the paired 610,000-fetch stream. Every finite count and
both raw hashes agree with Python. The 872-byte report SHA-256 is
`159996dd18ae605133b6e6466680ffd4770d00dd553d7d85464bb8daa84df95e`.

This supplies finite PI source effects, not resident executable origins throughout
boot, a complete mutation census, executable lifetimes, hardware agreement or
whole-ROM closure. Original Rust v1 inspection needs a separate implementation
decision and strict tests; queue insertion/removal/dispatch identity is separate
work. Preserve all raw hashes and keep production version/lifetime gates closed.
