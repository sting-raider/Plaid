//! Refine source declarations from copy-shaped calls in rebuilt ROM images.
use crate::{load_declarations, rom_images};
use plaid_core::{
    declared_loads::{DeclaredLoad, LoadEncoding, LoadImage},
    program::{GuestRange, ProgramMap, RomOffset},
    rom::CanonicalRom,
};
use std::{collections::BTreeMap, fs};

fn same_load(left: &DeclaredLoad, right: &DeclaredLoad) -> bool {
    left.source == right.source
        && left.encoding == right.encoding
        && left.destination.size == right.destination.size
        && left.linked.unwrap_or(left.destination.start)
            == right.linked.unwrap_or(right.destination.start)
        && left.linked.is_some() == right.linked.is_some()
        && left.relocatable == right.relocatable
}

fn reconcile_declarations(mapped: &LoadImage, declared: &mut LoadImage) -> Result<(), String> {
    // Reapply discovery's catalog-over-replay rule before comparing declarations.
    // Catalogs supplied by the loads file must still match that file themselves.
    declared.loads.extend(
        mapped
            .loads
            .iter()
            .filter(|load| {
                matches!(load.encoding, LoadEncoding::CatalogOverlay { .. })
                    && !load.evidence.iter().any(|id| id.starts_with("loads:"))
            })
            .cloned(),
    );
    plaid_core::declared_loads::exclude_replayed_catalog_text(declared);
    if mapped.loads.iter().any(|load| {
        load.evidence.iter().any(|id| id.starts_with("loads:"))
            && !declared
                .loads
                .iter()
                .any(|current| same_load(load, current))
    }) {
        return Err("copy-call map has stale load declarations; rediscover first".into());
    }
    Ok(())
}

