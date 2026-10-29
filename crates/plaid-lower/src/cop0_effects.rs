//! Source witnesses for global CP0 facts across declared host boundaries.
use super::*;

pub(super) const GLOBALS: u32 = (1 << 4) | (1 << 6) | (1 << 20);

pub(super) enum Domain {
    UnsignedDivision,
    SignedDivision,
    Queue { receive: bool },
    PiManager,
}

pub(super) fn domain(name: &str) -> Option<Domain> {
    match name {
        "__ull_div" | "__ull_rem" => Some(Domain::UnsignedDivision),
        "__ll_div" => Some(Domain::SignedDivision),
        "osRecvMesg" => Some(Domain::Queue { receive: true }),
        "osSendMesg" | "osJamMesg" => Some(Domain::Queue { receive: false }),
        "osCreatePiManager" => Some(Domain::PiManager),
        _ => None,
    }
}

impl Domain {
    /// Admit normal ABI completion, never a guest division trap.
    pub(super) fn guard(self, pc: u32) -> String {
        match self {
            Self::Queue { receive } => {
                let count = if receive { 1 } else { 2 };
                let early = if receive {
                    "fields[0] == 0u"
                } else {
                    "fields[0] <= 0x7fffffffu && fields[1] <= 0x7fffffffu && fields[0] >= fields[1]"
                };
                format!(
                    r#"int q_early=0;
if ((u32)s->r[6]==0u) {{
  u32 fields[2],p,index; u8 seg;
  for (u32 i=0;i<{count};i++) {{
    u32 v=(u32)s->r[4]+8u+8u*i;
    if (v>=0x80000000u && v<0xc0000000u) p=v&0x1fffffffu;
    else if (plaid_tlb_lookup(s,v,0,&p,&seg,&index,0,NULL)) return plaid_fault(s,0x{pc:08x}u,12);
    if ((v&3u) || p>PLAID_RAM_SIZE-4u) return plaid_fault(s,0x{pc:08x}u,12);
    fields[i]=(u32)s->ram[p]<<24 | (u32)s->ram[p+1]<<16 | (u32)s->ram[p+2]<<8 | s->ram[p+3];
  }}
  q_early = {early};
}}
if (!q_early && plaid_cp0_host_queue(s,0x{pc:08x}u)) {{ return 1; }}
"#
                )
            }
            Self::PiManager => {
                format!("if ((s32)s->r[7]<=0) return plaid_fault(s,0x{pc:08x}u,12);")
            }
            Self::UnsignedDivision | Self::SignedDivision => {
                let overflow = if matches!(self, Self::SignedDivision) {
                    " || (divisor==UINT64_MAX && ((u64)(u32)s->r[4]<<32|(u32)s->r[5])==0x8000000000000000ull)"
                } else {
                    ""
                };
                format!(
                    "u64 divisor=(u64)(u32)s->r[6]<<32|(u32)s->r[7]; if (!divisor{overflow}) return plaid_fault(s,0x{pc:08x}u,12);"
                )
            }
        }
    }
}

#[derive(Clone)]
pub(super) struct Proof {
    pub mask: u32,
    pub words: BTreeMap<u32, u32>,
    pub alias_delta: Option<u32>,
    pub normal_traps: bool,
}

/// Borrow a fixed proof only for an exact source copy whose direct jumps
/// retain the same address relationship. Native entry must additionally prove
/// every word is a physical alias through the callee's pinned TLB entry.
pub(super) fn physical_alias(
    image: &CodeImage,
    proof: &Proof,
    fixed: u32,
    placed: u32,
    size: u32,
) -> Option<Proof> {
    if size == 0
        || size > 16384
        || !size.is_multiple_of(4)
        || (0..size).step_by(4).any(|offset| {
            image
                .instruction_word(GuestAddr(fixed.wrapping_add(offset)))
                .is_none_or(|word| {
                    image.instruction_word(GuestAddr(placed.wrapping_add(offset))) != Some(word)
                })
        })
    {
        return None;
    }
    let delta = image.linked_pc(GuestAddr(placed)).0.wrapping_sub(fixed);
    for (&pc, &word) in &proof.words {
        if matches!(word >> 26, 2 | 3) {
            let target = |at: u32| (at.wrapping_add(4) & 0xf0000000) | ((word & 0x03ffffff) << 2);
            if target(pc).wrapping_add(delta) != target(pc.wrapping_add(delta)) {
                return None;
            }
        }
    }
    let mut alias = proof.clone();
    alias.alias_delta = Some(delta);
    Some(alias)
}

