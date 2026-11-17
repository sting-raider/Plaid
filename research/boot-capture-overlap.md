# Boot capture overlap and partition input reuse

The startup capture depends on the ROM and entry address. Run it concurrently
with discovery and write its outputs after closure. This preserves closure
error precedence and prevents rejected maps from producing startup headers.
The executor joins before the build attempt returns. Concurrent boot replay
publishers use distinct temporary files even within the same process.

Compare with `2268bfc9` using the retained Paper Mario load declarations and
an empty `PLAID_REPLAY_CACHE` for each run. Invoke `scripts/native.py` with
`--loads`, `--rt64` and `--seconds 5`. Both visible runs report fault 0.
The maps match byte for byte (142,348 blocks, 34 residual sites), as do
`native-manifest.json`, `sp_boot.h` and `ram_boot.h`. Startup capture and
header generation took 0.951 s on the critical path before the change. The
wait and header generation took 0.003 s after it. Other phases had different
cache and timing conditions, so this comparison covers only the startup
wait.

For partitioning, parse the retained 70,872,878-byte GoldenEye program once,
then alternate the old and new partition functions against separate copies
of the same load catalog. Both return false and leave identical load files.
The median of five samples drops from 0.375 s to 0.030 s after reusing the
parsed program. The synthetic partition contract exercises an actual split
as well as the ambiguous-source and protected-range refusals. The native
builder contract synchronizes both tasks with events and checks that an
open strict map still reports its closure refusal if the capture fails.
