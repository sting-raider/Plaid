use plaid_core::{
    GuestAddr,
    discovery::CodeImage,
    merge::{import_trace_with_rom, merge_maps},
    pipeline::discover_image,
    program::{GuestRange, ProgramMap, RomOffset},
    rom::CanonicalRom,
    solver::{Scope, solve},
    trace::DiscoveryTrace,
};
use std::{env, fs, process::ExitCode};

fn run() -> Result<(), String> {
    let args: Vec<_> = env::args().skip(1).collect();
    match args.as_slice() {
        [command, rom_path, map_path] if command == "solve" => {
            let rom = CanonicalRom::from_bytes(&fs::read(rom_path).map_err(|e| e.to_string())?)?;
            let map =
                ProgramMap::from_json(&fs::read_to_string(map_path).map_err(|e| e.to_string())?)?;
            if map.rom != rom.identity {
                return Err("map does not match canonical ROM".into());
            }
            let mut images: Vec<CodeImage> = Vec::new();
            for region in &map.regions {
                if let Some(offset) = region.rom_offset {
                    let mut image = CodeImage::from_rom(&rom, offset, region.range.clone())?;
                    // Partial regions may reference a larger image's identity.
                    // Only complete hash-matching source witnesses enter here.
                    if image.base.image == region.image {
                        image.base.generation = region.generation;
                        if !images
                            .iter()
                            .any(|old| old.base == image.base && old.words == image.words)
                        {
                            images.push(image);
                        }
                    }
                }
            }
            let report = solve(&map, &images, Scope::WholeRom)?;
            println!(
                "{}",
                serde_json::to_string_pretty(&report).map_err(|e| e.to_string())?
            );
        }
        [command, path] if command == "solve" => {
            let map = ProgramMap::from_json(&fs::read_to_string(path).map_err(|e| e.to_string())?)?;
            let report = solve(&map, &[], Scope::WholeRom)?;
            println!(
                "{}",
                serde_json::to_string_pretty(&report).map_err(|e| e.to_string())?
            );
        }
        [command, rom_path, trace_path, output] if command == "import-trace" => {
            let rom = CanonicalRom::from_bytes(&fs::read(rom_path).map_err(|e| e.to_string())?)?;
            let trace = DiscoveryTrace::from_ndjson(
                &fs::read_to_string(trace_path).map_err(|e| e.to_string())?,
            )?;
            if trace.header.rom != rom.identity {
                return Err("trace does not match normalized ROM identity".into());
            }
            let map = import_trace_with_rom(&trace, &[], &rom, 1_000_000)?;
            fs::write(output, map.to_json()?).map_err(|e| e.to_string())?;
            println!(
                "imported {} blocks; {} unresolved facts",
                map.blocks.len(),
                map.unresolved.len()
            );
        }
        [command, left, right, output] if command == "merge" => {
            let a = ProgramMap::from_json(&fs::read_to_string(left).map_err(|e| e.to_string())?)?;
            let b = ProgramMap::from_json(&fs::read_to_string(right).map_err(|e| e.to_string())?)?;
            fs::write(output, merge_maps(&a, &b)?.to_json()?).map_err(|e| e.to_string())?;
        }
        [command, rom_path, offset, start, size, entry, output] if command == "discover" => {
            let rom = CanonicalRom::from_bytes(&fs::read(rom_path).map_err(|e| e.to_string())?)?;
            let image = CodeImage::from_rom(
                &rom,
                RomOffset(number(offset)?),
                GuestRange {
                    start: GuestAddr(number32(start)?),
                    size: number32(size)?,
                },
            )?;
            let d = discover_image(
                rom.identity,
                &image,
                &[GuestAddr(number32(entry)?)],
                1_000_000,
            )?;
            fs::write(output, d.map.to_json()?).map_err(|e| e.to_string())?;
            println!(
                "discovered {} blocks, {} indirect sites, {} unresolved items",
                d.map.blocks.len(),
                d.map.indirect_sites.len(),
                d.map.unresolved.len()
            );
        }
        [command, path] if command == "rom-info" => {
            let rom = CanonicalRom::from_bytes(&fs::read(path).map_err(|e| e.to_string())?)?;
            println!(
                "{}",
                serde_json::to_string_pretty(&serde_json::json!({
                    "source_order": rom.source_order, "identity": rom.identity, "header": rom.header
                }))
                .map_err(|e| e.to_string())?
            );
        }
        [command, path] if command == "check-trace" => {
            let t =
                DiscoveryTrace::from_ndjson(&fs::read_to_string(path).map_err(|e| e.to_string())?)?;
            println!(
                "trace v{}: {} events; engine {} @ {}; canonical ROM {}",
                t.header.schema_version,
                t.events.len(),
                t.header.engine,
                t.header.revision,
                t.header.rom.sha256
            );
        }
        [command, path] if command == "check-map" => {
            let p = ProgramMap::from_json(&fs::read_to_string(path).map_err(|e| e.to_string())?)?;
            println!(
                "ProgramMap v{}: {} blocks, {} indirect sites, {} unresolved items",
                p.schema_version,
                p.blocks.len(),
                p.indirect_sites.len(),
                p.unresolved.len()
            );
        }
        _ => {
            return Err(
                "usage: plaid rom-info <rom> | check-trace <trace.ndjson> | check-map <map.json> | solve [rom] <map.json> | discover <rom> <rom-offset> <guest-start> <size> <entry> <output.json> | import-trace <rom> <trace.ndjson> <output.json> | merge <left.json> <right.json> <output.json>"
                    .into(),
            );
        }
    }
    Ok(())
}

fn number(value: &str) -> Result<u64, String> {
    if let Some(hex) = value.strip_prefix("0x") {
        u64::from_str_radix(hex, 16)
    } else {
        value.parse()
    }
    .map_err(|e| e.to_string())
}
fn number32(value: &str) -> Result<u32, String> {
    u32::try_from(number(value)?).map_err(|e| e.to_string())
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("plaid: {e}");
            ExitCode::FAILURE
        }
    }
}
