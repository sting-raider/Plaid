# Primary RSP mutation / CPU refetch reconciliation

Hypothesis: observed RSP primitive storage effects can explain subsequent CPU
SP backing reads without inferring a writer from equal payloads. A later actual
CPU SP Word store must supersede the prior observed byte writers.

The primary seven-phase fixture at `spikes/043-ares-rsp-cpu-refetch` passes
against unchanged ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`. It reports 31
ordered events, eight RSP byte sinks, one CPU Word sink and four CPU backing
reads. The repeated equal-value RSP SW creates four new byte writer identities;
the CPU overwrite replaces all four. The alternate SP aperture still reads
the same DMEM backing. Initial bytes retain unknown writers.

The original reference, sensor-disabled, sensor-enabled and repeated enabled
runs agree at every reported checkpoint, including the existing spike-042
machine digest and CPU clock/Count/exception fields. This is a reported-state
neutrality check, not a claim that every emulator state bit is covered. Ten
measured forgeries are rejected, including a deleted same-value byte effect.
Result SHA-256: `542e887cd45730ab019c790caeadaa6e4eb016deaaa26bb337178a9afc920ec1`.

The broader research branch `research/rsp-dmem-cpu-refetch-gpt56sol` tests
partial scalar/vector stores, a neighboring equal-valued write and unknown
foreign sinks. Its closeout records commit
`86b51ec21707a28dff4a630946569bbeecb0b7ec` and Actions run `37915637117`.
Its byte-history rule is useful, but its original-reference comparison covers
less reported state than the primary gate. Do not transplant that weaker
comparison. The seven-phase primary fixture also excludes foreign low-level
sinks. The broader cases have now been reconciled and reproduced with the
stronger primary checkpoint gate, rather than transplanting that comparison.

The extended nineteen-phase fixture retains 78 records, fifteen scoped RSP
primitive byte effects, two CPU Word effects, three foreign effects and ten
CPU backing reads. Every reported checkpoint agrees in original/disabled/
enabled/repeated runs. The original seven-phase result remains byte-exact.
The neighboring same-value SW leaves prior origin untouched. Scalar SB and
vector SBV create mixed per-byte writers. An unmatched same-value foreign sink
cuts only the touched byte to unknown; a subsequent measured same-value SB
establishes a new observed writer. A final same-value CPU SW replaces all four
writers. Its lower-level foreign Word sink must precede and match the completed
CPU SP Word callback in this controlled synchronous fixture.

Seventeen adversarial histories fail the strict field/type/context/sequence/
byte-history contract. A deliberately weaker payload-only replay accepts the
deleted same-value sink, equal-valued neighboring-sink move and foreign-sink
move: payload replay alone cannot authenticate causal history. Extended result
SHA-256: `d7973dcd198a5b4e281f0c5719789e40863a905b0cce70e66c9d4a9b8af303e6`.
Full locked plaid-core, fmt and strict workspace Clippy pass. The broader
research branch's controlled fixture is superseded by this reconciliation;
its broader unproved obligations remain open.

This promotes only original fixture/observer composition, under ADR-0077.
Pinned upstream source/license review remains the existing ares observer
boundary: core ISC / SLJIT BSD-2-Clause notices are retained in generated
ignored shadows. No upstream implementation is copied into production Rust.
No ultimate ROM ancestry, complete writer census, continuous executable
lifetime, hardware-equivalence or native closure certificate is established.
