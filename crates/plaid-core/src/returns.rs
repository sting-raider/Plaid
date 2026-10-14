//! Call/return closure for `jr $ra` (ADR-0127).
//!
//! A function is a call target; its body is every block reachable from it
//! without entering a call (branches, jumps, fallthroughs, return continuations
//! and constant-proven indirect jumps). A `jr $ra` site's target set is the
//! return continuation of every `$ra`-linking call that enters a function whose
//! body contains the site. This is closed only under the explicit assumption
//! that a return goes back to the call that entered its function; native code
//! checks that assumption at every return. A site reachable from a host-entered
//! entry, or from no function, receives no certificate.
use crate::{
    EvidenceKind, GuestAddr,
    discovery::CodeImage,
    indirect::{verify_constant, verify_static},
    program::*,
    rom::sha256,
};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

pub const PRODUCER: &str = "plaid-return-closure/v0";

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ReturnCertificate {
    pub site: CodeAddress,
    /// Function entries whose bodies contain the site.
    pub functions: BTreeSet<CodeAddress>,
    /// Return continuations of every `$ra`-linking call into those functions.
    pub continuations: BTreeSet<CodeAddress>,
    /// Some function is also a runtime callback (ADR-0130): returning to the
    /// runtime that entered it is closed by the declared runtime boundary.
    #[serde(default, skip_serializing_if = "std::ops::Not::not")]
    pub runtime_entered: bool,
}

fn is_jr_ra(word: u32) -> bool {
    word == 0x03e0_0008
}

fn block_of<'a>(map: &'a ProgramMap, pc: &CodeAddress) -> Option<&'a BasicBlock> {
    map.blocks.iter().find(|b| {
        b.start.image == pc.image
            && b.start.generation == pc.generation
            && b.start.pc.0 <= pc.pc.0
            && pc.pc.0 < b.start.pc.0.wrapping_add(b.size)
    })
}

fn in_block(block: &BasicBlock, site: &CodeAddress) -> bool {
    site.image == block.start.image
        && site.generation == block.start.generation
        && block.start.pc.0 <= site.pc.0
        && site.pc.0 < block.start.pc.0.wrapping_add(block.size)
}

/// `$ra`-linking calls as (call site, callee entry): JAL edges and JALR $ra
/// sites whose single target has a rechecked constant proof.
pub fn ra_calls(map: &ProgramMap, image: &CodeImage) -> Vec<(CodeAddress, CodeAddress)> {
    let mut calls: Vec<_> = map
        .direct_edges
        .iter()
        .filter(|e| e.kind == EdgeKind::Call)
        .map(|e| (e.site.clone(), e.target.clone()))
        .collect();
    for site in &map.indirect_sites {
        if site.link_register == Some(31) && verify_constant(map, image, site) {
            calls.extend(
                site.candidates
                    .keys()
                    .map(|t| (site.site.clone(), t.clone())),
            );
        }
    }
    calls
}

/// Block starts reachable from `entry` without entering a call.
pub fn function_body(
    map: &ProgramMap,
    image: &CodeImage,
    entry: &CodeAddress,
) -> BTreeSet<CodeAddress> {
    let mut body = BTreeSet::new();
    let mut pending = vec![entry.clone()];
    while let Some(start) = pending.pop() {
        let Some(block) = map.blocks.iter().find(|b| b.start == start) else {
            continue;
        };
        if !body.insert(start) {
            continue;
        }
        for edge in &map.direct_edges {
            if edge.kind != EdgeKind::Call && in_block(block, &edge.site) {
                pending.push(edge.target.clone());
            }
        }
        for site in &map.indirect_sites {
            if site.link_register.is_none()
                && in_block(block, &site.site)
                && verify_static(map, image, site)
            {
                pending.extend(site.candidates.keys().cloned());
            }
        }
    }
    body
}

/// Recompute the certificate from the current CFG and bytes.
pub fn certificate(
    map: &ProgramMap,
    image: &CodeImage,
    site: &CodeAddress,
) -> Option<ReturnCertificate> {
    if !is_jr_ra(image.word(site.pc)?) {
        return None;
    }
    let block = block_of(map, site)?.start.clone();
    let calls = ra_calls(map, image);
    let entered = crate::callbacks::targets(map, image);
    let callees: BTreeSet<_> = calls
        .iter()
        .map(|(_, t)| t.clone())
        .chain(entered.iter().cloned())
        .collect();
    // Entries reached only as constant-jump targets are interior blocks, not
    // host entries. Every other entry is host-entered with an unknown return.
    let jumped: BTreeSet<_> = map
        .indirect_sites
        .iter()
        .filter(|s| verify_static(map, image, s))
        .flat_map(|s| s.candidates.keys().cloned())
        .collect();
    for host in map
        .entries
        .keys()
        .filter(|e| !callees.contains(e) && !jumped.contains(e))
    {
        if function_body(map, image, host).contains(&block) {
            return None;
        }
    }
    let functions: BTreeSet<_> = callees
        .into_iter()
        .filter(|f| function_body(map, image, f).contains(&block))
        .collect();
    let continuations: BTreeSet<_> = calls
        .iter()
        .filter(|(_, t)| functions.contains(t))
        .map(|(c, _)| CodeAddress {
            pc: GuestAddr(c.pc.0.wrapping_add(8)),
            ..c.clone()
        })
        .collect();
    let runtime_entered = functions.iter().any(|f| entered.contains(f));
    if functions.is_empty() || (continuations.is_empty() && !runtime_entered) {
        return None;
    }
    Some(ReturnCertificate {
        site: site.clone(),
        functions,
        continuations,
        runtime_entered,
    })
}

pub fn verify(map: &ProgramMap, image: &CodeImage, site: &IndirectSite) -> bool {
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
    let Ok(proof) = serde_json::from_str::<ReturnCertificate>(&e.detail) else {
        return false;
    };
    certificate(map, image, &site.site).as_ref() == Some(&proof)
        && site.candidates.keys().cloned().collect::<BTreeSet<_>>() == proof.continuations
        && site
            .observed
            .keys()
            .all(|a| proof.continuations.contains(a))
}

/// Attach return certificates to otherwise unproven `jr $ra` sites.
pub fn annotate(map: &ProgramMap, image: &CodeImage) -> Result<ProgramMap, String> {
    let mut out = map.clone();
    let mut sites = BTreeSet::new();
    for old in &map.indirect_sites {
        let mut site = old.clone();
        if old.closed_proof.is_none()
            && let Some(proof) = certificate(map, image, &old.site)
            && old
                .observed
                .keys()
                .chain(old.candidates.keys())
                .all(|a| proof.continuations.contains(a))
        {
            let detail = serde_json::to_string(&proof).map_err(|e| e.to_string())?;
            let id = format!("return:{}", sha256(detail.as_bytes()));
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
            site.candidates = proof
                .continuations
                .iter()
                .map(|c| (c.clone(), refs.clone()))
                .collect::<BTreeMap<_, _>>();
            site.closed_proof = Some(id);
        }
        sites.insert(site);
    }
    out.indirect_sites = sites;
    out.validate()?;
    Ok(out)
}
