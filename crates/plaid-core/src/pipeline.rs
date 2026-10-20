//! Bounded fixed point between direct discovery and local target inference.
use crate::{
    GuestAddr,
    discovery::{CodeImage, Discovery, direct_cfg_bounded},
    indirect::analyze_indirect,
    program::*,
};
use std::collections::{BTreeMap, BTreeSet};

pub fn discover_image(
    rom: RomIdentity,
    image: &CodeImage,
    entries: &[GuestAddr],
    budget: usize,
) -> Result<Discovery, String> {
    discover_image_with_runtime(rom, image, entries, &[], None, budget)
}

/// Discovery that stops at declared runtime functions (ADR-0129). `evidence`
/// backs every declaration and is required when `runtime` is non-empty.
pub fn discover_image_with_runtime(
    rom: RomIdentity,
    image: &CodeImage,
    entries: &[GuestAddr],
    runtime: &[(GuestAddr, String, Vec<u8>)],
    evidence: Option<(String, Evidence)>,
    budget: usize,
) -> Result<Discovery, String> {
    discover_labelled(rom, image, entries, runtime, evidence, budget, true)
}

/// Discovery with declared load provenance available to every proof round.
#[allow(clippy::too_many_arguments)]
pub fn discover_image_with_loads(
    rom: RomIdentity,
    image: &CodeImage,
    entries: &[GuestAddr],
    runtime: &[(GuestAddr, String, Vec<u8>)],
    evidence: Option<(String, Evidence)>,
    loads: Option<&LoadContext>,
    budget: usize,
) -> Result<Discovery, String> {
    validate_load_context(image, loads)?;
    discover_seeded(
        rom, image, entries, runtime, evidence, budget, true, None, loads,
    )
}

/// Declared sources and their evidence; distinct from observed DMA mappings.
pub type LoadContext = (crate::declared_loads::LoadImage, BTreeMap<String, Evidence>);

pub(crate) fn validate_load_context(
    image: &CodeImage,
    loads: Option<&LoadContext>,
) -> Result<(), String> {
    if let Some((spec, evidence)) = loads
        && (evidence.keys().any(String::is_empty)
            || spec.loads.iter().any(|load| {
                load.evidence.is_empty()
                    || load.evidence.iter().any(|id| !evidence.contains_key(id))
            })
            || !crate::declared_loads::verify_slots(image, Some(spec)))
    {
        return Err("load context does not match image slots or evidence".into());
    }
    Ok(())
}

/// As [`discover_image_with_runtime`]; with `label` false the fixed point is
/// left without return certificates, for callers that iterate further and
/// label once at the end with [`crate::returns::annotate`].
pub(crate) fn discover_labelled(
    rom: RomIdentity,
    image: &CodeImage,
    entries: &[GuestAddr],
    runtime: &[(GuestAddr, String, Vec<u8>)],
    evidence: Option<(String, Evidence)>,
    budget: usize,
    label: bool,
) -> Result<Discovery, String> {
    discover_seeded(
        rom, image, entries, runtime, evidence, budget, label, None, None,
    )
}

/// Retain inferred decoder roots and candidate history without making them
/// arbitrary external entries on an outer address-taken discovery round.
#[allow(clippy::too_many_arguments)]
pub(crate) fn discover_seeded(
    rom: RomIdentity,
    image: &CodeImage,
    entries: &[GuestAddr],
    runtime: &[(GuestAddr, String, Vec<u8>)],
    evidence: Option<(String, Evidence)>,
    budget: usize,
    label: bool,
    previous: Option<&ProgramMap>,
    loads: Option<&LoadContext>,
) -> Result<Discovery, String> {
    let declared = match (runtime.is_empty(), evidence) {
        (true, _) => None,
        (false, None) => return Err("runtime declarations need evidence".into()),
        (false, Some((id, evidence))) => {
            let functions = runtime
                .iter()
                .map(|(a, name, callbacks)| {
                    let f = RuntimeFunction {
                        name: name.clone(),
                        evidence: [id.clone()].into(),
                        callbacks: callbacks.clone(),
                        status_global: None,
                        eeprom_timer: None,
                    };
                    (image.address(*a), f)
                })
                .collect();
            Some((id, evidence, functions))
        }
    };
    discover_bounded(
        rom,
        image,
        entries,
        declared.as_ref(),
        budget,
        label,
        previous,
        loads,
    )
}

type Declared = (String, Evidence, BTreeMap<CodeAddress, RuntimeFunction>);

