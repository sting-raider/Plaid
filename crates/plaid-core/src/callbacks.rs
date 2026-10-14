//! Runtime callbacks (ADR-0130): guest code pointers passed to declared
//! runtime functions, such as a thread entry given to `osCreateThread`.
//!
//! A declaration names the argument registers that carry guest code. At each
//! call or tail jump into the runtime function, the register's value after the
//! delay slot must be a constant proven by the same straight-line prefix rule
//! as local indirect targets. Proven targets are functions the runtime enters;
//! anything unproven stays a blocker.
use crate::{
    GuestAddr,
    discovery::{CodeImage, decode},
    indirect::{code_pointer, prefix_state, transfer},
    program::*,
};
use std::collections::BTreeSet;

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct Callback {
    /// The `jal`/`j` into the runtime function.
    pub site: CodeAddress,
    pub register: u8,
    /// `None` when the value is not proven.
    pub target: Option<CodeAddress>,
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

/// Every callback argument at every call or tail jump into a runtime function.
pub fn callbacks(map: &ProgramMap, image: &CodeImage) -> BTreeSet<Callback> {
    let mut out = BTreeSet::new();
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
            out.insert(Callback {
                site: edge.site.clone(),
                register,
                target: argument(map, image, &edge.site, register)
                    .map(|pc| image.address(GuestAddr(pc))),
            });
        }
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
