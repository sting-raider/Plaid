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
    discovery::{CodeImage, decode},
    indirect::{MapIndex, verify_constant_in, verify_static_in},
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
    /// Some function is a host entry (ADR-0146): returning to the host's
    /// return address hands control back to the host.
    #[serde(default, skip_serializing_if = "std::ops::Not::not")]
    pub host_entered: bool,
}

/// The register a `jr` returns through: `$ra`, or one that holds a copy of it
/// (ADR-0244, checked per function by [`holds_entry_ra`]).
fn jr_register(word: u32) -> Option<u32> {
    (word & 0xfc1f_ffff == 8).then_some(word >> 21 & 31)
}

/// `or`/`addu`/`daddu` of `$ra` and `$zero` into `rd`.
fn copies_ra(word: u32) -> Option<u32> {
    let (rs, rt, rd) = (word >> 21 & 31, word >> 16 & 31, word >> 11 & 31);
    (word >> 26 == 0
        && word >> 6 & 31 == 0
        && matches!(word & 63, 0x21 | 0x25 | 0x2d)
        && matches!((rs, rt), (31, 0) | (0, 31)))
    .then_some(rd)
}

/// Writes `$ra`: a linking jump or branch, or any instruction with `$ra` as
/// its destination.
fn writes_ra(word: u32, pc: GuestAddr) -> bool {
    let (op, rt) = (word >> 26, word >> 16 & 31);
    op == 3
        || (op == 0 && word & 63 == 9)
        || (op == 1 && (16..=19).contains(&rt))
        || decode(word, pc).destination_gpr() == Some(31)
}

/// `register` holds the `$ra` the function was entered with at every point of
/// its body: its only writes are copies of `$ra` in the entry block, before
/// anything there writes `$ra`. Lowered returns still check the value.
fn holds_entry_ra(
    image: &CodeImage,
    sizes: &BTreeMap<CodeAddress, u32>,
    body: &BTreeSet<CodeAddress>,
    entry: &CodeAddress,
    register: u32,
) -> Option<bool> {
    let mut copied = false;
    for block in body {
        let mut ra_written = false;
        for n in 0..sizes.get(block)? / 4 {
            let pc = GuestAddr(block.pc.0.wrapping_add(4 * n));
            let word = image.word(pc)?;
            if decode(word, pc).destination_gpr() == Some(register) {
                if block != entry || ra_written || copies_ra(word) != Some(register) {
                    return Some(false);
                }
                copied = true;
            }
            ra_written |= writes_ra(word, pc);
        }
    }
    Some(copied)
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
    let index = MapIndex::new(map);
    for site in &map.indirect_sites {
        if site.link_register == Some(31) && verify_constant_in(&index, map, image, site) {
            calls.extend(
                site.candidates
                    .keys()
                    .map(|t| (site.site.clone(), t.clone())),
            );
        }
    }
    calls
        .into_iter()
        .flat_map(|(site, target)| {
            let copies = if target.image != image.base.image
                || target.generation != image.base.generation
                || image.instruction_word(target.pc).is_some()
            {
                vec![target.pc.0]
            } else {
                image.slot_copies(target.pc.0)
            };
            copies.into_iter().map(move |pc| {
                (
                    site.clone(),
                    CodeAddress {
                        pc: GuestAddr(pc),
                        ..target.clone()
                    },
                )
            })
        })
        .collect()
}

/// Intra-function successors of every block start: non-call direct edges and
/// candidates of non-linking indirect sites with a rechecked static proof,
/// from every block that contains the site.
fn successors(map: &ProgramMap, image: &CodeImage) -> BTreeMap<CodeAddress, Vec<CodeAddress>> {
    let mut by_site: BTreeMap<CodeAddress, Vec<CodeAddress>> = BTreeMap::new();
    for edge in &map.direct_edges {
        if edge.kind != EdgeKind::Call {
            by_site
                .entry(edge.site.clone())
                .or_default()
                .push(edge.target.clone());
        }
    }
    let index = MapIndex::new(map);
    for site in &map.indirect_sites {
        if site.link_register.is_none() && verify_static_in(&index, map, image, site) {
            by_site
                .entry(site.site.clone())
                .or_default()
                .extend(site.candidates.keys().cloned());
        }
    }
    let mut out: BTreeMap<CodeAddress, Vec<CodeAddress>> = BTreeMap::new();
    for block in &map.blocks {
        // As before, the first block with a given start is the block.
        if out.contains_key(&block.start) {
            continue;
        }
        let end = u64::from(block.start.pc.0) + u64::from(block.size);
        let targets = out.entry(block.start.clone()).or_default();
        // CodeAddress orders by pc first: stop once past the block's end.
        for (site, to) in by_site.range(block.start.clone()..) {
            if u64::from(site.pc.0) >= end {
                break;
            }
            if in_block(block, site) {
                targets.extend(to.iter().cloned());
            }
        }
    }
    out
}

