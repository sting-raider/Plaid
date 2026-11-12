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
    pub slots: Slots,
}

/// One slot alternate: placed range, linked address, text size.
pub type Slot = (GuestRange, u32, u32);

/// The slot list plus a lookup index built on first use. Mutable access drops
/// the index, so callers edit it like the `Vec` it derefs to.
#[derive(Debug, Clone, Default)]
pub struct Slots {
    list: Vec<Slot>,
    index: std::sync::OnceLock<Option<SlotIndex>>,
}

/// `None` when placed ranges overlap or a range wraps; lookups then scan the
/// list in order, as before.
#[derive(Debug, Clone)]
struct SlotIndex {
    /// (placed start, slot) sorted by start; the ranges are disjoint
    placed: Vec<(u32, usize)>,
    /// (linked, slot) sorted by linked, and the largest text size
    linked: Vec<(u32, usize)>,
    max_text: u32,
}

impl From<Vec<Slot>> for Slots {
    fn from(list: Vec<Slot>) -> Self {
        Self {
            list,
            index: Default::default(),
        }
    }
}
impl FromIterator<Slot> for Slots {
    fn from_iter<I: IntoIterator<Item = Slot>>(iter: I) -> Self {
        Vec::from_iter(iter).into()
    }
}
impl std::ops::Deref for Slots {
    type Target = Vec<Slot>;
    fn deref(&self) -> &Vec<Slot> {
        &self.list
    }
}
impl std::ops::DerefMut for Slots {
    fn deref_mut(&mut self) -> &mut Vec<Slot> {
        self.index = Default::default();
        &mut self.list
    }
}
impl<'a> IntoIterator for &'a Slots {
    type Item = &'a Slot;
    type IntoIter = std::slice::Iter<'a, Slot>;
    fn into_iter(self) -> Self::IntoIter {
        self.list.iter()
    }
}
impl<'a> IntoIterator for &'a mut Slots {
    type Item = &'a mut Slot;
    type IntoIter = std::slice::IterMut<'a, Slot>;
    fn into_iter(self) -> Self::IntoIter {
        std::ops::DerefMut::deref_mut(self).iter_mut()
    }
}
impl Slots {
    fn index(&self) -> Option<&SlotIndex> {
        self.index
            .get_or_init(|| {
                let mut placed: Vec<(u32, usize)> = self
                    .list
                    .iter()
                    .enumerate()
                    .map(|(i, s)| (s.0.start.0, i))
                    .collect();
                placed.sort_unstable();
                let disjoint = placed.windows(2).all(|w| {
                    let a = &self.list[w[0].1].0;
                    u64::from(a.start.0) + u64::from(a.size) <= u64::from(w[1].0)
                });
                let fits = self.list.iter().all(|s| {
                    u64::from(s.0.start.0) + u64::from(s.0.size) <= 1 << 32
                        && u64::from(s.1) + u64::from(s.2) <= 1 << 32
                });
                (disjoint && fits).then(|| {
                    let mut linked: Vec<(u32, usize)> = self
                        .list
                        .iter()
                        .enumerate()
                        .map(|(i, s)| (s.1, i))
                        .collect();
                    linked.sort_unstable();
                    let max_text = self.list.iter().map(|s| s.2).max().unwrap_or(0);
                    SlotIndex {
                        placed,
                        linked,
                        max_text,
                    }
                })
            })
            .as_ref()
    }
    /// The slot whose placed range holds `pc` (at most one: they are
    /// disjoint), or `None` when there is no index.
    fn placed_at(&self, pc: u32) -> Option<Option<&Slot>> {
        let index = self.index()?;
        let at = index.placed.partition_point(|&(start, _)| start <= pc);
        Some(at.checked_sub(1).and_then(|k| {
            let slot = &self.list[index.placed[k].1];
            (pc - slot.0.start.0 < slot.0.size).then_some(slot)
        }))
    }
}

