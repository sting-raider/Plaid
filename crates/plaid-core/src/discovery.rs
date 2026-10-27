//! Conservative direct control-flow recovery, using pinned Rabbitizer decoding.
use crate::{
    EvidenceKind, GuestAddr,
    program::*,
    rom::{CanonicalRom, sha256},
};
use rabbitizer::{InstrCategory, Instruction};
use std::collections::{BTreeMap, BTreeSet};

pub const DECODER_REV: &str = "724a49a5b4dbfb99f1a9e6992e63964fd29c90c8";

#[derive(Debug, Clone)]
pub struct CodeImage {
    pub base: CodeAddress,
    pub words: Vec<u32>,
    pub rom_offset: Option<RomOffset>,
    pub physical_start: Option<PhysicalAddr>,
    /// Ranges inside the image that hold no supplied bytes, such as the gaps
    /// between disjoint declared loads (ADR-0150). `word` returns nothing
    /// there, so control or a table read that reaches one fails closed.
    pub holes: Vec<GuestRange>,
    /// Slot alternates placed in the image (ADR-0185): each placed range and
    /// the address the file is linked at, where its own code reaches its
    /// data. Table reads from code in a placed range use the placed copy.
    /// Fixed replay data uses an identity link and zero text, with the same
    /// declaration/content verification; it never supplies instructions.
    pub slots: Vec<(GuestRange, u32, u32)>,
}
impl CodeImage {
    /// Slot data remains readable for tables, but cannot supply instructions.
    pub fn instruction_word(&self, pc: GuestAddr) -> Option<u32> {
        if self.slots.iter().any(|(placed, _, text)| {
            let off = pc.0.wrapping_sub(placed.start.0);
            off < placed.size && off >= *text
        }) {
            return None;
        }
        self.word(pc)
    }
    /// Where code at `at` finds `address`: in a slot alternate's placed copy
    /// when `at` is in one and `address` is in its linked range (ADR-0185).
    pub fn slot_view(&self, at: GuestAddr, address: u32) -> u32 {
        self.slots
            .iter()
            .find_map(|(placed, linked, _)| {
                let off = address.wrapping_sub(*linked);
                (at.0.wrapping_sub(placed.start.0) < placed.size && off < placed.size)
                    .then(|| placed.start.0 + off)
            })
            .unwrap_or(address)
    }
    /// Architectural PC of a word held in an analysis slot alternate.
    pub fn linked_pc(&self, pc: GuestAddr) -> GuestAddr {
        GuestAddr(
            self.slots
                .iter()
                .find_map(|(placed, linked, _)| {
                    let offset = pc.0.wrapping_sub(placed.start.0);
                    (offset < placed.size).then(|| linked.wrapping_add(offset))
                })
                .unwrap_or(pc.0),
        )
    }
    /// J/JAL keeps the executing virtual PC region. An internal target stays
    /// in this alternate's storage; an external linked target remains virtual.
    pub fn jump_target(&self, pc: GuestAddr, word: u32) -> GuestAddr {
        let virtual_pc = self.linked_pc(pc).0;
        let target = (virtual_pc.wrapping_add(4) & 0xf000_0000) | ((word & 0x03ff_ffff) << 2);
        GuestAddr(self.slot_view(pc, target))
    }
    /// Relative transfers use the executing virtual PC, then select storage
    /// only when the destination remains inside this same alternate.
    pub fn branch_target(&self, pc: GuestAddr, word: u32) -> GuestAddr {
        let target = self
            .linked_pc(pc)
            .0
            .wrapping_add(4)
            .wrapping_add_signed(i32::from(word as i16) * 4);
        GuestAddr(self.slot_view(pc, target))
    }
    /// Every placed copy of `address` when it is in a slot's linked text:
    /// a pointer there names whichever alternate is loaded (ADR-0185).
    pub fn slot_copies(&self, address: u32) -> Vec<u32> {
        let copies: Vec<u32> = self
            .slots
            .iter()
            .filter_map(|(placed, linked, text)| {
                let off = address.wrapping_sub(*linked);
                (off < *text).then(|| placed.start.0 + off)
            })
            .collect();
        if copies.is_empty() {
            vec![address]
        } else {
            copies
        }
    }
    pub fn from_rom(
        rom: &CanonicalRom,
        offset: RomOffset,
        range: GuestRange,
    ) -> Result<Self, String> {
        range.validate(true)?;
        let begin = usize::try_from(offset.0).map_err(|_| "ROM offset too large")?;
        let end = begin
            .checked_add(range.size as usize)
            .ok_or("ROM range overflow")?;
        let bytes = rom
            .bytes()
            .get(begin..end)
            .ok_or("code mapping outside ROM")?;
        let words = bytes
            .as_chunks::<4>()
            .0
            .iter()
            .map(|w| u32::from_be_bytes(*w))
            .collect();
        Ok(Self {
            base: CodeAddress {
                pc: range.start,
                image: sha256(bytes),
                generation: 0,
            },
            words,
            rom_offset: Some(offset),
            physical_start: None,
            holes: Vec::new(),
            slots: Vec::new(),
        })
    }
    pub fn size(&self) -> Result<u32, String> {
        u32::try_from(self.words.len())
            .ok()
            .and_then(|n| n.checked_mul(4))
            .ok_or_else(|| "code image too large".into())
    }
    pub fn word(&self, pc: GuestAddr) -> Option<u32> {
        let offset = pc.0.checked_sub(self.base.pc.0)?;
        if !offset.is_multiple_of(4) || self.holes.iter().any(|h| h.contains(pc)) {
            return None;
        }
        self.words.get((offset / 4) as usize).copied()
    }
    /// The content-derived identity: the SHA-256 of the words, plus the hole
    /// layout when there are holes (ADR-0150).
    pub fn content_identity(&self) -> String {
        let mut bytes: Vec<u8> = self.words.iter().flat_map(|w| w.to_be_bytes()).collect();
        if !self.holes.is_empty() {
            bytes.extend(b"holes");
            for h in &self.holes {
                bytes.extend(h.start.0.to_be_bytes());
                bytes.extend(h.size.to_be_bytes());
            }
        }
        if !self.slots.is_empty() {
            bytes.extend(b"slots");
            for (placed, linked, text) in &self.slots {
                bytes.extend(placed.start.0.to_be_bytes());
                bytes.extend(placed.size.to_be_bytes());
                bytes.extend(linked.to_be_bytes());
                bytes.extend(text.to_be_bytes());
            }
        }
        sha256(&bytes)
    }
    pub fn address(&self, pc: GuestAddr) -> CodeAddress {
        CodeAddress {
            pc,
            ..self.base.clone()
        }
    }
}

