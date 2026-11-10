# RT64 launcher settings validation handoff

Hypothesis: launcher settings can configure RT64 presentation and four native
controller slots without changing the default runtime path or adding guest
instruction execution.

Prepared base: 62db2797aeb8e3eb3f398350c78f70684c58475e.
This is a draft candidate, not a validated or landed implementation.

Evidence on the candidate tree before this note:
- The RT64 Release shim built; CTest passed 4/4 (input, settings, RAM,
  fill-scissor). `python runtime/test_joybus.py` passed, including a synthetic
  four-channel sample. Six renderer-stub regressions passed after fixture repair.
- The full `python scripts/gate.py --roms C:/Users/aliza/Documents/ROMs/N64`
  passed fmt, clippy, cargo test, CLI, progress, all 80 runtime steps, and five
  ROM controls. Star Fox (1667 VI) and Rogue Squadron (1666 VI) had fault 0
  but missed the 1700 VI gate threshold under the parallel workload. The log is
  `target/gate-launcher-settings-rerun.log` (local ignored output).
- Individual 30-second reruns of Star Fox and Rogue passed with fault 0 and
  1798/1791 VI respectively. This is evidence consistent with contention; it
  does not replace a passing full gate. Local timings were 43.597 s and
  39.638 s respectively.
- A prior 30-second Star Fox run with title, fullscreen, and a remapped
  settings file exited 0, but no interactive visual or key-response check was
  possible. That run predates the final stretch patch and fixture edits.

The native computer-use pipe failed twice with `The system cannot find the
file specified`, so the requested visible hand check could not be performed.
The full gate and hand check are mandatory before landing. Verify keyboard
remapping, controller hotplug and player numbering, fullscreen toggles, icon,
all aspect modes (particularly stretch), n64Mode, and vsync on actual output.
Review Windows keyboard layout and JSON path handling, plus cross-thread
presentation configuration, before accepting the candidate.

Next: fetch current main; reconcile the candidate; rebuild the shim and run
its CTest contracts; perform the requested visible ROM check with
SDL_AUDIODRIVER=dummy; run `python scripts/native.py <rom> --rt64 --seconds 30`;
then run the full ROM gate on that exact tree. If main moves, reconcile and
repeat validation before the plain fast-forward CAS push. Do not start phase 2
until phase 1 has actually landed.

Integration hypothesis: launch settings reach RT64 without guest emulation; a clean, low-VI game control may be timing-sensitive under parallel gate load. Controller hardware and hotplug remain unverified and require a real controller.

Integration verification (Windows, dummy audio): Star Fox 64 Rev 1 `python
scripts/native.py <rom> --rt64 --seconds 30` completed at VI 1798, fault 0
(cold build and validation 147.979 s). Win32 GetWindowRect/GetMonitorInfo found
a 1324x832 window and 2560x1440 fullscreen matching the monitor; process titles
matched both requested values. ExtractAssociatedIcon differed from the system
application icon and WM_GETICON reported a window icon. A malformed --config
warned and ran to VI 179/fault 0 in three seconds; the settings contract checked
default retention. The input contract loads a remapped JSON and checks sampled
keyboard state. CTest passed 4/4. The earlier parallel controls were 1667 and
1666 VI; solo reruns were 1798 and 1791 VI (43.597 and 39.638 s respectively).
These are timing evidence, not a substitute for the final gate. Controller
hardware, hotplug, player numbering, visual aspect modes and fullscreen toggle
keys remain unverified.
