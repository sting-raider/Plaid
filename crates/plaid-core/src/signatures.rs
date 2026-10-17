//! Identification of host-runtime functions by n64sym signature (ADR-0133).
//!
//! A match is identification evidence, not proof: it only names a function so
//! it can be declared as a runtime function (ADR-0129), and the solver still
//! records the runtime ABI as an assumption. The matching rule reimplements
//! n64sym's `CSignatureFile::TestSymbol` (MIT, Copyright (c) 2017-2020
//! shygoo): CRC32 of the first 8 bytes and of the whole function, with the
//! immediate fields of relocated words cleared. Signature files are user
//! inputs (for example the pinned n64sym `builtin_signatures.sig`); none are
//! vendored.
use crate::{GuestAddr, discovery::CodeImage};
use std::collections::{BTreeMap, BTreeSet, HashMap};

#[path = "signature_bindings.rs"]
mod bindings;

/// Functions N64Recomp's runtime reimplements (`reimplemented_funcs` in
/// N64Recomp `src/symbol_lists.cpp`, MIT, Copyright (c) 2024 Wiseguy), plus
/// its ignored TLB functions.
#[rustfmt::skip]
pub const RUNTIME_FUNCTIONS: &[&str] = &[
    "__osInitialize_common", "osInitialize", "osGetMemSize",
    "osAiGetLength", "osAiGetStatus", "osAiSetFrequency", "osAiSetNextBuffer",
    "osViSetXScale", "osViSetYScale", "osCreateViManager", "osViBlack",
    "osViSetSpecialFeatures", "osViGetCurrentFramebuffer", "osViGetNextFramebuffer",
    "osViSwapBuffer", "osViSetMode", "osViSetEvent",
    "osDpSetNextBuffer",
    "osSpTaskLoad", "osSpTaskStartGo", "osSpTaskYield", "osSpTaskYielded", "__osSpSetPc",
    "osContInit", "osContStartReadData", "osContGetReadData", "osContStartQuery",
    "osContGetQuery", "osContSetCh",
    "osEepromProbe", "osEepromWrite", "osEepromLongWrite", "osEepromRead", "osEepromLongRead",
    "__osMotorAccess", "osMotorInit", "osMotorStart", "osMotorStop",
    "osPfsInitPak", "osPfsFreeBlocks", "osPfsAllocateFile", "osPfsDeleteFile",
    "osPfsFileState", "osPfsFindFile", "osPfsReadWriteFile",
    "osCartRomInit", "osCreatePiManager", "osPiReadIo", "osPiStartDma", "osEPiStartDma",
    "osPiGetStatus", "osEPiRawStartDma", "osEPiReadIo",
    // N64Recomp's osFlash* are left out: the FlashRAM is modelled on the PI
    // bus and libultra's flash code runs as guest code (ADR-0183)
    "osCreateThread", "osStartThread", "osStopThread", "osDestroyThread",
    "osSetThreadPri", "osGetThreadPri", "osGetThreadId",
    // in N64Recomp's `ignored_funcs`; OoT stores its address (ADR-0175)
    "osYieldThread",
    "osCreateMesgQueue", "osRecvMesg", "osSendMesg", "osJamMesg", "osSetEventMesg",
    "osGetTime", "osSetTime", "osSetTimer", "osStopTimer",
    "osVoiceSetWord", "osVoiceCheckWord", "osVoiceStopReadData", "osVoiceInit",
    "osVoiceMaskDictionary", "osVoiceStartReadData", "osVoiceControlGain",
    "osVoiceGetReadData", "osVoiceClearDictionary",
    "osSetIntMask", "__osDisableInt", "__osRestoreInt",
    // in N64Recomp's `ignored_funcs`; OoT hands its address to the 64DD
    // driver (ADR-0183)
    "osGetIntMask",
    "osVirtualToPhysical",
    "osGetCount", "osSetCount", "__osSetFpcCsr",
    "osInvalDCache", "osInvalICache", "osWritebackDCache", "osWritebackDCacheAll",
    "is_proutSyncPrintf", "__checkHardware_msp", "__checkHardware_kmc", "__checkHardware_isv",
    "__osInitialize_msp", "__osInitialize_kmc", "__osInitialize_isv", "__osRdbSend",
    "__ull_div", "__ll_div", "__ll_mul", "__ull_rem", "__ull_to_d", "__ull_to_f",
    // TLB functions N64Recomp ignores instead (`ignored_funcs`); the host
    // runtime owns the TLB (ADR-0155)
    "osMapTLB", "osUnmapTLB", "osUnmapTLBAll", "osSetTLBASID",
];

/// Evidence producer of runtime functions that only a reference symbol map
/// names (ADR-0171); the solver lists them in its runtime assumption.
pub const REFERENCE_MAP_PRODUCER: &str = "plaid-runtime-reference-map/v0";

