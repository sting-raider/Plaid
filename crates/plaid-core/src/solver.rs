//! Closure of a declared finite CFG is distinct from whole-ROM native readiness.
use crate::{
    discovery::{CodeImage, decode, direct_cfg_bounded},
    evidence_manifest::DiscoveryTraceManifestSet,
    indirect::{MapIndex, verify_constant_in},
    program::*,
    rom::{CanonicalRom, sha256},
    trace::DiscoveryTrace,
    trace_projection::verify_discovery_trace_execution_projection_with_rom,
};
use serde::Serialize;
use std::collections::{BTreeMap, BTreeSet};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Scope {
    WholeRom,
    DeclaredStaticImages,
    /// Declared static images plus RDRAM data loads/stores and pure HI/LO and
    /// compare arithmetic. Stores must never reach executable bytes; a native
    /// artifact checks every store and aborts on overlap (ADR-0126).
    DeclaredStaticImagesGuardedRam,
    /// The guarded scope plus address-taken dispatch (ADR-0153): a register
    /// call with no other proof targets one of the map's address-taken
    /// functions; a native artifact dispatches over that set and faults 3
    /// on any other target.
    DeclaredStaticImagesGuardedRamAddressTaken,
    /// VALIDATION ONLY (ADR-0218): the address-taken scope, except that an
    /// indirect site with no closure proof is accepted as a residual site. A
    /// native artifact dispatches it over every lowered entry and faults 3 on
    /// any other target. The report stays `native_complete: false` and lists
    /// the residual sites; every other blocker still refuses.
    DeclaredStaticImagesGuardedRamResidualDispatch,
}

impl Scope {
    fn is_static(self) -> bool {
        matches!(
            self,
            Scope::DeclaredStaticImages
                | Scope::DeclaredStaticImagesGuardedRam
                | Scope::DeclaredStaticImagesGuardedRamAddressTaken
                | Scope::DeclaredStaticImagesGuardedRamResidualDispatch
        )
    }
    /// The guarded scope's checked assumptions apply.
    pub fn guarded(self) -> bool {
        matches!(
            self,
            Scope::DeclaredStaticImagesGuardedRam
                | Scope::DeclaredStaticImagesGuardedRamAddressTaken
                | Scope::DeclaredStaticImagesGuardedRamResidualDispatch
        )
    }
    fn address_taken(self) -> bool {
        matches!(
            self,
            Scope::DeclaredStaticImagesGuardedRamAddressTaken
                | Scope::DeclaredStaticImagesGuardedRamResidualDispatch
        )
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ClosureStatus {
    Open,
    Closed,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize)]
pub struct Blocker {
    pub kind: String,
    pub site: Option<CodeAddress>,
    pub detail: String,
    pub evidence: EvidenceRefs,
}

#[derive(Debug, Clone, Serialize)]
pub struct SolveReport {
    pub schema_version: u32,
    pub scope: Scope,
    pub status: ClosureStatus,
    /// Discovery is necessary but insufficient for a verified native package.
    pub native_complete: bool,
    pub assumptions: Vec<String>,
    pub blockers: BTreeSet<Blocker>,
    pub discharged: BTreeSet<Unresolved>,
    /// Residual-dispatch mode only (ADR-0218): sites lowered as fail-closed
    /// dispatch over every lowered entry instead of a closed-target proof.
    #[serde(skip_serializing_if = "BTreeSet::is_empty")]
    pub residual_sites: BTreeSet<CodeAddress>,
}

/// Closure admission with independently preserved discovery-source expectations.
/// This authenticates raw primitives, installed entries, compiled roots and
/// supplied instruction snapshots, not sensor completeness or every derived
/// fact in the map. Other source domains
/// and all existing closure obligations still require their own verification.
#[derive(Debug, Clone, Serialize)]
pub struct DiscoverySourceSolveReport {
    pub format: String,
    /// Commitment to the exact canonical map passed to the solver.
    pub map_sha256: String,
    pub discovery_sources: DiscoveryTraceManifestSet,
    pub closure: SolveReport,
}

pub struct DiscoverySourceInputs<'a> {
    pub expected: &'a DiscoveryTraceManifestSet,
    pub traces: &'a [DiscoveryTrace],
    pub rom: &'a CanonicalRom,
    /// Known images supplied at the original import, which can differ from the
    /// instruction witnesses supplied to the solver.
    pub known_images: &'a [CodeImage],
    pub import_budget: usize,
}

/// Authenticate the external source set and its primitive/entry/compilation
/// projections before solving. Preserve `expected` outside editable artifacts;
/// constructing it from the submitted sources here would defeat deletion
/// resistance. Re-import uses the same known images and budget as the original
/// trace import. It never upgrades finite observations into a coverage proof.
pub fn solve_with_discovery_sources(
    map: &ProgramMap,
    images: &[CodeImage],
    scope: Scope,
    sources: &DiscoverySourceInputs<'_>,
) -> Result<DiscoverySourceSolveReport, String> {
    if map.rom != sources.rom.identity {
        return Err("map does not match canonical ROM".into());
    }
    sources
        .expected
        .verify_primitive_projections(map, sources.traces)?;
    for trace in sources.traces {
        verify_discovery_trace_execution_projection_with_rom(
            trace,
            sources.known_images,
            sources.rom,
            map,
            images,
            sources.import_budget,
        )?;
    }
    let closure = solve(map, images, scope)?;
    Ok(DiscoverySourceSolveReport {
        format: "plaid-discovery-source-solve-v0".into(),
        map_sha256: sha256(map.to_json()?.as_bytes()),
        discovery_sources: sources.expected.clone(),
        closure,
    })
}

/// Where the declared loads of `image` begin (ADR-0182).
fn load_starts(map: &ProgramMap, image: &CodeImage) -> BTreeSet<u32> {
    map.load_images
        .get(&image.base.image)
        .into_iter()
        .flat_map(|spec| spec.loads.iter().map(|l| l.destination.start.0))
        .collect()
}

fn source<'a>(images: &'a [CodeImage], address: &CodeAddress) -> Option<&'a CodeImage> {
    let mut found = images.iter().filter(|i| {
        i.base.image == address.image
            && i.base.generation == address.generation
            && i.word(address.pc).is_some()
    });
    let first = found.next()?;
    if found.next().is_some() {
        return None;
    }
    Some(first)
}

fn content_digest_claim(image: &str) -> Option<&str> {
    let digest = image.strip_prefix("trace-").unwrap_or(image);
    (digest.len() == 64
        && digest
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b)))
    .then_some(digest)
}

