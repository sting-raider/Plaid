//! Bounded pointer-table candidates from a guarded scalar dispatch pattern.
//! Snapshot reads are hypotheses: data immutability is not established here.
use crate::{
    EvidenceKind, GuestAddr,
    discovery::{CodeImage, decode},
    indirect::{MapIndex, signed_word, transfer},
    program::*,
    rom::sha256,
};
use serde::Serialize;
use std::collections::{BTreeMap, BTreeSet};

// a switch over a few hundred cases is ordinary compiler output (ADR-0183)
const MAX_ENTRIES: u32 = 1024;

#[derive(Serialize)]
struct TableEvidence {
    site: CodeAddress,
    load_pc: GuestAddr,
    guard_pc: GuestAddr,
    index_register: u8,
    table_start: GuestAddr,
    count: u32,
    prefix_sha256: String,
    snapshot_sha256: Option<String>,
    assumptions: [&'static str; 2],
}

fn field(word: u32, shift: u32) -> u8 {
    ((word >> shift) & 31) as u8
}

fn pattern(map: &MapIndex, image: &CodeImage, site: &IndirectSite) -> Option<TableEvidence> {
    if site.site.image != image.base.image || site.site.generation != image.base.generation {
        return None;
    }
    let pc = site.site.pc;
    let jump = image.word(pc)?;
    if jump >> 26 != 0 || !matches!(jump & 63, 8 | 9) {
        return None;
    }
    // IDO without the scheduler keeps a load-delay `nop` before the jump
    // (ADR-0154)
    let delay_nop = image.word(GuestAddr(pc.0.checked_sub(4)?))? == 0;
    let load_pc = GuestAddr(pc.0.checked_sub(if delay_nop { 8 } else { 4 })?);
    let load = image.word(load_pc)?;
    let add_pc = GuestAddr(load_pc.0.checked_sub(4)?);
    let add = image.word(add_pc)?;
    if load >> 26 != 35
        || field(load, 16) != field(jump, 21)
        || add >> 26 != 0
        || add & 63 != 33
        || field(add, 11) != field(load, 21)
    {
        return None;
    }
    let is_shift = |w: u32| {
        w >> 26 == 0 && w & 63 == 0 && (w >> 6) & 31 == 2 && field(w, 11) != 0 && field(w, 16) != 0
    };
    let (here, generation) = (site.site.image.as_str(), site.site.generation);
    let blocks: Vec<_> = map
        .containing(&site.site)
        .into_iter()
        .filter(|b| !b.delay_slot_entry)
        .collect();
    if blocks.len() != 1 || blocks[0].start.pc.0 > add_pc.0 {
        return None;
    }
    let block = blocks[0];
    // Nothing but the one incoming edge may enter the dispatch block.
    if map.jumped_to(&block.start)
        || map.jumped_in(here, generation, block.start.pc.0 + 1, pc.0)
        || map
            .edges_in(here, generation, block.start.pc.0 + 1, pc.0)
            .next()
            .is_some()
    {
        return None;
    }
    let [edge] = map.edges_to(&block.start)[..] else {
        return None;
    };
    if edge.site.image != image.base.image || edge.site.generation != image.base.generation {
        return None;
    }
    let branch = image.word(edge.site.pc)?;
    // The index scale is the nearest SLL before the add in the dispatch block
    // (GCC may schedule the table base LUI between them) or the delay slot of
    // a non-likely guard branch, which runs on both paths.
    let scales_add =
        |w: u32| is_shift(w) && (field(w, 11) == field(add, 21) || field(w, 11) == field(add, 16));
    let nearest = (block.start.pc.0..add_pc.0)
        .step_by(4)
        .rev()
        .map(GuestAddr)
        .find(|a| image.word(*a).is_some_and(scales_add));
    let (shift_pc, in_slot) = if let Some(at) = nearest {
        (at, false)
    } else if matches!(branch >> 26, 4 | 5)
        && image
            .word(GuestAddr(edge.site.pc.0.checked_add(4)?))
            .is_some_and(is_shift)
    {
        (GuestAddr(edge.site.pc.0 + 4), true)
    } else {
        return None;
    };
    let shift = image.word(shift_pc)?;
    let index = field(shift, 16);
    let scale = field(shift, 11);
    let base = if field(add, 21) == scale {
        field(add, 16)
    } else if field(add, 16) == scale {
        field(add, 21)
    } else {
        return None;
    };
    if base == scale {
        return None;
    }

    // The table bound is established by the SLTIU that last defines the
    // branch's flag; GCC may schedule unrelated instructions between them,
    // which must preserve the index. Alternate execution that enters the
    // compare-to-branch interval can reuse an
    // unconstrained/stale flag and still select the dispatch edge. When the
    // selected dispatch is the sequential branch fallthrough, entering the
    // physical delay-slot word also skips both compare and branch and then
    // falls directly into the dispatch block. Keep image/generation identity
    // explicit; equal guest PCs in another executable generation are unrelated.
    let flag = match (field(branch, 21), field(branch, 16)) {
        (0, 0) => return None,
        (flag, 0) | (0, flag) => flag,
        _ => return None,
    };
    // IDO can compute the bound and then take a branch whose only target is
    // the guard's block (ADR-0156); the walk then continues before that
    // branch's slot. The branch reads but must not write the flag or index.
    let same = |a: &CodeAddress| a.image == site.site.image && a.generation == site.site.generation;
    let guard_start = map
        .containing(&edge.site)
        .into_iter()
        .filter(|b| !b.delay_slot_entry)
        .map(|b| b.start.pc)
        .max()?;
    let into_guard = map.edges_to(&image.address(guard_start));
    let hop = match into_guard[..] {
        [e] if same(&e.site)
            && matches!(e.kind, EdgeKind::Branch | EdgeKind::Jump)
            && e.delay_slot != DelaySlot::None =>
        {
            Some(e.site.pc)
        }
        _ => None,
    };
    let mut hopped = None;
    let mut compare_pc = edge.site.pc;
    let mut interval = Vec::new();
    loop {
        if interval.len() > 32 {
            return None;
        }
        if compare_pc == guard_start
            && hopped.is_none()
            && let Some(branch) = hop
        {
            hopped = Some(branch);
            compare_pc = GuestAddr(branch.0.checked_add(8)?);
        }
        compare_pc = GuestAddr(compare_pc.0.checked_sub(4)?);
        let word = image.word(compare_pc)?;
        let instruction = decode(word, compare_pc);
        if instruction.destination_gpr() == Some(u32::from(flag)) {
            break;
        }
        if hopped == Some(compare_pc) {
            if instruction.destination_gpr() == Some(u32::from(index)) {
                return None;
            }
            interval.push(word);
            continue;
        }
        if !instruction.is_valid()
            || instruction.has_delay_slot()
            || instruction.is_trap()
            || matches!(instruction.opcode_name(), "syscall" | "break" | "eret")
            || instruction.destination_gpr() == Some(u32::from(index))
        {
            return None;
        }
        interval.push(word);
    }
    // The pieces of the path from the compare to the guard branch.
    let on_path = |pc: u32| match hopped {
        None => pc > compare_pc.0 && pc <= edge.site.pc.0,
        Some(branch) => {
            pc > compare_pc.0 && pc <= branch.0 + 4 || pc >= guard_start.0 && pc <= edge.site.pc.0
        }
    };
    // `on_path`, plus the guard's delay slot when it falls into the dispatch.
    let mut bypass = match hopped {
        None => vec![(compare_pc.0 + 1, edge.site.pc.0)],
        Some(branch) => vec![
            (compare_pc.0 + 1, branch.0 + 4),
            (guard_start.0, edge.site.pc.0),
        ],
    };
    if edge.site.pc.0.checked_add(8) == Some(block.start.pc.0) {
        bypass.push((edge.site.pc.0 + 4, edge.site.pc.0 + 4));
    }
    let compare = image.word(compare_pc)?;
    // Three direct entries into the interval still pass through the bound:
    // sequential flow from inside it, a branch whose delay slot is the
    // identical SLTIU (GCC's loop rotation puts it in a branch-likely slot),
    // and the fallthrough of a non-likely branch whose slot is the compare.
    let rebounds = |e: &DirectEdge| {
        let inside = on_path(e.target.pc.0);
        inside
            && same(&e.site)
            && (hopped == Some(e.site.pc) && e.target.pc == guard_start
                || e.kind == EdgeKind::Fallthrough
                && e.delay_slot == DelaySlot::None
                && e.site.pc.0 >= compare_pc.0
                && e.site.pc.0.checked_add(4) == Some(e.target.pc.0)
                // IDO puts the bound in the slot of the previous non-likely
                // branch, whose fallthrough always runs it (ADR-0151)
                || e.kind == EdgeKind::Fallthrough
                    && e.delay_slot == DelaySlot::Always
                    && e.site.pc.0.checked_add(4) == Some(compare_pc.0)
                    && e.site.pc.0.checked_add(8) == Some(e.target.pc.0)
                || e.kind != EdgeKind::Fallthrough
                    && e.delay_slot != DelaySlot::None
                    && e.site
                        .pc
                        .0
                        .checked_add(4)
                        .and_then(|a| image.word(GuestAddr(a)))
                        == Some(compare))
    };
    if bypass.iter().any(|&(lo, hi)| {
        map.jumped_in(here, generation, lo, hi)
            || map
                .edges_in(here, generation, lo, hi)
                .any(|candidate| !rebounds(candidate))
    }) {
        return None;
    }

    if compare >> 26 != 11 || field(compare, 21) != index {
        return None;
    } // SLTIU
    let count = u32::from(compare as u16);
    if count == 0 || count > MAX_ENTRIES {
        return None;
    }
    let guarded = matches!(branch >> 26, 4 | 20) && edge.kind == EdgeKind::Fallthrough
        || matches!(branch >> 26, 5 | 21) && edge.kind == EdgeKind::Branch;
    if !guarded {
        return None;
    }
    let mut prefix = Vec::new();
    prefix.extend(compare.to_be_bytes());
    for word in interval.iter().rev() {
        prefix.extend(word.to_be_bytes());
    }
    prefix.extend(branch.to_be_bytes());
    if edge.delay_slot != DelaySlot::None && !in_slot {
        let ds = GuestAddr(edge.site.pc.0.checked_add(4)?);
        let slot = image.word(ds)?;
        let instruction = decode(slot, ds);
        if !instruction.is_valid()
            || instruction.has_delay_slot()
            || instruction.is_trap()
            || matches!(instruction.opcode_name(), "syscall" | "break" | "eret")
            || instruction.destination_gpr() == Some(u32::from(index))
        {
            return None;
        }
        prefix.extend(slot.to_be_bytes());
    }
    let mut values = [None; 32];
    values[0] = Some(0);
    // Before the scale, the index must survive; after it, the scaled index.
    let (end, kept) = if in_slot {
        (add_pc, scale)
    } else {
        (shift_pc, index)
    };
    let mut current = block.start.pc;
    while current.0 < end.0 {
        let word = image.word(current)?;
        let instruction = decode(word, current);
        if !instruction.is_valid()
            || instruction.has_delay_slot()
            || instruction.is_trap()
            || instruction.destination_gpr() == Some(u32::from(kept))
        {
            return None;
        }
        transfer(word, current, &mut values);
        prefix.extend(word.to_be_bytes());
        current = GuestAddr(current.0.checked_add(4)?);
    }
    // Between the scale and the add, the scaled index must survive.
    let mut between = Vec::new();
    if !in_slot {
        transfer(shift, shift_pc, &mut values);
        let mut current = GuestAddr(shift_pc.0.checked_add(4)?);
        while current.0 < add_pc.0 {
            let word = image.word(current)?;
            let instruction = decode(word, current);
            if !instruction.is_valid()
                || instruction.has_delay_slot()
                || instruction.is_trap()
                || instruction.destination_gpr() == Some(u32::from(scale))
            {
                return None;
            }
            transfer(word, current, &mut values);
            between.push(word);
            current = GuestAddr(current.0.checked_add(4)?);
        }
    }
    let value = values[base as usize]?;
    let low = value as u32;
    if value != u64::from(low) && value != signed_word(low) {
        return None;
    }
    let table_start = GuestAddr(low.wrapping_add_signed(i32::from(load as i16)));
    if !table_start.0.is_multiple_of(4)
        || u64::from(table_start.0) + u64::from(count) * 4 > 1u64 << 32
    {
        return None;
    }
    for word in std::iter::once(shift)
        .chain(between)
        .chain([add, load])
        .chain(delay_nop.then_some(0))
        .chain([jump])
    {
        prefix.extend(word.to_be_bytes());
    }
    Some(TableEvidence {
        site: site.site.clone(),
        load_pc,
        guard_pc: edge.site.pc,
        index_register: index,
        table_start,
        count,
        prefix_sha256: sha256(&prefix),
        snapshot_sha256: None,
        assumptions: [
            "recognized scalar guard pattern suggests this dispatch index bound",
            "table snapshot is not proven immutable during execution",
        ],
    })
}

/// What one dispatch path must still establish, walking backwards from the
/// table add (ADR-0180).
#[derive(Clone)]
struct Need {
    /// Register that must hold `index << 2`, until its SLL is found.
    scaled: Option<u8>,
    /// The shifted register, once the SLL is found.
    index: Option<u8>,
    /// Register that must be a LUI-built constant, until its LUI is found.
    base: Option<u8>,
    /// ADDIU immediates applied after that LUI.
    base_low: u32,
    base_value: Option<u32>,
    /// Flags of conditional branches passed: (flag, branch selects in range, pc).
    flags: Vec<(u8, bool, u32)>,
    /// The guard's SLTIU: (register, count, branch pc).
    bound: Option<(u8, u32, u32)>,
    /// Whether an ANDI mask may bound the index: a `switch` dispatch (`jr`),
    /// whose table GCC fills over the whole masked range; a C array called
    /// through `jalr` may be shorter than its mask.
    masks: bool,
}

impl Need {
    fn done(&self) -> bool {
        self.scaled.is_none()
            && self.base.is_none()
            && matches!((self.index, self.bound), (Some(x), Some((r, _, _))) if x == r)
    }

