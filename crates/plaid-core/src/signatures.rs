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

/// Functions N64Recomp's runtime reimplements (`reimplemented_funcs` in
/// N64Recomp `src/symbol_lists.cpp`, MIT, Copyright (c) 2024 Wiseguy).
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
    "osFlashInit", "osFlashReadStatus", "osFlashReadId", "osFlashClearStatus",
    "osFlashAllErase", "osFlashAllEraseThrough", "osFlashSectorErase",
    "osFlashSectorEraseThrough", "osFlashCheckEraseEnd", "osFlashWriteBuffer",
    "osFlashWriteArray", "osFlashReadArray", "osFlashChange",
    "osCreateThread", "osStartThread", "osStopThread", "osDestroyThread",
    "osSetThreadPri", "osGetThreadPri", "osGetThreadId",
    "osCreateMesgQueue", "osRecvMesg", "osSendMesg", "osJamMesg", "osSetEventMesg",
    "osGetTime", "osSetTime", "osSetTimer", "osStopTimer",
    "osVoiceSetWord", "osVoiceCheckWord", "osVoiceStopReadData", "osVoiceInit",
    "osVoiceMaskDictionary", "osVoiceStartReadData", "osVoiceControlGain",
    "osVoiceGetReadData", "osVoiceClearDictionary",
    "osSetIntMask", "__osDisableInt", "__osRestoreInt",
    "osVirtualToPhysical",
    "osGetCount", "osSetCount", "__osSetFpcCsr",
    "osInvalDCache", "osInvalICache", "osWritebackDCache", "osWritebackDCacheAll",
    "is_proutSyncPrintf", "__checkHardware_msp", "__checkHardware_kmc", "__checkHardware_isv",
    "__osInitialize_msp", "__osInitialize_kmc", "__osInitialize_isv", "__osRdbSend",
    "__ull_div", "__ll_div", "__ll_mul", "__ull_rem", "__ull_to_d", "__ull_to_f",
];

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
}

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct Match {
    pub entry: GuestAddr,
    pub name: String,
    pub size: u32,
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Identification {
    /// One address per name and one name per address.
    pub matches: Vec<Match>,
    /// Names left undeclared because they matched several addresses, or
    /// shared an address with another name.
    pub ambiguous: BTreeSet<String>,
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
            [kind @ (".targ26" | ".hi16" | ".lo16"), _, offsets @ ..] if !offsets.is_empty() => {
                let sig = out
                    .last_mut()
                    .ok_or(format!("line {}: relocation before symbol", n + 1))?;
                for offset in offsets {
                    let offset = number(offset)?;
                    if offset % 4 != 0 || offset + 4 > sig.size {
                        return Err(format!("line {}: relocation outside {}", n + 1, sig.name));
                    }
                    let reloc = if *kind == ".targ26" {
                        Reloc::Targ26
                    } else {
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
            }),
            _ => return Err(format!("line {}: not a sig_v1 line", n + 1)),
        }
    }
    Ok(out)
}

fn crc32(bytes: &[u8]) -> u32 {
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
    // (entry, name) -> size; a name can have several signature variants
    let mut found: BTreeMap<(u32, &str), u32> = BTreeMap::new();
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
                if end <= image.words.len()
                    && stripped_crc(&image.words[at..end], &sig.relocs) == sig.crc_b
                {
                    found.insert(
                        (image.base.pc.0 + at as u32 * 4, sig.name.as_str()),
                        sig.size,
                    );
                }
            }
        }
    }
    let mut by_name: BTreeMap<&str, BTreeSet<u32>> = BTreeMap::new();
    let mut by_entry: BTreeMap<u32, BTreeSet<&str>> = BTreeMap::new();
    for (entry, name) in found.keys() {
        by_name.entry(name).or_default().insert(*entry);
        by_entry.entry(*entry).or_default().insert(name);
    }
    let mut out = Identification::default();
    for ((entry, name), size) in found {
        if by_name[name].len() == 1 && by_entry[&entry].len() == 1 {
            out.matches.push(Match {
                entry: GuestAddr(entry),
                name: name.into(),
                size,
            });
        } else {
            out.ambiguous.insert(name.into());
        }
    }
    out
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
