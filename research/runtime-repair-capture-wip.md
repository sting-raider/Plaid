# Runtime repair capture, work in progress

Integration claim: a bounded snapshot at a native fault can supply an observed
code image, provided the native dispatch selects the correct generation only
after checking its executable bytes against RAM. The existing composite load
image alone cannot represent multiple occupants at the same guest address.

The opt-in `--repair-capture` runtime argument currently writes a raw JSON
snapshot for fault 3 or a local trap (fault 15), using a 64 KiB window on each
side of the target, clipped to RDRAM. It is not yet a repair record: it has no
hash, DMA history, ingestion, generation-aware discovery, content-bound
dispatch, or rebuild loop. It must not be used as evidence or as permission to
execute guest code. The raw snapshot can contain copyrighted game bytes and
belongs only under ignored local build output.

`python runtime/test_repair_capture.py` verifies the bounded window, metadata,
trap target selection and refusal of non-RDRAM/non-repairable stops using
synthetic bytes. This is not the requested end-to-end synthetic ROM or a game
validation.

Local RE2 (USA Rev 1) baseline on 3fc7dd96 with this capture hook: visible
RT64 run stopped at VI 10, fault 15, PC 8004d348. The captured word there was
`afb00018`; the boot-ROM image word at that location was `787a1e28`. The raw
131072-byte window SHA-256 was
`7daa926be0a60eb09c5c56294967b3c1bb590e8599529ac24fc7278dafcb8d79`.
This establishes a byte difference in this run, not safe image lifetime or
successful recompilation. The raw capture remains under ignored `target/`.