    /// One instruction, walking backwards; None when the path cannot be proven.
    fn step(&mut self, pc: GuestAddr, word: u32) -> Option<()> {
        let instruction = decode(word, pc);
        if !instruction.is_valid()
            || instruction.has_delay_slot()
            || instruction.is_trap()
            || matches!(instruction.opcode_name(), "syscall" | "break" | "eret")
        {
            return None;
        }
        let Some(d) = instruction
            .destination_gpr()
            .map(|d| d as u8)
            .filter(|d| *d != 0)
        else {
            return Some(());
        };
        // Once the bound is known, the compared value must be the one shifted.
        if let (Some((r, _, _)), Some(_)) = (self.bound, self.scaled)
            && d == r
        {
            return None;
        }
        if Some(d) == self.scaled {
            if word >> 26 != 0 || word & 63 != 0 || (word >> 6) & 31 != 2 {
                return None;
            }
            let x = field(word, 16);
            if self.bound.is_some_and(|(r, _, _)| r != x) || x == 0 {
                return None;
            }
            self.scaled = None;
            self.index = Some(x);
            return Some(());
        }
        // `andi index, x, mask` bounds the index on this path (ADR-0183)
        if self.bound.is_none() && Some(d) == self.index {
            if word >> 26 != 12 || !self.masks {
                return None;
            }
            self.bound = Some((d, (word & 0xffff) + 1, pc.0));
            return Some(());
        }
        if Some(d) == self.base {
            match word >> 26 {
                15 => {
                    self.base_value = Some((word << 16).wrapping_add(self.base_low));
                    self.base = None;
                }
                9 if field(word, 21) == d => {
                    self.base_low = self.base_low.wrapping_add(i32::from(word as i16) as u32)
                }
                _ => return None,
            }
        }
        while let Some(i) = self.flags.iter().position(|(f, _, _)| *f == d) {
            let (_, in_range, guard) = self.flags.remove(i);
            if word >> 26 != 11 || self.bound.is_some() {
                continue; // not this dispatch's bound
            }
            let (r, count) = (field(word, 21), u32::from(word as u16));
            if self.index.is_some_and(|x| x != r) {
                continue;
            }
            if !in_range {
                return None; // this path dispatches when the index may be out of range
            }
            self.bound = Some((r, count, guard));
        }
        Some(())
    }
}

/// Jump tables whose GCC scheduling the shape in [`pattern`] does not
/// accept (ADR-0180): every CFG path into the dispatch must establish that
/// the add's operands are a LUI-built base and `index << 2`, after a branch
/// that selects the dispatch only when `sltiu flag, index, count` is set,
/// with the index unchanged between the compare and the shift, or an ANDI
/// mask that defines the index before its shift. Paths are
/// followed through each edge's delay slot only when that edge executes it.
/// Entries into the walked instructions, entry points, calls, returns,
/// loops and paths that disagree fail closed.
fn guarded(map: &MapIndex, image: &CodeImage, site: &IndirectSite) -> Option<TableEvidence> {
    if site.site.image != image.base.image || site.site.generation != image.base.generation {
        return None;
    }
    let pc = site.site.pc;
    let jump = image.word(pc)?;
    if jump >> 26 != 0 || !matches!(jump & 63, 8 | 9) {
        return None;
    }
    let delay_nop = image.word(GuestAddr(pc.0.checked_sub(4)?))? == 0;
    let load_pc = GuestAddr(pc.0.checked_sub(if delay_nop { 8 } else { 4 })?);
    let load = image.word(load_pc)?;
    let add_pc = GuestAddr(load_pc.0.checked_sub(4)?);
    let add = image.word(add_pc)?;
    if load >> 26 != 35
        || field(load, 16) != field(jump, 21)
        || add >> 26 != 0
        || add & 63 != 33
        || field(add, 11) != field(load, 21)
    {
        return None;
    }
    let (a, b) = (field(add, 21), field(add, 16));
    if a == 0 || b == 0 || a == b {
        return None;
    }
    let mut proven = None;
    for (scaled, base) in [(a, b), (b, a)] {
        let need = Need {
            scaled: Some(scaled),
            index: None,
            base: Some(base),
            base_low: 0,
            base_value: None,
            flags: Vec::new(),
            bound: None,
            masks: jump & 63 == 8,
        };
        let mut walk = Walk {
            map,
            image,
            steps: 0,
            seen: BTreeMap::new(),
            results: BTreeSet::new(),
        };
        if walk.block(pc, add_pc, need, &mut Vec::new()).is_some() {
            if proven.is_some() {
                return None;
            }
            proven = Some(walk);
        }
    }
    let walk = proven?;
    let mut tables = walk
        .results
        .iter()
        .map(|(start, count, _, _)| (*start, *count));
    let (base_value, count) = tables.next()?;
    if tables.any(|t| t != (base_value, count)) || count == 0 || count > MAX_ENTRIES {
        return None;
    }
    let (_, _, guard_pc, index) = *walk.results.iter().next()?;
    let table_start = GuestAddr(base_value.wrapping_add_signed(i32::from(load as i16)));
    if !table_start.0.is_multiple_of(4)
        || u64::from(table_start.0) + u64::from(count) * 4 > 1u64 << 32
    {
        return None;
    }
    let mut prefix = Vec::new();
    for (at, word) in
        walk.seen
            .iter()
            .chain([(&add_pc.0, &add), (&load_pc.0, &load), (&pc.0, &jump)])
    {
        prefix.extend(at.to_be_bytes());
        prefix.extend(word.to_be_bytes());
    }
    Some(TableEvidence {
        site: site.site.clone(),
        load_pc,
        guard_pc: GuestAddr(guard_pc),
        index_register: index,
        table_start,
        count,
        prefix_sha256: sha256(&prefix),
        snapshot_sha256: None,
        assumptions: [
            "every CFG path into the dispatch bounds its index (ADR-0180)",
            "table snapshot is not proven immutable during execution",
        ],
    })
}

/// The backward path search of [`guarded`].
struct Walk<'m, 'a> {
    map: &'m MapIndex<'a>,
    image: &'m CodeImage,
    steps: usize,
    /// Every instruction word the proof read, by pc.
    seen: BTreeMap<u32, u32>,
    /// Per proven path: (base value, count, guard branch pc, index register).
    results: BTreeSet<(u32, u32, u32, u8)>,
}

impl Walk<'_, '_> {
    fn word(&mut self, pc: u32) -> Option<u32> {
        self.steps += 1;
        if self.steps > 4096 {
            return None;
        }
        let word = self.image.word(GuestAddr(pc))?;
        self.seen.insert(pc, word);
        Some(word)
    }

