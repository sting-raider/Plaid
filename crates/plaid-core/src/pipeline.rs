//! Bounded fixed point between direct discovery and local target inference.
use crate::{
    GuestAddr,
    discovery::{CodeImage, Discovery, direct_cfg_bounded},
    indirect::{analyze_indirect, verify_constant},
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
                    };
                    (image.address(*a), f)
                })
                .collect();
            Some((id, evidence, functions))
        }
    };
    discover_bounded(rom, image, entries, declared.as_ref(), budget)
}

type Declared = (String, Evidence, BTreeMap<CodeAddress, RuntimeFunction>);

fn discover_bounded(
    rom: RomIdentity,
    image: &CodeImage,
    entries: &[GuestAddr],
    declared: Option<&Declared>,
    budget: usize,
) -> Result<Discovery, String> {
    let boundary: BTreeSet<GuestAddr> = declared
        .map(|(_, _, f)| f.keys().map(|a| a.pc).collect())
        .unwrap_or_default();
    let boundary = &boundary;
    let mut roots: BTreeSet<_> = entries.iter().copied().collect();
    let mut history: Option<ProgramMap> = None;
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
        let mut map = analyze_indirect(&discovery.map, image)?;
        if let Some(previous) = &history {
            // Repartitioning replaces block shapes, but inferred possible targets
            // and their original evidence survive even if a proof is revoked.
            map.evidence.extend(previous.evidence.clone());
            map.indirect_sites = map
                .indirect_sites
                .into_iter()
                .map(|mut s| {
                    for old in previous
                        .indirect_sites
                        .iter()
                        .filter(|old| old.site == s.site)
                    {
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
            map.indirect_sites = map
                .indirect_sites
                .iter()
                .map(|s| {
                    let mut s = s.clone();
                    if !verify_constant(&map, image, &s) {
                        s.closed_proof = None;
                    }
                    s
                })
                .collect();
        }
        let old_count = roots.len();
        // Proven callback arguments are functions the runtime enters (ADR-0130).
        for target in crate::callbacks::targets(&map, image) {
            if image.word(target.pc).is_some() {
                roots.insert(target.pc);
            }
        }
        for site in &map.indirect_sites {
            for target in site.candidates.keys() {
                if target.image == image.base.image
                    && target.generation == image.base.generation
                    && image.word(target.pc).is_some()
                    && !boundary.contains(&target.pc)
                {
                    roots.insert(target.pc);
                }
            }
        }
        map.validate()?;
        discovery.map = map.clone();
        if roots.len() == old_count {
            // Return certificates only label the fixed point; they add no roots.
            discovery.map = crate::returns::annotate(&discovery.map, image)?;
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