fn body_from(
    succ: &BTreeMap<CodeAddress, Vec<CodeAddress>>,
    entry: &CodeAddress,
) -> BTreeSet<CodeAddress> {
    body_within(succ, entry, |_| true)
}

fn body_within(
    succ: &BTreeMap<CodeAddress, Vec<CodeAddress>>,
    entry: &CodeAddress,
    accepts: impl Fn(&CodeAddress) -> bool,
) -> BTreeSet<CodeAddress> {
    let mut body = BTreeSet::new();
    let mut pending = vec![entry.clone()];
    while let Some(start) = pending.pop() {
        let Some(next) = succ.get(&start) else {
            continue;
        };
        if body.insert(start) {
            pending.extend(next.iter().filter(|a| accepts(a)).cloned());
        }
    }
    body
}

/// Block starts reachable from `entry` without entering a call.
pub fn function_body(
    map: &ProgramMap,
    image: &CodeImage,
    entry: &CodeAddress,
) -> BTreeSet<CodeAddress> {
    body_from(&successors(map, image), entry)
}

/// Bodies of many entries, sharing one successor index.
pub fn function_bodies<'a>(
    map: &ProgramMap,
    image: &CodeImage,
    entries: impl IntoIterator<Item = &'a CodeAddress>,
) -> BTreeMap<CodeAddress, BTreeSet<CodeAddress>> {
    let succ = successors(map, image);
    entries
        .into_iter()
        .map(|e| (e.clone(), body_from(&succ, e)))
        .collect()
}

/// Native function bodies stop at a binding boundary: a tail into another
/// content-bound image enters that image's native wrapper instead. Return
/// closure still uses the unrestricted graph to propagate continuations.
/// An `unproven` jump (a residual site, ADR-0223) also reaches its candidate
/// and observed targets, so they are lowered as labels it can dispatch to.
pub fn function_bodies_partitioned<'a>(
    map: &ProgramMap,
    image: &CodeImage,
    entries: impl IntoIterator<Item = &'a CodeAddress>,
    partition: impl Fn(&CodeAddress) -> Option<usize>,
    unproven: &BTreeSet<CodeAddress>,
) -> BTreeMap<CodeAddress, BTreeSet<CodeAddress>> {
    let mut succ = successors(map, image);
    for site in map
        .indirect_sites
        .iter()
        .filter(|s| s.link_register.is_none() && unproven.contains(&s.site))
    {
        if let Some(block) = map.blocks.iter().find(|b| in_block(b, &site.site)) {
            succ.entry(block.start.clone())
                .or_default()
                .extend(site.candidates.keys().chain(site.observed.keys()).cloned());
        }
    }
    entries
        .into_iter()
        .map(|entry| {
            let region = partition(entry);
            (
                entry.clone(),
                body_within(&succ, entry, |target| partition(target) == region),
            )
        })
        .collect()
}

/// Map-wide facts every return certificate shares, computed once per map.
pub struct Closure<'a> {
    index: MapIndex<'a>,
    /// Callee entry -> its `$ra`-linking call sites.
    callers: BTreeMap<CodeAddress, Vec<CodeAddress>>,
    entered: BTreeSet<CodeAddress>,
    /// Block start -> callees whose body contains it.
    containing: BTreeMap<CodeAddress, BTreeSet<CodeAddress>>,
    /// Block start -> host entries whose body contains it (ADR-0146).
    hosted: BTreeMap<CodeAddress, BTreeSet<CodeAddress>>,
    succ: BTreeMap<CodeAddress, Vec<CodeAddress>>,
    sizes: BTreeMap<CodeAddress, u32>,
}