#[allow(clippy::too_many_arguments)]
fn discover_bounded(
    rom: RomIdentity,
    image: &CodeImage,
    entries: &[GuestAddr],
    declared: Option<&Declared>,
    budget: usize,
    label: bool,
    previous: Option<&ProgramMap>,
    loads: Option<&LoadContext>,
) -> Result<Discovery, String> {
    let boundary: BTreeSet<GuestAddr> = declared
        .map(|(_, _, f)| f.keys().map(|a| a.pc).collect())
        .unwrap_or_default();
    let boundary = &boundary;
    let mut roots: BTreeSet<_> = entries.iter().copied().collect();
    let mut external = roots.clone();
    if let Some(previous) = previous {
        for entry in previous
            .entries
            .keys()
            .filter(|a| a.image == image.base.image && a.generation == image.base.generation)
        {
            roots.insert(entry.pc);
            if !previous.derived_entries.contains_key(entry) {
                external.insert(entry.pc);
            }
        }
    }
    let mut history = previous.cloned();
    let mut last = None;
    for _ in 0..budget.clamp(1, 512) {
        let mut discovery = direct_cfg_bounded(
            rom.clone(),
            image,
            &roots.iter().copied().collect::<Vec<_>>(),
            budget,
            boundary,
        )?;
        if let Some((id, evidence, functions)) = declared {
            discovery.map.evidence.insert(id.clone(), evidence.clone());
            discovery.map.runtime_functions = functions.clone();
        }
        if let Some((spec, evidence)) = loads {
            discovery.map.evidence.extend(evidence.clone());
            discovery
                .map
                .load_images
                .insert(image.base.image.clone(), spec.clone());
        }
        let mut map = discovery.map.clone();
        if let Some(previous) = &history {
            // Repartitioning replaces block shapes, but inferred possible targets
            // and their original evidence survive even if a proof is revoked.
            map.evidence.extend(previous.evidence.clone());
            let mut by_site: BTreeMap<&CodeAddress, Vec<&IndirectSite>> = BTreeMap::new();
            for old in &previous.indirect_sites {
                by_site.entry(&old.site).or_default().push(old);
            }
            map.indirect_sites = map
                .indirect_sites
                .into_iter()
                .map(|mut s| {
                    for old in by_site.get(&s.site).into_iter().flatten() {
                        for (target, refs) in &old.candidates {
                            s.candidates
                                .entry(target.clone())
                                .or_default()
                                .extend(refs.clone());
                        }
                    }
                    s
                })
                .collect();
        }
        // A decoder seed is derived only while every real external origin
        // remains excluded. Candidate edges are rechecked against current bytes.
        for site in &map.indirect_sites {
            if site.link_register.is_none() {
                for target in site.candidates.keys() {
                    if map.entries.contains_key(target) && !external.contains(&target.pc) {
                        map.derived_entries
                            .entry(target.clone())
                            .or_default()
                            .insert(site.site.clone());
                    }
                }
            }
        }
        for (entry, sources) in map.derived_entries.clone() {
            map.record_derived_entry(entry, sources)?;
        }
        map = analyze_indirect(&map, image)?;
        let old_count = (roots.len(), external.len());
        // Linked calls into a content-bound slot discover every supplied text
        // alternate. Keep the edge's architectural target; native dispatch
        // chooses the byte-verified alternate when the call executes.
        for edge in map.direct_edges.iter().filter(|e| e.kind == EdgeKind::Call) {
            for target in image.slot_copies(edge.target.pc.0) {
                if target != edge.target.pc.0
                    && image.instruction_word(GuestAddr(target)).is_some()
                    && !boundary.contains(&GuestAddr(target))
                {
                    roots.insert(GuestAddr(target));
                    external.insert(GuestAddr(target));
                }
            }
        }
        // Proven callback arguments are functions the runtime enters (ADR-0130).
        for target in crate::callbacks::targets(&map, image) {
            if image.word(target.pc).is_some() {
                roots.insert(target.pc);
                external.insert(target.pc);
            }
        }
        for site in &map.indirect_sites {
            for target in site.candidates.keys() {
                if target.image == image.base.image && target.generation == image.base.generation {
                    let copies = if site.link_register.is_some() {
                        image.slot_copies(target.pc.0)
                    } else {
                        vec![target.pc.0]
                    };
                    for target in copies.into_iter().map(GuestAddr) {
                        if image.instruction_word(target).is_some() && !boundary.contains(&target) {
                            roots.insert(target);
                            if site.link_register.is_some() {
                                external.insert(target);
                            }
                        }
                    }
                }
            }
        }
        map.derived_entries
            .retain(|entry, _| !external.contains(&entry.pc));
        map.validate()?;
        discovery.map = map.clone();
        if (roots.len(), external.len()) == old_count {
            // Return certificates only label the fixed point; they add no roots.
            if label {
                discovery.map = crate::returns::annotate(&discovery.map, image)?;
            }
            return Ok(discovery);
        }
        history = Some(map);
        last = Some(discovery);
    }
    let mut discovery = last.expect("at least one bounded discovery pass");
    let evidence = discovery.map.evidence.keys().cloned().collect();
    discovery.map.unresolved.insert(Unresolved {
        kind: "resource_limit".into(),
        site: None,
        detail: "indirect discovery fixed-point iteration budget reached".into(),
        evidence,
    });
    discovery.map.validate()?;
    Ok(discovery)
}
