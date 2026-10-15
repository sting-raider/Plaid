//! Runtime callbacks (ADR-0130): guest code pointers passed to declared
//! runtime functions, such as a thread entry given to `osCreateThread`.
//!
//! A declaration names the argument registers that carry guest code. At each
//! call or tail jump into the runtime function, the register's value after the
//! delay slot must be a constant proven by the same straight-line prefix rule
//! as local indirect targets. Proven targets are functions the runtime enters;
//! anything unproven stays a blocker.
//!
//! A wrapper may forward its own argument to the runtime (ADR-0149), as
//! SM64's `create_thread` does through an IDO `-O0` stack spill. The targets
//! are then the values every direct caller passes, provided nothing else can
//! enter the wrapper.
use crate::{
    GuestAddr,
    discovery::{CodeImage, decode},
    indirect::{code_pointer, prefix_state, transfer},
    program::*,
};
use std::collections::{BTreeMap, BTreeSet};

/// How many wrapper levels a forwarded callback may pass through.
const FORWARD_DEPTH: usize = 4;

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct Callback {
    /// The `jal`/`j` into the runtime function.
    pub site: CodeAddress,
    pub register: u8,
    /// `None` when the value is not proven.
    pub target: Option<CodeAddress>,
    /// The value reached the runtime through a wrapper's argument (ADR-0149).
    pub forwarded: bool,
}

/// Value of `register` when control reaches the callee of the direct transfer
/// at `site`, i.e. after its delay slot.
fn argument(map: &ProgramMap, image: &CodeImage, site: &CodeAddress, register: u8) -> Option<u32> {
    let (_, mut state, _) = prefix_state(map, image, site)?;
    let word = image.word(site.pc)?;
    if !matches!(word >> 26, 2 | 3) {
        return None;
    }
    let slot_pc = GuestAddr(site.pc.0.checked_add(4)?);
    let slot = image.word(slot_pc)?;
    let i = decode(slot, slot_pc);
    if !i.is_valid() || i.has_delay_slot() || i.is_trap() {
        return None;
    }
    transfer(slot, slot_pc, &mut state);
    code_pointer(state[usize::from(register)]?)
}

/// The incoming argument register that `register` still holds after the
/// delay slot of the direct transfer at `site`, when the site's straight-line
/// prefix starts at the function entry. The pass tracks `a0..a3` through
/// moves and word spills to `$sp` slots. A store through any other base is
/// assumed not to write those slots, which C's object rules give for an IDO
/// argument home; the solver records that assumption.
fn forwarded(map: &ProgramMap, image: &CodeImage, site: &CodeAddress, register: u8) -> Option<u8> {
    let (_, _, prefix) = prefix_state(map, image, site)?;
    let slot_pc = GuestAddr(site.pc.0.checked_add(4)?);
    let slot = image.word(slot_pc)?;
    let i = decode(slot, slot_pc);
    if !i.is_valid() || i.has_delay_slot() || i.is_trap() {
        return None;
    }
    let mut words: Vec<u32> = prefix
        .as_chunks::<4>()
        .0
        .iter()
        .map(|w| u32::from_be_bytes(*w))
        .collect();
    words.pop(); // the transfer itself
    words.push(slot);
    let mut regs: [Option<u8>; 32] = [None; 32];
    for r in 4..=7 {
        regs[r as usize] = Some(r);
    }
    let mut sp: Option<i64> = Some(0);
    let mut slots: BTreeMap<i64, Option<u8>> = BTreeMap::new();
    for word in words {
        let (op, rs, rt) = (word >> 26, (word >> 21) & 31, ((word >> 16) & 31) as usize);
        let offset = i64::from(word as i16);
        let store = matches!(op, 40..=46 | 56 | 57 | 60 | 61 | 63);
        let load = matches!(op, 26 | 27 | 32..=39 | 48 | 49 | 52 | 53 | 55);
        if op == 9 && rs == 29 && rt == 29 {
            sp = sp.map(|d| d + offset);
            continue;
        }
        if store && rs == 29 {
            // a word spill records its value; any other width clobbers
            match sp {
                Some(d) => {
                    let reach = if op == 43 { 4 } else { 8 };
                    slots.retain(|k, _| (k - (d + offset)).abs() >= reach);
                    if op == 43 {
                        slots.insert(d + offset, regs[rt]);
                    }
                }
                None => slots.clear(),
            }
        } else if !load && (rs == 29 || (op == 0 && rt == 29)) {
            // the frame address escapes into another register
            sp = None;
            slots.clear();
        }
        if store && !matches!(op, 56 | 60) {
            continue;
        }
        let dest = decode(word, GuestAddr(0)).destination_gpr();
        let value = match (op, word & 63) {
            (35, _) if rs == 29 => sp.and_then(|d| slots.get(&(d + offset)).copied().flatten()),
            (0, 33 | 37 | 45) if rt == 0 => regs[rs as usize],
            (0, 33 | 37 | 45) if rs == 0 => regs[rt],
            _ => None,
        };
        if let Some(r) = dest {
            if r == 29 {
                sp = None;
                slots.clear();
            }
            regs[r as usize] = value;
        }
        regs[0] = None;
    }
    regs[usize::from(register)]
}

