# Next

1. Establish explicit physical/cartridge backing and contextual executable image
   identities for raw fetches. A separate physical/cache observer now preserves
   existing translated/endian-selected fetch inputs without additional accesses;
   broad checkpoints/v0 projection and cache/TLB/endian fixtures pass. The v1
   importer now retains these facts, requires explicit mapped capacity and
   preserves byte-identical v0 serialization. Keep source/lifetime unknown.
   A bounded delegating-ROM-device experiment now distinguishes actual returned
   halfwords from PI latch/open-bus/prior-data reads. Its broader prefix verifies
   1,852 actual reads at 65 canonical ROM offsets with exact v1 projection/state
   agreement. The v2 importer rechecks policy, access, capacity and canonical words
   against the complete raw source, preserving known/unknown variants. Establish
   contextual image/lifetime witnesses next; other memory sources stay unknown.
   The streaming importer now preserves 64-bit PCs,
   fetched-word/slot variants and digest-qualified first/last indices/counts,
   rechecks the complete source and refuses closure of unknown identities. The pinned
   ares probe reaches 52,424 RAM/548 SP/65 cartridge addresses on the untouched
   homebrew; repeated streams and CPU/memory checkpoints match. Its 53,037-summary
   map is 20,053,874 bytes; raw data is still required for rechecking and chronology.
   Keep RAM copies/lifetime unknown;
   establish cartridge backing only through explicit mapping and byte verification.
   Model cartridge-resident executable sources and a capable capture path. The
   pinned homebrew spike exposes unsupported B0001040 execution in new_dynarec;
   the interpreter also lacks LLD and fails upstream exception/LLAddr checks.
   A pinned ares interpreter now independently agrees on the eight integer/control
   fixtures and checks cartridge fetch, LLD/SCD and address errors. Its broader raw
   observer is now validated within a synthetic SP-entry/budget scope. Add
   The bounded CPU power-entry experiment now records the existing PIF firmware
   input and matching repeated CPU/device/memory checkpoints. Its checksum stage
   passes with Config 7006E463; the one-million-call loader prefix is PI-busy.
   The longer ten-million-call prefix now repeats exactly and reaches guest tests
   with no reported failures. Research v4 now explicitly versions the complete
   declared boot profile and preserves the earlier stream/checkpoint goldens.
   Production v4 import now rechecks supplied firmware, complete profile and
   power-entry observation against the complete raw source. Both boot corpora
   verify and self-merge with unchanged legacy map hashes. Establish cache/copy/
   mutation lineage and contextual executable identities next. Keep PIF HLE and
   fixed NTSC/6102 scope visible; PIF backing and RAM/SP lineage remain unknown.
   A selected instruction-cache snapshot sensor now passes twelve controlled
   cases, with unchanged CPU/timing and full RAM/cache hashes. The one-million
   boot prefix now preserves 400,954 snapshots and exact prior-stream/checkpoint
   agreement. The ten-million prefix matches too, at 8,118 resident tuples.
   V5 import now rechecks both complete sources and resident context. Continue
   actual fill/copy/mutation lineage;
   the controlled completed-fill callback now passes. Extend tag-store/
   invalidation and backing witnesses before constructing execution lifetimes;
   guest CACHE retagging is now measured: current tags can name a different page
   from the resident words' historical fill. Observe actual completed cache
   operations and preserve data history separately from effective access;
   the controlled tag-store/index-invalidate observer now passes. Verify hit/
   miss/fill/writeback outcomes, actual backing witnesses and unified ordering;
   retain slot/event identities without inferring fill lineage or lifetimes.
   Continue RSP/exception/TLB/FPU verification
   before extending semantic claims.
2. Model/sense non-PI copies and executable writes beyond PI-backed snapshots.
   The constant aligned cached-RDRAM SW sensor is partial; general addresses,
   other sizes, TLB/uncached paths and CPU-copy provenance remain unmodeled.
   Extend restored target-entry sensing beyond successful dirty lookups; verified
   snapshots now explain pending same-epoch returns, and explicit source-unit
   tags identify older units still executing. Preserve boot-source/lifecycle
   obligations; keep
   speculative compilation distinct from execution.
3. Prove pointer-table data immutability and guard coverage before issuing exhaustive
   table certificates. Extend cross-block joins only with rechecked invariants;
   the current table recognizer and single-predecessor chains are restricted passes.
4. Track decompression, CPU copies, address aliases and overlay unload/reload,
   relocation and instruction-patch snapshots. PI copy sensing alone is insufficient.
5. Implement whole-ROM certificate verifiers for roots/boot, exceptions, execution
   modes, RSP identity and executable mutation. No flags may waive these obligations.
6. Design a provenance-bearing candidate adapter if promoting the partial
   spimdisasm spike; assess known-symbol signatures separately. Measure analysis
   size/cost before making scalability claims.
7. Begin tiny native integer lowering only after discovery beyond the current
   synthetic scope is demonstrably useful, with reference differential tests.

Native lowering remains deferred until discovery is demonstrably useful.

Keep user ROMs in ignored `roms/` and derived maps/traces in ignored `artifacts/`.
