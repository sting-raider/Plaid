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
use std::collections::{BTreeMap, BTreeSet, btree_map::Entry};

// a switch over a few hundred cases is ordinary compiler output (ADR-0183)
const MAX_ENTRIES: u32 = 1024;
// Bound recursion separately from the shared instruction-read budget.
const MAX_PATH_FRAMES: usize = 32;

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
    /// Completed paths can seed discovery when another path defeats closure.
    #[serde(skip_serializing_if = "std::ops::Not::not")]
    incomplete_paths: bool,
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
        incomplete_paths: false,
        assumptions: [
            "recognized scalar guard pattern suggests this dispatch index bound",
            "table snapshot is not proven immutable during execution",
        ],
    })
}

/// What one dispatch path must still establish, walking backwards from the
/// table load (ADR-0180, ADR-0206).
#[derive(Clone, PartialEq, Eq)]
struct Need {
    /// Register holding the address used by the dispatch load.
    address: Option<u8>,
    /// The `addu` operands once the address definition is found.
    operands: Option<(u8, u8)>,
    /// Register that must hold `index << 2`, until its SLL is found.
    scaled: Option<u8>,
    /// A byte offset and guarded index may advance as separate loop variables.
    relation: Option<crate::affine_word::AffineWord>,
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
    /// Constants still required at earlier definitions, by GPR.
    constants: BTreeMap<u8, u32>,
    /// Exact word cell awaiting its defining SW, relative to unchanged SP.
    stack_pointer: Option<i16>,
    /// The reload must belong to a frame allocated on every incoming path.
    frame_bytes: Option<u32>,
}

impl Need {
    /// Values still needed before this point; a matched captured index/bound
    /// has already been discharged. Induction still compares the complete Need.
    fn pending_registers(&self) -> BTreeSet<u8> {
        let mut registers: BTreeSet<_> = self.constants.keys().copied().collect();
        registers.extend(self.address);
        registers.extend(self.scaled);
        registers.extend(self.base);
        if let Some(relation) = &self.relation {
            registers.extend(relation.registers());
        }
        if let Some((a, b)) = self.operands {
            registers.extend([a, b]);
        }
        if self.bound.is_none() {
            registers.extend(self.index);
        }
        if self.index.is_none() && self.relation.is_none() {
            registers.extend(self.bound.map(|(r, _, _)| r));
        }
        registers.extend(self.flags.iter().map(|(r, _, _)| *r));
        registers
    }

