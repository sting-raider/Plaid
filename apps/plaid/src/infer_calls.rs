//! Refine source declarations from copy-shaped calls in rebuilt ROM images.
use crate::{load_declarations, rom_images};
use plaid_core::{
    declared_loads::DeclaredLoad,
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
    let (declared, _) = load_declarations(Some(&path), offset, base)?.ok_or("missing loads")?;
    // New candidates may already have been appended since this map was made.
    // Every original declaration must still describe the same source and slot;
    // synthetic placements/evidence IDs can change when declarations grow.
    if mapped.is_some_and(|spec| {
        spec.loads.iter().any(|load| {
            load.evidence.iter().any(|id| id.starts_with("loads:"))
                && !declared
                    .loads
                    .iter()
                    .any(|current| same_load(load, current))
        })
    }) {
        return Err("copy-call map has stale load declarations; rediscover first".into());
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
    for image in rom_images(&rom, &map)? {
        for candidate in plaid_core::copy_calls::infer(rom.bytes(), &map, &image)
            .into_iter()
            .chain(plaid_core::copy_catalogs::infer(rom.bytes(), &map, &image))
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