    /// Walk back from `end` (exclusive) to the start of the block holding
    /// `anchor`, then into every predecessor; `path` holds the block starts
    /// on this path. Nothing may enter between that start and `anchor`
    /// (inclusive): such an entry would skip what the walk relies on.
    fn block(
        &mut self,
        anchor: GuestAddr,
        end: GuestAddr,
        mut need: Need,
        path: &mut Vec<u32>,
    ) -> Option<()> {
        let (here, generation) = (self.image.base.image.as_str(), self.image.base.generation);
        let address = self.image.address(anchor);
        let start = self
            .map
            .containing(&address)
            .into_iter()
            .filter(|b| !b.delay_slot_entry)
            .map(|b| b.start.pc)
            .max()?;
        if path.contains(&start.0) || path.len() >= 16 {
            return None;
        }
        if self.entered(start.0 + 1, anchor.0 + 4) {
            return None;
        }
        let mut at = end.0;
        while at > start.0 {
            at -= 4;
            let word = self.word(at)?;
            need.step(GuestAddr(at), word)?;
            if need.done() {
                return self.finish(&need);
            }
        }
        let entry = self.image.address(start);
        if self.map.jumped_to(&entry) {
            return None;
        }
        let edges = self.map.edges_to(&entry);
        if edges.is_empty() {
            return None;
        }
        path.push(start.0);
        for edge in edges {
            if edge.site.image != here
                || edge.site.generation != generation
                || !matches!(
                    edge.kind,
                    EdgeKind::Branch | EdgeKind::Jump | EdgeKind::Fallthrough
                )
            {
                return None;
            }
            let mut need = need.clone();
            let site = edge.site.pc.0;
            let word = self.word(site)?;
            if !decode(word, edge.site.pc).has_delay_slot() {
                // plain fallthrough: the site is the predecessor's last word
                if edge.kind != EdgeKind::Fallthrough || site.checked_add(4) != Some(start.0) {
                    return None;
                }
                self.block(edge.site.pc, GuestAddr(site + 4), need, path)?;
                continue;
            }
            // entering at the delay slot runs it and falls through without the
            // branch: that bypasses the guard only into the fallthrough
            if edge.kind == EdgeKind::Fallthrough && self.entered(site + 4, site + 8) {
                return None;
            }
            if edge.delay_slot != DelaySlot::None {
                let slot = self.word(site + 4)?;
                need.step(GuestAddr(site + 4), slot)?;
            }
            if need.done() {
                self.finish(&need)?;
                continue;
            }
            let op = word >> 26;
            match op {
                4 | 5 | 20 | 21 => {
                    let (s, t) = (field(word, 21), field(word, 16));
                    if (s == 0) != (t == 0) && need.bound.is_none() {
                        let in_range = matches!(op, 4 | 20) && edge.kind == EdgeKind::Fallthrough
                            || matches!(op, 5 | 21) && edge.kind == EdgeKind::Branch;
                        need.flags.push((s.max(t), in_range, site));
                    }
                }
                // non-linking compares against zero, J and COP1 branches
                1 if field(word, 16) < 4 => {}
                2 | 6 | 7 | 22 | 23 | 17 => {}
                _ => return None,
            }
            self.block(edge.site.pc, GuestAddr(site), need, path)?;
        }
        path.pop();
        Some(())
    }

