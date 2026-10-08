# Direct CFG evidence

2026-10-08. Hypothesis: recursive discovery on an explicit code image can preserve
direct and delayed execution while exposing targets absent from that mapping.

Rabbitizer revision and license decision: ADR-0007. No performance claim.
Synthetic tests cover signed/backward branches, BC1 likely, annulled slots, JAL
return continuations, JALR rd=0, JR unresolved sites, target-based block splitting,
entry into a delay slot, missing/nested slots, exceptional instructions, unmapped
targets, traversal budget and J region boundaries (including PC zero).

`cargo test --workspace` and strict Clippy pass. These tests validate discovery
facts, not CPU execution state. Calls' return continuations are conservative
potential return edges, not proof that the callee returns. A block range containing
a likely slot does not imply the slot executes on both paths. ROM boot, interrupts,
TLB changes and inter-image targets remain outside this direct discovery layer.
