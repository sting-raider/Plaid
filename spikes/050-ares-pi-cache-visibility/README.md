# PI copy and cached execution visibility

Reconciled original ISC fixture from
`research/pi-dma-icache-compose-gpt56sol` exact head
`b7d78e3372a1077f1cf75c0558a7b63a4222ed82`.

```text
python spikes/050-ares-pi-cache-visibility/test_verify.py
python spikes/050-ares-pi-cache-visibility/run.py
```

The shared 003 builder runs exact ares
`9408cb43d4948fc3ea6e152a307a34348df3fe04` with interpreted CPU/RSP, NTSC/6102,
deterministic entropy, big-endian kernel and 8-MiB identity RDRAM. Windows uses
WSL Ubuntu. Ten exact source blobs and the builder's clean pin gate precede
unmodified baseline and optional existing observer builds. The fixture's two
queue names are directly qualified; it generates no sources beside tracked code.
Generated reference builds/notices stay ignored under
`target/ares-pi-cache-visibility-primary/`.

Real PI MMIO requests perform two synchronous 32-byte copies. The first receives
a queued completion while old instructions stay resident. The second copies
bytes with all 512 real queue slots full and receives no completion. Both need
guest CACHE invalidation and a subsequent backing read/fill to execute new bits.
The PI completion field is a finite fixture label, not an authenticated queue
token or general overlapping-request identity.

`verify.py` independently declares this finite chronology and checks exact types,
keys, all 117 records, every source halfword/destination byte, full cache line,
fetch virtual/physical/bus address, checkpoint order and reported final state.
Eleven synthetic tests plus ten measured-record forgeries retain the branch
runner's three newly exposed tail/address holes and other visibility/census
negatives. Baseline, observer-disabled and enabled runs must agree on eight
selected checkpoints and final reported PC/Count/exception/t0/RAM/PI state;
repeated enabled stdout must match. This is not equality of all machine state.

Primary trace SHA-256:
`4b6a39c3a46a729a173d404a9a7d9b1a9f3d402d5d8540a8622d8f96b05a8f9f`.
Schema-0 primary result SHA-256:
`32b6f52e18c4fd3427d8374921e9103da8771452938208336a8577022a27645c`.

Producer ancestry, queue/completion identity, mutation coverage, executable
lifetime and native completeness remain false. Restore/equal-writer controls
exist only in the reviewed branch's separate abstract model, not this executed
fixture. See `research/pi-cache-primary.md`; no branch workflow, abstract model,
custom compiler, upstream implementation, ROM or firmware is imported.
