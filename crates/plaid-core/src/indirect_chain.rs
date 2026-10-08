//! Restricted cross-block constant certificates. No joins, call summaries,
//! memory reads or loop invariants are assumed. Reconstruct CFG from bytes.
use crate::{
    GuestAddr,
    discovery::{CodeImage, decode, direct_cfg},
    indirect::{signed_word, transfer},
    program::*,
    rom::sha256,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

const MAX_WORDS: usize = 65_536;
const MAX_CHAIN: usize = 128;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct ChainCertificate {
    pub site: CodeAddress,
    pub target: CodeAddress,
    pub blocks: Vec<CodeAddress>,
    pub edges: Vec<ChainEdge>,
    pub words_sha256: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct ChainEdge {
    pub site: CodeAddress,
    pub target: CodeAddress,
    pub kind: EdgeKind,
    pub delay_slot: DelaySlot,
}

fn scalar(word: u32, pc: GuestAddr) -> bool {
    let i = decode(word, pc);
    i.is_valid()
        && matches!(
            i.opcode_name(),
            "lui"
                | "ori"
                | "andi"
                | "xori"
                | "addiu"
                | "daddiu"
                | "sll"
                | "srl"
                | "sra"
                | "addu"
                | "subu"
                | "and"
                | "or"
                | "xor"
                | "nor"
                | "daddu"
        )
}

fn plain_control(word: u32, pc: GuestAddr) -> bool {
    let i = decode(word, pc);
    i.is_valid()
        && !i.does_link()
        && matches!(
            i.opcode_name(),
            "j" | "beq"
                | "bne"
                | "blez"
                | "bgtz"
                | "beql"
                | "bnel"
                | "blezl"
                | "bgtzl"
                | "bltz"
                | "bgez"
                | "bltzl"
                | "bgezl"
        )
}

fn containing<'a>(map: &'a ProgramMap, address: &CodeAddress) -> Option<&'a BasicBlock> {
    let mut found = map.blocks.iter().filter(|block| {
        block.start.image == address.image
            && block.start.generation == address.generation
            && !block.delay_slot_entry
            && GuestRange {
                start: block.start.pc,
                size: block.size,
            }
            .contains(address.pc)
    });
    let block = found.next()?;
    if found.next().is_some() {
        None
    } else {
        Some(block)
    }
}

