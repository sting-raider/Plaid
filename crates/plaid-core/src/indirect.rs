//! A bounded value analysis, not a CPU interpreter. Unknown writes kill values.
use crate::{
    EvidenceKind, GuestAddr,
    discovery::{CodeImage, decode},
    program::*,
    rom::sha256,
};
use serde::{Deserialize, Serialize};
use std::{
    collections::{BTreeMap, BTreeSet},
    ops::Bound::{self, Excluded, Included, Unbounded},
};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ConstantCertificate {
    pub block: CodeAddress,
    pub site: CodeAddress,
    pub target: CodeAddress,
    pub prefix_sha256: String,
}

pub(crate) fn signed_word(value: u32) -> u64 {
    i64::from(value as i32) as u64
}

pub(crate) fn transfer(word: u32, pc: GuestAddr, state: &mut [Option<u64>; 32]) {
    let i = decode(word, pc);
    // Upstream getters assert that the instruction semantically has that
    // operand (LUI has no rs). Raw fields are safe for this bounded transfer.
    let rs = state[((word >> 21) & 31) as usize];
    let rt = state[((word >> 16) & 31) as usize];
    let imm = u64::from(word as u16);
    let signed_imm = i64::from(word as i16) as u64;
    let dest = i.destination_gpr();
    let value = match word >> 26 {
        15 => Some(signed_word((imm as u32) << 16)), // LUI
        13 => rs.map(|r| r | imm),                   // ORI
        12 => rs.map(|r| r & imm),                   // ANDI
        14 => rs.map(|r| r ^ imm),                   // XORI
        9 => rs.map(|r| signed_word((r as u32).wrapping_add(signed_imm as u32))), // ADDIU
        25 => rs.map(|r| r.wrapping_add(signed_imm)), // DADDIU
        0 => match word & 63 {
            0 => rt.map(|r| signed_word((r as u32) << ((word >> 6) & 31))),
            2 => rt.map(|r| signed_word((r as u32) >> ((word >> 6) & 31))),
            3 => rt.map(|r| signed_word(((r as i32) >> ((word >> 6) & 31)) as u32)),
            33 => rs
                .zip(rt)
                .map(|(a, b)| signed_word((a as u32).wrapping_add(b as u32))),
            35 => rs
                .zip(rt)
                .map(|(a, b)| signed_word((a as u32).wrapping_sub(b as u32))),
            36 => rs.zip(rt).map(|(a, b)| a & b),
            37 => rs.zip(rt).map(|(a, b)| a | b),
            38 => rs.zip(rt).map(|(a, b)| a ^ b),
            39 => rs.zip(rt).map(|(a, b)| !(a | b)),
            45 => rs.zip(rt).map(|(a, b)| a.wrapping_add(b)),
            _ => None,
        },
        _ => None,
    };
    // Rabbitizer reports the actual destination, including pseudo forms.
    if let Some(r) = dest
        && r != 0
    {
        state[r as usize] = value;
    }
    state[0] = Some(0);
}

type Key<'a> = (u32, &'a str, u64);

/// Keys of one image and generation with pc in `lo..=hi`; ("", 0) is the least
/// (image, generation), so the bounds are exact.
fn span<'a, V>(
    keys: impl Fn((Bound<Key<'a>>, Bound<Key<'a>>)) -> V,
    lo: u32,
    hi: u32,
) -> Option<V> {
    let upper = hi
        .checked_add(1)
        .map_or(Unbounded, |u| Excluded((u, "", 0)));
    (lo <= hi).then(|| keys((Included((lo, "", 0)), upper)))
}

/// What the per-site proofs look up in a map, built once so that analysing
/// every site of a large map stays linear (ADR-0173).
pub struct MapIndex<'a> {
    /// Blocks by image and generation, sorted by start, with the largest size.
    blocks: BTreeMap<(&'a str, u64), (Vec<&'a BasicBlock>, u32)>,
    /// Entries and indirect candidates or observations.
    jumped: BTreeSet<Key<'a>>,
    /// Direct edges by target.
    edges: BTreeMap<Key<'a>, Vec<&'a DirectEdge>>,
}

impl<'a> MapIndex<'a> {
    pub fn new(map: &'a ProgramMap) -> Self {
        let mut blocks: BTreeMap<(&str, u64), (Vec<&BasicBlock>, u32)> = BTreeMap::new();
        for b in &map.blocks {
            let (list, max) = blocks
                .entry((b.start.image.as_str(), b.start.generation))
                .or_default();
            list.push(b);
            *max = (*max).max(b.size);
        }
        for (list, _) in blocks.values_mut() {
            list.sort_by_key(|b| b.start.pc.0);
        }
        let jumped = map
            .entries
            .keys()
            .chain(
                map.indirect_sites
                    .iter()
                    .flat_map(|s| s.candidates.keys().chain(s.observed.keys())),
            )
            .map(key)
            .collect();
        let mut edges: BTreeMap<_, Vec<_>> = BTreeMap::new();
        for e in &map.direct_edges {
            edges.entry(key(&e.target)).or_default().push(e);
        }
        Self {
            blocks,
            jumped,
            edges,
        }
    }

