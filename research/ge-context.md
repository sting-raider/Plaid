# Bounded native Context writes (ADR-0297)

Hypothesis: a privileged MTC0/DMTC0 may update Context.PTEBase without knowing
its read-only BadVPN value. A write cannot establish complete Context read state.
The preceding GoldenEye frontier stops at VI1/fault12/PC80801bbc, MTC0 Context,
with all VI registers and graphics/audio counts zero. This candidate addresses
that general write operation; no game identity or constant is special-cased.

The pinned ISC ares interpreter-scc.cpp setControlRegister(4) writes bits23..63
and preserves BadVPN bits4..22. Both move forms pass the GPR payload in that
reference. The native helper retains the same projection, leaves reserved low
bits zero and records the written base. Its Context read still refuses fault12:
no reset/exception receipt establishes BadVPN. HLE boundaries invalidate the
existing staging-known mask, including Context, as before. No reference code is
copied and no guest decoder, interpreter or JIT is introduced.

Eight synthetic programs match the pinned native oracle for every reported
GPR/FPR, HI/LO, PC, FCSR, coherent RAM word and Context value. Explicit independent
synthetic BadVPN seeds verify preservation; they are not production reset facts.
Full-width payloads, zero, all-one low words and writes from r0 are covered for
both move forms. Unknown reads retain the destination value and refuse atomically;
unknown Status and user privilege writes likewise preserve all state except the
reported fault. An unmasked-write mutation fails the same comparison.

The first mutation fixture accidentally shared the seeded BadVPN bits. Changing
the payload to distinct read-only and reserved bits makes that mutation fail.
This corrected test passes in target/context-focused.log; its machine-readable
receipt and generated fixtures are under target/context-contract/.

This contract shares the final exact-tree gate and controls with mapped ABI
callbacks (ADR-0298), retaining a separate verifier for each reduction. General Context
reads, reset/exception provenance, refill delivery and Random/Wired timing remain
separate obligations; no logo/title or native-completeness claim is made.


The visible silent prototype now passes the former Context write and reaches
VI0/fault3/PC8080089c, RA bfc00000, on first SDK thread entry. The native
thread-entry dispatcher omits this already-lowered source. Virtual calls to a
mapped osCreateThread ABI are not enumerated by the callback pass, which only
looks up the exact direct-edge target. This is a separate callback-closure
obligation. The100-second GCC15.2 prototype build and2.735-second stop wrapper
are recorded under target/ge-context/. No VI/graphics/audio initialized; the
RDRAM PNG remains unrendered. Full gate and controls still precede integration.