/// Bounded fixed-text traversal, including both branch arms, delay slots,
/// direct callees and tails. Unknown control flow cannot preserve a fact.
/// A mapped leaf is confined to its complete guarded host source extent.
pub(super) fn preserved(
    image: &CodeImage,
    entry: u32,
    size: Option<u32>,
    normal_division: bool,
) -> Option<Proof> {
    let size = size?;
    if size == 0 || !size.is_multiple_of(4) {
        return None;
    }
    let mapped = image
        .slots
        .iter()
        .find(|(range, _, _)| range.contains(GuestAddr(entry)));
    let mapped_end = if mapped.is_some() {
        Some(entry.checked_add(size)?)
    } else {
        None
    };
    let mut pending = BTreeSet::from([entry]);
    let mut visited = BTreeSet::new();
    let mut proof = Proof {
        mask: GLOBALS,
        words: BTreeMap::new(),
        alias_delta: None,
        normal_traps: false,
    };
    while let Some(pc) = pending.pop_first() {
        if !visited.insert(pc) {
            continue;
        }
        let mut read = |at| -> Option<u32> {
            let source = match mapped_end {
                Some(end) => entry <= at && at < end && mapped.unwrap().0.contains(GuestAddr(at)),
                None => {
                    (0x8000_0000..0x8080_0000).contains(&at)
                        && !image
                            .slots
                            .iter()
                            .any(|(range, _, _)| range.contains(GuestAddr(at)))
                }
            };
            if proof.words.len() >= 4096 || !source {
                return None;
            }
            let word = image.instruction_word(GuestAddr(at))?;
            let ins = plaid_core::discovery::decode(word, GuestAddr(at));
            let division_break = normal_division
                && plaid_core::solver::is_break(word)
                && matches!(word, 0x0006_000d | 0x0007_000d);
            if !division_break
                && (!ins.is_valid()
                    || ins.is_trap()
                    || plaid_core::discovery::is_conditional_trap(word)
                    || matches!(ins.opcode_name(), "syscall" | "break"))
            {
                return None;
            }
            if word >> 26 == 16 && matches!(word >> 21 & 31, 4 | 5) {
                proof.mask &= !(1 << (word >> 11 & 31));
            }
            proof.words.insert(at, word);
            proof.normal_traps |= division_break;
            Some(word)
        };
        let word = read(pc)?;
        if plaid_core::solver::is_eret(word) || plaid_core::solver::is_break(word) {
            continue;
        }
        let ins = plaid_core::discovery::decode(word, GuestAddr(pc));
        if ins.has_delay_slot() {
            let slot = read(pc.checked_add(4)?)?;
            if is_control(slot)
                || plaid_core::solver::is_eret(slot)
                || plaid_core::solver::is_break(slot)
            {
                return None;
            }
            if word >> 26 == 0 {
                if word & 63 != 8 || word >> 21 & 31 != 31 {
                    return None;
                }
                continue;
            }
            if ins.is_jump_with_address() {
                pending.insert(image.jump_target(GuestAddr(pc), word).0);
                if ins.does_link() {
                    pending.insert(pc.checked_add(8)?);
                }
            } else if ins.is_branch() {
                pending.insert(image.branch_target(GuestAddr(pc), word).0);
                pending.insert(pc.checked_add(8)?);
            } else {
                return None;
            }
        } else {
            pending.insert(pc.checked_add(4)?);
        }
    }
    Some(proof)
}

