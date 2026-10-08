# Actual PI request and CPU dispatch scopes

Run `python spikes/035-ares-pi-queue-dispatch-context/run.py`; Windows uses WSL.
Run `test_recipe.py` for optional generation/reuse checks (compiler stubs).

The opt-in shared builder adds PI accepted-length-write boundaries before queue
insertion/copy and a scope around the actual CPU queue callback. Original external
metadata joins request -> successful insertion -> valid removal -> CPU callback ->
busy/interrupt status. Source/binaries/notices and raw results stay ignored.

Five component cases execute both PI DMA directions, cancellation followed by a
read, unbound duplicate queue events, insertion failure with actual byte writes,
and a direct status call outside CPU dispatch. Original/disabled/repeated reported
CPU/PI/backing/hidden checkpoints agree; six forged joins fail independent replay.
No guest instruction/MMIO execution, hardware timing, byte-transfer-at-dispatch,
restored provenance, whole-ROM closure or production image promotion is claimed.