/// Argument registers of a runtime function that carry guest code pointers.
pub fn callback_registers(name: &str) -> Vec<u8> {
    match name {
        // osCreateThread(thread, id, entry, arg, sp, pri)
        "osCreateThread" => vec![6],
        _ => Vec::new(),
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
enum Reloc {
    Targ26,
    Half,
}

/// Relocation kinds of a signature's first two words, which crcA covers.
type Head = (Option<Reloc>, Option<Reloc>);

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Signature {
    pub name: String,
    pub size: u32,
    crc_a: u32,
    crc_b: u32,
    relocs: BTreeMap<u32, Reloc>,
    /// `.targ26` offsets and the symbol each one calls (ADR-0171).
    calls: BTreeMap<u32, String>,
    /// `.hi16` and `.lo16` offsets of each data symbol (ADR-0182).
    data: BTreeMap<String, (Vec<u32>, Vec<u32>)>,
}

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct Match {
    pub entry: GuestAddr,
    pub name: String,
    pub size: u32,
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Identification {
    /// One name per address, and one address per name in each connected
    /// supplied image unless every copy is relocation-free code (ADR-0191).
    pub matches: Vec<Match>,
    /// Names with no selected declaration because they matched several
    /// addresses in a component, or shared an address with another name.
    pub ambiguous: BTreeSet<String>,
    /// Verified scalar address references, distinct for each selected SDK copy.
    /// This is address evidence, not a claim that the global value is immutable.
    pub data_bindings: BTreeMap<GuestAddr, BTreeMap<String, GuestAddr>>,
}

/// Parse an n64sym `sig_v1` file.
pub fn parse(text: &str) -> Result<Vec<Signature>, String> {
    let mut out: Vec<Signature> = Vec::new();
    let number = |s: &str| {
        u32::from_str_radix(s.trim_start_matches("0x"), 16).map_err(|e| format!("{s}: {e}"))
    };
    for (n, line) in text.lines().enumerate() {
        let fields: Vec<&str> = line.split_whitespace().collect();
        match fields.as_slice() {
            [] => {}
            [first, ..] if first.starts_with('#') => {}
            [kind @ (".targ26" | ".hi16" | ".lo16"), symbol, offsets @ ..]
                if !offsets.is_empty() =>
            {
                let sig = out
                    .last_mut()
                    .ok_or(format!("line {}: relocation before symbol", n + 1))?;
                for offset in offsets {
                    let offset = number(offset)?;
                    if offset % 4 != 0 || offset + 4 > sig.size {
                        return Err(format!("line {}: relocation outside {}", n + 1, sig.name));
                    }
                    let reloc = if *kind == ".targ26" {
                        sig.calls.insert(offset, symbol.to_string());
                        Reloc::Targ26
                    } else {
                        let (hi, lo) = sig.data.entry(symbol.to_string()).or_default();
                        if *kind == ".hi16" { hi } else { lo }.push(offset);
                        Reloc::Half
                    };
                    sig.relocs.insert(offset, reloc);
                }
            }
            [name, size, crc_a, crc_b] if !name.starts_with('.') => out.push(Signature {
                name: name.to_string(),
                size: number(size)?,
                crc_a: number(crc_a)?,
                crc_b: number(crc_b)?,
                relocs: BTreeMap::new(),
                calls: BTreeMap::new(),
                data: BTreeMap::new(),
            }),
            _ => return Err(format!("line {}: not a sig_v1 line", n + 1)),
        }
    }
    Ok(out)
}

pub(crate) fn crc32(bytes: &[u8]) -> u32 {
    !bytes.iter().fold(!0u32, |mut crc, b| {
        crc ^= u32::from(*b);
        for _ in 0..8 {
            crc = crc >> 1 ^ 0xedb8_8320 & (crc & 1).wrapping_neg();
        }
        crc
    })
}

fn strip(word: u32, reloc: Option<Reloc>) -> u32 {
    match reloc {
        Some(Reloc::Targ26) => word & 0xfc00_0000,
        Some(Reloc::Half) => word & 0xffff_0000,
        None => word,
    }
}

fn stripped_crc(words: &[u32], relocs: &BTreeMap<u32, Reloc>) -> u32 {
    let bytes: Vec<u8> = words
        .iter()
        .enumerate()
        .flat_map(|(i, w)| strip(*w, relocs.get(&(i as u32 * 4)).copied()).to_be_bytes())
        .collect();
    crc32(&bytes)
}

/// Find the signatures named in `wanted` in a code image. Only whole-word,
/// word-aligned signatures are considered.
pub fn identify(image: &CodeImage, signatures: &[Signature], wanted: &[&str]) -> Identification {
    let wanted: BTreeSet<&str> = wanted.iter().copied().collect();
    // index by (relocation pattern of the first two words, crcA)
    let mut index: HashMap<(Head, u32), Vec<&Signature>> = HashMap::new();
    for sig in signatures
        .iter()
        .filter(|s| wanted.contains(s.name.as_str()) && s.size >= 8 && s.size % 4 == 0)
    {
        let key = (
            (sig.relocs.get(&0).copied(), sig.relocs.get(&4).copied()),
            sig.crc_a,
        );
        index.entry(key).or_default().push(sig);
    }
    let patterns: BTreeSet<Head> = index.keys().map(|(head, _)| *head).collect();
    // (entry, name) -> the signature variants that match there
    let mut found: BTreeMap<(u32, &str), Vec<&Signature>> = BTreeMap::new();
    for at in 0..image.words.len().saturating_sub(1) {
        for (r0, r1) in &patterns {
            let head = [strip(image.words[at], *r0), strip(image.words[at + 1], *r1)];
            let bytes: Vec<u8> = head.iter().flat_map(|w| w.to_be_bytes()).collect();
            for sig in index
                .get(&((*r0, *r1), crc32(&bytes)))
                .into_iter()
                .flatten()
            {
                let end = at + sig.size as usize / 4;
                let entry = image.base.pc.0 + at as u32 * 4;
                // two words are only the index key and also occur inside
                // other functions: such a match must begin where a function
                // can (ADR-0183)
                if end <= image.words.len()
                    && (0..sig.size / 4).all(|k| image.word(GuestAddr(entry + 4 * k)).is_some())
                    && (sig.size > 8 || crate::data_roots::plausible(image, GuestAddr(entry)))
                    // A constant-return stub cannot identify a particular SDK
                    // service: unrelated switch arms have exactly these bytes.
                    && !(sig.size == 8
                        && image.words[at] == 0x03e0_0008
                        && matches!(image.words[at + 1] >> 16, 0x2402 | 0x3402))
                    && stripped_crc(&image.words[at..end], &sig.relocs) == sig.crc_b
                {
                    found
                        .entry((entry, sig.name.as_str()))
                        .or_default()
                        .push(sig);
                }
            }
        }
    }
    // Disjoint supplied images can contain independently linked SDK copies.
    // Their data globals and name uniqueness belong to separate namespaces;
    // call relocations still constrain targets across the complete image.
    let namespace = |entry: u32| {
        image
            .holes
            .iter()
            .filter(|h| h.end() <= u64::from(entry))
            .count()
    };
    let global = resolve(image, found.clone(), &|_| 0);
    if image.holes.is_empty() {
        return global;
    }
    let local = resolve(image, found, &namespace);
    combine(global, local)
}

fn combine(global: Identification, local: Identification) -> Identification {
    // Whole-image relocation evidence can identify services split across
    // components. Keep it alongside independent-copy evidence, but never
    // select between conflicting names or sizes at the same address.
    let mut matches: BTreeMap<GuestAddr, Match> = BTreeMap::new();
    let mut conflicts = BTreeSet::new();
    let mut ambiguous = BTreeSet::new();
    let mut data_bindings = BTreeMap::new();
    let mut data_conflicts = BTreeSet::new();
    for identified in [global, local] {
        ambiguous.extend(identified.ambiguous);
        for m in identified.matches {
            let data = identified
                .data_bindings
                .get(&m.entry)
                .cloned()
                .unwrap_or_default();
            if let Some(previous) = data_bindings.get(&m.entry) {
                if previous != &data {
                    data_conflicts.insert(m.entry);
                }
            } else {
                data_bindings.insert(m.entry, data);
            }
            if let Some(previous) = matches.get(&m.entry) {
                if previous != &m {
                    conflicts.insert(m.entry);
                    ambiguous.extend([previous.name.clone(), m.name.clone()]);
                }
            } else {
                matches.insert(m.entry, m);
            }
        }
    }
    matches.retain(|entry, _| !conflicts.contains(entry));
    ambiguous.retain(|name| !matches.values().any(|m| &m.name == name));
    data_bindings.retain(|entry, data| {
        !data.is_empty() && matches.contains_key(entry) && !data_conflicts.contains(entry)
    });
    Identification {
        matches: matches.into_values().collect(),
        ambiguous,
        data_bindings,
    }
}

fn resolve(
    image: &CodeImage,
    mut found: BTreeMap<(u32, &str), Vec<&Signature>>,
    namespace: &impl Fn(u32) -> usize,
) -> Identification {
    // A call relocation to a function identified elsewhere must jump to it
    // (ADR-0171), and a data symbol must have the address identified
    // functions give it while no other global has that address (ADR-0182):
    // drop the variants that disagree, until nothing changes.
    loop {
        let settled = settle(&found, namespace);
        let mut symbols: BTreeMap<(usize, &str), BTreeSet<u32>> = BTreeMap::new();
        for ((entry, name), sigs) in &found {
            if settled.contains_key(&(namespace(*entry), *name)) {
                for sig in sigs {
                    for (symbol, value) in data_symbols(image, *entry, sig) {
                        symbols
                            .entry((namespace(*entry), symbol))
                            .or_default()
                            .insert(value);
                    }
                }
            }
        }
        let before: usize = found.values().map(Vec::len).sum();
        for ((entry, _), sigs) in found.iter_mut() {
            sigs.retain(|sig| {
                sig.calls.iter().all(|(offset, callee)| {
                    let entries: BTreeSet<_> = settled
                        .iter()
                        .filter(|((_, name), _)| *name == callee)
                        .flat_map(|(_, entries)| entries)
                        .collect();
                    entries.is_empty()
                        || jump_target(image, entry + offset).is_some_and(|t| entries.contains(&t))
                }) && data_symbols(image, *entry, sig)
                    .into_iter()
                    .all(|(symbol, value)| {
                        symbols
                            .get(&(namespace(*entry), symbol))
                            .is_none_or(|v| v.contains(&value))
                            && !symbols.iter().any(|((scope, other), v)| {
                                *scope == namespace(*entry)
                                    && *other != symbol
                                    && global(other)
                                    && global(symbol)
                                    && v.contains(&value)
                            })
                    })
            });
        }
        found.retain(|_, sigs| !sigs.is_empty());
        if found.values().map(Vec::len).sum::<usize>() == before {
            break;
        }
    }
    let settled = settle(&found, namespace);
    let mut out = Identification::default();
    for ((entry, name), sigs) in &found {
        if settled.contains_key(&(namespace(*entry), *name)) {
            let data = bindings::collect(image, *entry, sigs);
            if !data.is_empty() {
                out.data_bindings.insert(GuestAddr(*entry), data);
            }
            out.matches.push(Match {
                entry: GuestAddr(*entry),
                name: name.to_string(),
                size: sigs[0].size,
            });
        } else {
            out.ambiguous.insert(name.to_string());
        }
    }
    out
}

/// Names identified by the candidates: each of a name's addresses carries
/// only that name, and a name at several addresses in one namespace is identified only when
/// none of its matching variants has a relocation, so every copy is the same
/// code (ADR-0171).
fn settle<'a>(
    found: &BTreeMap<(u32, &'a str), Vec<&Signature>>,
    namespace: &impl Fn(u32) -> usize,
) -> BTreeMap<(usize, &'a str), BTreeSet<u32>> {
    let mut by_name: BTreeMap<(usize, &str), BTreeSet<u32>> = BTreeMap::new();
    let mut by_entry: BTreeMap<u32, usize> = BTreeMap::new();
    for (entry, name) in found.keys() {
        by_name
            .entry((namespace(*entry), name))
            .or_default()
            .insert(*entry);
        *by_entry.entry(*entry).or_default() += 1;
    }
    by_name.retain(|(_, name), entries| {
        entries.iter().all(|e| by_entry[e] == 1)
            && (entries.len() == 1
                || entries
                    .iter()
                    .all(|e| found[&(*e, *name)].iter().all(|s| s.relocs.is_empty())))
    });
    by_name
}

/// Each data symbol's address in the match of `sig` at `entry`: its first
/// `.hi16` word's immediate, shifted, plus its first `.lo16` word's signed
/// immediate.
fn data_symbols<'s>(image: &CodeImage, entry: u32, sig: &'s Signature) -> Vec<(&'s str, u32)> {
    sig.data
        .iter()
        .filter_map(|(symbol, (hi, lo))| {
            let hi = image.word(GuestAddr(entry + hi.first()?))?;
            let lo = image.word(GuestAddr(entry + lo.first()?))?;
            Some((symbol.as_str(), (hi << 16).wrapping_add(lo as i16 as u32)))
        })
        .collect()
}

/// A named global, not one of n64sym's section-relative names such as
/// `vimgr_data_0010`, which may alias a global at the same address.
fn global(symbol: &str) -> bool {
    let mut parts = symbol.rsplitn(3, '_');
    let (offset, section) = (parts.next(), parts.next());
    !(matches!(section, Some("text" | "data" | "rodata" | "bss"))
        && offset.is_some_and(|o| !o.is_empty() && o.chars().all(|c| c.is_ascii_hexdigit())))
}

/// Target of the J or JAL at `pc`.
fn jump_target(image: &CodeImage, pc: u32) -> Option<u32> {
    let word = image.word(GuestAddr(pc))?;
    matches!(word >> 26, 2 | 3)
        .then(|| (pc.wrapping_add(4) & 0xf000_0000) | (word & 0x03ff_ffff) << 2)
}

/// Name runtime functions from a reference symbol map instead of signatures
/// (ADR-0148): a decomp's linker map or splat `symbol_addrs`, parsed by
/// [`crate::recall::parse_symbols`]. Only word-aligned entries inside the
/// image count, and a name at several addresses is ambiguous. Sizes are not
/// known, so matches carry size 0.
pub fn from_symbols(
    image: &CodeImage,
    symbols: &BTreeMap<u32, String>,
    wanted: &[&str],
) -> Identification {
    let start = image.base.pc.0;
    let mut by_name: BTreeMap<&str, Vec<u32>> = BTreeMap::new();
    for (entry, name) in symbols.range(start..) {
        if image.word(GuestAddr(*entry)).is_some() && wanted.contains(&name.as_str()) {
            by_name.entry(name).or_default().push(*entry);
        }
    }
    let mut out = Identification::default();
    for (name, entries) in by_name {
        match entries.as_slice() {
            [entry] => out.matches.push(Match {
                entry: GuestAddr(*entry),
                name: name.into(),
                size: 0,
            }),
            _ => {
                out.ambiguous.insert(name.into());
            }
        }
    }
    out
}

/// Signature identification, completed from a reference symbol map only
/// where the ROM's own bytes leave a name open (ADR-0171). A map name that a
/// signature places at another address, or at an address a signature gives
/// another name, disagrees with the ROM: it is left out and reported as
/// ambiguous; in the first case the signature's match goes too. Returns the
/// names that rest on the map alone.
pub fn with_reference_map(
    signatures: Identification,
    map: Identification,
) -> (Identification, BTreeSet<String>) {
    let mut by_name: BTreeMap<String, BTreeSet<u32>> = BTreeMap::new();
    for m in &signatures.matches {
        by_name.entry(m.name.clone()).or_default().insert(m.entry.0);
    }
    let named: BTreeSet<u32> = signatures.matches.iter().map(|m| m.entry.0).collect();
    let mut out = signatures;
    let mut map_only = BTreeSet::new();
    let mut conflicts = BTreeSet::new();
    for m in map.matches {
        match by_name.get(&m.name) {
            Some(entries) if entries.contains(&m.entry.0) => {}
            Some(_) => {
                conflicts.insert(m.name);
            }
            None if named.contains(&m.entry.0) => {
                conflicts.insert(m.name);
            }
            None => {
                map_only.insert(m.name.clone());
                out.matches.push(m);
            }
        }
    }
    out.matches.retain(|m| !conflicts.contains(&m.name));
    out.data_bindings
        .retain(|entry, _| out.matches.iter().any(|m| m.entry == *entry));
    map_only.retain(|n| !conflicts.contains(n));
    out.ambiguous.extend(map.ambiguous);
    out.ambiguous.extend(conflicts);
    out.ambiguous
        .retain(|n| !out.matches.iter().any(|m| &m.name == n));
    out.matches.sort();
    (out, map_only)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::program::CodeAddress;

    #[test]
    fn crc32_is_the_zlib_polynomial() {
        assert_eq!(crc32(b"123456789"), 0xcbf4_3926);
    }

    // addiu sp,-24; sw ra,20(sp); jal <reloc>; nop; lw ra,20(sp); jr ra; addiu sp,24
    const BODY: [u32; 7] = [
        0x27bd_ffe8,
        0xafbf_0014,
        0x0c00_0000,
        0,
        0x8fbf_0014,
        0x03e0_0008,
        0x27bd_0018,
    ];

    fn sig_text(name: &str) -> String {
        let relocs = BTreeMap::from([(8, Reloc::Targ26)]);
        let crc_a = stripped_crc(&BODY[..2], &relocs);
        let crc_b = stripped_crc(&BODY, &relocs);
        format!(
            "# sig_v1

{name} 0x1C 0x{crc_a:08X} 0x{crc_b:08X}
 .targ26 callee 0x008
"
        )
    }

    fn image(copies: &[(usize, u32)]) -> CodeImage {
        let mut words = vec![0; 64];
        for (at, target) in copies {
            words[*at..*at + 7].copy_from_slice(&BODY);
            words[at + 2] |= target >> 2 & 0x03ff_ffff;
        }
        CodeImage {
            base: CodeAddress {
                pc: GuestAddr(0x8000_0400),
                image: "t".into(),
                generation: 0,
            },
            words,
            rom_offset: None,
            physical_start: None,
            holes: Vec::new(),
            slots: Vec::new(),
        }
    }

    #[test]
    fn matches_ignore_relocated_fields_and_fail_closed_on_ambiguity() {
        let sigs = parse(&sig_text("osCreateThread")).unwrap();
        let one = identify(&image(&[(8, 0x8000_1234)]), &sigs, RUNTIME_FUNCTIONS);
        assert_eq!(
            one.matches,
            vec![Match {
                entry: GuestAddr(0x8000_0420),
                name: "osCreateThread".into(),
                size: 0x1c,
            }]
        );
        assert!(one.ambiguous.is_empty());
        assert!(
            identify(&image(&[(8, 0)]), &sigs, &["osStartThread"])
                .matches
                .is_empty()
        );
        let two = identify(
            &image(&[(8, 0x8000_1234), (30, 0x8000_5678)]),
            &sigs,
            RUNTIME_FUNCTIONS,
        );
        assert!(two.matches.is_empty());
        assert_eq!(
            two.ambiguous,
            BTreeSet::from(["osCreateThread".to_string()])
        );
        // an unrelocated word that differs breaks the match
        let mut changed = image(&[(8, 0)]);
        changed.words[12] = 0x8fbf_0018;
        assert!(
            identify(&changed, &sigs, RUNTIME_FUNCTIONS)
                .matches
                .is_empty()
        );
        // two names on one address are ambiguous
        let both = parse(&(sig_text("osStartThread") + &sig_text("osCreateThread"))).unwrap();
        let shared = identify(&image(&[(8, 0)]), &both, RUNTIME_FUNCTIONS);
        assert!(shared.matches.is_empty() && shared.ambiguous.len() == 2);
        assert_eq!(callback_registers("osCreateThread"), vec![6]);
    }

    #[test]
    fn symbol_maps_name_runtime_functions_inside_the_image() {
        let symbols = BTreeMap::from([
            (0x8000_0420, "osCreateThread".to_string()),
            (0x8000_0440, "game_main".to_string()),
            (0x8000_0460, "osSendMesg".to_string()),
            (0x8000_0480, "osSendMesg".to_string()),
            (0x8000_0502, "osRecvMesg".to_string()),
            (0x8000_0600, "osGetTime".to_string()),
        ]);
        let found = from_symbols(&image(&[]), &symbols, RUNTIME_FUNCTIONS);
        assert_eq!(
            found.matches,
            vec![Match {
                entry: GuestAddr(0x8000_0420),
                name: "osCreateThread".into(),
                size: 0,
            }]
        );
        // osRecvMesg is misaligned and osGetTime lies past the 64-word image
        assert_eq!(found.ambiguous, BTreeSet::from(["osSendMesg".to_string()]));
    }

    /// A signature line for `words`, with `.targ26` relocations calling the
    /// named symbols at the given offsets.
    fn sig_for(name: &str, words: &[u32], calls: &[(u32, &str)]) -> String {
        let relocs: BTreeMap<u32, Reloc> = calls.iter().map(|(o, _)| (*o, Reloc::Targ26)).collect();
        let (a, b) = (
            stripped_crc(&words[..2], &relocs),
            stripped_crc(words, &relocs),
        );
        let mut text = format!("{name} 0x{:X} 0x{a:08X} 0x{b:08X}\n", words.len() * 4);
        for (offset, symbol) in calls {
            text += &format!(" .targ26 {symbol} 0x{offset:03X}\n");
        }
        text
    }

    #[test]
    fn call_relocations_and_identical_copies_settle_names() {
        // two leaves at 0x400 and 0x410; BODY at 0x420 calls the first and at
        // 0x450 calls the second, as osEepromLongWrite and osEepromLongRead
        // compile to the same code apart from that call
        let write = [0x2402_0001, 0x03e0_0008, 0];
        let read = [0x2402_0002, 0x03e0_0008, 0];
        let copy = [0x2402_0003, 0x03e0_0008, 0];
        let mut img = image(&[(8, 0x8000_0400), (20, 0x8000_0410)]);
        for (at, words) in [(0, write), (4, read), (40, copy), (44, copy)] {
            img.words[at..at + 3].copy_from_slice(&words);
        }
        let text = sig_for("osEepromWrite", &write, &[])
            + &sig_for("osEepromRead", &read, &[])
            + &sig_for("osEepromLongWrite", &BODY, &[(8, "osEepromWrite")])
            + &sig_for("__ull_rem", &copy, &[]);
        let found = identify(&img, &parse(&text).unwrap(), RUNTIME_FUNCTIONS);
        let at = |name: &str| -> Vec<u32> {
            found
                .matches
                .iter()
                .filter(|m| m.name == name)
                .map(|m| m.entry.0)
                .collect()
        };
        assert_eq!(at("osEepromLongWrite"), [0x8000_0420]);
        // relocation-free code at two addresses is the same function twice
        assert_eq!(at("__ull_rem"), [0x8000_04a0, 0x8000_04b0]);
        assert!(found.ambiguous.is_empty(), "{:?}", found.ambiguous);
        // without the callee identified, the relocation cannot decide
        let text = sig_for("osEepromLongWrite", &BODY, &[(8, "osEepromWrite")]);
        let open = identify(&img, &parse(&text).unwrap(), RUNTIME_FUNCTIONS);
        assert!(open.matches.is_empty());
        assert_eq!(
            open.ambiguous,
            BTreeSet::from(["osEepromLongWrite".to_string()])
        );
    }

    /// A signature line for `words` loading one data symbol through a
    /// `.hi16` at 0 and a `.lo16` at 4.
    fn sig_data(name: &str, words: &[u32], symbol: &str) -> String {
        let relocs = BTreeMap::from([(0, Reloc::Half), (4, Reloc::Half)]);
        let (a, b) = (
            stripped_crc(&words[..2], &relocs),
            stripped_crc(words, &relocs),
        );
        format!(
            "{name} 0x{:X} 0x{a:08X} 0x{b:08X}\n .hi16 {symbol} 0x000\n .lo16 {symbol} 0x004\n",
            words.len() * 4
        )
    }

    #[test]
    fn data_symbols_settle_lookalike_getters() {
        // lui t6, %hi(sym); lw t6, %lo(sym)(t6); then a read or a write of
        // the framebuffer field: the current- and next-framebuffer getters
        // differ only in the relocated global (ADR-0182)
        let lui = 0x3c0e_8000;
        let get = |lo: u32| [lui, 0x8dce_0000 | lo, 0x8dc2_0004, 0x03e0_0008, 0];
        let swap = [lui, 0x8dce_1004, 0xadc4_0004, 0x03e0_0008, 0];
        let mut img = image(&[]);
        img.words[0..5].copy_from_slice(&get(0x1000)); // reads __osViCurr
        img.words[8..13].copy_from_slice(&get(0x1004)); // reads __osViNext
        img.words[16..21].copy_from_slice(&swap);
        let getter = sig_data("osViGetCurrentFramebuffer", &get(0), "__osViCurr");
        let open = identify(&img, &parse(&getter).unwrap(), RUNTIME_FUNCTIONS);
        assert!(open.matches.is_empty());
        let text = getter.clone() + &sig_data("osViSwapBuffer", &swap, "__osViNext");
        let found = identify(&img, &parse(&text).unwrap(), RUNTIME_FUNCTIONS);
        let at: BTreeMap<_, _> = found
            .matches
            .iter()
            .map(|m| (m.name.as_str(), m.entry.0))
            .collect();
        assert_eq!(at["osViGetCurrentFramebuffer"], 0x8000_0400);
        assert_eq!(at["osViSwapBuffer"], 0x8000_0440);
        assert_eq!(
            found.data_bindings[&GuestAddr(0x8000_0400)]["__osViCurr"],
            GuestAddr(0x8000_1000)
        );
        assert!(found.ambiguous.is_empty(), "{:?}", found.ambiguous);
        // a section-relative name may alias a global, so it decides nothing
        let alias = getter + &sig_data("osViSwapBuffer", &swap, "vimgr_data_0004");
        let still = identify(&img, &parse(&alias).unwrap(), RUNTIME_FUNCTIONS);
        assert!(still.ambiguous.contains("osViGetCurrentFramebuffer"));
        assert!(global("__osViNext") && !global("vimgr_data_0004") && global("osViSwapBuffer"));
    }

    #[test]
    fn disjoint_sdk_copies_have_independent_globals_and_name_uniqueness() {
        let get = |lo: u32| [0x3c0e_8000, 0x8dce_0000 | lo, 0x8dc2_0004, 0x03e0_0008, 0];
        let anchor = |lo: u32| [0x3c0e_8000, 0x8dce_0000 | lo, 0xadc4_0004, 0x03e0_0008, 0];
        let mut img = image(&[]);
        for (at, words) in [
            (0, get(0x1000)),
            (8, anchor(0x1000)),
            (32, get(0x2000)),
            (40, anchor(0x2000)),
        ] {
            img.words[at..at + 5].copy_from_slice(&words);
        }
        let text = sig_data("osViGetCurrentFramebuffer", &get(0), "__osViCurr")
            + &sig_data("osViSwapBuffer", &anchor(0), "__osViCurr");
        let sigs = parse(&text).unwrap();
        // Two relocated copies inside one supplied component remain ambiguous.
        assert!(identify(&img, &sigs, RUNTIME_FUNCTIONS).matches.is_empty());
        img.holes.push(crate::program::GuestRange {
            start: GuestAddr(0x8000_0440),
            size: 0x40,
        });
        let found = identify(&img, &sigs, RUNTIME_FUNCTIONS);
        assert_eq!(found.matches.len(), 4);
        assert!(found.ambiguous.is_empty());
        assert_eq!(
            found.data_bindings[&GuestAddr(0x8000_0400)]["__osViCurr"],
            GuestAddr(0x8000_1000)
        );
        assert_eq!(
            found.data_bindings[&GuestAddr(0x8000_0480)]["__osViCurr"],
            GuestAddr(0x8000_2000)
        );
        // In each component a different named global still excludes a lookalike.
        let wrong = text + &sig_data("osViGetNextFramebuffer", &get(0), "__osViNext");
        assert_eq!(
            identify(&img, &parse(&wrong).unwrap(), RUNTIME_FUNCTIONS).matches,
            found.matches
        );
        // Crossing a gap never supplies a complete signature.
        img.holes[0].start = GuestAddr(0x8000_0408);
        assert_eq!(identify(&img, &sigs, RUNTIME_FUNCTIONS).matches.len(), 2);
    }

    #[test]
    fn call_relocations_still_check_callees_across_disjoint_images() {
        let leaf = [0x2402_0001, 0x03e0_0008, 0];
        let mut img = image(&[(0, 0x8000_0480)]);
        img.words[32..35].copy_from_slice(&leaf);
        img.holes.push(crate::program::GuestRange {
            start: GuestAddr(0x8000_0440),
            size: 0x40,
        });
        let text = sig_for("osEepromLongWrite", &BODY, &[(8, "osEepromWrite")])
            + &sig_for("osEepromWrite", &leaf, &[]);
        let sigs = parse(&text).unwrap();
        assert_eq!(identify(&img, &sigs, RUNTIME_FUNCTIONS).matches.len(), 2);
        img.words[2] += 4; // identical masked CRC, but wrong cross-image call
        let found = identify(&img, &sigs, RUNTIME_FUNCTIONS);
        assert_eq!(found.matches.len(), 1);
        assert_eq!(found.matches[0].name, "osEepromWrite");
    }

    #[test]
    fn constant_return_switch_arms_do_not_identify_runtime_services() {
        let mut img = image(&[]);
        for slot in [0x2402_000b, 0x3402_000b] {
            let stub = [0x03e0_0008, slot];
            img.words[..2].copy_from_slice(&stub);
            let sigs = parse(&sig_for("osVoiceInit", &stub, &[])).unwrap();
            let found = identify(&img, &sigs, RUNTIME_FUNCTIONS);
            assert!(found.matches.is_empty());
            assert!(found.ambiguous.is_empty());
        }
        // A small effectful function is still eligible for its exact signature.
        let effectful = [0x03e0_0008, 0x4442_f800]; // return FCSR
        img.words[..2].copy_from_slice(&effectful);
        let sigs = parse(&sig_for("__osSetFpcCsr", &effectful, &[])).unwrap();
        assert_eq!(identify(&img, &sigs, RUNTIME_FUNCTIONS).matches.len(), 1);
    }

    #[test]
    fn whole_image_data_evidence_still_identifies_services_split_across_images() {
        let get = |lo: u32| [0x3c0e_8000, 0x8dce_0000 | lo, 0x8dc2_0004, 0x03e0_0008, 0];
        let swap = [0x3c0e_8000, 0x8dce_1004, 0xadc4_0004, 0x03e0_0008, 0];
        let mut img = image(&[]);
        img.words[..5].copy_from_slice(&get(0x1000));
        img.words[8..13].copy_from_slice(&get(0x1004));
        img.words[32..37].copy_from_slice(&swap);
        img.holes.push(crate::program::GuestRange {
            start: GuestAddr(0x8000_0440),
            size: 0x40,
        });
        let text = sig_data("osViGetCurrentFramebuffer", &get(0), "__osViCurr")
            + &sig_data("osViSwapBuffer", &swap, "__osViNext");
        let found = identify(&img, &parse(&text).unwrap(), RUNTIME_FUNCTIONS);
        assert_eq!(found.matches.len(), 2);
        assert_eq!(found.matches[0].entry.0, 0x8000_0400);
        assert_eq!(found.matches[1].entry.0, 0x8000_0480);
        assert!(found.ambiguous.is_empty());
    }

    #[test]
    fn conflicting_identifications_never_select_a_runtime_boundary() {
        let declaration = |name: &str, size| Identification {
            matches: vec![Match {
                entry: GuestAddr(0x8000_0400),
                name: name.into(),
                size,
            }],
            ambiguous: BTreeSet::new(),
            data_bindings: BTreeMap::new(),
        };
        let identical = combine(declaration("osGetTime", 12), declaration("osGetTime", 12));
        assert_eq!(identical.matches.len(), 1);
        for (name, size) in [("osSetTime", 12), ("osGetTime", 16)] {
            let conflict = combine(declaration("osGetTime", 12), declaration(name, size));
            assert!(conflict.matches.is_empty());
            assert!(conflict.ambiguous.contains("osGetTime"));
            assert!(conflict.ambiguous.contains(name));
        }
        let mut first = declaration("osGetTime", 12);
        first.data_bindings.insert(
            GuestAddr(0x8000_0400),
            [("global".into(), GuestAddr(0x8000_1000))].into(),
        );
        let mut other = first.clone();
        other
            .data_bindings
            .get_mut(&GuestAddr(0x8000_0400))
            .unwrap()
            .insert("global".into(), GuestAddr(0x8000_2000));
        let conflict = combine(first, other);
        assert_eq!(conflict.matches.len(), 1);
        assert!(conflict.data_bindings.is_empty());
    }

    #[test]
    fn a_reference_map_fills_only_what_the_rom_leaves_open() {
        let m = |name: &str, entry: u32| Match {
            entry: GuestAddr(entry),
            name: name.into(),
            size: 0,
        };
        let mut signatures = Identification {
            matches: vec![m("osEepromWrite", 0x400), m("osGetTime", 0x430)],
            ambiguous: BTreeSet::from(["osInitialize".to_string()]),
            data_bindings: BTreeMap::new(),
        };
        signatures.data_bindings.insert(
            GuestAddr(0x430),
            [("global".into(), GuestAddr(0x1000))].into(),
        );
        let map = Identification {
            matches: vec![
                m("osEepromWrite", 0x400), // agrees
                m("osInitialize", 0x500),  // the ROM leaves it open
                m("osGetTime", 0x440),     // the ROM puts it elsewhere
                m("osContInit", 0x400),    // the ROM names that address
            ],
            ambiguous: BTreeSet::from(["osSendMesg".to_string()]),
            data_bindings: BTreeMap::new(),
        };
        let (found, map_only) = with_reference_map(signatures, map);
        assert!(found.data_bindings.is_empty());
        assert_eq!(
            found.matches,
            [m("osEepromWrite", 0x400), m("osInitialize", 0x500)]
        );
        assert_eq!(map_only, BTreeSet::from(["osInitialize".to_string()]));
        let ambiguous: Vec<_> = found.ambiguous.iter().map(String::as_str).collect();
        assert_eq!(ambiguous, ["osContInit", "osGetTime", "osSendMesg"]);
    }

    #[test]
    fn parse_rejects_malformed_signature_files() {
        assert!(
            parse(
                ".targ26 x 0x0
"
            )
            .is_err()
        );
        assert!(
            parse(
                "f 0x8 0x0 0x0
 .targ26 x 0x8
"
            )
            .is_err()
        );
        assert!(
            parse(
                "f 0x8 0x0
"
            )
            .is_err()
        );
        assert!(
            parse(
                "f 0x8 zz 0x0
"
            )
            .is_err()
        );
    }
}