    fn done(&self) -> bool {
        self.stack_pointer.is_none()
            && self.frame_bytes.is_none()
            && self.address.is_none()
            && self.operands.is_none()
            && self.scaled.is_none()
            && self.relation.is_none()
            && self.base.is_none()
            && self.constants.is_empty()
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
        // Until the defining SW, reject every other store: even a different
        // virtual address or stack offset could alias under a guest mapping.
        if let Some(offset) = self.stack_pointer {
            if word >> 26 == 43 && field(word, 21) == 29 && word as i16 == offset {
                let source = field(word, 16);
                if matches!(source, 0 | 29) {
                    return None;
                }
                self.address = Some(source);
                self.stack_pointer = None;
            } else if matches!(word >> 26, 16 | 40..=47 | 56..=63) {
                return None;
            }
        }
        if self.frame_bytes.is_some() && instruction.destination_gpr() == Some(29) {
            let allocation = -i32::from(word as i16);
            if self.stack_pointer.is_some()
                || word >> 26 != 9
                || field(word, 21) != 29
                || allocation <= 0
                || (allocation as u32) < self.frame_bytes?
            {
                return None;
            }
            self.frame_bytes = None;
            // Allocation also defines a GPR: retain its pointer arithmetic and
            // kill any prior SP branch flag through the ordinary transfer.
        }
        let Some(d) = instruction
            .destination_gpr()
            .map(|d| d as u8)
            .filter(|d| *d != 0)
        else {
            return Some(());
        };
        // Constant propagation consumes a definition. Until shared obligations
        // are modeled together, it must not hide a pointer/index definition.
        if self.constants.contains_key(&d)
            && (self.address == Some(d)
                || self.operands.is_some_and(|(a, b)| d == a || d == b)
                || self.scaled == Some(d)
                || self.base == Some(d)
                || self.index == Some(d)
                || self
                    .relation
                    .as_ref()
                    .is_some_and(|r| r.registers().any(|r| r == d))
                || self.flags.iter().any(|(flag, _, _)| *flag == d))
        {
            return None;
        }
        if let Some(relation) = &mut self.relation {
            relation.step(pc, word, &mut self.constants)?;
            if relation.is_nonzero_constant() {
                return None;
            }
            if relation.is_zero() {
                self.index = Some(self.bound?.0);
                self.relation = None;
            }
        }
        // An affine goal carries the earlier index value through its terms.
        // Otherwise it must still survive unchanged until the SLL is found.
        if self.index.is_none()
            && self.relation.is_none()
            && self.bound.is_some_and(|(r, _, _)| r == d)
        {
            return None;
        }
        // Early pointer/scale transfers also overwrite any older flag value.
        // Only SLTIU below can discharge a flag as a matching range guard.
        if word >> 26 != 11 {
            self.flags.retain(|(flag, _, _)| *flag != d);
        }
        if Some(d) == self.address {
            if word >> 26 == 35 && field(word, 21) == 29 {
                let offset = word as i16;
                if offset < 0
                    || offset % 4 != 0
                    || self.frame_bytes.is_some()
                    || self.pending_registers().contains(&29)
                {
                    return None;
                }
                // ADDU below must still prove the restored pointer. This does
                // not claim that SW/LW preserve an arbitrary 64-bit GPR.
                self.address = None;
                self.stack_pointer = Some(offset);
                self.frame_bytes = Some(offset as u32 + 4);
                return Some(());
            }
            if word >> 26 != 0 || word & 63 != 33 {
                return None;
            }
            let (a, b) = (field(word, 21), field(word, 16));
            if a == 0 || b == 0 || a == b {
                return None;
            }
            self.address = None;
            self.operands = Some((a, b));
            return Some(());
        }
        if let Some(required) = self.constants.remove(&d) {
            let mut require = |register: u8, value: u32| -> Option<()> {
                if register == 0 {
                    (value == 0).then_some(())
                } else if self.constants.insert(register, value).is_some() {
                    None
                } else {
                    Some(())
                }
            };
            match word >> 26 {
                // ADDIU is invertible modulo 2^32.
                9 => {
                    let source = field(word, 21);
                    let before = required.wrapping_sub(i32::from(word as i16) as u32);
                    require(source, before)?;
                }
                // ORI/XORI with zero as one source are exact constant loads;
                // with zero immediate they preserve the other source.
                13 | 14 => {
                    let source = field(word, 21);
                    let immediate = word as u16 as u32;
                    if source == 0 {
                        if immediate != required {
                            return None;
                        }
                    } else if immediate == 0 {
                        require(source, required)?;
                    } else {
                        return None;
                    }
                }
                15 => {
                    if (word & 0xffff) << 16 != required {
                        return None;
                    }
                }
                0 => match word & 63 {
                    // ADDU/OR with a zero operand preserve the other source.
                    33 | 37 => {
                        let (a, b) = (field(word, 21), field(word, 16));
                        let source = if a == 0 {
                            b
                        } else if b == 0 {
                            a
                        } else {
                            return None;
                        };
                        require(source, required)?;
                    }
                    _ => return None,
                },
                _ => return None,
            }
            return Some(());
        }
        if let Some((a, b)) = self.operands
            && (d == a || d == b)
            && self.scaled.is_none()
            && self.base.is_none()
            && self.index.is_none()
        {
            let other = if d == a { b } else { a };
            if word >> 26 == 0 && word & 63 == 0 && (word >> 6) & 31 == 2 {
                let index = field(word, 16);
                if index == other || index == 0 {
                    return None;
                }
                self.scaled = Some(d);
                self.base = Some(other);
                self.operands = None;
            } else if word >> 26 == 0 && word & 63 == 4 {
                let (index, amount) = (field(word, 16), field(word, 21));
                if index == other
                    || index == 0
                    || amount == 0
                    || amount == d
                    || amount == index
                    || amount == other
                {
                    return None;
                }
                self.scaled = Some(d);
                self.base = Some(other);
                self.operands = None;
            } else if word >> 26 == 15 || word >> 26 == 9 && field(word, 21) == d {
                self.base = Some(d);
                self.scaled = Some(other);
                self.operands = None;
            } else {
                return None;
            }
        }
        if Some(d) == self.scaled {
            let immediate_shift =
                word >> 26 == 0 && word & 63 == 0 && field(word, 21) == 0 && (word >> 6) & 31 == 2;
            let variable_shift = word >> 26 == 0
                && word & 63 == 4
                && field(word, 21) != 0
                && field(word, 21) != d
                && field(word, 21) != field(word, 16)
                && self.constants.insert(field(word, 21), 2).is_none();
            if !immediate_shift && !variable_shift {
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
        if self.index.is_none()
            && let (Some(offset), Some((index, _, _))) = (self.scaled, self.bound)
        {
            self.relation = Some(crate::affine_word::AffineWord::scaled_index(offset, index));
            self.scaled = None;
        }
        Some(())
    }
}

struct DispatchLoad {
    pc: GuestAddr,
    word: u32,
    gap: Vec<(u32, u32)>,
}

/// Find the surviving LW definition without crossing a control transfer or
/// permitting an alternate entry between that definition and its use.
fn nearest_dispatch_load(
    map: &MapIndex,
    image: &CodeImage,
    pc: GuestAddr,
    jump: u32,
) -> Option<DispatchLoad> {
    let target_register = field(jump, 21);
    if target_register == 0 {
        return None;
    }
    let start = map
        .containing(&image.address(pc))
        .into_iter()
        .filter(|block| !block.delay_slot_entry)
        .map(|block| block.start.pc)
        .max()?;
    let mut at = pc.0.checked_sub(4)?;
    let mut gap = Vec::new();
    loop {
        if at < start.0 {
            return None;
        }
        let word = image.word(GuestAddr(at))?;
        let instruction = decode(word, GuestAddr(at));
        if !instruction.is_valid()
            || instruction.has_delay_slot()
            || instruction.is_trap()
            || matches!(instruction.opcode_name(), "syscall" | "break" | "eret")
        {
            return None;
        }
        if instruction.destination_gpr() == Some(u32::from(target_register)) {
            if word >> 26 != 35 || field(word, 16) != target_register {
                return None;
            }
            let lo = at.checked_add(4)?;
            let hi = pc.0.checked_add(4)?;
            if lo.checked_add(3)? < hi
                && (map.jumped_in(image.base.image.as_str(), image.base.generation, lo, hi - 4)
                    || map
                        .edges_in(image.base.image.as_str(), image.base.generation, lo, hi - 4)
                        .next()
                        .is_some())
            {
                return None;
            }
            gap.reverse();
            return Some(DispatchLoad {
                pc: GuestAddr(at),
                word,
                gap,
            });
        }
        gap.push((at, word));
        if at == start.0 {
            return None;
        }
        at = at.checked_sub(4)?;
    }
}

/// Recover the base, scaled index and matching guard over every predecessor
/// path, including scheduled pointer definitions before the guard. Edge delay
/// slots execute only where the CFG says they do. Unknown entries, calls,
/// unresolved cycles and paths that disagree fail closed.
fn guarded(map: &MapIndex, image: &CodeImage, site: &IndirectSite) -> Option<TableEvidence> {
    if site.site.image != image.base.image || site.site.generation != image.base.generation {
        return None;
    }
    let pc = site.site.pc;
    let jump = image.word(pc)?;
    if jump >> 26 != 0 || !matches!(jump & 63, 8 | 9) {
        return None;
    }
    let DispatchLoad {
        pc: load_pc,
        word: load,
        gap,
    } = nearest_dispatch_load(map, image, pc, jump)?;
    if field(load, 16) != field(jump, 21) {
        return None;
    }
    let need = Need {
        address: Some(field(load, 21)),
        operands: None,
        scaled: None,
        relation: None,
        index: None,
        base: None,
        base_low: 0,
        base_value: None,
        flags: Vec::new(),
        bound: None,
        masks: jump & 63 == 8,
        constants: BTreeMap::new(),
        stack_pointer: None,
        frame_bytes: None,
    };
    let mut walk = Walk {
        map,
        image,
        slot: image
            .slots
            .iter()
            .position(|(placed, _, _)| placed.contains(pc)),
        steps: 0,
        seen: BTreeMap::new(),
        bindings: BTreeMap::new(),
        results: BTreeSet::new(),
        effects: BTreeMap::new(),
        runtime: BTreeMap::new(),
    };
    // Retain completed witnesses even when another predecessor is unproven.
    // They remain hypotheses: only an exhaustive walk can certify closure.
    let incomplete_paths = walk.block(pc, load_pc, need, &mut Vec::new()).is_none();
    // Call arrays may contain nullable/optional entries; retain their existing
    // all-path behavior rather than proposing incomplete switch candidates.
    if incomplete_paths && site.link_register.is_some() {
        return None;
    }
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
    for (at, word) in walk.seen.iter() {
        prefix.extend(at.to_be_bytes());
        prefix.extend(word.to_be_bytes());
    }
    if !walk.bindings.is_empty() {
        prefix.extend(b"callee-bindings-v0");
        for (raw, (linked, placed, source)) in &walk.bindings {
            prefix.extend(raw.to_be_bytes());
            prefix.extend(linked.to_be_bytes());
            prefix.extend(placed.to_be_bytes());
            prefix.extend(source.to_be_bytes());
        }
    }
    if !walk.runtime.is_empty() {
        prefix.extend(b"runtime-register-effects-v0");
        prefix.extend(serde_json::to_vec(&walk.runtime).ok()?);
    }
    for (at, word) in std::iter::once((load_pc.0, load))
        .chain(gap)
        .chain(std::iter::once((pc.0, jump)))
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
        incomplete_paths,
        assumptions: [
            if incomplete_paths {
                "completed CFG paths suggest candidates; other paths remain unproven"
            } else {
                "every CFG path into the dispatch bounds its index (ADR-0180)"
            },
            "table snapshot is not proven immutable during execution",
        ],
    })
}

