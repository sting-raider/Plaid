# Lower DMEM storage effects revoke older SP ancestry

CPU-window and DMA wrapper observations do not enumerate RSP DMEM primitive
writes. Compose the previously validated spike042 callback into the existing raw
history clock. Record every completed aligned/masked primitive lane, including
equal writes, without granting an RSP instruction, register or task parent.

Strict history v6 adds `rsp_dmem_effect` for bounded DMEM offsets and Byte/Half/
Word/Dual payloads. The existing shared SP writer state cuts only those bytes.
IMEM remains independent. Lower DMA effects precede their higher store wrapper;
the existing unique source-read receipts remain available for that installation.
V3/v5 sources reject the new record and preserve their existing report contracts.
The containing SP projection is report-v2 for v6; all broad flags remain false.

```text
python spikes/090-rsp-dmem-storage-cuts/test_consumer.py
python spikes/090-rsp-dmem-storage-cuts/run.py
python spikes/090-rsp-dmem-storage-cuts/run.py --verify-existing
```

The consumer tests compare both production SP writer/PI consumers and the
independent Python model. They retain equal byte and four-Byte cuts, partial
parents, source reads before cuts/installations, IMEM independence, valid widths
and strict malformed/legacy-policy rejection.

The actual pinned ISC ares fixture composes PI RAM parents through DMEM DMA,
CPU DMEM execution, an equal decoded RSP SW and later CPU DMEM/IMEM consumption.
At the pin, aligned RSP SW performs four completed Byte effects, including an
equal zero byte. Its142-event source and22 full backing/machine checkpoints agree
baseline/disabled/enabled/repeat. An initial Word-effect expectation was corrected
to these measured lanes without rebuilding unchanged binaries or relaxing checks.
Explicit host descriptor, mapping, IMEM seed, register and DMA stepping controls
remain opaque; this adds no RSP producer ancestry or hardware timing claim.

Local discovery adds `--history storage-rsp` in spike057. The actual100k supplied
ROM prefix retains424,660 records and1,008 lower DMEM effects, with exact earlier
paired fetch/checkpoint controls and repeated source equality. Canonical and
independent consumers agree; all PI parents remain unknown in this early prefix.
Ignored target/ contains ROM-derived sources, reference shadows and required
notices. No ROM/assets or reference implementation enter production.

This covers observed lower effects, not raw-pointer, restore/reset, other backends,
complete scheduler/writer census, executable lifetime, whole-ROM or native closure.
