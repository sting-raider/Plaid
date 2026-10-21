//! ROM-backed RSP candidate registry; no runtime execution supplies inputs.
use plaid_core::{GuestAddr, discovery::CodeImage, program::ProgramMap, rom::CanonicalRom};
use std::{collections::BTreeSet, fs};

/// `sources` are RAM ranges the game fills by PI DMA from the ROM, observed in
/// the analysis-time replay (ADR-0225). One is a root only where a CPU constant
/// names its start; it never enters CPU discovery.
pub fn generate(
    rom: &CanonicalRom,
    map: &ProgramMap,
    images: Vec<CodeImage>,
    sources: Vec<CodeImage>,
    output: &str,
) -> Result<(), String> {
    let out = std::path::Path::new(output);
    fs::create_dir_all(out).map_err(|e| e.to_string())?;
    let mut registry = String::from("#include \"rsp_state.h\"\n");
    let mut names = Vec::new();
    let mut boot_sizes = Vec::new();
    let mut masks = Vec::new();
    let mut manifest = Vec::new();
    let mut seen = BTreeSet::new();
    let named: BTreeSet<GuestAddr> = images
        .iter()
        .flat_map(|image| plaid_core::rsp_rom::constants(image, map))
        .collect();
    let static_images = images.len();
    for (k, image) in images.into_iter().chain(sources).enumerate() {
        let dma = k >= static_images;
        let mut roots = if dma {
            BTreeSet::new()
        } else {
            plaid_core::rsp_rom::roots(&image, map)
        };
        if dma && named.contains(&image.base.pc) {
            roots.insert(image.base.pc);
        }
        let overlays = plaid_core::rsp_rom::overlay_descriptors(&image, &roots);
        for root in roots {
            let bytes: Vec<_> = (0..0x1000)
                .step_by(4)
                .map_while(|n| image.word(GuestAddr(root.0 + n)))
                .flat_map(u32::to_be_bytes)
                .collect();
            if !plaid_lower::rsp::plausible_text(&bytes) {
                continue;
            }
            // Both standard rspboot placements are candidates. Word identity
            // guards retain the exact origin when microcode overlays IMEM.
            // A recognized task boot shorter than IMEM is its own candidate.
            let boot = (bytes.len() < 0x1000
                && plaid_core::rsp_rom::boot_ucode_size(&bytes).is_some())
            .then_some((0, bytes.len() as u32, 0));
            let variants = [(0, 0x1000, 0), (0, 0xf80, 0x80)]
                .into_iter()
                .chain(boot)
                .chain(overlays.iter().copied());
            for (offset, requested_size, imem) in variants {
                let address = root.0.checked_add(offset).ok_or("RSP address overflow")?;
                let text: Vec<_> = (0..requested_size)
                    .step_by(4)
                    .map_while(|n| image.word(GuestAddr(address + n)))
                    .flat_map(u32::to_be_bytes)
                    .collect();
                if text.len() != requested_size as usize || !plaid_lower::rsp::plausible_text(&text)
                {
                    continue;
                }
                let size = text.len();
                let text = text.as_slice();
                let hash = plaid_core::rom::sha256(text);
                if !seen.insert((imem, hash.clone())) {
                    continue;
                }
                let name = format!("rom_{}_{imem:x}", &hash[..16]);
                let lowered = plaid_lower::rsp::lower_rsp(text, imem, &name)?;
                let reachable = plaid_lower::rsp::reachable_words(text, imem)?;
                let mut mask = [0u8; 128];
                for &pc in &reachable.words {
                    mask[pc as usize / 32] |= 1 << (pc / 4 % 8);
                }
                fs::write(out.join(format!("{name}.c")), lowered.c).map_err(|e| e.to_string())?;
                fs::write(out.join(format!("{name}.bin")), text).map_err(|e| e.to_string())?;
                registry += &format!("extern const plaid_rsp_text plaid_rsp_text_{name};\n");
                manifest.push(serde_json::json!({"name":name,"image":image.base.image,
                            "guest_address":address,"root":root.0,"source_kind":if dma {"pi_dma"} else if offset == 0 {"pointer"} else {"overlay_descriptor"},"imem":imem,"size":size,"sha256":hash,
                            "fault_stubs":lowered.stubs.len(),
                            "reachable_words":reachable.words,
                            "unresolved_indirect":reachable.indirect,
                            "reachability_exits":reachable.exits}));
                names.push(name);
                boot_sizes.push(plaid_core::rsp_rom::boot_ucode_size(text).unwrap_or(0));
                masks.push(mask);
            }
        }
    }
    if names.len() > 64 {
        return Err(format!(
            "{} RSP texts exceed runtime registry limit",
            names.len()
        ));
    }
    registry += "const plaid_rsp_text *const plaid_rsp_texts[] = {";
    for name in &names {
        registry += &format!("&plaid_rsp_text_{name},");
    }
    registry += "0};\n";
    registry += "const u8 plaid_rsp_rom_reachable[][128] = {\n";
    for mask in masks {
        registry += &format!("{{{}}},\n", mask.map(|v| v.to_string()).join(","));
    }
    registry += "{0}};\n";
    registry += "const u32 plaid_rsp_boot_ucode_sizes[] = {";
    for size in &boot_sizes {
        registry += &format!("{size},");
    }
    registry += "0};\n";
    fs::write(out.join("rsp_registry.c"), registry).map_err(|e| e.to_string())?;
    fs::write(
        out.join("rsp-files.json"),
        serde_json::to_string_pretty(&serde_json::json!({
            "schema":"plaid-rsp-rom-v1", "rom_sha256":rom.identity.sha256,
            "complete":false, "texts":manifest
        }))
        .map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;
    println!("{} ROM-derived RSP texts", names.len());
    Ok(())
}