pub fn refine(rom_path: &str, map_path: &str, loads_path: &str) -> Result<(), String> {
    let rom = CanonicalRom::from_bytes(&fs::read(rom_path).map_err(|e| e.to_string())?)?;
    let map = ProgramMap::from_json(&fs::read_to_string(map_path).map_err(|e| e.to_string())?)?;
    if map.rom != rom.identity {
        return Err("copy-call map belongs to another ROM".into());
    }
    if map.load_images.len() > 1 {
        return Err("copy-call refinement requires one discovery image".into());
    }
    let mapped = map.load_images.values().next();
    let (offset, base) = mapped.map_or_else(
        || {
            (
                RomOffset(0x1000),
                GuestRange {
                    start: rom.header.boot_address,
                    size: rom.boot_image_size().unwrap_or(0x100000),
                },
            )
        },
        |spec| (spec.base_offset, spec.base.clone()),
    );
    let path = loads_path.to_string();
    let (mut declared, _) = load_declarations(Some(&path), offset, base)?.ok_or("missing loads")?;
    let images = rom_images(&rom, &map)?;
    // New candidates may already have been appended since this map was made.
    // Every original declaration must still describe the same source and slot;
    // synthetic placements/evidence IDs can change when declarations grow.
    if let Some(spec) = mapped {
        reconcile_declarations(spec, &mut declared)?;
    }
    let mut doc: serde_json::Value =
        serde_json::from_slice(&fs::read(loads_path).map_err(|e| e.to_string())?)
            .map_err(|e| e.to_string())?;
    let mut fixed: Vec<_> = mapped
        .map(|spec| spec.base.clone())
        .into_iter()
        .chain(
            declared
                .loads
                .iter()
                .filter(|load| load.linked.is_none())
                .map(|load| load.destination.clone()),
        )
        .collect();
    if mapped.is_none() {
        fixed.extend(
            map.regions
                .iter()
                .filter(|r| r.rom_offset.is_some())
                .map(|r| r.range.clone()),
        );
    }
    let mut found = BTreeMap::new();
    for image in &images {
        for candidate in plaid_core::copy_calls::infer(rom.bytes(), &map, image)
            .into_iter()
            .chain(plaid_core::copy_catalogs::infer(rom.bytes(), &map, image))
        {
            let key = (candidate.source.0, candidate.end.0, candidate.destination.0);
            found
                .entry(key)
                .or_insert((candidate, image.base.image.clone()));
        }
    }
    let mut evidence = Vec::new();
    for ((source, end, destination), (candidate, image)) in found {
        let size = end
            .checked_sub(source)
            .ok_or("copy-call source range underflow")?;
        if declared.loads.iter().any(|load| {
            load.source.0 == source
                && u64::from(load.destination.size) == size
                && load.linked.unwrap_or(load.destination.start).0 == destination
        }) || fixed.iter().any(|range| {
            u64::from(destination) < range.end()
                && u64::from(range.start.0) < u64::from(destination) + size
        }) {
            continue;
        }
        doc["loads"]
            .as_array_mut()
            .ok_or("loads array missing")?
            .push(serde_json::json!({
                "destination": format!("{destination:#x}"), "size": format!("{size:#x}"),
                "rom": format!("{source:#x}"), "encoding": "raw", "slot": true,
            }));
        evidence.push(format!(
            "ROM-only copy-call/v1 candidate {source:#x}..{end:#x} at {destination:#x}; helper {:#x}, callers {:?}, rebuilt image {image}; exact native slot binding required",
            candidate.helper.0, candidate.callers
        ));
    }
    let mut mapped_sources = std::collections::BTreeSet::new();
    for image in &images {
        for candidate in plaid_core::tlb_catalogs::infer(rom.bytes(), &map, image) {
            let (source, end, virtual_base) = (
                candidate.source.0,
                candidate.end.0,
                candidate.virtual_base.0,
            );
            let size = end
                .checked_sub(source)
                .ok_or("mapped copy source range underflow")?;
            if !mapped_sources.insert((source, end, virtual_base))
                || declared.loads.iter().any(|load| {
                    load.source.0 == source
                        && u64::from(load.destination.size) == size
                        && load.linked == Some(candidate.virtual_base)
                })
            {
                continue;
            }
            doc["loads"]
                .as_array_mut()
                .ok_or("loads array missing")?
                .push(serde_json::json!({
                    "destination": format!("{virtual_base:#x}"), "size": format!("{size:#x}"),
                    "rom": format!("{source:#x}"), "encoding": "tlb_raw", "slot": true,
                    "text_size": format!("{:#x}", candidate.text_size),
                }));
            evidence.push(format!("ROM-only mapped-copy candidate {source:#x}..{end:#x} at {virtual_base:#x}, entry {:#x}, witness {:?}; unchanged source bytes and native TLB binding required", candidate.entry.0, (candidate.caller, candidate.helper, candidate.table)));
        }
    }
    if evidence.is_empty() {
        println!("no new copy-call load candidates");
        return Ok(());
    }
    let source = doc["source"].as_str().ok_or("load source missing")?;
    doc["source"] = format!("{source}; {}", evidence.join("; ")).into();
    fs::write(
        loads_path,
        serde_json::to_string_pretty(&doc).map_err(|e| e.to_string())? + "\n",
    )
    .map_err(|e| e.to_string())?;
    println!(
        "{} copy-call load candidates -> {loads_path}",
        evidence.len()
    );
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use plaid_core::{GuestAddr, declared_loads::OverlayCompression};

    #[test]
    fn catalog_trimmed_replays_match_only_the_same_current_declaration() {
        let replay = DeclaredLoad {
            source: RomOffset(0),
            destination: GuestRange {
                start: GuestAddr(0x80002000),
                size: 0x100,
            },
            encoding: LoadEncoding::AresBoot {
                entry: GuestAddr(0x80002040),
            },
            evidence: ["loads:old".into()].into(),
            relocatable: false,
            linked: None,
        };
        let catalog = DeclaredLoad {
            source: RomOffset(0x3000),
            destination: GuestRange {
                start: GuestAddr(0x80802040),
                size: 0x60,
            },
            encoding: LoadEncoding::CatalogOverlay {
                encoding: OverlayCompression::Raw,
                encoded_size: 0x60,
                text_size: 0x40,
                bss_size: 0x20,
            },
            evidence: ["overlays:catalog".into()].into(),
            relocatable: true,
            linked: Some(GuestAddr(0x80002040)),
        };
        let current = LoadImage {
            base_offset: RomOffset(0x1000),
            base: GuestRange {
                start: GuestAddr(0x80000400),
                size: 0x100,
            },
            loads: vec![replay.clone()],
        };
        let mut mapped = current.clone();
        mapped.loads.push(catalog.clone());
        plaid_core::declared_loads::exclude_replayed_catalog_text(&mut mapped);
        assert_eq!(mapped.loads[0].destination.size, 0x40);
        assert_eq!(mapped.loads[1].destination.start.0, 0x80002080);
        assert_eq!(mapped.loads[1].destination.size, 0x80);
        let mut updated = current.clone();
        updated.loads[0].evidence = ["loads:new".into()].into();
        reconcile_declarations(&mapped, &mut updated).unwrap();
        assert!(same_load(&mapped.loads[0], &updated.loads[0]));
        assert!(same_load(&mapped.loads[1], &updated.loads[1]));
        assert_eq!(updated.loads[0].encoding, replay.encoding);
        assert_eq!(updated.loads[0].evidence, ["loads:new".into()].into());
        // Neither containment alone nor a changed witness permits arbitrary slices.
        for mutation in 0..6 {
            let mut changed = current.clone();
            match mutation {
                0 => changed.loads.clear(),
                1 => {
                    changed.loads[0].encoding = LoadEncoding::AresBoot {
                        entry: GuestAddr(0x80002044),
                    }
                }
                2 => changed.loads[0].source = RomOffset(4),
                3 => changed.loads[0].destination.size -= 4,
                4 => changed.loads[0].destination.start.0 += 4,
                _ => changed.loads[0].encoding = LoadEncoding::Raw,
            }
            assert!(
                reconcile_declarations(&mapped, &mut changed).is_err(),
                "mutation {mutation}"
            );
        }
        let mut forged = mapped.clone();
        forged.loads[0].destination.size -= 4;
        assert!(reconcile_declarations(&forged, &mut current.clone()).is_err());
        // Nonbinding catalogs cannot trim, and declared catalogs cannot self-authenticate.
        let mut nonbinding = mapped.clone();
        nonbinding.loads.last_mut().unwrap().relocatable = false;
        assert!(reconcile_declarations(&nonbinding, &mut current.clone()).is_err());
        let mut supplied = current.clone();
        let mut catalog = catalog;
        catalog.evidence = ["loads:old".into()].into();
        supplied.loads = vec![catalog];
        let mut removed = current.clone();
        removed.loads.clear();
        assert!(reconcile_declarations(&supplied, &mut removed).is_err());
    }
}