    /// The blocks of the site's image that contain its pc.
    pub(crate) fn containing(&self, site: &CodeAddress) -> Vec<&'a BasicBlock> {
        let Some((list, max)) = self.blocks.get(&(site.image.as_str(), site.generation)) else {
            return Vec::new();
        };
        let end = list.partition_point(|b| b.start.pc.0 <= site.pc.0);
        list[..end]
            .iter()
            .rev()
            .take_while(|b| site.pc.0 - b.start.pc.0 < *max)
            .filter(|b| {
                GuestRange {
                    start: b.start.pc,
                    size: b.size,
                }
                .contains(site.pc)
            })
            .copied()
            .collect()
    }

    /// Whether an entry or indirect candidate or observation is `at`.
    pub(crate) fn jumped_to(&self, at: &CodeAddress) -> bool {
        self.jumped.contains(&key(at))
    }

    /// Whether an entry or indirect candidate or observation is in `lo..=hi`.
    pub(crate) fn jumped_in(&self, image: &str, generation: u64, lo: u32, hi: u32) -> bool {
        span(
            |r| {
                self.jumped
                    .range(r)
                    .any(|k| (k.1, k.2) == (image, generation))
            },
            lo,
            hi,
        )
        .unwrap_or(false)
    }

    /// Direct edges whose target is in `lo..=hi`.
    pub(crate) fn edges_in(
        &self,
        image: &str,
        generation: u64,
        lo: u32,
        hi: u32,
    ) -> impl Iterator<Item = &'a DirectEdge> {
        span(|r| self.edges.range(r), lo, hi)
            .into_iter()
            .flatten()
            .filter(move |(k, _)| (k.1, k.2) == (image, generation))
            .flat_map(|(_, v)| v.iter().copied())
    }

    /// Direct edges into `target`.
    pub(crate) fn edges_to(&self, target: &CodeAddress) -> Vec<&'a DirectEdge> {
        let pc = target.pc.0;
        self.edges_in(&target.image, target.generation, pc, pc)
            .collect()
    }

    /// Whether control can enter the image in `(after, upto]`.
    fn entered_between(&self, image: &str, generation: u64, after: u32, upto: u32) -> bool {
        after < upto
            && (self.jumped_in(image, generation, after + 1, upto)
                || self
                    .edges_in(image, generation, after + 1, upto)
                    .next()
                    .is_some())
    }
}

fn key(a: &CodeAddress) -> Key<'_> {
    (a.pc.0, a.image.as_str(), a.generation)
}

/// Register values just before `site`, from a straight-line prefix that starts
/// at the site's block and that no other control flow enters. Returns the
/// block start, the state and the prefix bytes including the site word.
pub(crate) fn prefix_state_in(
    index: &MapIndex,
    image: &CodeImage,
    site: &CodeAddress,
) -> Option<(CodeAddress, [Option<u64>; 32], Vec<u8>)> {
    if image.base.image != site.image || image.base.generation != site.generation {
        return None;
    }
    let blocks = index.containing(site);
    if blocks.len() != 1 || blocks[0].delay_slot_entry {
        return None;
    }
    let block = blocks[0];
    if index.entered_between(&site.image, site.generation, block.start.pc.0, site.pc.0) {
        return None;
    }
    let mut state = [None; 32];
    state[0] = Some(0);
    let mut prefix = Vec::new();
    let mut pc = block.start.pc;
    loop {
        let word = image.word(pc)?;
        let i = decode(word, pc);
        if !i.is_valid() || i.is_trap() || matches!(i.opcode_name(), "syscall" | "break" | "eret") {
            return None;
        }
        prefix.extend(word.to_be_bytes());
        if pc == site.pc {
            return Some((block.start.clone(), state, prefix));
        }
        if i.has_delay_slot() || pc.0 >= site.pc.0 {
            return None;
        }
        transfer(word, pc, &mut state);
        pc = GuestAddr(pc.0.checked_add(4)?);
    }
}

/// A 32-bit code address held in a 64-bit register, if it is one.
pub(crate) fn code_pointer(value: u64) -> Option<u32> {
    let low = value as u32;
    ((value == u64::from(low) || value == signed_word(low)) && low.is_multiple_of(4)).then_some(low)
}

fn certificate_in(
    index: &MapIndex,
    image: &CodeImage,
    site: &CodeAddress,
) -> Option<ConstantCertificate> {
    let (block, state, prefix) = prefix_state_in(index, image, site)?;
    let i = decode(image.word(site.pc)?, site.pc);
    if !matches!(i.opcode_name(), "jr" | "jalr") {
        return None;
    }
    // Capture before the delay slot or JALR link write modifies rs.
    let low = code_pointer(state[i.get_rs() as usize]?)?;
    Some(ConstantCertificate {
        block,
        site: site.clone(),
        target: image.address(GuestAddr(low)),
        prefix_sha256: sha256(&prefix),
    })
}