    /// Whether control can enter at a word in `lo..hi` other than by
    /// running the word before it.
    fn entered(&self, lo: u32, hi: u32) -> bool {
        let (here, generation) = (self.image.base.image.as_str(), self.image.base.generation);
        lo + 3 < hi
            && (self.map.jumped_in(here, generation, lo, hi - 4)
                || self
                    .map
                    .edges_in(here, generation, lo, hi - 4)
                    .next()
                    .is_some())
    }

    fn finish(&mut self, need: &Need) -> Option<()> {
        let (index, count, guard) = need.bound?;
        self.results.insert((need.base_value?, count, guard, index));
        Some(())
    }
}

pub const PRODUCER: &str = "plaid-pointer-table-candidates/v0";

/// The recognized table, its snapshot words and the evidence detail.
fn evidence(
    index: &MapIndex,
    image: &CodeImage,
    site: &IndirectSite,
) -> Option<(TableEvidence, Option<Vec<u32>>, String)> {
    let mut table = pattern(index, image, site).or_else(|| guarded(index, image, site))?;
    // a slot alternate's table is read from its placed copy (ADR-0185)
    table.table_start = GuestAddr(image.slot_view(site.site.pc, table.table_start.0));
    let words: Option<Vec<_>> = (0..table.count)
        .map(|n| image.word(GuestAddr(table.table_start.0 + n * 4)))
        .collect();
    if let Some(words) = &words {
        table.snapshot_sha256 = Some(sha256(
            &words
                .iter()
                .flat_map(|word| word.to_be_bytes())
                .collect::<Vec<_>>(),
        ));
    }
    let detail = serde_json::to_string(&table).ok()?;
    Some((table, words, detail))
}

/// A table proof closes a site only when it is recomputed from the current CFG
/// and bytes, its snapshot is complete and aligned, and the candidates are
/// exactly the snapshot targets. Whether the table may be treated as
/// immutable is a scope decision (ADR-0132), not part of this check.
pub fn verify(map: &ProgramMap, image: &CodeImage, site: &IndirectSite) -> bool {
    verify_in(&MapIndex::new(map), map, image, site)
}

/// [`verify`] with the map's index built once by the caller.
pub fn verify_in(
    index: &MapIndex,
    map: &ProgramMap,
    image: &CodeImage,
    site: &IndirectSite,
) -> bool {
    let Some(e) = site
        .closed_proof
        .as_ref()
        .and_then(|id| map.evidence.get(id))
    else {
        return false;
    };
    if e.kind != EvidenceKind::Static
        || e.producer != PRODUCER
        || site.link_register.is_some()
        || site.delay_slot != DelaySlot::Always
    {
        return false;
    }
    let Some((_, Some(words), detail)) = evidence(index, image, site) else {
        return false;
    };
    let targets: std::collections::BTreeSet<_> = words
        .iter()
        .map(|w| image.address(GuestAddr(image.slot_view(site.site.pc, *w))))
        .collect();
    detail == e.detail
        && words.iter().all(|w| w.is_multiple_of(4))
        && site
            .candidates
            .keys()
            .cloned()
            .collect::<std::collections::BTreeSet<_>>()
            == targets
        && site.observed.keys().all(|a| targets.contains(a))
}

/// Guest bytes of a verified table, as (start, entry count).
pub fn table_range(
    index: &MapIndex,
    map: &ProgramMap,
    image: &CodeImage,
    site: &IndirectSite,
) -> Option<(GuestAddr, u32)> {
    if !verify_in(index, map, image, site) {
        return None;
    }
    let (table, _, _) = evidence(index, image, site)?;
    Some((table.table_start, table.count))
}

pub(crate) fn analyze(map: &ProgramMap, image: &CodeImage) -> Result<ProgramMap, String> {
    let mut out = map.clone();
    let index = MapIndex::new(map);
    for old in &map.indirect_sites {
        let Some((table, words, detail)) = evidence(&index, image, old) else {
            continue;
        };
        let id = format!("table-candidates:{}", sha256(detail.as_bytes()));
        out.evidence.insert(
            id.clone(),
            Evidence {
                kind: EvidenceKind::Static,
                producer: PRODUCER.into(),
                revision: "0".into(),
                detail,
            },
        );
        let refs: EvidenceRefs = [id.clone()].into();
        if let Some(words) = words {
            let mut site = old.clone();
            out.indirect_sites.remove(old);
            let fresh = site.candidates.is_empty() && site.closed_proof.is_none();
            let aligned = words.iter().all(|w| w.is_multiple_of(4));
            for (n, target) in words.into_iter().enumerate() {
                if target.is_multiple_of(4) {
                    site.candidates
                        .entry(image.address(GuestAddr(image.slot_view(old.site.pc, target))))
                        .or_default()
                        .insert(id.clone());
                } else {
                    out.unresolved.insert(Unresolved {
                        kind: "invalid_pointer_table_entry".into(),
                        site: Some(old.site.clone()),
                        detail: format!(
                            "unaligned snapshot pointer {target:08x} at table index {n}"
                        ),
                        evidence: refs.clone(),
                    });
                }
            }
            // Closing is only a claim; `verify` rechecks it and only the
            // guarded scope accepts it.
            if (fresh || site.closed_proof.as_deref() == Some(id.as_str()))
                && aligned
                && site.link_register.is_none()
                && site
                    .observed
                    .keys()
                    .all(|a| site.candidates.contains_key(a))
            {
                site.closed_proof = Some(id.clone());
            }
            out.indirect_sites.insert(site);
            out.unresolved.insert(Unresolved {
                kind: "pointer_table_immutability_unproven".into(),
                site: Some(old.site.clone()),
                detail: "bounded snapshot candidates do not prove table contents or exhaustive runtime targets".into(),
                evidence: refs.clone(),
            });
            out.unresolved.insert(Unresolved {
                kind: "pointer_table_target_identity_unproven".into(),
                site: Some(old.site.clone()),
                detail: "numeric table targets do not prove target image/generation, mapping context, cache-resident generation or executable lifetime".into(),
                evidence: refs,
            });
        } else {
            out.unresolved.insert(Unresolved {
                kind: "pointer_table_source_missing".into(),
                site: Some(old.site.clone()),
                detail: format!(
                    "{} entries at {:?} lack a complete supplied memory snapshot",
                    table.count, table.table_start
                ),
                evidence: refs,
            });
        }
    }
    out.validate()?;
    Ok(out)
}
