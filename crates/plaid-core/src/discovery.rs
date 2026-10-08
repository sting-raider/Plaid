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
}
impl CodeImage {
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
        if !offset.is_multiple_of(4) {
            return None;
        }
        self.words.get((offset / 4) as usize).copied()
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

fn unsupported(i: &Instruction) -> bool {
    !i.is_valid() || i.is_trap() || matches!(i.opcode_name(), "syscall" | "break" | "eret")
}

pub fn direct_cfg(
    rom: RomIdentity,
    image: &CodeImage,
    entries: &[GuestAddr],
    budget: usize,
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
        let Some(word) = image.word(pc) else {
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
            terminal.insert(pc, 4);
            map.unresolved.insert(Unresolved {
                kind: "exception_or_unsupported_instruction".into(),
                site: Some(site),
                detail: format!(
                    "instruction {word:08x} ({}) requires additional execution model",
                    i.opcode_name()
                ),
                evidence: evidence.clone(),
            });
            continue;
        }
        if i.has_delay_slot() {
            let links = i.does_link() && !(i.opcode_name() == "jalr" && i.get_rd() == 0);
            let ds = GuestAddr(pc.0.wrapping_add(4));
            let ds_word = image.word(ds);
            let ds_valid = ds_word.is_some_and(|w| {
                let d = decode(w, ds);
                !unsupported(&d) && !d.has_delay_slot()
            });
            terminal.insert(
                pc,
                if ds_word.is_some() && ds.0 > pc.0 {
                    8
                } else {
                    4
                },
            );
            if let Some(w) = ds_word {
                words.insert(image.address(ds), w);
            }
            if !ds_valid {
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
            if i.is_branch() || i.is_jump_with_address() {
                // Rabbitizer treats PC=0 as an unspecified address for J. Use
                // literal ISA arithmetic so low-address synthetic inputs work.
                let target = GuestAddr(if i.is_jump_with_address() {
                    (pc.0.wrapping_add(4) & 0xf0000000) | ((word & 0x03ffffff) << 2)
                } else {
                    pc.0.wrapping_add(4)
                        .wrapping_add_signed(i32::from(word as i16) * 4)
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
                leaders.insert(target);
                pending.insert(target);
            } else {
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
            if image.word(next).is_some() {
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