fn content_digest(image: &CodeImage) -> String {
    image.content_identity()
}

fn conflicting_region_provenance(a: &Region, b: &Region) -> Option<CodeAddress> {
    if a.image != b.image || a.generation != b.generation {
        return None;
    }
    let overlap_start = u64::from(a.range.start.0).max(u64::from(b.range.start.0));
    let overlap_end = a.range.end().min(b.range.end());
    if overlap_start >= overlap_end {
        return None;
    }
    let a_delta = overlap_start - u64::from(a.range.start.0);
    let b_delta = overlap_start - u64::from(b.range.start.0);
    let rom_conflict = match (a.rom_offset, b.rom_offset) {
        (Some(a_offset), Some(b_offset)) => a_offset.0 + a_delta != b_offset.0 + b_delta,
        _ => false,
    };
    let physical_conflict = match (a.physical_start, b.physical_start) {
        (Some(a_start), Some(b_start)) => {
            u64::from(a_start.0) + a_delta != u64::from(b_start.0) + b_delta
        }
        _ => false,
    };
    (rom_conflict || physical_conflict).then_some(CodeAddress {
        pc: crate::GuestAddr(overlap_start as u32),
        image: a.image.clone(),
        generation: a.generation,
    })
}

fn supplied_region_provenance_conflict(
    image: &CodeImage,
    region: &Region,
    pc: crate::GuestAddr,
) -> bool {
    let Some(image_delta) = pc.0.checked_sub(image.base.pc.0) else {
        return false;
    };
    let Some(region_delta) = pc.0.checked_sub(region.range.start.0) else {
        return false;
    };
    let rom_conflict = match (image.rom_offset, region.rom_offset) {
        (Some(image_offset), Some(region_offset)) => {
            image_offset.0.checked_add(u64::from(image_delta))
                != region_offset.0.checked_add(u64::from(region_delta))
        }
        _ => false,
    };
    let physical_conflict = match (image.physical_start, region.physical_start) {
        (Some(image_start), Some(region_start)) => {
            u64::from(image_start.0) + u64::from(image_delta)
                != u64::from(region_start.0) + u64::from(region_delta)
        }
        _ => false,
    };
    rom_conflict || physical_conflict
}

fn static_identity_blockers(
    map: &ProgramMap,
    images: &[CodeImage],
    scope: Scope,
) -> BTreeSet<Blocker> {
    let mut blockers = BTreeSet::new();

    // Production image constructors currently use raw SHA-256 identities for
    // ROM/load images and `trace-<SHA-256>` for trace-only images. Opaque v0
    // labels remain compatible until CodeImage grows a mandatory content digest.
    for image in images {
        if let Some(claimed) = content_digest_claim(&image.base.image)
            && content_digest(image) != claimed
        {
            blockers.insert(Blocker {
                kind: "instruction_source_identity_mismatch".into(),
                site: Some(image.base.clone()),
                detail:
                    "supplied instruction bytes do not match their content-derived image identity"
                        .into(),
                evidence: EvidenceRefs::new(),
            });
        }
    }

    // Fragment boundaries cannot hide two values for one exact execution
    // identity and guest PC. Check supplied words before selecting block roots.
    let mut words: BTreeMap<(&str, u64, u32), u32> = BTreeMap::new();
    let mut holders: BTreeMap<(&str, u64), usize> = BTreeMap::new();
    for image in images {
        *holders
            .entry((image.base.image.as_str(), image.base.generation))
            .or_default() += 1;
    }
    for image in images {
        // One image's words have distinct PCs: only another image with the
        // same identity can disagree with them.
        if holders[&(image.base.image.as_str(), image.base.generation)] < 2 {
            continue;
        }
        for (index, word) in image.words.iter().copied().enumerate() {
            let pc = crate::GuestAddr(image.base.pc.0 + (index as u32) * 4);
            let key = (image.base.image.as_str(), image.base.generation, pc.0);
            if let Some(previous) = words.get(&key) {
                if *previous != word {
                    let site = image.address(pc);
                    let evidence = map
                        .regions
                        .iter()
                        .filter(|region| {
                            region.image == site.image
                                && region.generation == site.generation
                                && region.range.contains(site.pc)
                        })
                        .flat_map(|region| region.evidence.iter().cloned())
                        .collect();
                    blockers.insert(Blocker {
                        kind: "conflicting_instruction_sources".into(),
                        site: Some(site),
                        detail: "supplied CodeImage fragments disagree on bytes for one execution identity"
                            .into(),
                        evidence,
                    });
                }
            } else {
                words.insert(key, word);
            }
        }
    }

    if !scope.is_static() {
        return blockers;
    }

    // Two distinct immutable identities cannot simultaneously own the same
    // decoded guest instruction bytes without a mapping/lifetime selector.
    // Each identity's blocks sorted by start, with the largest size, so a block
    // finds its overlaps in another identity by binary search.
    let mut identities: BTreeMap<(&str, u64), (Vec<&BasicBlock>, u64)> = BTreeMap::new();
    for b in &map.blocks {
        let (list, max) = identities
            .entry((b.start.image.as_str(), b.start.generation))
            .or_default();
        list.push(b);
        *max = (*max).max(u64::from(b.size));
    }
    for (list, _) in identities.values_mut() {
        list.sort_by_key(|b| b.start.pc.0);
    }
    let identities: Vec<_> = identities.into_values().collect();
    for (index, (blocks, _)) in identities.iter().enumerate() {
        for (others, max) in &identities[index + 1..] {
            for a in blocks {
                let a_start = u64::from(a.start.pc.0);
                let a_end = a_start + u64::from(a.size);
                let end = others.partition_point(|b| u64::from(b.start.pc.0) < a_end);
                for b in others[..end]
                    .iter()
                    .rev()
                    .take_while(|b| u64::from(b.start.pc.0) + max > a_start)
                {
                    let b_start = u64::from(b.start.pc.0);
                    let b_end = b_start + u64::from(b.size);
                    if a_start < b_end && b_start < a_end {
                        blockers.insert(Blocker {
                    kind: "ambiguous_guest_executable_identity".into(),
                    site: None,
                    detail: "distinct decoded executable image/generation identities overlap guest address space; mapping/lifetime selection is unproven"
                        .into(),
                    evidence: a.evidence.union(&b.evidence).cloned().collect(),
                });
                    }
                }
            }
        }
    }

    // Region rows are independent observations. For one identity, all
    // simultaneously-known affine backing facts must agree over their guest
    // intersection. Across identities, overlapping known physical backing needs
    // an alias/lifetime relation; absent backing remains unknown rather than
    // being inferred from virtual address shape or equal payloads.
    let regions: Vec<_> = map.regions.iter().collect();
    for (index, a) in regions.iter().enumerate() {
        for b in &regions[index + 1..] {
            if a.image == b.image && a.generation == b.generation {
                if let Some(site) = conflicting_region_provenance(a, b) {
                    blockers.insert(Blocker {
                        kind: "conflicting_region_provenance".into(),
                        site: Some(site),
                        detail: "overlapping regions for one executable identity assert incompatible ROM or physical backing"
                            .into(),
                        evidence: a.evidence.union(&b.evidence).cloned().collect(),
                    });
                }
                continue;
            }

            let (Some(a_physical), Some(b_physical)) = (a.physical_start, b.physical_start) else {
                continue;
            };
            let a_start = u64::from(a_physical.0);
            let a_end = a_start + u64::from(a.range.size);
            let b_start = u64::from(b_physical.0);
            let b_end = b_start + u64::from(b.range.size);
            if a_start < b_end && b_start < a_end {
                blockers.insert(Blocker {
                    kind: "ambiguous_physical_executable_identity".into(),
                    site: None,
                    detail: "distinct executable image/generation identities overlap explicit physical backing; alias/lifetime equivalence is unproven"
                        .into(),
                    evidence: a.evidence.union(&b.evidence).cloned().collect(),
                });
            }
        }
    }

    blockers
}