#[derive(Debug, Clone)]
pub struct Discovery {
    pub map: ProgramMap,
    /// All decoded bytes, including slots. No runtime executor is present.
    pub words: BTreeMap<CodeAddress, u32>,
}

pub fn decode(word: u32, pc: GuestAddr) -> Instruction {
    Instruction::new(word, pc.0, InstrCategory::CPU)
}

/// Register identities that make an integer branch impossible, independently
/// of incoming state. Link writes and non-likely delay slots still execute.
pub fn branch_never_taken(word: u32) -> bool {
    let (op, rs, rt) = (word >> 26, (word >> 21) & 31, (word >> 16) & 31);
    match op {
        1 => rs == 0 && matches!(rt, 0 | 2 | 16 | 18), // BLTZ/L/AL/ALL zero
        7 | 23 => rs == 0 && rt == 0,                  // BGTZ/L zero
        5 | 21 => rs == rt,                            // BNE/L r,r
        _ => false,
    }
}

/// Admission heuristic for an alternate call identity, never a code/data proof.
/// Reject a reserved encoding in a short straight-line prefix; transfers and
/// the scan limit keep the identity for ordinary discovery. Rejected identities
/// must be reported by the solver and refused by native slot dispatch.
pub(crate) fn slot_entry_decodable(image: &CodeImage, pc: GuestAddr) -> bool {
    for n in 0..64 {
        let at = GuestAddr(pc.0.wrapping_add(4 * n));
        let Some(word) = image.instruction_word(at) else {
            return false;
        };
        let instruction = decode(word, at);
        if !instruction.is_valid() {
            return false;
        }
        if instruction.has_delay_slot() || unsupported(&instruction) {
            return true;
        }
    }
    true
}

/// TGE TGEU TLT TLTU TEQ TNE and their immediate forms (ADR-0145). Their
/// not-taken path falls through, so discovery continues past them.
pub fn is_conditional_trap(word: u32) -> bool {
    match word >> 26 {
        0 => matches!(word & 63, 48..=52 | 54),
        1 => matches!((word >> 16) & 31, 8..=12 | 14),
        _ => false,
    }
}

