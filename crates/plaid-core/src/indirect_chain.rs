//! Restricted cross-block constant certificates. No call summaries, memory reads
//! or loop invariants are assumed. Reconstruct CFG from bytes.
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
const MAX_JOIN_PATHS: usize = 2;

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

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct JoinCertificate {
    pub site: CodeAddress,
    pub target: CodeAddress,
    pub paths: Vec<JoinPath>,
    pub words_sha256: String,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct JoinPath {
    pub blocks: Vec<CodeAddress>,
    pub edges: Vec<ChainEdge>,
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

fn roots(map: &ProgramMap, image: &CodeImage) -> BTreeSet<GuestAddr> {
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
    roots
}

fn expected_map(map: &ProgramMap, image: &CodeImage, roots: &BTreeSet<GuestAddr>) -> Option<ProgramMap> {
    if image.words.len() > MAX_WORDS || roots.is_empty() {
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
        None
    } else {
        Some(expected)
    }
}

fn edge_matches(a: &DirectEdge, b: &DirectEdge) -> bool {
    a.site == b.site
        && a.target == b.target
        && a.kind == b.kind
        && a.delay_slot == b.delay_slot
}

fn chain_edge_matches(a: &DirectEdge, b: &ChainEdge) -> bool {
    a.site == b.site
        && a.target == b.target
        && a.kind == b.kind
        && a.delay_slot == b.delay_slot
}

fn validate_block_and_incoming(map: &ProgramMap, expected: &ProgramMap, block: &BasicBlock) -> bool {
    if !map
        .blocks
        .iter()
        .any(|b| b.start == block.start && b.size == block.size && !b.delay_slot_entry)
    {
        return false;
    }
    map.direct_edges
        .iter()
        .filter(|e| e.target == block.start)
        .all(|edge| expected.direct_edges.iter().any(|candidate| edge_matches(edge, candidate)))
}

pub(crate) fn certificate(
    map: &ProgramMap,
    image: &CodeImage,
    site: &CodeAddress,
) -> Option<ChainCertificate> {
    if site.image != image.base.image || site.generation != image.base.generation {
        return None;
    }
    let roots = roots(map, image);
    let expected = expected_map(map, image, &roots)?;
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
        if !validate_block_and_incoming(map, &expected, block) {
            return None;
        }
    }
    for edge in &edges {
        if !map
            .direct_edges
            .iter()
            .any(|candidate| chain_edge_matches(candidate, edge))
        {
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

#[derive(Clone)]
struct ReversePath {
    blocks: Vec<BasicBlock>,
    edges: Vec<ChainEdge>,
    visited: BTreeSet<CodeAddress>,
}

fn enumerate_two_paths(
    expected: &ProgramMap,
    roots: &BTreeSet<GuestAddr>,
    site: &CodeAddress,
) -> Option<Vec<(Vec<BasicBlock>, Vec<ChainEdge>)>> {
    let first = containing(expected, site)?.clone();
    let mut stack = vec![ReversePath {
        blocks: vec![first.clone()],
        edges: Vec::new(),
        visited: [first.start.clone()].into(),
    }];
    let mut completed = Vec::new();
    while let Some(path) = stack.pop() {
        let current = path.blocks.last()?;
        if roots.contains(&current.start.pc) {
            let mut blocks = path.blocks;
            let mut edges = path.edges;
            blocks.reverse();
            edges.reverse();
            completed.push((blocks, edges));
            if completed.len() > MAX_JOIN_PATHS {
                return None;
            }
            continue;
        }
        let incoming: Vec<_> = expected
            .direct_edges
            .iter()
            .filter(|edge| edge.target == current.start)
            .collect();
        if incoming.is_empty() || incoming.len() > MAX_JOIN_PATHS {
            return None;
        }
        for edge in incoming {
            if !matches!(
                edge.kind,
                EdgeKind::Jump | EdgeKind::Branch | EdgeKind::Fallthrough
            ) {
                return None;
            }
            let predecessor = containing(expected, &edge.site)?.clone();
            if path.blocks.len() == MAX_CHAIN || path.visited.contains(&predecessor.start) {
                return None;
            }
            let mut next = path.clone();
            next.visited.insert(predecessor.start.clone());
            next.blocks.push(predecessor);
            next.edges.push(ChainEdge {
                site: edge.site.clone(),
                target: edge.target.clone(),
                kind: edge.kind,
                delay_slot: edge.delay_slot,
            });
            stack.push(next);
        }
        if stack.len() + completed.len() > MAX_JOIN_PATHS {
            return None;
        }
    }
    (completed.len() == MAX_JOIN_PATHS).then_some(completed)
}

fn simulate_path(
    image: &CodeImage,
    site: &CodeAddress,
    blocks: &[BasicBlock],
    edges: &[ChainEdge],
) -> Option<(CodeAddress, Vec<u8>)> {
    if blocks.len() != edges.len().checked_add(1)? {
        return None;
    }
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
                    let instruction = decode(word, pc);
                    if !matches!(instruction.opcode_name(), "jr" | "jalr") {
                        return None;
                    }
                    let target = state[instruction.get_rs() as usize]?;
                    let low = target as u32;
                    if !low.is_multiple_of(4)
                        || (target != u64::from(low) && target != signed_word(low))
                    {
                        return None;
                    }
                    return Some((image.address(GuestAddr(low)), bytes));
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

/// Bounded fallback for exactly two acyclic root-to-site paths. Each path is
/// evaluated independently from an unknown incoming register state (except r0),
/// and the certificate exists only when both paths derive the same concrete
/// indirect target. This proves a target set, not provenance identity of equal
/// register values and not completion of the final JR/JALR delay slot.
pub(crate) fn join_certificate(
    map: &ProgramMap,
    image: &CodeImage,
    site: &CodeAddress,
) -> Option<JoinCertificate> {
    if site.image != image.base.image || site.generation != image.base.generation {
        return None;
    }
    let roots = roots(map, image);
    let expected = expected_map(map, image, &roots)?;
    let paths = enumerate_two_paths(&expected, &roots, site)?;
    let mut certified_paths = Vec::new();
    let mut target = None;
    let mut bytes = Vec::new();
    for (blocks, edges) in paths {
        for block in &blocks {
            if !validate_block_and_incoming(map, &expected, block) {
                return None;
            }
        }
        for edge in &edges {
            if !map
                .direct_edges
                .iter()
                .any(|candidate| chain_edge_matches(candidate, edge))
            {
                return None;
            }
        }
        let (path_target, path_bytes) = simulate_path(image, site, &blocks, &edges)?;
        if target.as_ref().is_some_and(|old| old != &path_target) {
            return None;
        }
        target = Some(path_target);
        bytes.extend((path_bytes.len() as u64).to_be_bytes());
        bytes.extend(path_bytes);
        certified_paths.push(JoinPath {
            blocks: blocks.into_iter().map(|block| block.start).collect(),
            edges,
        });
    }
    certified_paths.sort();
    Some(JoinCertificate {
        site: site.clone(),
        target: target?,
        paths: certified_paths,
        words_sha256: sha256(&bytes),
    })
}