/// The backward path search of [`guarded`].
struct Walk<'m, 'a> {
    map: &'m MapIndex<'a>,
    image: &'m CodeImage,
    /// Pending pointer obligations cannot cross executable slot bindings.
    slot: Option<usize>,
    steps: usize,
    /// Every instruction word the proof read, by pc.
    seen: BTreeMap<u32, u32>,
    bindings: BTreeMap<u32, (u32, u32, u64)>,
    /// Per proven path: (base value, count, guard branch pc, index register).
    results: BTreeSet<(u32, u32, u32, u8)>,
    /// Map, image and caller slot are immutable within this walk. Cached effects
    /// retain their source words/bindings and are never shared with a verifier.
    effects: BTreeMap<(GuestAddr, u8), crate::callee_effects::NoWrite>,
    runtime: BTreeMap<u32, RuntimeFunction>,
}

struct WalkFrame {
    start: u32,
    anchor: u32,
    end: u32,
    need: Need,
}

impl Walk<'_, '_> {
    /// A fixed-text return may duplicate a slot call's continuation. Its exact
    /// source must still be covered by the callee effect proof below.
    fn incoming_jump(&mut self, pc: u32) -> Option<u32> {
        if self.slot.is_none()
            || self
                .image
                .slots
                .iter()
                .any(|(placed, _, _)| placed.contains(GuestAddr(pc)))
        {
            return self.word(pc);
        }
        self.steps += 1;
        if self.steps > 4096 {
            return None;
        }
        let word = self.image.instruction_word(GuestAddr(pc))?;
        if word != 0x03e0_0008 {
            return None;
        }
        self.seen.insert(pc, word);
        Some(word)
    }

