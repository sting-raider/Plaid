# Executable load evidence

2026-10-08. Hypothesis: comparing an observed executable snapshot with canonical
ROM bytes can establish source provenance without inventing relocation facts.

Inspected pinned Mupen `cart_rom.c::cart_rom_dma_write` and `pi_controller.c`.
The PI "write" handler transfers cartridge bytes into RDRAM. Source uses
`CART_ROM_ADDR_MASK`; copies truncate at ROM/RDRAM limits and can zero-fill beyond
ROM. Both KSEG aliases are invalidated afterward. The requested PI length is not
necessarily the number of ROM bytes copied. Future instrumentation must distinguish
actual copy length and data loads from executable observations.

`record_load` checks canonical identity, source bounds, aligned executable subset
and captured post-copy bytes. It records exact mappings, generation-specific
regions, verified reload events and overlapping-source overlay candidates. Changed
bytes remain Unknown (possibly relocation/patch/generated code); no guessed class
can remove the blocker. Original snapshots stay in memory, not in ProgramMap JSON.

30 Rust tests and strict Clippy pass, including exact copies/reloads, overlapping
sources, changed bytes, malformed snapshots and identity mismatch. Live PI DMA
sensor integration and complete overlay/relocation lifecycle remain follow-ups.
