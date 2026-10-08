//! A bounded value analysis, not a CPU interpreter. Unknown writes kill values.
use crate::{
    EvidenceKind, GuestAddr,
    discovery::{CodeImage, decode},
    program::*,
    rom::sha256,
};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ConstantCertificate {
    pub block: CodeAddress,
    pub site: CodeAddress,
    pub target: CodeAddress,
    pub prefix_sha256: String,
}

fn signed_word(value: u32) -> u64 {
    i64::from(value as i32) as u64
}

fn transfer(word: u32, pc: GuestAddr, state: &mut [Option<u64>; 32]) {
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

fn certificate(
    map: &ProgramMap,
    image: &CodeImage,
    site: &CodeAddress,
) -> Option<ConstantCertificate> {
    if image.base.image != site.image || image.base.generation != site.generation {
        return None;
    }
    let blocks: Vec<_> = map
        .blocks
        .iter()
        .filter(|b| {
            b.start.image == site.image
                && b.start.generation == site.generation
                && GuestRange {
                    start: b.start.pc,
                    size: b.size,
                }
                .contains(site.pc)
        })
        .collect();
    if blocks.len() != 1 || blocks[0].delay_slot_entry {
        return None;
    }
    let block = blocks[0];
    let bypass = |a: &CodeAddress| {
        a.image == site.image
            && a.generation == site.generation
            && a.pc.0 > block.start.pc.0
            && a.pc.0 <= site.pc.0
    };
    if map.entries.keys().any(bypass)
        || map.direct_edges.iter().any(|e| bypass(&e.target))
        || map
            .indirect_sites
            .iter()
            .any(|s| s.candidates.keys().chain(s.observed.keys()).any(bypass))
    {
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
            if !matches!(i.opcode_name(), "jr" | "jalr") {
                return None;
            }
            // Capture before the delay slot or JALR link write modifies rs.
            let target = state[i.get_rs() as usize]?;
            let low = target as u32;
            if (target != u64::from(low) && target != signed_word(low)) || !low.is_multiple_of(4) {
                return None;
            }
            return Some(ConstantCertificate {
                block: block.start.clone(),
                site: site.clone(),
                target: image.address(GuestAddr(low)),
                prefix_sha256: sha256(&prefix),
            });
        }
        if i.has_delay_slot() || pc.0 >= site.pc.0 {
            return None;
        }
        transfer(word, pc, &mut state);
        pc = GuestAddr(pc.0.checked_add(4)?);
    }
}

/// Sets a closed local target only when a straight-line prefix dominates the site
/// in this declared CFG. Whole-ROM coverage and modification are separate gates.
pub fn analyze_indirect(map: &ProgramMap, image: &CodeImage) -> Result<ProgramMap, String> {
    map.validate()?;
    let mut out = map.clone();
    out.indirect_sites.clear();
    for old in &map.indirect_sites {
        let mut site = old.clone();
        if let Some(proof) = certificate(map, image, &old.site) {
            let detail = serde_json::to_string(&proof).map_err(|e| e.to_string())?;
            let id = format!("constant:{}", sha256(detail.as_bytes()));
            out.evidence.insert(
                id.clone(),
                Evidence {
                    kind: EvidenceKind::Static,
                    producer: "plaid-local-constant/v0".into(),
                    revision: "0".into(),
                    detail,
                },
            );
            site.candidates
                .entry(proof.target.clone())
                .or_default()
                .insert(id.clone());
            // A disagreement is retained as a candidate conflict; never close it.
            if site.candidates.len() == 1 && site.observed.keys().all(|a| *a == proof.target) {
                site.closed_proof = Some(id);
            } else {
                site.closed_proof = None;
            }
        } else {
            site.closed_proof = None;
        }
        out.indirect_sites.insert(site);
    }
    // New candidate edges may themselves enter a prefix and break dominance.
    out.indirect_sites = out
        .indirect_sites
        .iter()
        .map(|old| {
            let mut site = old.clone();
            if !verify_constant(&out, image, old) {
                site.closed_proof = None;
            }
            site
        })
        .collect();
    out.validate()?;
    Ok(out)
}

/// Recompute the certificate using current CFG and bytes; producer labels alone
/// are insufficient. A later merge/bypass or altered prefix invalidates it.
pub fn verify_constant(map: &ProgramMap, image: &CodeImage, site: &IndirectSite) -> bool {
    let Some(id) = &site.closed_proof else {
        return false;
    };
    let Some(e) = map.evidence.get(id) else {
        return false;
    };
    if e.kind != EvidenceKind::Static || e.producer != "plaid-local-constant/v0" {
        return false;
    }
    let Ok(proof) = serde_json::from_str::<ConstantCertificate>(&e.detail) else {
        return false;
    };
    certificate(map, image, &site.site).as_ref() == Some(&proof)
        && site.candidates.len() == 1
        && site.candidates.contains_key(&proof.target)
        && site.observed.keys().all(|a| *a == proof.target)
}