    fn word(&mut self, pc: u32) -> Option<u32> {
        self.steps += 1;
        if self.steps > 4096 {
            return None;
        }
        if self
            .image
            .slots
            .iter()
            .position(|(placed, _, _)| placed.contains(GuestAddr(pc)))
            != self.slot
        {
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
        path: &mut Vec<WalkFrame>,
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
        let entry = self.image.address(start);
        if path.len() >= MAX_PATH_FRAMES {
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
        if self.map.external_entry(self.image, &entry) {
            return None;
        }
        if let Some(previous) = path
            .iter()
            .find(|frame| frame.start == start.0 && frame.anchor == anchor.0 && frame.end == end.0)
        {
            // Compare predicates at the block's start after processing every
            // instruction. Backedge-only branch flags may have been killed by
            // definitions in the block. All non-cycle paths still need a witness.
            return (need == previous.need).then_some(());
        }
        let edges = self.map.edges_to(&entry);
        let indirect = self.map.indirect_to(&entry);
        if edges.is_empty() && indirect.is_empty() {
            return None;
        }
        path.push(WalkFrame {
            start: start.0,
            anchor: anchor.0,
            end: end.0,
            need: need.clone(),
        });
        let mut returns = BTreeSet::new();
        for edge in indirect {
            if edge.site.image != here
                || edge.site.generation != generation
                || edge.link_register.is_some()
                || edge.delay_slot != DelaySlot::Always
            {
                return None;
            }
            let site = edge.site.pc;
            let jump = self.incoming_jump(site.0)?;
            // Checked returns duplicate the call's continuation edge. Require
            // each source to occur in a no-write callee proof below.
            if jump == 0x03e0_0008 {
                returns.insert(site.0);
                continue;
            }
            // Only a canonical non-return JR transfers unchanged register state.
            if jump & 0xfc1f_ffff != 8 || matches!(field(jump, 21), 0 | 31) {
                return None;
            }
            let mut incoming = need.clone();
            let slot = GuestAddr(site.0.checked_add(4)?);
            incoming.step(slot, self.word(slot.0)?)?;
            if incoming.done() {
                self.finish(&incoming)?;
            } else {
                self.block(site, site, incoming, path)?;
            }
        }
        for edge in edges {
            if edge.site.image != here || edge.site.generation != generation {
                return None;
            }
            let mut need = need.clone();
            let site = edge.site.pc.0;
            let word = self.word(site)?;
            if edge.kind == EdgeKind::ReturnContinuation {
                // Register-only effects cannot prove stack memory or SP lineage.
                if need.frame_bytes.is_some() {
                    return None;
                }
                let registers = need.pending_registers();
                if registers.is_empty() {
                    return None;
                }
                if word >> 26 != 3
                    || edge.delay_slot != DelaySlot::None
                    || site.checked_add(8) != Some(start.0)
                    || self.entered(site + 4, site + 8)
                {
                    return None;
                }
                let target = self.image.jump_target(edge.site.pc, word);
                for register in registers {
                    let key = (target, register);
                    if let Entry::Vacant(entry) = self.effects.entry(key) {
                        let budget = 4096usize.checked_sub(self.steps)?;
                        let effect = crate::callee_effects::no_gpr_write_bound(
                            self.map,
                            self.map.source(),
                            self.image,
                            target,
                            register,
                            budget,
                            self.slot,
                        )?;
                        self.steps += effect.reads;
                        entry.insert(effect);
                    }
                    let effect = &self.effects[&key];
                    returns.retain(|pc| !effect.returns.contains(pc));
                    self.bindings.extend(&effect.bindings);
                    self.runtime.extend(effect.runtime.clone());
                    self.seen.extend(&effect.words);
                }
                let slot = self.word(site + 4)?;
                need.step(GuestAddr(site + 4), slot)?;
                if need.done() {
                    self.finish(&need)?;
                } else {
                    self.block(edge.site.pc, GuestAddr(site), need, path)?;
                }
                continue;
            }
            if !matches!(
                edge.kind,
                EdgeKind::Branch | EdgeKind::Jump | EdgeKind::Fallthrough
            ) {
                return None;
            }
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
                        let flag = (s.max(t), in_range, site);
                        // No intervening definition survived the flag tracking:
                        // this edge cannot satisfy both zero and nonzero.
                        if need
                            .flags
                            .iter()
                            .any(|(r, truth, _)| *r == flag.0 && *truth != flag.1)
                        {
                            continue;
                        }
                        if !need.flags.contains(&flag) {
                            need.flags.push(flag);
                        }
                    }
                }
                // non-linking compares against zero, J and COP1 branches
                1 if field(word, 16) < 4 => {}
                2 | 6 | 7 | 22 | 23 | 17 => {}
                _ => return None,
            }
            self.block(edge.site.pc, GuestAddr(site), need, path)?;
        }
        if !returns.is_empty() {
            return None;
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
    // A scalar bound is not enough to identify the memory as a table. In
    // particular, a bounded load from a code address can look exactly like a
    // switch dispatch while the loaded words are executable instructions.
    // Such a range stays an ordinary unresolved indirect site; treating
    // instruction words as target pointers would add false roots and invalid
    // pointer-table blockers. Residual dispatch still checks its run-time
    // target against lowered entries.
    let table_end = table
        .table_start
        .0
        .checked_add(table.count.checked_mul(4)?)?;
    if index.source().blocks.iter().any(|block| {
        block.start.image == site.site.image
            && block.start.generation == site.site.generation
            && block.start.pc.0 < table_end
            && table.table_start.0 < block.start.pc.0.saturating_add(block.size)
    }) {
        return None;
    }
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
    let Some((table, Some(words), detail)) = evidence(index, image, site) else {
        return false;
    };
    if table.incomplete_paths {
        return false;
    }
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

fn overlaps_decoded_code(index: &MapIndex, site: &IndirectSite, evidence_id: &str) -> bool {
    let Some(evidence) = index.source().evidence.get(evidence_id) else {
        return false;
    };
    if evidence.producer != PRODUCER {
        return false;
    }
    let Ok(detail) = serde_json::from_str::<serde_json::Value>(&evidence.detail) else {
        return false;
    };
    let (Some(start), Some(count)) = (
        detail
            .get("table_start")
            .and_then(serde_json::Value::as_u64),
        detail.get("count").and_then(serde_json::Value::as_u64),
    ) else {
        return false;
    };
    let (Ok(start), Ok(count)) = (u32::try_from(start), u32::try_from(count)) else {
        return false;
    };
    let Some(end) = count
        .checked_mul(4)
        .and_then(|size| start.checked_add(size))
    else {
        return false;
    };
    index.source().blocks.iter().any(|block| {
        block.start.image == site.site.image
            && block.start.generation == site.site.generation
            && block.start.pc.0 < end
            && start < block.start.pc.0.saturating_add(block.size)
    })
}

pub(crate) fn analyze(map: &ProgramMap, image: &CodeImage) -> Result<ProgramMap, String> {
    let mut out = map.clone();
    let index = MapIndex::new(map);
    let sites: Vec<_> = map.indirect_sites.iter().collect();
    let found = crate::indirect::par_map(&sites, |old| evidence(&index, image, old));
    for (old, found) in sites.into_iter().zip(found) {
        let Some((table, words, detail)) = found else {
            // Candidate history survives ordinary proof revocation, but an
            // independently decoded instruction overlap disproves the old
            // interpretation of these bytes as pointer-table entries. Keep
            // its evidence record for audit while withdrawing those edges.
            let stale: BTreeSet<_> = old
                .candidates
                .values()
                .flatten()
                .filter(|id| overlaps_decoded_code(&index, old, id))
                .cloned()
                .collect();
            if stale.is_empty() {
                continue;
            }
            let mut site = old.clone();
            site.candidates.retain(|_, refs| {
                refs.retain(|id| !stale.contains(id));
                !refs.is_empty()
            });
            if site
                .closed_proof
                .as_ref()
                .is_some_and(|id| stale.contains(id))
            {
                site.closed_proof = None;
            }
            out.indirect_sites.remove(old);
            out.indirect_sites.insert(site);
            out.unresolved.retain(|item| {
                item.site.as_ref() != Some(&old.site)
                    || !item.evidence.iter().any(|id| stale.contains(id))
                    || !matches!(
                        item.kind.as_str(),
                        "invalid_pointer_table_entry"
                            | "pointer_table_immutability_unproven"
                            | "pointer_table_target_identity_unproven"
                            | "pointer_table_source_missing"
                    )
            });
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
            if !table.incomplete_paths
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
            // Candidate-only paths impose no table-immutability assumption:
            // their unresolved indirect site still requires residual dispatch.
            if !table.incomplete_paths {
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
            }
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
