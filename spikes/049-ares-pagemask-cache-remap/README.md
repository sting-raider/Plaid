# Executed large-page cache remap controls

Original project-owned ISC fixture reconciled from
`research/pagemask-icache-remap-compose-gpt56sol` exact head
`9679c4b9bd658d53e14932f62b6ffa6d78148f84`.

```text
python spikes/049-ares-pagemask-cache-remap/test_verify.py
python spikes/049-ares-pagemask-cache-remap/run.py
```

The shared 003 builder runs unmodified exact ares
`9408cb43d4948fc3ea6e152a307a34348df3fe04`, with both recompilers disabled,
NTSC/6102, deterministic entropy, big-endian kernel context and 8-MiB identity
RDRAM. Windows uses WSL Ubuntu. No observer or TLB/cache patch is requested.
The fixture invokes real `CPU::TLBWI()` directly from staged entries; it does
not execute decoded guest TLBWI or MTC0 for these mapping/context operations.
Backing mutations are debugger-side writes. Repeated stdout must match.

Six strict synthetic contracts retain fixed-4K decoys, stale backing, temporary
mapping/ASID unreachability, equal-payload remap/miss, nested type/census and cache
hash checks. The 16-KiB and 64-KiB selectors are 0x4000 and 0x10000; correct
selected physical tags differ from planted equal-value 4-KiB guesses. Same-value
TLB writes and failed ASID translations preserve residents; differing physical
tags cause later fetch misses. Miss counts progress 0,1,1,2,3,3,3,3,4,5.

Ignored schema-0 output lives under `target/ares-pagemask-cache-remap-primary/`.
Compact fact SHA-256:
`4227e340a3000607b70cde96339a379737ea46167a7cf10573fe7aba093050fd`.
Primary result SHA-256:
`d884a8ce86b01192750afd9f7539e2a618f5a0dcb72c54f777134c9561fe8a35`.
The reported complete I-cache tag/index/word digest is
`9929c6d182ea6efd93fe325a9c71040c944babd9037fba2f7254ca944471125d`;
this is not a full-machine-state or observer-neutrality comparison.

These facts do not capture mapping/context/fill/writer generations. See
`research/pagemask-cache-primary.md` for the branch model's accepted fabricated
miss. Gopher64's physical cache indexing differs from ares's virtual indexing;
this fixture supplies no universal hardware rule. Mutation census, producer
ancestry, executable lifetime and native completeness remain explicitly false.
Generated reference builds/notices remain ignored; no upstream implementation,
ROM, firmware, branch workflow or custom compiler is vendored.
