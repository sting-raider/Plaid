# Storage mutation sensing

The optional `memory_mutation_access` builder flag observes successful ordinary
storage primitives beneath the identity-only RDRAM callbacks. It records writes
after the existing little-endian `Memory::Writable::write` executes. Byte/half/Word
payloads are truncated and addresses use the actual mask. Dual and unaligned
writes retain their actual component effects; equal writes are separate events.
The callback identifies the writable **object**, so reallocation and unrelated
banks cannot silently reuse its backing identity. It performs no additional guest
read, translation, decoder, clock or memory operation.

Kind0 is a completed scalar effect. Kind1/2/3 are conservative whole-storage
fill/file-load/restore cuts, with no invented per-byte write ancestry. Kind4 is
retirement before the old allocation is freed. Saving does not emit a restore.
All existing recipes/protocols remain unchanged when the option is disabled;
reuse removes both generated memory headers. Three exact source digests guard
the recipe, and reference code/LICENSE remain in ignored build directories.

Run locally:

```text
python spikes/086-storage-mutation-sensing/test_prepare.py
python spikes/086-storage-mutation-sensing/run.py
python spikes/086-storage-mutation-sensing/run.py --verify-existing
```

The actual baseline/disabled/enabled/repeat fixture compares complete ordinary
RAM and hidden backing at20 checkpoints plus GPR/PC/selected CP0/RI state. Its
independent25-effect sequence includes ordinary/equal/base-class/EBus/translated
writes, failed translation, out-of-range suppression, Dual/16-byte burst/unaligned
splits, requestor routing, save/restore, fill/load/retire/reallocation and a foreign
bank. Requestor labels exercise actual storage calls, **not** complete DMA/device
tasks or CPU execution. This is a component mutation sensor, not a whole-machine
coverage certificate.

Next compose these effects on the existing global fetch/writer clock, with actual
producer contexts and conservative unknown-parent cuts. Raw pointer writes,
JIT/Vulkan backends, hidden-RAM mutations and scheduler/lifecycle coverage are
separate obligations. No whole-ROM, executable-lifetime or native flag is promoted.