/// COP0 moves lower to register-specific checked state operations (ADR-0235).
/// Unmodeled registers fault explicitly; no timer/exception values are invented.
pub fn is_cop0_move(word: u32) -> bool {
    word >> 26 == 16 && matches!((word >> 21) & 31, 0 | 1 | 4 | 5) && word & 0x7ff == 0
}

/// TLBWI/TLBR/TLBP; Random-dependent TLBWR remains outside the native subset.
pub fn is_cop0_tlb(word: u32) -> bool {
    matches!(word, 0x4200_0001 | 0x4200_0002 | 0x4200_0008)
}

/// ERET has a runtime-checked state transition, but no static return-target proof.
pub fn is_eret(word: u32) -> bool {
    word == 0x4200_0018
}

/// COP1 data moves: MFC1 DMFC1 MTC1 DMTC1 LWC1 LDC1 SWC1 SDC1 (ADR-0131).
pub fn is_cop1_move(word: u32) -> bool {
    match word >> 26 {
        17 => matches!((word >> 21) & 31, 0 | 1 | 4 | 5) && word & 0x7ff == 0,
        49 | 53 | 57 | 61 => true,
        _ => false,
    }
}

/// COP1 arithmetic, conversions and FCSR access lowered under the guarded
/// scope (ADR-0139/0143): ADD SUB MUL DIV SQRT ABS MOV NEG .S/.D,
/// CVT/ROUND/TRUNC/CEIL/FLOOR to W and L from S/D, CVT.S from D/W/L, CVT.D
/// from S/W/L, CFC1, CTC1.
pub fn is_cop1_arith(word: u32) -> bool {
    let (fmt, f) = ((word >> 21) & 31, word & 63);
    word >> 26 == 17
        && match fmt {
            2 | 6 => word & 0x7ff == 0,
            16 | 17 => {
                matches!(f, 0..=15 | 36 | 37) || (f == 32 && fmt == 17) || (f == 33 && fmt == 16)
            }
            20 | 21 => matches!(f, 32 | 33),
            _ => false,
        }
}

/// `BREAK` (ADR-0138): a checked abort in the guarded scope.
pub fn is_break(word: u32) -> bool {
    word >> 26 == 0 && word & 63 == 13
}

/// COP1 `C.cond.S/D` compares (ADR-0135).
pub fn is_cop1_compare(word: u32) -> bool {
    word >> 26 == 17 && matches!((word >> 21) & 31, 16 | 17) && word & 0x7f0 == 0x30
}

/// `BC1F BC1T BC1FL BC1TL` (ADR-0135).
pub fn is_cop1_branch(word: u32) -> bool {
    word >> 26 == 17 && (word >> 21) & 31 == 8 && (word >> 18) & 7 == 0
}

fn allowed_static_effect(word: u32, pc: crate::GuestAddr, guarded_ram: bool) -> bool {
    if guarded_ram
        && (is_cop0_move(word)
            || is_cop0_tlb(word)
            || is_eret(word)
            || is_cop1_move(word)
            || is_cop1_compare(word)
            || is_cop1_branch(word)
            || is_cop1_arith(word)
            || is_break(word)
            || crate::discovery::is_conditional_trap(word))
    {
        return true;
    }
    let i = decode(word, pc);
    if !i.is_valid() || i.is_trap() || i.is_float() {
        return false;
    }
    if i.is_branch() {
        return matches!(word >> 26, 1 | 4..=7 | 20..=23);
    }
    if i.is_jump() {
        return matches!(word >> 26, 2 | 3) || (word >> 26 == 0 && matches!(word & 63, 8 | 9));
    }
    if guarded_ram
        && match word >> 26 {
            0 => matches!(
                word & 63,
                4 | 6 | 7 | 16..=20 | 22..=32 | 34 | 42..=44 | 46 | 47 | 56 | 58..=60 | 62 | 63
            ),
            // LL LLD SC SCD (ADR-0145) are guarded memory accesses too.
            8 | 10 | 11 | 24 | 26 | 27 | 32..=39 | 40..=46 | 48 | 52 | 55 | 56 | 60 | 63 => true,
            _ => false,
        }
    {
        return true;
    }
    match word >> 26 {
        9 | 12 | 13 | 14 | 15 | 25 => true,
        // SYNC (15) is a no-op on the VR4300.
        0 => matches!(word & 63, 0 | 2 | 3 | 15 | 33 | 35 | 36 | 37 | 38 | 39 | 45),
        _ => false,
    }
}