#[cfg(test)]
mod tests {
    use super::*;
    fn image(words: Vec<u32>) -> CodeImage {
        CodeImage {
            base: plaid_core::program::CodeAddress {
                pc: GuestAddr(0x80000400),
                image: "synthetic".into(),
                generation: 0,
            },
            words,
            rom_offset: None,
            physical_start: None,
            holes: Vec::new(),
            slots: Vec::new(),
        }
    }
    #[test]
    fn cp0_global_proof_traverses_callees_slots_and_both_arms() {
        // JAL callee; NOP; JR ra; MTC0 k0,Wired; callee: JR ra; MTC0 k0,Context.
        let code = image(vec![
            0x0c000104, 0, 0x03e00008, 0x409a3000, 0x03e00008, 0x409a2000,
        ]);
        let proof = preserved(&code, 0x80000400, Some(16), false).unwrap();
        assert_eq!(proof.mask, 1 << 20);
        assert_eq!(proof.words.len(), 6);
        let branch = image(vec![0x14000003, 0, 0x03e00008, 0, 0x03e00008, 0x409aa000]);
        assert_eq!(
            preserved(&branch, 0x80000400, Some(24), false)
                .unwrap()
                .mask,
            GLOBALS & !(1 << 20)
        );
    }
    #[test]
    fn cp0_global_proof_refuses_unknown_sources_and_transfers() {
        for words in [
            vec![0x0320f809, 0],
            vec![0x03200008, 0],
            vec![0x0000000c],
            vec![0xffff_ffff],
            vec![0],
        ] {
            assert!(preserved(&image(words), 0x80000400, Some(4), false).is_none());
        }
        let code = image(vec![0x03e00008, 0]);
        assert_eq!(
            preserved(&code, 0x80000400, Some(8), false).unwrap().mask,
            GLOBALS
        );
        assert!(preserved(&code, 0x80000400, None, false).is_none());
    }
    #[test]
    fn mapped_leaf_proof_stays_inside_the_guarded_runtime_extent() {
        let mut code = image(vec![0x03e00008, 0]);
        code.slots.push((
            plaid_core::program::GuestRange {
                start: GuestAddr(0x80000400),
                size: 8,
            },
            0x60000000,
            8,
        ));
        assert_eq!(
            preserved(&code, 0x80000400, Some(8), false).unwrap().mask,
            GLOBALS
        );
        assert!(preserved(&code, 0x80000400, Some(4), false).is_none());
        code.words[0] = 0x0c000400;
        assert!(preserved(&code, 0x80000400, Some(8), false).is_none());
    }
    #[test]
    fn physical_alias_keeps_source_words_and_jump_relationships() {
        let body = [0x03e0c021, 0x0c000106, 0, 0x0300f821, 0x03e00008, 0];
        let mut words = body.to_vec();
        words.extend([0x03e00008, 0x409a3000]);
        words.resize(0x4000, 0);
        words.extend(body);
        let mut code = image(words);
        code.slots.push((
            plaid_core::program::GuestRange {
                start: GuestAddr(0x80010400),
                size: 24,
            },
            0x60000400,
            24,
        ));
        let proof = preserved(&code, 0x80000400, Some(24), false).unwrap();
        let alias = physical_alias(&code, &proof, 0x80000400, 0x80010400, 24).unwrap();
        assert_eq!(alias.alias_delta, Some(0xe0000000));
        assert_eq!(alias.words, proof.words);
        code.words[0x4000] ^= 1;
        assert!(physical_alias(&code, &proof, 0x80000400, 0x80010400, 24).is_none());
        code.words[0x4000] ^= 1;
        code.slots[0].1 += 4;
        assert!(physical_alias(&code, &proof, 0x80000400, 0x80010400, 24).is_none());
    }
    #[test]
    fn division_abort_paths_require_the_explicit_normal_abi_domain() {
        let code = image(vec![0x14000003, 0, 0x03e00008, 0, 0x0007000d]);
        assert!(preserved(&code, 0x80000400, Some(20), false).is_none());
        assert!(
            preserved(&code, 0x80000400, Some(20), true)
                .unwrap()
                .normal_traps
        );
    }
}