impl<'a> Closure<'a> {
    pub fn new(map: &'a ProgramMap, image: &CodeImage) -> Self {
        let calls = ra_calls(map, image);
        let entered = crate::callbacks::targets(map, image);
        let callees: BTreeSet<_> = calls
            .iter()
            .map(|(_, t)| t.clone())
            .chain(entered.iter().cloned())
            .collect();
        // Entries reached only as constant-jump targets are interior blocks, not
        // host entries. Every other entry is host-entered and returns to the host.
        let index = MapIndex::new(map);
        let jumped: BTreeSet<_> = map
            .indirect_sites
            .iter()
            .filter(|s| verify_static_in(&index, map, image, s))
            .flat_map(|s| s.candidates.keys().cloned())
            .collect();
        let succ = successors(map, image);
        let mut hosted: BTreeMap<CodeAddress, BTreeSet<CodeAddress>> = BTreeMap::new();
        for host in map
            .entries
            .keys()
            .filter(|e| !callees.contains(e) && !jumped.contains(e))
        {
            for block in body_from(&succ, host) {
                hosted.entry(block).or_default().insert(host.clone());
            }
        }
        let mut containing: BTreeMap<CodeAddress, BTreeSet<CodeAddress>> = BTreeMap::new();
        for f in &callees {
            for block in body_from(&succ, f) {
                containing.entry(block).or_default().insert(f.clone());
            }
        }
        let mut callers: BTreeMap<CodeAddress, Vec<CodeAddress>> = BTreeMap::new();
        for (site, target) in calls {
            callers.entry(target).or_default().push(site);
        }
        let mut sizes = BTreeMap::new();
        for block in &map.blocks {
            sizes.entry(block.start.clone()).or_insert(block.size);
        }
        Self {
            index,
            callers,
            entered,
            containing,
            hosted,
            succ,
            sizes,
        }
    }

    /// Recompute the certificate from the current CFG and bytes.
    pub fn certificate(&self, image: &CodeImage, site: &CodeAddress) -> Option<ReturnCertificate> {
        let register = jr_register(image.word(site.pc)?)?;
        // the first containing block in map order, as the CFG partitions it
        let block = self.index.containing(site).last()?.start.clone();
        let hosts = self.hosted.get(&block).cloned().unwrap_or_default();
        let mut functions = self.containing.get(&block).cloned().unwrap_or_default();
        if register != 31
            && !functions.iter().chain(&hosts).all(|f| {
                holds_entry_ra(image, &self.sizes, &body_from(&self.succ, f), f, register)
                    == Some(true)
            })
        {
            return None;
        }
        let continuations: BTreeSet<_> = functions
            .iter()
            .filter_map(|f| self.callers.get(f))
            .flatten()
            .map(|c| CodeAddress {
                pc: if c.image == image.base.image && c.generation == image.base.generation {
                    image.sequential_pc(c.pc, 8)
                } else {
                    GuestAddr(c.pc.0.wrapping_add(8))
                },
                ..c.clone()
            })
            .collect();
        let runtime_entered = functions.iter().any(|f| self.entered.contains(f));
        let host_entered = !hosts.is_empty();
        functions.extend(hosts);
        if functions.is_empty() || (continuations.is_empty() && !runtime_entered && !host_entered) {
            return None;
        }
        Some(ReturnCertificate {
            site: site.clone(),
            functions,
            continuations,
            runtime_entered,
            host_entered,
        })
    }

    pub fn verify(&self, map: &ProgramMap, image: &CodeImage, site: &IndirectSite) -> bool {
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
        self.certificate(image, &site.site).as_ref() == Some(&proof)
            && site.candidates.keys().cloned().collect::<BTreeSet<_>>() == proof.continuations
            && site
                .observed
                .keys()
                .all(|a| proof.continuations.contains(a))
    }
}

/// Recompute the certificate from the current CFG and bytes.
pub fn certificate(
    map: &ProgramMap,
    image: &CodeImage,
    site: &CodeAddress,
) -> Option<ReturnCertificate> {
    Closure::new(map, image).certificate(image, site)
}

pub fn verify(map: &ProgramMap, image: &CodeImage, site: &IndirectSite) -> bool {
    Closure::new(map, image).verify(map, image, site)
}

/// Attach return certificates to otherwise unproven `jr $ra` sites.
pub fn annotate(map: &ProgramMap, image: &CodeImage) -> Result<ProgramMap, String> {
    let mut out = map.clone();
    let mut sites = BTreeSet::new();
    let closure = Closure::new(map, image);
    for old in &map.indirect_sites {
        let mut site = old.clone();
        if old.closed_proof.is_none()
            && let Some(proof) = closure.certificate(image, &old.site)
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