pub(crate) fn certificate(
    map: &ProgramMap,
    image: &CodeImage,
    site: &CodeAddress,
) -> Option<ChainCertificate> {
    if image.words.len() > MAX_WORDS
        || site.image != image.base.image
        || site.generation != image.base.generation
    {
        return None;
    }
    let in_image = |address: &&CodeAddress| {
        address.image == image.base.image && address.generation == image.base.generation
    };
    let mut roots: BTreeSet<_> = map
        .entries
        .keys()
        .filter(in_image)
        .map(|address| address.pc)
        .collect();
    // Unknown incoming indirect/cross-image transfers are boundaries, even if
    // their targets are finite candidates. Do not recursively assume proofs.
    roots.extend(
        map.indirect_sites
            .iter()
            .flat_map(|s| s.candidates.keys().chain(s.observed.keys()))
            .filter(in_image)
            .map(|address| address.pc),
    );
    roots.extend(
        map.direct_edges
            .iter()
            .filter(|e| {
                e.site.image != image.base.image || e.site.generation != image.base.generation
            })
            .map(|e| &e.target)
            .filter(in_image)
            .map(|address| address.pc),
    );
    if roots.is_empty() {
        return None;
    }
    let expected = direct_cfg(
        map.rom.clone(),
        image,
        &roots.iter().copied().collect::<Vec<_>>(),
        MAX_WORDS,
    )
    .ok()?
    .map;
    if expected
        .unresolved
        .iter()
        .any(|u| u.kind == "resource_limit")
    {
        return None;
    }
    let mut blocks = vec![containing(&expected, site)?.clone()];
    let mut edges = Vec::new();
    let mut visited: BTreeSet<_> = [blocks[0].start.clone()].into();
    loop {
        let current = blocks.last()?;
        if roots.contains(&current.start.pc) {
            break;
        }
        let incoming: Vec<_> = expected
            .direct_edges
            .iter()
            .filter(|e| e.target == current.start)
            .collect();
        if incoming.len() != 1 {
            break;
        }
        let edge = incoming[0];
        if !matches!(
            edge.kind,
            EdgeKind::Jump | EdgeKind::Branch | EdgeKind::Fallthrough
        ) {
            break;
        }
        let predecessor = containing(&expected, &edge.site)?;
        if !visited.insert(predecessor.start.clone()) || blocks.len() == MAX_CHAIN {
            return None;
        }
        blocks.push(predecessor.clone());
        edges.push(ChainEdge {
            site: edge.site.clone(),
            target: edge.target.clone(),
            kind: edge.kind,
            delay_slot: edge.delay_slot,
        });
    }
    if blocks.len() < 2 {
        return None;
    }
    // Contradictory map facts cannot serve as a second, different CFG. Missing
    // facts are rejected here as well as by the solver's general CFG check.
    for block in &blocks {
        if !map
            .blocks
            .iter()
            .any(|b| b.start == block.start && b.size == block.size && !b.delay_slot_entry)
        {
            return None;
        }
        for edge in map.direct_edges.iter().filter(|e| e.target == block.start) {
            if !expected.direct_edges.iter().any(|e| {
                e.site == edge.site
                    && e.target == edge.target
                    && e.kind == edge.kind
                    && e.delay_slot == edge.delay_slot
            }) {
                return None;
            }
        }
    }
    for edge in &edges {
        if !map.direct_edges.iter().any(|e| {
            e.site == edge.site
                && e.target == edge.target
                && e.kind == edge.kind
                && e.delay_slot == edge.delay_slot
        }) {
            return None;
        }
    }
    blocks.reverse();
    edges.reverse();
    let mut state = [None; 32];
    state[0] = Some(0);
    let mut bytes = Vec::new();
    for (n, block) in blocks.iter().enumerate() {
        let end = edges.get(n).map_or(site.pc, |edge| edge.site.pc);
        let mut pc = block.start.pc;
        loop {
            let word = image.word(pc)?;
            bytes.extend(word.to_be_bytes());
            if pc == end {
                if n == edges.len() {
                    let i = decode(word, pc);
                    if !matches!(i.opcode_name(), "jr" | "jalr") {
                        return None;
                    }
                    let target = state[i.get_rs() as usize]?;
                    let low = target as u32;
                    if !low.is_multiple_of(4)
                        || (target != u64::from(low) && target != signed_word(low))
                    {
                        return None;
                    }
                    return Some(ChainCertificate {
                        site: site.clone(),
                        target: image.address(GuestAddr(low)),
                        blocks: blocks.iter().map(|b| b.start.clone()).collect(),
                        edges,
                        words_sha256: sha256(&bytes),
                    });
                }
                let edge = &edges[n];
                let instruction = decode(word, pc);
                if instruction.has_delay_slot() {
                    if !plain_control(word, pc) {
                        return None;
                    }
                    if edge.delay_slot != DelaySlot::None {
                        let ds = GuestAddr(pc.0.checked_add(4)?);
                        let slot = image.word(ds)?;
                        if !scalar(slot, ds) {
                            return None;
                        }
                        bytes.extend(slot.to_be_bytes());
                        transfer(slot, ds, &mut state);
                    }
                } else {
                    if edge.kind != EdgeKind::Fallthrough || !scalar(word, pc) {
                        return None;
                    }
                    transfer(word, pc, &mut state);
                }
                break;
            }
            if pc.0 > end.0 || !scalar(word, pc) {
                return None;
            }
            transfer(word, pc, &mut state);
            pc = GuestAddr(pc.0.checked_add(4)?);
        }
    }
    None
}
