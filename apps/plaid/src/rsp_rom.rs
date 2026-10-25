//! ROM-backed RSP candidate registry; no runtime execution supplies inputs.
use plaid_core::{GuestAddr, discovery::CodeImage, program::ProgramMap, rom::CanonicalRom};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
};

#[derive(Clone, Copy)]
enum Kind {
    Text,
    Overlay,
    Composite,
}

/// What the runtime compares when it matches a task (ADR-0240): the IMEM
/// base and the value of every word reachable from it. Texts equal under it
/// cannot be told apart there, though they may differ where code is entered
/// at another word (ADR-0245).
fn match_key(text: &[u8], imem: u32, reachable: &plaid_lower::rsp::RspReachability) -> String {
    let words: Vec<u8> = reachable
        .words
        .iter()
        .flat_map(|&pc| {
            let at = (pc - imem) as usize;
            pc.to_be_bytes()
                .into_iter()
                .chain(text[at..at + 4].iter().copied())
        })
        .collect();
    format!("{imem}:{}", plaid_core::rom::sha256(&words))
}

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
    let mut texts: Vec<(Vec<u8>, String)> = Vec::new();
    let mut seen = BTreeSet::new();
    let mut same_code: BTreeMap<String, usize> = BTreeMap::new();
    let mut matchable = Vec::new();
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
            let replacements = plaid_core::rsp_rom::boot_self_replacements(&bytes);
            for (bytes, self_dma) in std::iter::once((bytes, false))
                .chain(replacements.into_iter().map(|bytes| (bytes, true)))
            {
                // A short task text may be followed directly by data (ADR-0253).
                let short = &bytes[..bytes.len().min(0xf80)];
                if !plaid_lower::rsp::plausible_text(&bytes)
                    && !plaid_lower::rsp::plausible_program(short, 0x80)
                    && !plaid_lower::rsp::plausible_task(short, 0x80)
                {
                    continue;
                }
                // Both standard rspboot placements are candidates. Word identity
                // guards retain the exact origin when microcode overlays IMEM.
                // A recognized task boot shorter than IMEM is its own candidate.
                let boot = (bytes.len() < 0x1000
                    && plaid_core::rsp_rom::boot_ucode_size(&bytes).is_some())
                .then_some((0, bytes.len() as u32, 0));
                let short = (bytes.len() < 0xf80 && boot.is_none()).then_some((
                    0,
                    bytes.len() as u32,
                    0x80,
                ));
                // An overlay in the resident text's range also becomes that text
                // with the overlay in place (ADR-0246): its code may run on into,
                // or take a delay slot from, the resident words around it.
                let variants = [(0, 0x1000, 0), (0, 0xf80, 0x80)]
                    .into_iter()
                    .chain(boot)
                    .chain(short)
                    .map(|v| (v, Kind::Text))
                    .chain(overlays.iter().map(|&v| (v, Kind::Overlay)))
                    .chain(
                        overlays
                            .iter()
                            .filter(|&&(_, size, imem)| imem >= 0x80 && imem + size <= 0x1000)
                            .map(|&v| (v, Kind::Composite)),
                    );
                let resident: Vec<u8> = bytes.iter().copied().take(0xf80).collect();
                for ((offset, requested_size, imem), kind) in variants {
                    let address = root.0.checked_add(offset).ok_or("RSP address overflow")?;
                    let text: Vec<_> = if self_dma {
                        bytes
                            .iter()
                            .skip(offset as usize)
                            .take(requested_size as usize)
                            .copied()
                            .collect()
                    } else {
                        (0..requested_size)
                            .step_by(4)
                            .map_while(|n| image.word(GuestAddr(address + n)))
                            .flat_map(u32::to_be_bytes)
                            .collect()
                    };
                    // An overlay table states its entry's extent (ADR-0243).
                    let plausible = match kind {
                        Kind::Text => {
                            plaid_lower::rsp::plausible_text(&text)
                                || plaid_lower::rsp::plausible_program(&text, imem)
                                || plaid_lower::rsp::plausible_task(&text, imem)
                        }
                        _ => {
                            plaid_lower::rsp::plausible_overlay(&text)
                                || plaid_lower::rsp::plausible_short_overlay(&text, imem, &resident)
                        }
                    };
                    if text.len() != requested_size as usize || !plausible {
                        continue;
                    }
                    let (text, imem) = match kind {
                        Kind::Composite if resident.len() == 0xf80 => {
                            let mut full = resident.clone();
                            let at = (imem - 0x80) as usize;
                            full[at..at + text.len()].copy_from_slice(&text);
                            (full, 0x80)
                        }
                        Kind::Composite => continue,
                        _ => (text, imem),
                    };
                    let size = text.len();
                    let text = text.as_slice();
                    let hash = plaid_core::rom::sha256(text);
                    if !seen.insert((imem, hash.clone())) {
                        continue;
                    }
                    let name = format!("rom_{}_{imem:x}", &hash[..16]);
                    let reachable = plaid_lower::rsp::reachable_words(text, imem)?;
                    // Two matches for one task are refused at run time, so only the
                    // largest of texts it cannot tell apart is matched against a
                    // task; it accepts every task size the others do. All still run.
                    let key = match_key(text, imem, &reachable);
                    let matched = match same_code.get(&key) {
                        Some(&k) if texts[k].0.len() >= size => false,
                        Some(&k) => {
                            matchable[k] = false;
                            true
                        }
                        None => true,
                    };
                    if matched {
                        same_code.insert(key, names.len());
                    }
                    let lowered = plaid_lower::rsp::lower_rsp(text, imem, &name)?;
                    let mut mask = [0u8; 128];
                    for &pc in &reachable.words {
                        mask[pc as usize / 32] |= 1 << (pc / 4 % 8);
                    }
                    let entry = serde_json::json!({"name":name,"image":image.base.image,
                            "guest_address":address,"root":root.0,"source_kind":if self_dma {"boot_self_dma"} else if dma {"pi_dma"} else if matches!(kind, Kind::Composite) {"overlay_composite"} else if offset == 0 {"pointer"} else {"overlay_descriptor"},"imem":imem,"size":size,"sha256":hash,
                            "fault_stubs":lowered.stubs.len(),
                            "reachable_words":reachable.words,
                            "unresolved_indirect":reachable.indirect,
                            "reachability_exits":reachable.exits});
                    let boot_size = plaid_core::rsp_rom::boot_ucode_size(text).unwrap_or(0);
                    names.push(name);
                    texts.push((text.to_vec(), lowered.c));
                    boot_sizes.push(boot_size);
                    masks.push(mask);
                    manifest.push(entry);
                    matchable.push(matched);
                }
            }
        }
    }
    for (entry, m) in manifest.iter_mut().zip(&matchable) {
        entry["matchable"] = (*m).into();
    }
    for (name, (text, c)) in names.iter().zip(&texts) {
        fs::write(out.join(format!("{name}.c")), c).map_err(|e| e.to_string())?;
        fs::write(out.join(format!("{name}.bin")), text).map_err(|e| e.to_string())?;
        registry += &format!("extern const plaid_rsp_text plaid_rsp_text_{name};\n");
    }
    if names.len() > 256 {
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
    registry += "const u8 plaid_rsp_rom_matchable[] = {";
    for m in &matchable {
        registry += &format!("{},", u8::from(*m));
    }
    registry += "0};\n";
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

#[cfg(test)]
mod tests {
    use super::match_key;
    use plaid_lower::rsp::reachable_words;

    fn text(words: &[u32], len: usize, fill: u8) -> Vec<u8> {
        let mut t: Vec<u8> = words.iter().flat_map(|w| w.to_be_bytes()).collect();
        t.resize(len, fill);
        t
    }

    fn key(t: &[u8]) -> String {
        match_key(t, 0, &reachable_words(t, 0).unwrap())
    }

    #[test]
    fn texts_are_one_candidate_only_when_their_reachable_code_matches() {
        let run = [0x3401_0001, 0x0000_000d]; // ori at, zero, 1; break
        let short = text(&run, 0x100, 0);
        assert_eq!(key(&short), key(&text(&run, 0x1000, 0xff)));
        assert_ne!(
            key(&short),
            key(&text(&[0x3401_0002, 0x0000_000d], 0x100, 0))
        );
        // A boot ends in a register jump into the text it loaded; only the
        // words up to that jump are compared.
        let jump = [0x0020_0008, 0x0000_0000]; // jr at; nop
        assert_eq!(key(&text(&jump, 0x100, 0)), key(&text(&jump, 0x1000, 0xff)));
        assert_ne!(key(&text(&jump, 0x100, 0)), key(&text(&run, 0x100, 0)));
    }
}
