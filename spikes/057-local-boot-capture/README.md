# Explicit local boot capture

Capture a bounded canonical `.z64` ROM using the existing pinned ares v5 observer,
supplied local firmware, and an explicit supported NTSC CIC configuration:

```powershell
python spikes/057-local-boot-capture/run.py --rom 'C:/local/rom.z64' --cic CIC-NUS-6105 --output target/local-boot/rom --budget 10000
```

The shared profiled driver accepts an optional final `CIC-NUS-6102` or
`CIC-NUS-6105` argument. Omitting it retains 6102. Cartridge configuration and
emitted metadata use the same selection. Unsupported selections reject before
loading the reference. Unprofiled and declared post-IPL2 fixtures retain their
old interface and 6102 scope. Build inputs include the shared selector header.

Outputs must remain under ignored `target/` or `artifacts/`. The ROM and firmware
stay external to git. The recipe checks pinned source, firmware identity, full
existing machine checkpoints across disabled/repeated tracing, repeated trace
bytes, messages, profile/header, source sequence and stop footer. For 6102 it
also checks that the omitted argument emits identical trace/checkpoint bytes.
Use `--verify-existing` to recheck retained inputs without a reference rebuild.
Use `--build target/path/to/existing/build` to reuse a compatible build for
another ROM/profile; the builder rechecks every recorded input before reuse.
DrvFS runs retain the complete Git clean-source check with serial index reads.
The call budget is bounded by the existing driver's ten-million-call ceiling.
Hashing uses bounded chunks for retained traces; a larger budget still proves
only the supplied finite prefix. Budget exhaustion does not establish completion.

Import/recheck the result using `plaid import-boot-fetch` and
`plaid verify-boot-fetch`. A configuration declaration does not authenticate a
ROM's CIC or establish hardware boot truth. Keep an independent CIC diagnostic
receipt when selecting a configuration. No game hashes or compatibility hacks
are embedded in the recipe. The finite prefix does not prove boot completion,
mutation census, executable lifetime, whole-ROM closure or native completeness.
SP/RAM fetch sources can remain unknown; the observer does not supply their
ultimate writer ancestry. This recipe has no complete PI/SP/PIF history sidecar.