/// Values of `register` at the runtime transfer `site`: the proven constant,
/// or, when a wrapper forwards its argument, what each of its callers passes.
fn values(
    map: &ProgramMap,
    image: &CodeImage,
    site: &CodeAddress,
    register: u8,
    depth: usize,
    wrappers: &mut BTreeSet<CodeAddress>,
    out: &mut BTreeSet<Callback>,
) {
    let constant = argument(map, image, site, register).map(|pc| image.address(GuestAddr(pc)));
    if constant.is_none()
        && depth > 0
        && let Some(r) = forwarded(map, image, site, register)
        && let Some((entry, callers)) = closed_callers(map, image, site)
    {
        wrappers.insert(entry);
        for caller in callers {
            values(map, image, &caller, r, depth - 1, wrappers, out);
        }
        return;
    }
    out.insert(Callback {
        site: site.clone(),
        register,
        target: constant,
        forwarded: depth < FORWARD_DEPTH,
    });
}

/// The direct call and jump sites into the function whose entry block holds
/// `site`, when those are the only ways in: the entry is no program entry,
/// indirect candidate, observation or runtime callback target.
fn closed_callers(
    map: &ProgramMap,
    image: &CodeImage,
    site: &CodeAddress,
) -> Option<(CodeAddress, Vec<CodeAddress>)> {
    let (entry, _, _) = prefix_state(map, image, site)?;
    let callers: Vec<_> = map
        .direct_edges
        .iter()
        .filter(|e| e.target == entry && matches!(e.kind, EdgeKind::Call | EdgeKind::Jump))
        .map(|e| e.site.clone())
        .collect();
    let other_way_in = map.entries.contains_key(&entry)
        || map
            .direct_edges
            .iter()
            .any(|e| e.target == entry && !matches!(e.kind, EdgeKind::Call | EdgeKind::Jump))
        || map
            .indirect_sites
            .iter()
            .any(|s| s.candidates.contains_key(&entry) || s.observed.contains_key(&entry));
    (!callers.is_empty() && !other_way_in).then_some((entry, callers))
}

/// Every callback argument at every call or tail jump into a runtime function.
pub fn callbacks(map: &ProgramMap, image: &CodeImage) -> BTreeSet<Callback> {
    let mut out = BTreeSet::new();
    let mut wrappers = BTreeSet::new();
    for edge in &map.direct_edges {
        let Some(f) = map.runtime_functions.get(&edge.target) else {
            continue;
        };
        if !matches!(edge.kind, EdgeKind::Call | EdgeKind::Jump)
            || edge.site.image != image.base.image
            || edge.site.generation != image.base.generation
        {
            continue;
        }
        for &register in &f.callbacks {
            values(
                map,
                image,
                &edge.site,
                register,
                FORWARD_DEPTH,
                &mut wrappers,
                &mut out,
            );
        }
    }
    // A wrapper the runtime also enters receives unknown arguments, so what
    // its callers pass is not every value it forwards.
    let entered: BTreeSet<_> = out.iter().filter_map(|c| c.target.clone()).collect();
    if wrappers.iter().any(|w| entered.contains(w)) {
        return out
            .into_iter()
            .map(|mut c| {
                if c.forwarded {
                    c.target = None;
                }
                c
            })
            .collect();
    }
    out
}

/// Proven callback targets: functions the runtime may enter.
pub fn targets(map: &ProgramMap, image: &CodeImage) -> BTreeSet<CodeAddress> {
    callbacks(map, image)
        .into_iter()
        .filter_map(|c| c.target)
        .collect()
}