/// Sets a closed local target only when a straight-line prefix dominates the site
/// in this declared CFG. Whole-ROM coverage and modification are separate gates.
pub fn analyze_indirect(map: &ProgramMap, image: &CodeImage) -> Result<ProgramMap, String> {
    map.validate()?;
    let mut out = map.clone();
    out.indirect_sites.clear();
    let index = MapIndex::new(map);
    for old in &map.indirect_sites {
        let mut site = old.clone();
        let proof = if let Some(proof) = certificate_in(&index, image, &old.site) {
            Some((
                "plaid-local-constant/v0",
                proof.target.clone(),
                serde_json::to_string(&proof),
            ))
        } else if let Some(proof) = crate::indirect_chain::certificate(map, image, &old.site) {
            Some((
                "plaid-cross-block-constant/v0",
                proof.target.clone(),
                serde_json::to_string(&proof),
            ))
        } else {
            crate::indirect_chain::join_certificate(map, image, &old.site).map(|proof| {
                (
                    "plaid-cross-block-join/v0",
                    proof.target.clone(),
                    serde_json::to_string(&proof),
                )
            })
        };
        if let Some((producer, target, detail)) = proof {
            let detail = detail.map_err(|e| e.to_string())?;
            let id = format!("constant:{}", sha256(detail.as_bytes()));
            out.evidence.insert(
                id.clone(),
                Evidence {
                    kind: EvidenceKind::Static,
                    producer: producer.into(),
                    revision: "0".into(),
                    detail,
                },
            );
            site.candidates
                .entry(target.clone())
                .or_default()
                .insert(id.clone());
            // A disagreement is retained as a candidate conflict; never close it.
            if site.candidates.len() == 1 && site.observed.keys().all(|a| *a == target) {
                site.closed_proof = Some(id);
            } else {
                site.closed_proof = None;
            }
        } else {
            site.closed_proof = None;
        }
        out.indirect_sites.insert(site);
    }
    out = crate::tables::analyze(&out, image)?;
    // New candidate edges may themselves enter a prefix and break dominance.
    let index = MapIndex::new(&out);
    let sites = out
        .indirect_sites
        .iter()
        .map(|old| {
            let mut site = old.clone();
            if !verify_static_in(&index, &out, image, old) {
                site.closed_proof = None;
            }
            site
        })
        .collect();
    out.indirect_sites = sites;
    out.validate()?;
    Ok(out)
}

/// A rechecked static target proof: a constant certificate or a verified jump
/// table (ADR-0132). Scopes decide whether a table's immutability holds.
pub fn verify_static(map: &ProgramMap, image: &CodeImage, site: &IndirectSite) -> bool {
    verify_static_in(&MapIndex::new(map), map, image, site)
}

/// [`verify_static`] with the map's index built once by the caller.
pub fn verify_static_in(
    index: &MapIndex,
    map: &ProgramMap,
    image: &CodeImage,
    site: &IndirectSite,
) -> bool {
    verify_constant_in(index, map, image, site) || crate::tables::verify_in(index, map, image, site)
}

/// Recompute the certificate using current CFG and bytes; producer labels alone
/// are insufficient. A later merge/bypass or altered prefix invalidates it.
pub fn verify_constant(map: &ProgramMap, image: &CodeImage, site: &IndirectSite) -> bool {
    verify_constant_in(&MapIndex::new(map), map, image, site)
}

/// [`verify_constant`] with the map's index built once by the caller.
pub fn verify_constant_in(
    index: &MapIndex,
    map: &ProgramMap,
    image: &CodeImage,
    site: &IndirectSite,
) -> bool {
    let Some(word) = image.word(site.site.pc) else {
        return false;
    };
    let i = decode(word, site.site.pc);
    let link = if i.opcode_name() == "jalr" && ((word >> 11) & 31) != 0 {
        Some(((word >> 11) & 31) as u8)
    } else {
        None
    };
    if site.link_register != link || site.delay_slot != DelaySlot::Always {
        return false;
    }
    let Some(id) = &site.closed_proof else {
        return false;
    };
    let Some(e) = map.evidence.get(id) else {
        return false;
    };
    if e.kind != EvidenceKind::Static {
        return false;
    }
    let target = match e.producer.as_str() {
        "plaid-local-constant/v0" => {
            let Ok(proof) = serde_json::from_str::<ConstantCertificate>(&e.detail) else {
                return false;
            };
            if certificate_in(index, image, &site.site).as_ref() != Some(&proof) {
                return false;
            }
            proof.target
        }
        "plaid-cross-block-constant/v0" => {
            let Ok(proof) =
                serde_json::from_str::<crate::indirect_chain::ChainCertificate>(&e.detail)
            else {
                return false;
            };
            if crate::indirect_chain::certificate(map, image, &site.site).as_ref() != Some(&proof) {
                return false;
            }
            proof.target
        }
        "plaid-cross-block-join/v0" => {
            let Ok(proof) =
                serde_json::from_str::<crate::indirect_chain::JoinCertificate>(&e.detail)
            else {
                return false;
            };
            if crate::indirect_chain::join_certificate(map, image, &site.site).as_ref()
                != Some(&proof)
            {
                return false;
            }
            proof.target
        }
        _ => return false,
    };
    site.candidates.len() == 1
        && site.candidates.contains_key(&target)
        && site.observed.keys().all(|a| *a == target)
}
