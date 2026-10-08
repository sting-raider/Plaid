# Bounded boot access history

Hypothesis: the controlled access sensors can stream a single ordered sidecar on
the existing one-million-call power-entry boot prefix without changing any byte
of the v5 fetch capture or reported CPU/device/memory/cache checkpoint.

```powershell
python spikes/027-ares-boot-history/run.py
python spikes/027-ares-boot-history/run.py --verify-existing
python spikes/027-ares-boot-history/test_verifier.py
```

This retains the existing NTSC/6102/8-MiB/deterministic/reference-PIF-HLE/checksum
profile and actual supplied ignored firmware/ROM inputs. Both recompilers remain
disabled. Original project observers stream scalar/burst successful identity-RAM
accesses, fill callbacks, selected completed CACHE operations, successful fetch
boundaries and pre-decoder fetches. They sample already-returned results/current
fields without extra guest accesses, translations or clocks. Memory use of the
sidecar observer is constant; generated trace volume is deliberately measured.

The existing v5 file remains intact. The `.history.ndjson` sidecar has its own
header, contiguous ordinals, explicit access IDs and complete footer; the verifier
checks the whole stream against every corresponding v5 fetch. Scalar call
addresses and aligned backing addresses are separate, and scalar store values
are raw input bits (written lanes use the low `bytes*8` bits). Whole-ROM production
import, source/image/lifetime promotion and native output remain separate work.

## Verdict: VALIDATED for the one-million-call declared prefix

### Evidence

- Plain/enabled/repeated reported checkpoints agree on x64 WSL Ubuntu/G++ 15.2;
  a fresh default v5 build separately reproduces the same earlier checkpoint.
- The complete 210,032,160-byte v5 stream preserves SHA-256
  `c0dcae4870aaec1b30097d7fd95f2b6214f043e2ac1dea6366b1814655ce4ce9`.
- The sidecar repeats byte-identically: 859,502,085 bytes, SHA-256
  `f4ee931e8536026a5a42581092e5be40aa43cfc91b6dc330d557314834edb842`.
- All 5,051,089 records pass complete rechecking: one million begin/end/prologue
  triples, 2,050,501 scalar accesses, 44 bursts, 32 fills and 512 CACHE completions.
  Every fill joins an adjacent actual RAM burst inside its fetch context and
  matches the complete v5 resident snapshot. All 19 uncached CPU data reads stay
  outside fetch contexts. This prefix has no uncached RAM instruction fetches;
  the controlled scalar fixture supplies that primitive's execution evidence.
- Scalar classes include 411,646 SP-DMA dualword writes and 1,638,808 PI-DMA byte
  writes. These are completed backing mutations, not transfer-origin/completion,
  generation or installation-lifetime certificates.
- An equal-valued read ambiguity and eleven malformed wire/context variants pass
  conservative verifier tests. `--verify-existing` rechecks complete retained
  streams, checkpoints and actual input hashes without rerunning the CPU.

### Constraints and surprises

- Identity-only successful backing callbacks are incomplete mutation coverage.
  Missing/remapped/degraded/EBUS/SP/PIF/ROM backing remains unclaimed by this RAM
  sensor. Unknown fills retain unknown source.
- Boundaries exclude failed CPU translations and do not certify retirement.
- This script performs one power and no host restore during capture. General
  reset/restore/NMI lifetimes are not established by absence in this finite run.
- D-cache residency, source register dataflow, overlays and RSP installation
  lifetimes remain separate from RAM transactions.
- The result cannot establish complete guest-suite or whole-ROM coverage.
- The initial 180-second limit expired near 770,000 calls and produced truncated
  files; these were rejected. This sidecar runner explicitly permits 600 seconds
  per run. Other boot runners retain their original timeout. The larger output
  is a measured research cost, not a native performance result.

### Recommendation

Preserve the narrow receipt and design strict source-linked production handling
as a separate decision. Keep whole-ROM reports OPEN.
