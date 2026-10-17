//! SDK profiles are signature identities, never game identities or addresses.
use super::*;

pub fn verify(map: &crate::program::ProgramMap) -> Result<(), String> {
    if map
        .runtime_functions
        .values()
        .any(|f| f.name == "__osGetSR" || f.status_global.is_some())
        && (!map.cop1_fr0
            || ["osCreateThread", "osSetIntMask"].iter().any(|name| {
                let functions: Vec<_> = map
                    .runtime_functions
                    .values()
                    .filter(|f| f.name == *name)
                    .collect();
                functions.is_empty() || functions.iter().any(|f| f.status_global.is_none())
            })
            || map.runtime_functions.values().any(|f| {
                f.name == "osGetIntMask"
                    || (matches!(f.name.as_str(), "osInitialize" | "__osInitialize_common")
                        && f.status_global.is_none())
            }))
    {
        return Err("Status reads require the verified FR=0 SDK thread/mask ABI".into());
    }
    Ok(())
}

fn supported(image: &CodeImage, m: &Match, signatures: &[Signature]) -> bool {
    if !matches!(
        m.name.as_str(),
        "osCreateThread" | "osSetIntMask" | "osInitialize"
    ) {
        return false;
    }
    let variants: Vec<_> = signatures
        .iter()
        .filter(|s| s.name == m.name && s.size == m.size)
        .filter(|s| {
            let words: Option<Vec<_>> = (0..s.size / 4)
                .map(|k| image.instruction_word(GuestAddr(m.entry.0 + k * 4)))
                .collect();
            words.is_some_and(|words| stripped_crc(&words, &s.relocs) == s.crc_b)
        })
        .collect();
    !variants.is_empty()
        && variants.iter().all(|s| {
            matches!(
                (s.name.as_str(), s.size, s.crc_b),
                ("osCreateThread", 0x144, 0x5251_64f9)
                    | ("osSetIntMask", 0xa0, 0xa5f9_c656)
                    | ("osInitialize", 0x28c, 0xa26e_9830)
            )
        })
}

pub(super) fn annotate(image: &CodeImage, signatures: &[Signature], out: &mut Identification) {
    let scope = |pc: GuestAddr| {
        image
            .holes
            .iter()
            .filter(|h| h.end() <= u64::from(pc.0))
            .count()
    };
    let mut globals: BTreeMap<usize, BTreeSet<GuestAddr>> = BTreeMap::new();
    for m in &out.matches {
        if m.name == "osSetIntMask"
            && supported(image, m, signatures)
            && let Some(address) = out
                .data_bindings
                .get(&m.entry)
                .and_then(|data| data.get("__OSGlobalIntMask"))
        {
            globals.entry(scope(m.entry)).or_default().insert(*address);
        }
    }
    for m in &out.matches {
        if supported(image, m, signatures)
            && let Some(addresses) = globals.get(&scope(m.entry))
            && addresses.len() == 1
        {
            out.status_globals
                .insert(m.entry, *addresses.first().unwrap());
        }
    }
    // Reading the complete word is admitted only with a supported thread and
    // mask ABI throughout the selected program. Other CP0 writes stay guest
    // code and retain their ordinary unsupported-instruction obligations.
    let capable = ["osCreateThread", "osSetIntMask"].iter().all(|name| {
        let matches: Vec<_> = out.matches.iter().filter(|m| m.name == *name).collect();
        !matches.is_empty()
            && matches
                .iter()
                .all(|m| out.status_globals.contains_key(&m.entry))
    }) && !out.matches.iter().any(|m| {
        m.name == "osGetIntMask"
            || (matches!(m.name.as_str(), "osInitialize" | "__osInitialize_common")
                && !out.status_globals.contains_key(&m.entry))
    });
    if !capable {
        out.matches.retain(|m| m.name != "__osGetSR");
        out.status_globals.clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::program::{CodeAddress, ProgramMap, RomIdentity, RuntimeFunction};

    fn fixture() -> ProgramMap {
        let mut map = ProgramMap::new(RomIdentity {
            sha256: "00".repeat(32),
            size: 0x1000,
        });
        map.cop1_fr0 = true;
        for (index, name) in ["osCreateThread", "osSetIntMask", "__osGetSR"]
            .iter()
            .enumerate()
        {
            map.runtime_functions.insert(
                CodeAddress {
                    pc: GuestAddr(0x80000400 + index as u32 * 16),
                    image: "00".repeat(32),
                    generation: 0,
                },
                RuntimeFunction {
                    name: (*name).into(),
                    evidence: BTreeSet::new(),
                    callbacks: Vec::new(),
                    status_global: (index < 2).then_some(GuestAddr(0x80002000)),
                },
            );
        }
        map
    }

    #[test]
    fn status_read_requires_every_sdk_copy_and_declared_fr0() {
        let mut map = fixture();
        assert!(verify(&map).is_ok());
        map.cop1_fr0 = false;
        assert!(verify(&map).is_err());
        map.cop1_fr0 = true;
        let (mut address, mut copy) = map
            .runtime_functions
            .iter()
            .next()
            .map(|(a, f)| (a.clone(), f.clone()))
            .unwrap();
        address.pc.0 += 0x100;
        copy.status_global = None;
        map.runtime_functions.insert(address.clone(), copy);
        assert!(verify(&map).is_err());
        map.runtime_functions
            .get_mut(&address)
            .unwrap()
            .status_global = Some(GuestAddr(0x80003000));
        assert!(verify(&map).is_ok());
        map.runtime_functions.get_mut(&address).unwrap().name = "osGetIntMask".into();
        assert!(verify(&map).is_err());
    }

    #[test]
    fn status_bindings_without_status_read_require_declared_fr0() {
        let mut map = fixture();
        map.runtime_functions.retain(|_, f| f.name != "__osGetSR");
        assert!(verify(&map).is_ok());
        map.cop1_fr0 = false;
        assert!(verify(&map).is_err());
    }

    #[test]
    fn unrecognized_signature_keeps_status_read_as_guest_code() {
        let image = CodeImage {
            base: CodeAddress {
                pc: GuestAddr(0x80000400),
                image: "00".repeat(32),
                generation: 0,
            },
            words: vec![0x40026000, 0x03e00008, 0],
            rom_offset: None,
            physical_start: None,
            holes: Vec::new(),
            slots: Vec::new(),
        };
        let mut out = Identification::default();
        out.matches.push(Match {
            entry: GuestAddr(0x80000400),
            name: "__osGetSR".into(),
            size: 12,
        });
        annotate(&image, &[], &mut out);
        assert!(out.matches.is_empty());
    }
}