fn unsupported(i: &Instruction) -> bool {
    !i.is_valid() || i.is_trap() || matches!(i.opcode_name(), "syscall" | "break" | "eret")
}

pub fn direct_cfg(
    rom: RomIdentity,
    image: &CodeImage,
    entries: &[GuestAddr],
    budget: usize,
) -> Result<Discovery, String> {
    direct_cfg_bounded(rom, image, entries, budget, &BTreeSet::new())
}

/// Direct discovery that records calls and jumps into `runtime` entries but
/// never decodes them (ADR-0129).
pub fn direct_cfg_bounded(
    rom: RomIdentity,
    image: &CodeImage,
    entries: &[GuestAddr],
    budget: usize,
    runtime: &BTreeSet<GuestAddr>,
) -> Result<Discovery, String> {
    let size = image.size()?;
    GuestRange {
        start: image.base.pc,
        size,
    }
    .validate(true)?;
    let mut map = ProgramMap::new(rom);
    let evidence_id = format!(
        "static:{}:{}:{:08x}",
        image.base.image, image.base.generation, image.base.pc.0
    );
    let evidence: EvidenceRefs = [evidence_id.clone()].into();
    map.evidence.insert(
        evidence_id,
        Evidence {
            kind: EvidenceKind::Static,
            producer: "plaid-direct-cfg/rabbitizer".into(),
            revision: DECODER_REV.into(),
            detail: "recursive direct discovery in an explicitly supplied mapping".into(),
        },
    );
    map.regions.insert(Region {
        image: image.base.image.clone(),
        generation: image.base.generation,
        range: GuestRange {
            start: image.base.pc,
            size,
        },
        rom_offset: image.rom_offset,
        physical_start: image.physical_start,
        overlay: None,
        evidence: evidence.clone(),
    });
    let mut pending = BTreeSet::new();
    let mut leaders = BTreeSet::new();
    let mut normal = BTreeSet::new();
    let mut terminal = BTreeMap::new();
    let mut words = BTreeMap::new();
    for &pc in entries {
        if !pc.0.is_multiple_of(4) {
            return Err("unaligned CFG entry".into());
        }
        map.entries.insert(image.address(pc), evidence.clone());
        pending.insert(pc);
        leaders.insert(pc);
    }
    while let Some(pc) = pending.pop_first() {
        if normal.contains(&pc) {
            continue;
        }
        let site = image.address(pc);
        let Some(word) = image.instruction_word(pc) else {
            map.unresolved.insert(Unresolved {
                kind: "unmapped_target".into(),
                site: Some(site),
                detail: "reachable PC has no instruction source in supplied mapping".into(),
                evidence: evidence.clone(),
            });
            continue;
        };
        if normal.len() >= budget {
            map.unresolved.insert(Unresolved {
                kind: "resource_limit".into(),
                site: Some(site),
                detail: "direct CFG instruction budget reached".into(),
                evidence: evidence.clone(),
            });
            break;
        }
        normal.insert(pc);
        words.insert(site.clone(), word);
        let i = decode(word, pc);
        if unsupported(&i) {
            map.unresolved.insert(Unresolved {
                kind: "exception_or_unsupported_instruction".into(),
                site: Some(site.clone()),
                detail: format!(
                    "instruction {word:08x} ({}) requires additional execution model",
                    i.opcode_name()
                ),
                evidence: evidence.clone(),
            });
            if !is_conditional_trap(word) {
                terminal.insert(pc, 4);
                continue;
            }
        }
        if i.has_delay_slot() {
            let never_taken = i.is_valid() && branch_never_taken(word);
            let annulled = never_taken && i.is_branch_likely();
            let links = i.does_link() && !(i.opcode_name() == "jalr" && i.get_rd() == 0);
            let ds = GuestAddr(pc.0.wrapping_add(4));
            let ds_word = image.instruction_word(ds);
            let ds_valid = ds_word.is_some_and(|w| {
                let d = decode(w, ds);
                !unsupported(&d) && !d.has_delay_slot()
            });
            terminal.insert(
                pc,
                if !annulled && ds_word.is_some() && ds.0 > pc.0 {
                    8
                } else {
                    4
                },
            );
            if let Some(w) = ds_word.filter(|_| !annulled) {
                words.insert(image.address(ds), w);
            }
            if !annulled && !ds_valid {
                map.unresolved.insert(Unresolved {
                    kind: "unsupported_delay_slot".into(),
                    site: Some(site.clone()),
                    detail:
                        "delay slot absent, exceptional, reserved, or contains a control transfer"
                            .into(),
                    evidence: evidence.clone(),
                });
            }
            let delay = if i.is_branch_likely() {
                DelaySlot::TakenOnly
            } else {
                DelaySlot::Always
            };
            if (i.is_branch() || i.is_jump_with_address()) && !never_taken {
                // Rabbitizer treats PC=0 as an unspecified address for J. Use
                // literal ISA arithmetic so low-address synthetic inputs work.
                let target = GuestAddr(if i.is_jump_with_address() {
                    image.jump_target(pc, word).0
                } else {
                    image.branch_target(pc, word).0
                });
                let kind = if links {
                    EdgeKind::Call
                } else if i.is_branch() {
                    EdgeKind::Branch
                } else {
                    EdgeKind::Jump
                };
                map.direct_edges.insert(DirectEdge {
                    site: site.clone(),
                    target: image.address(target),
                    kind,
                    delay_slot: delay,
                    evidence: evidence.clone(),
                });
                // A linked slot call selects an executable identity at run time;
                // the overlapping fallback ROM window is not another identity.
                let slot_call = kind == EdgeKind::Call
                    && image.slot_copies(target.0).iter().any(|&t| t != target.0);
                if !slot_call && !(runtime.contains(&target) && kind != EdgeKind::Branch) {
                    leaders.insert(target);
                    pending.insert(target);
                }
            } else if !never_taken {
                map.indirect_sites.insert(IndirectSite {
                    site: site.clone(),
                    link_register: if links { Some(i.get_rd() as u8) } else { None },
                    delay_slot: delay,
                    candidates: BTreeMap::new(),
                    observed: BTreeMap::new(),
                    closed_proof: None,
                    evidence: evidence.clone(),
                });
            }
            if (i.is_branch() && !i.is_unconditional_branch()) || links {
                let next = GuestAddr(pc.0.wrapping_add(8));
                if links {
                    map.direct_edges.insert(DirectEdge {
                        site: site.clone(),
                        target: image.address(next),
                        kind: EdgeKind::ReturnContinuation,
                        delay_slot: DelaySlot::None,
                        evidence: evidence.clone(),
                    });
                }
                if i.is_branch() && !i.is_unconditional_branch() {
                    map.direct_edges.insert(DirectEdge {
                        site,
                        target: image.address(next),
                        kind: EdgeKind::Fallthrough,
                        delay_slot: if i.is_branch_likely() {
                            DelaySlot::None
                        } else {
                            DelaySlot::Always
                        },
                        evidence: evidence.clone(),
                    });
                }
                leaders.insert(next);
                pending.insert(next);
            }
        } else {
            let next = GuestAddr(pc.0.wrapping_add(4));
            if image.instruction_word(next).is_some() {
                pending.insert(next);
            } else {
                terminal.insert(pc, 4);
                map.direct_edges.insert(DirectEdge {
                    site,
                    target: image.address(next),
                    kind: EdgeKind::Fallthrough,
                    delay_slot: DelaySlot::None,
                    evidence: evidence.clone(),
                });
                pending.insert(next);
            }
        }
    }
    // Partition after traversal, so a newly found target splits earlier linear code.
    for &leader in &leaders {
        if !normal.contains(&leader) {
            continue;
        }
        let mut pc = leader;
        let mut block_size = 0;
        loop {
            block_size += terminal.get(&pc).copied().unwrap_or(4);
            if terminal.contains_key(&pc) {
                break;
            }
            let next = GuestAddr(pc.0.wrapping_add(4));
            if leaders.contains(&next) {
                map.direct_edges.insert(DirectEdge {
                    site: image.address(pc),
                    target: image.address(next),
                    kind: EdgeKind::Fallthrough,
                    delay_slot: DelaySlot::None,
                    evidence: evidence.clone(),
                });
                break;
            }
            if !normal.contains(&next) {
                break;
            }
            pc = next;
        }
        map.blocks.insert(BasicBlock {
            start: image.address(leader),
            size: block_size,
            delay_slot_entry: false,
            evidence: evidence.clone(),
        });
    }
    map.validate()?;
    Ok(Discovery { map, words })
}