impl CodeImage {
    /// Slot data remains readable for tables, but cannot supply instructions.
    pub fn instruction_word(&self, pc: GuestAddr) -> Option<u32> {
        let data = |(placed, _, text): &Slot| {
            let off = pc.0.wrapping_sub(placed.start.0);
            off < placed.size && off >= *text
        };
        let in_data = match self.slots.placed_at(pc.0) {
            Some(slot) => slot.is_some_and(data),
            None => self.slots.iter().any(data),
        };
        if in_data {
            return None;
        }
        self.word(pc)
    }
    /// A slot inside the branch's own supplied text. Analyses that require a
    /// contiguous prefix must refuse an independently fetched delay instruction.
    pub fn inline_delay_word(&self, branch: GuestAddr) -> Option<u32> {
        if self.slots.iter().any(|(placed, _, text)| {
            placed.contains(branch) && branch.0 - placed.start.0 + 4 >= *text
        }) {
            return None;
        }
        self.instruction_word(GuestAddr(branch.0.checked_add(4)?))
    }
    /// Where code at `at` finds `address`: in a slot alternate's placed copy
    /// when `at` is in one and `address` is in its linked range (ADR-0185).
    pub fn slot_view(&self, at: GuestAddr, address: u32) -> u32 {
        let view = |(placed, linked, _): &Slot| {
            let off = address.wrapping_sub(*linked);
            (at.0.wrapping_sub(placed.start.0) < placed.size && off < placed.size)
                .then(|| placed.start.0 + off)
        };
        match self.slots.placed_at(at.0) {
            Some(slot) => slot.and_then(view),
            None => self.slots.iter().find_map(view),
        }
        .unwrap_or(address)
    }
    /// Architectural PC of a word held in an analysis slot alternate.
    pub fn linked_pc(&self, pc: GuestAddr) -> GuestAddr {
        let link = |(placed, linked, _): &Slot| {
            let offset = pc.0.wrapping_sub(placed.start.0);
            (offset < placed.size).then(|| linked.wrapping_add(offset))
        };
        GuestAddr(
            match self.slots.placed_at(pc.0) {
                Some(slot) => slot.and_then(link),
                None => self.slots.iter().find_map(link),
            }
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
    /// Sequential execution follows the guest PC across fragment boundaries;
    /// neighboring analysis storage does not identify the next guest bytes.
    pub fn sequential_pc(&self, pc: GuestAddr, bytes: u32) -> GuestAddr {
        let step = |(placed, linked, _): &Slot| {
            let offset = pc.0.wrapping_sub(placed.start.0);
            (offset < placed.size).then(|| {
                let next = offset.wrapping_add(bytes);
                GuestAddr(if next < placed.size {
                    placed.start.0.wrapping_add(next)
                } else {
                    linked.wrapping_add(next)
                })
            })
        };
        match self.slots.placed_at(pc.0) {
            Some(slot) => slot.and_then(step),
            None => self.slots.iter().find_map(step),
        }
        .unwrap_or(GuestAddr(pc.0.wrapping_add(bytes)))
    }
    /// Every placed copy of `address` when it is in a slot's linked text:
    /// a pointer there names whichever alternate is loaded (ADR-0185).
    pub fn slot_copies(&self, address: u32) -> Vec<u32> {
        let copy = |(placed, linked, text): &Slot| {
            let off = address.wrapping_sub(*linked);
            (off < *text).then(|| placed.start.0 + off)
        };
        let copies: Vec<u32> = match self.slots.index() {
            Some(index) => {
                // only links at most max_text below `address` can hold it; keep list order
                let lo = index
                    .linked
                    .partition_point(|&(l, _)| l < address.saturating_sub(index.max_text));
                let hi = index.linked.partition_point(|&(l, _)| l <= address);
                let mut hits: Vec<usize> = index.linked[lo..hi].iter().map(|&(_, i)| i).collect();
                hits.sort_unstable();
                hits.iter().filter_map(|&i| copy(&self.slots[i])).collect()
            }
            None => self.slots.iter().filter_map(copy).collect(),
        };
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
            slots: Default::default(),
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
        if !offset.is_multiple_of(4) || self.in_hole(pc) {
            return None;
        }
        self.words.get((offset / 4) as usize).copied()
    }
    fn in_hole(&self, pc: GuestAddr) -> bool {
        // Many holes come only from a composite, which builds them sorted and
        // disjoint (declared_loads); a few hand-made ones are scanned.
        if self.holes.len() < 16 {
            return self.holes.iter().any(|h| h.contains(pc));
        }
        debug_assert!(self.holes.is_sorted_by_key(|h| h.start.0));
        let after = self.holes.partition_point(|h| h.start.0 <= pc.0);
        after > 0 && self.holes[after - 1].contains(pc)
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
pub fn slot_entry_decodable(image: &CodeImage, pc: GuestAddr) -> bool {
    let remaining = image.slots.iter().find_map(|(placed, _, _)| {
        placed
            .contains(pc)
            .then(|| placed.size - (pc.0 - placed.start.0))
    });
    for n in 0..64 {
        if remaining.is_some_and(|bytes| 4 * n >= bytes) {
            // Another source is ordinary discovery's obligation, not this prefix.
            return true;
        }
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

/// What discovery learns from one reachable PC. Pure, so a wave of PCs can be
/// visited on every core; applying the visits in any order builds the same map.
#[derive(Default)]
struct Visit {
    /// the PC decoded (it is not an unmapped target)
    decoded: bool,
    unresolved: Vec<Unresolved>,
    terminal: Option<u32>,
    words: Vec<(CodeAddress, u32)>,
    edges: Vec<DirectEdge>,
    indirect: Option<IndirectSite>,
    /// successors, and whether each one starts a block
    next: Vec<(GuestAddr, bool)>,
}

fn visit(
    image: &CodeImage,
    runtime: &BTreeSet<GuestAddr>,
    evidence: &EvidenceRefs,
    pc: GuestAddr,
) -> Visit {
    let mut v = Visit::default();
    let site = image.address(pc);
    let Some(word) = image.instruction_word(pc) else {
        v.unresolved.push(Unresolved {
            kind: "unmapped_target".into(),
            site: Some(site),
            detail: "reachable PC has no instruction source in supplied mapping".into(),
            evidence: evidence.clone(),
        });
        return v;
    };
    v.decoded = true;
    v.words.push((site.clone(), word));
    let i = decode(word, pc);
    if unsupported(&i) {
        v.unresolved.push(Unresolved {
            kind: "exception_or_unsupported_instruction".into(),
            site: Some(site.clone()),
            detail: format!(
                "instruction {word:08x} ({}) requires additional execution model",
                i.opcode_name()
            ),
            evidence: evidence.clone(),
        });
        if !is_conditional_trap(word) {
            v.terminal = Some(4);
            return v;
        }
    }
    if i.has_delay_slot() {
        let never_taken = i.is_valid() && branch_never_taken(word);
        let annulled = never_taken && i.is_branch_likely();
        let links = i.does_link() && !(i.opcode_name() == "jalr" && i.get_rd() == 0);
        let ds = image.sequential_pc(pc, 4);
        let ds_word = (ds.0 == pc.0.wrapping_add(4))
            .then(|| image.instruction_word(ds))
            .flatten();
        let ds_valid = ds_word.is_some_and(|w| {
            let d = decode(w, ds);
            !unsupported(&d) && !d.has_delay_slot()
        });
        v.terminal = Some(
            if !annulled && ds_word.is_some() && ds.0 == pc.0.wrapping_add(4) {
                8
            } else {
                4
            },
        );
        if let Some(w) = ds_word.filter(|_| !annulled) {
            v.words.push((image.address(ds), w));
        }
        if !annulled && !ds_valid {
            v.unresolved.push(Unresolved {
                kind: "unsupported_delay_slot".into(),
                site: Some(site.clone()),
                detail: "delay slot absent, exceptional, reserved, or contains a control transfer"
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
            v.edges.push(DirectEdge {
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
                v.next.push((target, true));
            }
        } else if !never_taken {
            v.indirect = Some(IndirectSite {
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
            let next = image.sequential_pc(pc, 8);
            if links {
                v.edges.push(DirectEdge {
                    site: site.clone(),
                    target: image.address(next),
                    kind: EdgeKind::ReturnContinuation,
                    delay_slot: DelaySlot::None,
                    evidence: evidence.clone(),
                });
            }
            if i.is_branch() && !i.is_unconditional_branch() {
                v.edges.push(DirectEdge {
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
            let bound_next = next.0 != pc.0.wrapping_add(8)
                && image.slot_copies(next.0).iter().any(|&copy| copy != next.0);
            if !bound_next {
                v.next.push((next, true));
            }
        }
    } else {
        let next = image.sequential_pc(pc, 4);
        if next.0 == pc.0.wrapping_add(4) && image.instruction_word(next).is_some() {
            v.next.push((next, false));
        } else {
            v.terminal = Some(4);
            v.edges.push(DirectEdge {
                site,
                target: image.address(next),
                kind: EdgeKind::Fallthrough,
                delay_slot: DelaySlot::None,
                evidence: evidence.clone(),
            });
            let bound_next = next.0 != pc.0.wrapping_add(4)
                && image.slot_copies(next.0).iter().any(|&copy| copy != next.0);
            if !bound_next {
                v.next.push((next, true));
            }
        }
    }
    v
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
    direct_cfg_continued(rom, image, entries, budget, runtime, None).map(|(d, _)| d)
}

/// A finished traversal before block partitioning: every set in it is a union
/// over what each root reaches, so walking more roots from it gives the same
/// sets as walking all of them afresh (ADR-0326).
#[derive(Clone)]
pub struct Walk {
    image: CodeAddress,
    runtime: BTreeSet<GuestAddr>,
    budget: usize,
    entries: BTreeSet<GuestAddr>,
    map: ProgramMap,
    normal: BTreeSet<GuestAddr>,
    terminal: BTreeMap<GuestAddr, u32>,
    words: BTreeMap<CodeAddress, u32>,
    leaders: BTreeSet<GuestAddr>,
    seen: BTreeSet<GuestAddr>,
}

/// [`direct_cfg_bounded`] that continues `previous` when it walked a subset of
/// `entries` in the same image, boundary and budget. The returned walk is
/// `None` when the budget forced the sequential traversal.
pub fn direct_cfg_continued(
    rom: RomIdentity,
    image: &CodeImage,
    entries: &[GuestAddr],
    budget: usize,
    runtime: &BTreeSet<GuestAddr>,
    previous: Option<Walk>,
) -> Result<(Discovery, Option<Walk>), String> {
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
    let mut seen = BTreeSet::new();
    let walk_started = std::time::Instant::now();
    let fresh = map.clone();
    let all: BTreeSet<GuestAddr> = entries.iter().copied().collect();
    if let Some(w) = previous.filter(|w| {
        w.image == image.base
            && &w.runtime == runtime
            && w.budget == budget
            && w.entries.is_subset(&all)
            && std::env::var_os("PLAID_SERIAL_CFG").is_none()
    }) {
        (map, normal, terminal, words, leaders, seen) =
            (w.map, w.normal, w.terminal, w.words, w.leaders, w.seen);
        for &pc in all.difference(&w.entries) {
            if !pc.0.is_multiple_of(4) {
                return Err("unaligned CFG entry".into());
            }
            map.entries.insert(image.address(pc), evidence.clone());
            leaders.insert(pc);
            if !normal.contains(&pc) {
                pending.insert(pc);
            }
        }
    } else {
        for &pc in entries {
            if !pc.0.is_multiple_of(4) {
                return Err("unaligned CFG entry".into());
            }
            map.entries.insert(image.address(pc), evidence.clone());
            pending.insert(pc);
            leaders.insert(pc);
        }
    }
    #[allow(clippy::too_many_arguments)]
    fn apply(
        v: Visit,
        pc: GuestAddr,
        map: &mut ProgramMap,
        normal: &mut BTreeSet<GuestAddr>,
        terminal: &mut BTreeMap<GuestAddr, u32>,
        words: &mut BTreeMap<CodeAddress, u32>,
        leaders: &mut BTreeSet<GuestAddr>,
        pending: &mut BTreeSet<GuestAddr>,
    ) {
        if v.decoded {
            normal.insert(pc);
        }
        map.unresolved.extend(v.unresolved);
        if let Some(t) = v.terminal {
            terminal.insert(pc, t);
        }
        words.extend(v.words);
        map.direct_edges.extend(v.edges);
        map.indirect_sites.extend(v.indirect);
        for (to, leader) in v.next {
            if leader {
                leaders.insert(to);
            }
            pending.insert(to);
        }
    }
    // Visit waves of pending PCs on every core, each worker following its
    // straight-line run. The reachable set, and so the map, is the fixed point
    // whatever the order; only where the instruction budget cuts off depends on
    // order, so a traversal that reaches it is redone in the sequential order.
    let mut parallel = std::env::var_os("PLAID_SERIAL_CFG").is_none();
    if parallel {
        while !pending.is_empty() && normal.len() < budget {
            let wave: Vec<GuestAddr> = std::mem::take(&mut pending).into_iter().collect();
            seen.extend(wave.iter().copied());
            let known = &normal;
            let runs = crate::indirect::par_map(&wave, |&start| {
                let mut out = Vec::new();
                let mut pc = start;
                loop {
                    let v = visit(image, runtime, &evidence, pc);
                    let follow = match v.next.as_slice() {
                        [(n, false)] if !known.contains(n) && out.len() < 4096 => Some(*n),
                        _ => None,
                    };
                    out.push((pc, v));
                    let Some(n) = follow else { break };
                    pc = n;
                }
                out
            });
            for (pc, v) in runs.into_iter().flatten() {
                seen.insert(pc);
                apply(
                    v,
                    pc,
                    &mut map,
                    &mut normal,
                    &mut terminal,
                    &mut words,
                    &mut leaders,
                    &mut pending,
                );
            }
            pending.retain(|pc| !seen.contains(pc) && !normal.contains(pc));
        }
        if normal.len() >= budget {
            // Redo the whole traversal in order, from every entry.
            parallel = false;
            pending.clear();
            (map, normal, terminal, words, leaders) = (
                fresh,
                BTreeSet::new(),
                BTreeMap::new(),
                BTreeMap::new(),
                BTreeSet::new(),
            );
            for &pc in entries {
                map.entries.insert(image.address(pc), evidence.clone());
                pending.insert(pc);
                leaders.insert(pc);
            }
        }
    }
    while let Some(pc) = pending.pop_first() {
        if normal.contains(&pc) {
            continue;
        }
        let v = visit(image, runtime, &evidence, pc);
        if v.decoded && normal.len() >= budget {
            map.unresolved.insert(Unresolved {
                kind: "resource_limit".into(),
                site: Some(image.address(pc)),
                detail: "direct CFG instruction budget reached".into(),
                evidence: evidence.clone(),
            });
            break;
        }
        apply(
            v,
            pc,
            &mut map,
            &mut normal,
            &mut terminal,
            &mut words,
            &mut leaders,
            &mut pending,
        );
    }
    crate::timing::note("cfg.walk", walk_started.elapsed());
    let clone_started = std::time::Instant::now();
    let walk = parallel.then(|| Walk {
        image: image.base.clone(),
        runtime: runtime.clone(),
        budget,
        entries: all,
        map: map.clone(),
        normal: normal.clone(),
        terminal: terminal.clone(),
        words: words.clone(),
        leaders: leaders.clone(),
        seen,
    });
    crate::timing::note("cfg.clone", clone_started.elapsed());
    let partition_started = std::time::Instant::now();
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
    crate::timing::note("cfg.partition", partition_started.elapsed());
    let validate_started = std::time::Instant::now();
    map.validate()?;
    crate::timing::note("cfg.validate", validate_started.elapsed());
    Ok((Discovery { map, words }, walk))
}

#[cfg(test)]
mod prefix_tests {
    use super::*;

    #[test]
    fn identity_link_prefix_still_stops_at_its_source_end() {
        let base = GuestAddr(0x8000_0000);
        let mut image = CodeImage {
            base: CodeAddress {
                pc: base,
                image: "00".repeat(32),
                generation: 0,
            },
            words: vec![0, 0, 0x7000_0000],
            rom_offset: None,
            physical_start: None,
            holes: vec![],
            slots: vec![(
                GuestRange {
                    start: base,
                    size: 8,
                },
                base.0,
                8,
            )]
            .into(),
        };
        assert!(!decode(image.words[2], GuestAddr(base.0 + 8)).is_valid());
        assert!(slot_entry_decodable(&image, GuestAddr(base.0 + 4)));
        image.words[1] = 0x7000_0000;
        assert!(!slot_entry_decodable(&image, GuestAddr(base.0 + 4)));
    }

    #[test]
    fn a_continued_walk_equals_a_fresh_one() {
        let base = GuestAddr(0x8000_0000);
        let image = CodeImage {
            base: CodeAddress {
                pc: base,
                image: "00".repeat(32),
                generation: 0,
            },
            // A: jal B; jr ra (0x08 is a later root inside A). B at 0x10.
            // C at 0x20: a branch over one instruction, then jr ra.
            words: vec![
                0x0c00_0004,
                0,
                0x03e0_0008,
                0,
                0x2402_0001,
                0x03e0_0008,
                0,
                0,
                0x1000_0002,
                0,
                0x2402_0001,
                0x03e0_0008,
                0,
            ],
            rom_offset: None,
            physical_start: None,
            holes: vec![],
            slots: Default::default(),
        };
        let rom = RomIdentity {
            sha256: "a".repeat(64),
            size: 4096,
        };
        let at = |o: u32| GuestAddr(base.0 + o);
        let none = BTreeSet::new();
        let (first, walk) =
            direct_cfg_continued(rom.clone(), &image, &[at(0)], 1000, &none, None).unwrap();
        assert!(walk.is_some());
        let all = [at(0), at(0x20), at(8)];
        let (continued, _) =
            direct_cfg_continued(rom.clone(), &image, &all, 1000, &none, walk).unwrap();
        let fresh = direct_cfg_bounded(rom, &image, &all, 1000, &none).unwrap();
        assert_eq!(continued.map.to_json(), fresh.map.to_json());
        assert_eq!(continued.words, fresh.words);
        assert!(
            fresh.map.blocks.len() > first.map.blocks.len(),
            "C adds blocks"
        );
    }
}