pub fn solve(map: &ProgramMap, images: &[CodeImage], scope: Scope) -> Result<SolveReport, String> {
    map.validate()?;
    for image in images {
        GuestRange {
            start: image.base.pc,
            size: image.size()?,
        }
        .validate(true)?;
    }
    let mut blockers = static_identity_blockers(map, images, scope);
    if let Err(detail) = crate::signatures::verify_status_abi(map) {
        blockers.insert(Blocker {
            kind: "runtime_status_abi".into(),
            site: None,
            detail,
            evidence: BTreeSet::new(),
        });
    }
    let mut discharged = BTreeSet::new();
    let mut add = |kind: &str, site: Option<CodeAddress>, detail: &str, evidence: EvidenceRefs| {
        blockers.insert(Blocker {
            kind: kind.into(),
            site,
            detail: detail.into(),
            evidence,
        });
    };
    let starts: BTreeSet<_> = map
        .blocks
        .iter()
        .filter(|b| !b.delay_slot_entry)
        .map(|b| b.start.clone())
        .collect();
    let mut valid_slots = BTreeSet::new();
    for image in images {
        if crate::declared_loads::verify_slots(image, map.load_images.get(&image.base.image)) {
            valid_slots.insert(image.base.image.clone());
        } else {
            add(
                "slot_metadata_mismatch",
                Some(image.base.clone()),
                "slot mappings, text bounds and content identity must match the declared loads",
                EvidenceRefs::new(),
            );
        }
    }
    // A call into a slot (ADR-0185) lands on whichever alternate RAM holds:
    // closed when some alternate has a block there; the binding verifies the
    // one that runs, and none faults.
    let into_slot = |a: &CodeAddress| {
        scope.guarded()
            && images.iter().any(|i| {
                i.base.image == a.image
                    && valid_slots.contains(&i.base.image)
                    && i.base.generation == a.generation
                    && i.slots.iter().any(|(placed, linked, text)| {
                        let off = a.pc.0.wrapping_sub(*linked);
                        off < *text
                            && map.load_images.get(&i.base.image).is_some_and(|spec| {
                                spec.loads.iter().any(|l| {
                                    l.relocatable
                                        && l.destination == *placed
                                        && l.linked == Some(crate::GuestAddr(*linked))
                                })
                            })
                            && starts.contains(&i.address(crate::GuestAddr(placed.start.0 + off)))
                    })
            })
    };
    // A reachable BREAK or conditional trap aborts natively in the guarded
    // scope (ADR-0138/0145).
    let checked_word = |u: &Unresolved, accept: fn(u32) -> bool| {
        scope.guarded()
            && u.kind == "exception_or_unsupported_instruction"
            && u.site.as_ref().is_some_and(|a| {
                source(images, a)
                    .and_then(|image| image.word(a.pc))
                    .is_some_and(accept)
            })
    };
    let checked_trap = |u: &Unresolved| checked_word(u, crate::discovery::is_conditional_trap);
    let checked_break = |u: &Unresolved| checked_word(u, is_break) || checked_trap(u);
    let checked_eret = |u: &Unresolved| checked_word(u, is_eret);
    if !map.fetch_observations.is_empty() {
        add(
            "fetch_execution_identity_unknown",
            None,
            "raw fetched words have no established image generation, lifetime or retirement identity",
            map.fetch_observations
                .iter()
                .flat_map(|f| f.evidence.clone())
                .collect(),
        );
    }
    if map.fetch_observations.is_empty() && !map.fetch_captures.is_empty() {
        add(
            "unverified_fetch_capture",
            None,
            "retained raw fetch capture metadata cannot prove zero observed execution without complete raw-source verification",
            map.fetch_captures.keys().cloned().collect(),
        );
    }
    for dispatch in &map.target_dispatch_observations {
        add(
            "unresolved_raw_target_dispatch",
            None,
            "retained target lookup/runtime link lacks source-site execution correlation",
            dispatch.evidence.clone(),
        );
    }
    for observation in &map.indirect_observations {
        let possible_sources: Vec<_> = map
            .indirect_sites
            .iter()
            .filter(|site| {
                site.site.pc == observation.site
                    && match &observation.source_unit {
                        Some(unit) => site.evidence.contains(unit),
                        None => site.site.generation == observation.generation,
                    }
            })
            .collect();
        let event_refs: EvidenceRefs = observation
            .evidence
            .iter()
            // Explicit reusable source-unit context is not a transfer event.
            .filter(|id| observation.source_unit.as_ref() != Some(*id))
            .cloned()
            .collect();
        let mut unresolved_evidence: EvidenceRefs = event_refs
            .iter()
            .filter(|raw_ref| {
                possible_sources
                    .iter()
                    .flat_map(|site| site.observed.iter())
                    .filter(|(target, refs)| {
                        target.pc == observation.target && refs.contains(*raw_ref)
                    })
                    .count()
                    != 1
            })
            .cloned()
            .collect();
        if event_refs.is_empty() {
            // Context alone cannot witness that a concrete transfer occurred.
            unresolved_evidence = observation.evidence.clone();
        }
        if !unresolved_evidence.is_empty() {
            add(
                "unresolved_raw_indirect_execution",
                if possible_sources.len() == 1 {
                    Some(possible_sources[0].site.clone())
                } else {
                    None
                },
                "raw executed indirect transfer lacks exactly one provenance-linked declared source/target identity",
                unresolved_evidence,
            );
        }
    }
    for verification in &map.entry_verifications {
        if verification.register_mask != 0 {
            let mut evidence = verification.evidence.clone();
            evidence.insert(verification.source_unit.clone());
            add(
                "restricted_entry",
                Some(verification.entry.clone()),
                &format!(
                    "retained entry verification records unsupported register-state mask {:08x}",
                    verification.register_mask
                ),
                evidence,
            );
        }
        if scope.is_static() && verification.generation != 0 {
            add(
                "entry_verification_after_invalidation",
                Some(verification.entry.clone()),
                "entry bytes were verified after an observed invalidation; executable lifetime is not closed for immutable static scope",
                verification.evidence.clone(),
            );
        }
    }
    if map.entries.is_empty() {
        add(
            "missing_entry_universe",
            None,
            "no executable roots are declared",
            EvidenceRefs::new(),
        );
    }
    for (entry, refs) in &map.entries {
        if !starts.contains(entry) {
            add(
                "missing_entry_block",
                Some(entry.clone()),
                "entry has no normal decoded block",
                refs.clone(),
            );
        }
    }
    let (mut uses_cop0, mut uses_cop1, mut uses_compare) = (false, false, false);
    for b in &map.blocks {
        if b.delay_slot_entry {
            add(
                "unsupported_delay_slot_entry",
                Some(b.start.clone()),
                "special predecessor state is not modeled",
                b.evidence.clone(),
            );
        }
        let Some(image) = source(images, &b.start) else {
            add(
                "missing_instruction_source",
                Some(b.start.clone()),
                "no unique instruction image supplied for this block",
                b.evidence.clone(),
            );
            continue;
        };
        let range = GuestRange {
            start: b.start.pc,
            size: b.size,
        };
        for offset in (0..b.size).step_by(4) {
            let pc = crate::GuestAddr(b.start.pc.0 + offset);
            let Some(word) = image.word(pc) else {
                add(
                    "missing_instruction_source",
                    Some(image.address(pc)),
                    "block extends beyond supplied instruction bytes",
                    b.evidence.clone(),
                );
                continue;
            };
            uses_cop0 |= is_cop0_move(word) || is_cop0_tlb(word) || is_eret(word);
            uses_compare |= is_cop1_compare(word) || is_cop1_arith(word);
            uses_cop1 |= is_cop1_move(word)
                || is_cop1_compare(word)
                || is_cop1_branch(word)
                || is_cop1_arith(word);
            if scope.is_static() && !allowed_static_effect(word, pc, scope.guarded()) {
                add(
                    "unsupported_scope_effect",
                    Some(image.address(pc)),
                    "declared immutable integer scope excludes memory, COP, trapping and unsupported effects",
                    b.evidence.clone(),
                );
            }
        }
        let covering_regions: Vec<_> = map
            .regions
            .iter()
            .filter(|r| {
                r.image == b.start.image
                    && r.generation == b.start.generation
                    && r.range.start.0 <= b.start.pc.0
                    && r.range.end() >= range.end()
            })
            .collect();
        if covering_regions.is_empty() {
            add(
                "unknown_executable_region",
                Some(b.start.clone()),
                "block is not contained by a matching executable region",
                b.evidence.clone(),
            );
        } else {
            for region in covering_regions {
                if supplied_region_provenance_conflict(image, region, b.start.pc) {
                    add(
                        "supplied_image_provenance_conflict",
                        Some(b.start.clone()),
                        "supplied instruction image contradicts explicit executable Region provenance",
                        region.evidence.clone(),
                    );
                }
            }
        }
    }
    let index = MapIndex::new(map);
    for edge in &map.direct_edges {
        if index.containing(&edge.site).is_empty() {
            add(
                "unmapped_direct_site",
                Some(edge.site.clone()),
                "edge source is outside all decoded blocks",
                edge.evidence.clone(),
            );
        }
        let into_runtime = matches!(edge.kind, EdgeKind::Call | EdgeKind::Jump)
            && map.runtime_functions.contains_key(&edge.target);
        if !starts.contains(&edge.target)
            && !into_runtime
            && !((edge.kind == EdgeKind::Call
                || !(0x8000_0000..0xc000_0000).contains(&edge.target.pc.0))
                && into_slot(&edge.target))
        {
            add(
                "unresolved_direct_target",
                Some(edge.site.clone()),
                &format!("no decoded block at target {:?}", edge.target),
                edge.evidence.clone(),
            );
        }
    }
    // Declared runtime functions (ADR-0129) close calls into them only under the
    // guarded scope's explicit ABI assumption; their bodies must stay undecoded.
    let runtime_ok = scope.guarded();
    for (a, f) in &map.runtime_functions {
        if !runtime_ok {
            add(
                "runtime_boundary_outside_scope",
                Some(a.clone()),
                "declared runtime functions are accepted only under the guarded assumption scope",
                f.evidence.clone(),
            );
        }
        if !index.containing(a).is_empty() {
            add(
                "runtime_function_decoded",
                Some(a.clone()),
                "a declared runtime function's bytes are also decoded as guest code",
                f.evidence.clone(),
            );
        }
    }
    let mut forwarded_callbacks = false;
    for image in images {
        for c in crate::callbacks::callbacks(map, image) {
            forwarded_callbacks |= c.forwarded && c.target.is_some();
            if !c.target.as_ref().is_some_and(|t| starts.contains(t)) {
                let evidence = map
                    .direct_edges
                    .iter()
                    .find(|e| e.site == c.site)
                    .map(|e| e.evidence.clone())
                    .unwrap_or_default();
                add(
                    "unresolved_runtime_callback",
                    Some(c.site.clone()),
                    &format!(
                        "guest code passed to a runtime function in r{} has no proven target block",
                        c.register
                    ),
                    evidence,
                );
            }
        }
    }
    let mut return_closure = false;
    let mut tables = BTreeSet::new();
    // One shared return-closure context per image, not one per site.
    let mut closures: BTreeMap<String, crate::returns::Closure> = BTreeMap::new();
    // Address-taken dispatch (ADR-0153): every address-taken function must be
    // a decoded block start whose layout and body can be a CPU function, or
    // a declared runtime function, which the host calls (ADR-0185).
    let load_starts: BTreeMap<&str, _> = images
        .iter()
        .map(|image| (image.base.image.as_str(), load_starts(map, image)))
        .collect();
    let address_taken_ok = scope.address_taken()
        && !map.address_taken.is_empty()
        && map.address_taken.keys().all(|a| {
            (starts.contains(a) || map.runtime_functions.contains_key(a))
                && source(images, a).is_some_and(|image| {
                    let starts = &load_starts[image.base.image.as_str()];
                    // A replayed call stands in for the layout clue (ADR-0226).
                    let called = map.address_taken[a].iter().any(|id| {
                        map.evidence
                            .get(id)
                            .is_some_and(|e| e.producer == crate::data_roots::OBSERVED_CALL)
                    });
                    crate::data_roots::plausible_at(image, a.pc, starts)
                        || called && crate::data_roots::executed_start(image, a.pc)
                })
        });
    let mut uses_address_taken = false;
    let mut residual_sites = BTreeSet::new();
    for site in &map.indirect_sites {
        // Return certificates hold only under the guarded scope's checked
        // call/return assumption; every other scope keeps such sites OPEN.
        let returns = scope.guarded()
            && source(images, &site.site).is_some_and(|image| {
                closures
                    .entry(image.base.image.clone())
                    .or_insert_with(|| crate::returns::Closure::new(map, image))
                    .verify(map, image, site)
            });
        return_closure |= returns;
        // A verified jump table closes only under the guarded scope, whose
        // native artifact store-protects table bytes (ADR-0132).
        let table = scope.guarded()
            && source(images, &site.site).is_some_and(|image| {
                crate::tables::verify_in(&index, map, image, site)
                    || crate::tail_cells::verify_in(&index, map, image, site)
            });
        if table {
            tables.insert(site.site.clone());
        }
        let constant = source(images, &site.site)
            .is_some_and(|image| verify_constant_in(&index, map, image, site));
        let dispatched =
            !returns && !table && !constant && address_taken_ok && site.link_register.is_some();
        uses_address_taken |= dispatched;
        let proof_valid = returns || table || constant || dispatched;
        // Native code cannot run from SP memory: a residual site faults there
        // instead of requiring a block that cannot exist (ADR-0256).
        let sp_memory = |target: &CodeAddress| {
            (0x8000_0000..0xc000_0000).contains(&target.pc.0)
                && (0x0400_0000..0x0400_2000).contains(&(target.pc.0 & 0x1fff_ffff))
                && !site.observed.contains_key(target)
        };
        let residual = (!proof_valid || site.candidates.keys().any(sp_memory))
            && scope == Scope::DeclaredStaticImagesGuardedRamResidualDispatch;
        if residual {
            residual_sites.insert(site.site.clone());
        }
        if !proof_valid && !residual {
            add(
                "unresolved_indirect_site",
                Some(site.site.clone()),
                "finite candidates or samples are insufficient; no rechecked closed-target certificate",
                site.evidence.clone(),
            );
        }
        for target in site.candidates.keys().chain(site.observed.keys()) {
            if !starts.contains(target)
                && !(residual && sp_memory(target))
                && !(site.link_register.is_some() && map.runtime_functions.contains_key(target))
                && !((site.link_register.is_some()
                    || !(0x8000_0000..0xc000_0000).contains(&target.pc.0))
                    && into_slot(target))
            {
                add(
                    "unresolved_indirect_target",
                    Some(site.site.clone()),
                    &format!("candidate/observed target {:?} has no block", target),
                    site.evidence.clone(),
                );
            }
        }
        // Candidate hypotheses may be incomplete, including an empty set.
        // Only a claimed exhaustive set can contradict execution evidence.
        // Rechecking still rejects a certificate with an out-of-set sample.
        if site.closed_proof.is_some()
            && site
                .observed
                .keys()
                .any(|a| !site.candidates.contains_key(a))
        {
            add(
                "indirect_evidence_disagreement",
                Some(site.site.clone()),
                "observed target is outside the claimed closed target set",
                site.evidence.clone(),
            );
        }
    }
    // Re-derive instruction control flow. A hand-edited/partial map cannot close
    // merely by deleting its missing edges or indirect sites.
    for image in images {
        let roots: BTreeSet<_> = starts
            .iter()
            .chain(map.entries.keys())
            .filter(|a| {
                a.image == image.base.image
                    && a.generation == image.base.generation
                    && image.word(a.pc).is_some()
            })
            .map(|a| a.pc)
            .collect();
        if roots.is_empty() {
            continue;
        }
        let boundary: BTreeSet<_> = map
            .runtime_functions
            .keys()
            .filter(|a| a.image == image.base.image && a.generation == image.base.generation)
            .map(|a| a.pc)
            .collect();
        let expected = direct_cfg_bounded(
            map.rom.clone(),
            image,
            &roots.into_iter().collect::<Vec<_>>(),
            image.words.len(),
            &boundary,
        )?
        .map;
        let provenance: EvidenceRefs = map
            .regions
            .iter()
            .filter(|r| r.image == image.base.image && r.generation == image.base.generation)
            .flat_map(|r| r.evidence.iter().cloned())
            .collect();
        let edge_key = |e: &DirectEdge| (e.site.clone(), e.target.clone(), e.kind, e.delay_slot);
        let block_key = |b: &BasicBlock| (b.start.clone(), b.size, b.delay_slot_entry);
        let edges: BTreeSet<_> = map.direct_edges.iter().map(edge_key).collect();
        let sites: BTreeSet<_> = map
            .indirect_sites
            .iter()
            .map(|s| (s.site.clone(), s.link_register, s.delay_slot))
            .collect();
        let blocks: BTreeSet<_> = map.blocks.iter().map(block_key).collect();
        let expected_edges: BTreeSet<_> = expected.direct_edges.iter().map(edge_key).collect();
        let expected_blocks: BTreeSet<_> = expected.blocks.iter().map(block_key).collect();
        for edge in &expected.direct_edges {
            if !edges.contains(&edge_key(edge)) {
                add(
                    "missing_decoded_edge",
                    Some(edge.site.clone()),
                    "instruction bytes require a direct edge absent from the map",
                    provenance.clone(),
                );
            }
        }
        for site in &expected.indirect_sites {
            if !sites.contains(&(site.site.clone(), site.link_register, site.delay_slot)) {
                add(
                    "missing_decoded_indirect_site",
                    Some(site.site.clone()),
                    "instruction bytes require an indirect site absent from the map",
                    provenance.clone(),
                );
            }
        }
        for b in &expected.blocks {
            if !blocks.contains(&block_key(b)) {
                add(
                    "missing_decoded_block",
                    Some(b.start.clone()),
                    "reachable instruction bytes require a block/extent absent from the map",
                    provenance.clone(),
                );
            }
        }
        for b in &map.blocks {
            if b.start.image == image.base.image
                && b.start.generation == image.base.generation
                && image.word(b.start.pc).is_some()
                && !expected_blocks.contains(&block_key(b))
            {
                add(
                    "unexpected_block_extent",
                    Some(b.start.clone()),
                    "declared block disagrees with re-derived block boundaries",
                    b.evidence.clone(),
                );
            }
        }
        for edge in &map.direct_edges {
            if edge.site.image == image.base.image
                && edge.site.generation == image.base.generation
                && image.word(edge.site.pc).is_some()
                && !expected_edges.contains(&edge_key(edge))
            {
                add(
                    "unexpected_decoded_edge",
                    Some(edge.site.clone()),
                    "declared direct edge contradicts instruction-derived control flow",
                    edge.evidence.clone(),
                );
            }
        }
        for u in &expected.unresolved {
            if checked_eret(u) {
                if scope == Scope::DeclaredStaticImagesGuardedRamResidualDispatch {
                    residual_sites.extend(u.site.clone());
                } else {
                    add(
                        "eret_return_target_unknown",
                        u.site.clone(),
                        "ERET requires a closed return-target proof or explicit residual dispatch",
                        u.evidence.clone(),
                    );
                }
            }
            if !(u.kind == "unmapped_target"
                && u.site
                    .as_ref()
                    .is_some_and(|a| starts.contains(a) || into_slot(a)))
                && !checked_break(u)
                && !checked_eret(u)
            {
                add(&u.kind, u.site.clone(), &u.detail, provenance.clone());
            }
        }
    }
    let (mut uses_break, mut uses_trap) = (false, false);
    for u in &map.unresolved {
        let table_obligation = matches!(
            u.kind.as_str(),
            "pointer_table_immutability_unproven" | "pointer_table_target_identity_unproven"
        ) && u.site.as_ref().is_some_and(|a| tables.contains(a));
        let checked_break = checked_break(u);
        uses_trap |= checked_trap(u);
        uses_break |= checked_break && !checked_trap(u);
        if table_obligation
            || checked_break
            || checked_eret(u)
            || (u.kind == "unmapped_target"
                && u.site
                    .as_ref()
                    .is_some_and(|a| starts.contains(a) || into_slot(a)))
        {
            discharged.insert(u.clone());
        } else {
            add(&u.kind, u.site.clone(), &u.detail, u.evidence.clone());
        }
    }
    for o in map.overlays.values() {
        add(
            "unresolved_overlay_lifecycle",
            None,
            if o.candidate {
                "overlay is a candidate; load/unload/relocation policy is unproven"
            } else {
                "overlay lifecycle certificate verifier is not implemented"
            },
            o.evidence.clone(),
        );
    }
    for r in &map.relocations {
        add(
            "unverified_relocation",
            Some(r.site.clone()),
            "relocation semantics certificate verifier is not implemented",
            r.evidence.clone(),
        );
    }
    for w in &map.executable_writes {
        add(
            "unresolved_executable_write",
            None,
            &format!(
                "{:?} event needs a complete executable modification policy",
                w.kind
            ),
            w.evidence.clone(),
        );
    }
    // These successful cached-RDRAM word effects have an explicit direct-segment
    // sink contract. Equal payloads still mutate; missing Region backing is not
    // inferred from the executable virtual address.
    for store in &map.word_store_observations {
        let physical = store.destination.0 & 0x1fff_ffff;
        let overlaps = map.regions.iter().any(|region| {
            region.physical_start.is_some_and(|start| {
                u64::from(start.0) < u64::from(physical) + 4
                    && u64::from(physical) < u64::from(start.0) + u64::from(region.range.size)
            })
        });
        let represented = map
            .executable_writes
            .iter()
            .any(|write| write.evidence == store.evidence);
        if overlaps && !represented {
            add(
                "unresolved_executable_write",
                None,
                "retained successful cached-RDRAM store overlaps explicit executable backing but its derived executable-write fact is absent",
                store.evidence.clone(),
            );
        }
    }
    if scope.is_static() && !map.word_store_observations.is_empty() {
        add(
            "dynamic_effect_outside_scope",
            None,
            "declared static scope cannot include successful word-store execution",
            map.word_store_observations
                .iter()
                .flat_map(|store| store.evidence.clone())
                .collect(),
        );
    }
    if scope.is_static()
        && (!map.loads.is_empty()
            || !map.dma_observations.is_empty()
            || !map.rsp_microcodes.is_empty())
    {
        add(
            "dynamic_effect_outside_scope",
            None,
            "declared static scope cannot include loads or RSP execution",
            EvidenceRefs::new(),
        );
    }
    // Declared loads (ADR-0136): only the guarded scope checks them natively.
    let load_evidence: EvidenceRefs = map
        .load_images
        .values()
        .flat_map(|spec| spec.loads.iter().flat_map(|l| l.evidence.clone()))
        .collect();
    if !map.load_images.is_empty() && !scope.guarded() {
        add(
            "dynamic_effect_outside_scope",
            None,
            "declared loads are accepted only under the guarded scope",
            load_evidence.clone(),
        );
    }
    for (id, spec) in &map.load_images {
        for b in map.blocks.iter().filter(|b| &b.start.image == id) {
            let (start, end) = (
                u64::from(b.start.pc.0),
                u64::from(b.start.pc.0) + u64::from(b.size),
            );
            for l in &spec.loads {
                let (ls, le) = (u64::from(l.destination.start.0), l.destination.end());
                if start < le && end > ls && !(start >= ls && end <= le) {
                    add(
                        "block_straddles_declared_load",
                        Some(b.start.clone()),
                        "a block runs between base bytes and a declared load, so one entry check cannot cover it",
                        l.evidence.clone(),
                    );
                }
            }
        }
    }
    if scope == Scope::WholeRom {
        for (kind, detail) in [
            (
                "unproven_executable_universe",
                "whole-ROM executable roots, boot and mapping universe have no verified closure certificate",
            ),
            (
                "unmodeled_exception_paths",
                "exception/interrupt entry coverage and dispatch are unproven",
            ),
            (
                "unproven_load_overlay_policy",
                "all future executable DMA, copies, overlays and relocations are unproven",
            ),
            (
                "unproven_executable_write_policy",
                "absence or complete representation of future executable writes is unproven",
            ),
            (
                "unproven_rsp_policy",
                "required RSP microcode execution identities and coverage are unproven",
            ),
            (
                "unsupported_execution_modes",
                "full R4300 execution/address/TLB modes are not represented by v0",
            ),
        ] {
            add(kind, None, detail, EvidenceRefs::new());
        }
    }
    let mut assumptions = if scope.is_static() {
        vec![
            "Only explicitly declared image entries execute; code bytes stay immutable.".into(),
            "Interrupts, exceptions, DMA, MMIO, overlays, RSP and external entry sources are excluded."
                .into(),
            "32-bit guest address compatibility model and the supported integer/control-flow subset only."
                .into(),
        ]
    } else {
        Vec::new()
    };
    if uses_address_taken {
        assumptions.push(format!(
            "Every register call without another proof targets one of the {} address-taken functions (ADR-0153): function starts named by an aligned ROM word or by a code constant in decoded guest code, as C function pointers must be; a native artifact dispatches over that set and faults 3 on any other target.",
            map.address_taken.len()
        ));
    }
    if !residual_sites.is_empty() {
        assumptions.push(format!(
            "VALIDATION ONLY (ADR-0218): {} indirect site(s) have no closure proof; a native artifact dispatches each over every lowered entry and faults 3 on any other target. The artifact is not natively complete.",
            residual_sites.len()
        ));
    }
    if forwarded_callbacks {
        assumptions.push(
            "A wrapper that forwards its own argument to a runtime callback (ADR-0149) is entered only by its direct callers, and no store through a pointer writes the stack slot where it spills that argument (C object rules for an argument home); the native runtime enters only the proven targets and faults 3 on any other."
                .into(),
        );
    }
    if return_closure {
        assumptions.push(
            "Each jr $ra returns to the continuation of the call that entered its function, or to the host's return address for a host-entered function; a native artifact checks the return address at every return and aborts on mismatch."
                .into(),
        );
    }
    if scope.guarded() {
        assumptions.push(
            "Data loads/stores are naturally aligned RDRAM accesses through KSEG0/KSEG1 or global TLB entries admitted by checked SDK/TLBWI mutations (ADR-0162/0235) (unaligned LWL/LWR/LDL/LDR read their containing aligned word, and SWL/SWR/SDL/SDR write single bytes), never reach executable bytes, and use only one cache view per 16-byte line: cached at its physical D-cache index, cached at the other index, or uncached; a native artifact checks every store and access and aborts on violation, with no fallback execution."
                .into(),
        );
        if !tables.is_empty() {
            assumptions.push(
                "Recognized jump tables are read-only bytes of the declared image: a native artifact checks every store and aborts on a write to table bytes, and dispatches only to the table's snapshot targets."
                    .into(),
            );
        }
        if uses_cop0 {
            assumptions.push(
                "COP0 operations use known kernel Status and staging registers, normalized global 32-bit TLB entries, and no unmodeled timer, exception, interrupt-delivery or SDK-thread Status effects; a native artifact faults 12 on unsupported state, invalidates staging knowledge across runtime boundaries, and never falls back to guest execution (ADR-0235)."
                    .into(),
            );
        }
        if uses_cop1 {
            assumptions.push(
                if map.cop1_fr0 {
                    "COP1 is usable with 32 FPRs and doubles in even/odd pairs (Status.CU1 = 1, Status.FR = 0, as libultra threads run; ADR-0160) wherever COP1 instructions execute."
                } else {
                    "COP1 is usable with 64-bit FPRs (Status.CU1 = 1, Status.FR = 1) wherever COP1 instructions execute."
                }
                .into(),
            );
        }
        if uses_compare {
            assumptions.push(
                "COP1 operations stay inside the modeled subset: no NaN compare operand, no NaN or subnormal arithmetic operand, no out-of-range conversion and no enabled FPU exception (FCSR is modeled as pinned ares: rounding mode on the host FPU, cause and sticky flags, FS flushing); a native artifact checks each operation and aborts otherwise, with no fallback execution."
                    .into(),
            );
        }
        let relocatable = map
            .load_images
            .values()
            .flat_map(|spec| &spec.loads)
            .filter(|l| l.relocatable)
            .count();
        if relocatable > 0 {
            assumptions.push(format!(
                "{relocatable} relocatable overlay(s) are lowered at their link addresses and run only through a run-time binding (ADR-0181): an indirect transfer to a real address binds the one overlay whose relocated bytes and zeroed BSS match RAM there byte for byte (ambiguity or a mismatch aborts, fault 3); relocated immediates are read from the bound bytes and return addresses are the bound copy's; a store or runtime write into bound text revokes the binding, so code entered afterwards aborts (fault 8), and a store by the overlay's own code into its text aborts (fault 2)."
            ));
        }
        if map
            .load_images
            .values()
            .any(|spec| spec.loads.iter().any(|l| !l.relocatable))
        {
            let count: usize = map
                .load_images
                .values()
                .map(|spec| spec.loads.iter().filter(|l| !l.relocatable).count())
                .sum();
            assumptions.push(format!(
                "{count} declared load(s) place their decoded bytes at their destinations before any of their code runs: a native artifact compares each load's executable bytes in RAM with the declared bytes on entry into its code and aborts on a mismatch (fault 8); a store or runtime write into a verified load's executable bytes revokes that verification, so the next entry compares again (ADR-0161), and a store by the load's own code into them aborts (fault 2)."
            ));
        }
        if !map.runtime_functions.is_empty() {
            let names: Vec<_> = map
                .runtime_functions
                .values()
                .map(|f| f.name.as_str())
                .collect();
            let status = if names.contains(&"__osGetSR")
                || map
                    .runtime_functions
                    .values()
                    .any(|f| f.status_global.is_some())
            {
                " Status observation uses the verified cold-start FR=0 SDK thread/mask ABI: complete live Status is known only after a supported thread dispatch; unknown boot contexts, incompatible saved modes and PRENMI delivery fault explicitly. The all-blocked HLE idle dispatcher accepts pending events without changing any blocked context's saved interrupt preference."
            } else {
                ""
            };
            assumptions.push(format!(
                "Declared runtime functions ({}) are host-provided: entered only by call or tail call at their entry, they follow the o32 ABI (preserving s0-s7, gp, sp and fp, and returning to $ra), enter guest code only at proven callback arguments through the artifact's fail-closed plaid_enter dispatch, write guest RAM only after plaid_runtime_write accepts the range, and their guest bodies are neither analyzed nor lowered.{status}",
                names.join(", ")
            ));
            // names no ROM signature backs (ADR-0171)
            let mut by_map: Vec<_> = map
                .runtime_functions
                .values()
                .filter(|f| {
                    f.evidence.iter().any(|id| {
                        map.evidence.get(id).is_some_and(|e| {
                            e.producer == crate::signatures::REFERENCE_MAP_PRODUCER
                        })
                    })
                })
                .map(|f| f.name.as_str())
                .collect();
            by_map.dedup();
            if !by_map.is_empty() {
                assumptions.push(format!(
                    "Runtime functions named only by a reference symbol map, not by a signature of the ROM's own bytes ({}), are the libultra functions of those names (ADR-0171).",
                    by_map.join(", ")
                ));
            }
        }
        assumptions.push(
            "Overflow-trapping ADD/ADDI/SUB/DADD/DADDI/DSUB never overflow; a native artifact checks each one and aborts on overflow, with no fallback execution."
                .into(),
        );
        if uses_trap {
            assumptions.push(
                "Conditional traps (TEQ, TGE, ...) are never taken (their Trap exception handler is not modeled); a native artifact checks each one and aborts if taken, with no fallback execution."
                    .into(),
            );
        }
        if uses_break {
            assumptions.push(
                "BREAK is never executed (its Breakpoint exception handler is not modeled); a native artifact aborts if one is reached, with no fallback execution."
                    .into(),
            );
        }
    }
    Ok(SolveReport {
        schema_version: 0,
        scope,
        status: if blockers.is_empty() {
            ClosureStatus::Closed
        } else {
            ClosureStatus::Open
        },
        native_complete: false,
        assumptions,
        blockers,
        discharged,
        residual_sites,
    })
}
