//! Discovery roots from function pointers stored as data (ADR-0152).
//!
//! Most of a data-driven game's code is reached only through pointers in its
//! data: SM64's behavior scripts, geo layouts and level scripts all name
//! functions by address, and code takes other functions' addresses with
//! `lui`/`addiu` pairs. This scan proposes discovery roots, not closure
//! facts. A wrong root decodes junk whose blockers keep the map OPEN; it
//! never closes anything.
use crate::{GuestAddr, discovery::CodeImage, program::ProgramMap};
use std::collections::{BTreeMap, BTreeSet};

const JR_RA: u32 = 0x03e0_0008;

/// Whether `pc` starts a function by layout: the image start, a declared
/// load's start (`starts`), or right after a `jr ra` and its delay slot,
/// possibly followed by zero padding.
fn after_return(image: &CodeImage, pc: GuestAddr, starts: &BTreeSet<u32>) -> bool {
    if pc == image.base.pc || starts.contains(&pc.0) {
        return true;
    }
    let word = |back: u32| {
        pc.0.checked_sub(back)
            .and_then(|a| image.word(GuestAddr(a)))
    };
    // after a hole: a declared load (a relocatable overlay's text, say)
    // begins with a function (ADR-0181)
    if word(4).is_none() {
        return true;
    }
    if word(8) == Some(JR_RA) {
        return true;
    }
    // `jr ra; nop` then padding: skip at least one zero word
    let mut back = 4;
    while back <= 32 && word(back) == Some(0) {
        back += 4;
    }
    back > 4 && word(back) == Some(JR_RA)
}

/// Addresses built in code by `lui r, hi` and a later `addiu`/`ori` from `r`
/// within 16 words, the way compiled code takes a function's address.
fn code_constants(image: &CodeImage) -> impl Iterator<Item = u32> + '_ {
    image.words.iter().enumerate().flat_map(move |(i, &w)| {
        let rt = (w >> 16) & 31;
        let hi = (w & 0xffff) << 16;
        let lui = w >> 26 == 15 && rt != 0;
        image.words[i + 1..]
            .iter()
            .take(if lui { 16 } else { 0 })
            .filter(move |&&x| matches!(x >> 26, 9 | 13) && (x >> 21) & 31 == rt)
            .map(move |&x| {
                if x >> 26 == 13 {
                    hi | (x & 0xffff)
                } else {
                    hi.wrapping_add(x as i16 as u32)
                }
            })
    })
}

/// The word after each `jr ra`'s delay slot and any zero padding: where the
/// next function starts when functions are laid out back to back, including
/// ones nothing references.
fn after_returns(image: &CodeImage) -> impl Iterator<Item = u32> + '_ {
    image.words.iter().enumerate().filter_map(move |(i, &w)| {
        if w != JR_RA {
            return None;
        }
        let mut next = i + 2;
        while next < image.words.len() && next < i + 10 && image.words[next] == 0 {
            next += 1;
        }
        Some(image.base.pc.0.wrapping_add(4 * next as u32))
    })
}

fn function_start(image: &CodeImage, pc: GuestAddr, starts: &BTreeSet<u32>) -> bool {
    pc.0.is_multiple_of(4)
        && image
            .word(pc)
            .is_some_and(|w| w != 0 && crate::discovery::decode(w, pc).is_valid())
        && after_return(image, pc, starts)
}

/// Function starts in `image` named by aligned big-endian words of `bytes`
/// (a whole ROM, say) or by an address constant built in the image's code.
pub fn scan(bytes: &[u8], image: &CodeImage) -> BTreeSet<GuestAddr> {
    bytes
        .as_chunks::<4>()
        .0
        .iter()
        .map(|w| u32::from_be_bytes(*w))
        .chain(code_constants(image))
        .map(GuestAddr)
        .filter(|&pc| function_start(image, pc, &BTreeSet::new()))
        .collect()
}

/// Whether the words from `pc` to its first `jr ra` and delay slot can be
/// CPU code: every word decodes, none is a COP2 or COP3 access, which the
/// VR4300 lacks, and every direct jump or branch lands in the image (RSP
/// microcode is the usual impostor, ADR-0155).
fn cpu_code(image: &CodeImage, pc: GuestAddr) -> bool {
    let mut at = pc.0;
    for _ in 0..4096 {
        let Some(w) = image.word(GuestAddr(at)) else {
            return false;
        };
        let i = crate::discovery::decode(w, GuestAddr(at));
        if matches!(w >> 26, 18 | 19 | 50 | 54 | 58 | 62) || !i.is_valid() {
            return false;
        }
        let target = if i.is_jump_with_address() {
            Some((at.wrapping_add(4) & 0xf000_0000) | ((w & 0x03ff_ffff) << 2))
        } else if i.is_branch() {
            Some(
                at.wrapping_add(4)
                    .wrapping_add_signed(i32::from(w as i16) * 4),
            )
        } else {
            None
        };
        if target.is_some_and(|t| image.word(GuestAddr(t)).is_none()) {
            return false;
        }
        if w == JR_RA {
            return image.word(GuestAddr(at.wrapping_add(4))).is_some();
        }
        at = at.wrapping_add(4);
    }
    false
}

/// Whether `pc` can be an address-taken function: a function start by
/// layout whose body can be CPU code (ADR-0153).
pub fn plausible(image: &CodeImage, pc: GuestAddr) -> bool {
    plausible_at(image, pc, &BTreeSet::new())
}

/// [`plausible`] where the declared loads starting at `starts` each begin
/// with a function (ADR-0182): relocatable overlays are packed back to back
/// at their link addresses, so the word before one is the last one's data.
pub fn plausible_at(image: &CodeImage, pc: GuestAddr, starts: &BTreeSet<u32>) -> bool {
    function_start(image, pc, starts) && cpu_code(image, pc)
}

/// Address-taken roots from data (ADR-0153): aligned words of `bytes` that
/// name a function start in `image` whose body can be CPU code.
/// A decodable Yaz0 stream contributes its decoded words instead of its
/// compressed bytes, which are not data (ADR-0175).
pub fn rom_words(bytes: &[u8], image: &CodeImage, starts: &BTreeSet<u32>) -> BTreeSet<GuestAddr> {
    let mut out = BTreeSet::new();
    let mut take = |words: &[u8]| {
        out.extend(
            words
                .as_chunks::<4>()
                .0
                .iter()
                .map(|w| GuestAddr(u32::from_be_bytes(*w)))
                .filter(|&pc| plausible_at(image, pc, starts)),
        )
    };
    let mut at = 0;
    let mut raw = 0;
    while at + 4 <= bytes.len() {
        if bytes[at..].starts_with(b"Yaz0")
            && let Ok((decoded, used)) = crate::declared_loads::yaz0_stream(&bytes[at..])
        {
            take(&bytes[raw..at]);
            take(&decoded);
            at += used.next_multiple_of(4);
            raw = at.min(bytes.len());
        } else {
            at += 4;
        }
    }
    take(&bytes[raw..]);
    out
}

/// Address constants (`lui r, hi` then `addiu`/`ori` from `r`) built in
/// decoded code of `map`, as `(function start, lui site)`. The pair is
/// followed through up to 16 decoded words in address order, across block
/// boundaries, until `r` is redefined: GCC puts the `lui` in a branch delay
/// slot and the `addiu` in a later block (ADR-0182). Constants in undecoded
/// bytes, such as a runtime function's body, do not count.
pub fn block_constants(
    image: &CodeImage,
    map: &ProgramMap,
    starts: &BTreeSet<u32>,
) -> BTreeMap<GuestAddr, GuestAddr> {
    let decoded: std::collections::HashSet<u32> = map
        .blocks
        .iter()
        .filter(|b| b.start.image == image.base.image)
        .flat_map(|b| (0..b.size / 4).map(move |i| b.start.pc.0 + 4 * i))
        .collect();
    let mut out = BTreeMap::new();
    for &at in &decoded {
        let Some(w) = image.word(GuestAddr(at)) else {
            continue;
        };
        let rt = (w >> 16) & 31;
        if w >> 26 != 15 || rt == 0 {
            continue;
        }
        let hi = (w & 0xffff) << 16;
        for q in (1..=16).map(|k| at.wrapping_add(4 * k)) {
            let Some(x) = image.word(GuestAddr(q)).filter(|_| decoded.contains(&q)) else {
                break;
            };
            if matches!(x >> 26, 9 | 13) && (x >> 21) & 31 == rt {
                let value = if x >> 26 == 13 {
                    hi | (x & 0xffff)
                } else {
                    hi.wrapping_add(x as i16 as u32)
                };
                let pc = GuestAddr(value);
                if plausible_at(image, pc, starts) {
                    let site = out.entry(pc).or_insert(GuestAddr(at));
                    *site = (*site).min(GuestAddr(at));
                }
            }
            if crate::discovery::decode(x, GuestAddr(0)).destination_gpr() == Some(rt) {
                break;
            }
        }
    }
    out
}

/// Function starts by layout after a return that discovery of `map` has not
/// already decoded: an early `jr ra` inside a decoded function is followed
/// by more of that function, not by a new one. Declared runtime functions
/// stay a boundary.
pub fn layout(image: &CodeImage, map: &ProgramMap) -> BTreeSet<GuestAddr> {
    let decoded: Vec<(u32, u32)> = map
        .blocks
        .iter()
        .filter(|b| b.start.image == image.base.image)
        .map(|b| (b.start.pc.0, b.start.pc.0.wrapping_add(b.size)))
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect();
    let inside = |pc: u32| {
        let i = decoded.partition_point(|(s, _)| *s <= pc);
        i > 0 && pc < decoded[i - 1].1
    };
    // IDO -O0 can leave a dead `jr ra` epilogue right after the real one
    after_returns(image)
        .filter(|&pc| {
            image.word(GuestAddr(pc)) != Some(JR_RA)
                && !inside(pc)
                && !map
                    .runtime_functions
                    .contains_key(&image.address(GuestAddr(pc)))
        })
        .map(GuestAddr)
        .filter(|&pc| function_start(image, pc, &BTreeSet::new()))
        .collect()
}

/// Producer of the address-taken evidence (ADR-0153).
pub const ADDRESS_TAKEN: &str = "plaid-address-taken/v0";

/// Discovery whose roots also include the address-taken functions: ROM words
/// first, then constants from decoded blocks, until no new function appears.
/// The set is recorded in `address_taken`; its functions stay map entries.
/// Declared runtime functions are a boundary and never join the set.
#[allow(clippy::too_many_arguments)]
pub fn discover_address_taken(
    rom: crate::program::RomIdentity,
    bytes: &[u8],
    image: &CodeImage,
    entries: &[GuestAddr],
    runtime: &[(GuestAddr, String, Vec<u8>)],
    evidence: Option<(String, crate::program::Evidence)>,
    starts: &BTreeSet<u32>,
    budget: usize,
) -> Result<crate::discovery::Discovery, String> {
    let runtime_entries: BTreeSet<GuestAddr> = runtime.iter().map(|(a, _, _)| *a).collect();
    let mut taken: BTreeSet<GuestAddr> = rom_words(bytes, image, starts)
        .into_iter()
        .filter(|a| !runtime_entries.contains(a))
        .collect();
    // each round starts from the last round's roots, so it does not repeat
    // the indirect passes that found them
    let mut seeds: BTreeSet<GuestAddr> = BTreeSet::new();
    loop {
        let roots: Vec<_> = entries
            .iter()
            .chain(&taken)
            .chain(&seeds)
            .copied()
            .collect::<BTreeSet<_>>()
            .into_iter()
            .collect();
        // return certificates add no roots, so they label only the last round
        let mut d = crate::pipeline::discover_labelled(
            rom.clone(),
            image,
            &roots,
            runtime,
            evidence.clone(),
            budget,
            false,
        )?;
        let before = taken.len();
        seeds.extend(
            d.map
                .entries
                .keys()
                .filter(|a| a.image == image.base.image && a.generation == image.base.generation)
                .map(|a| a.pc),
        );
        taken.extend(
            block_constants(image, &d.map, starts)
                .into_keys()
                .filter(|a| !runtime_entries.contains(a)),
        );
        if taken.len() == before {
            if !d.map.unresolved.iter().any(|u| u.kind == "resource_limit") {
                d.map = crate::returns::annotate(&d.map, image)?;
            }
            let id = format!("address-taken:{}", rom.sha256);
            d.map.evidence.insert(
                id.clone(),
                crate::program::Evidence {
                    kind: crate::EvidenceKind::Static,
                    producer: ADDRESS_TAKEN.into(),
                    revision: "0".into(),
                    detail: "function starts named by an aligned ROM word or a code constant in a decoded block, whose body can be CPU code (ADR-0153)".into(),
                },
            );
            for a in &taken {
                let address = image.address(*a);
                d.map
                    .address_taken
                    .insert(address.clone(), [id.clone()].into());
                if let Some(refs) = d.map.entries.get_mut(&address) {
                    refs.insert(id.clone());
                }
            }
            return Ok(d);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::program::CodeAddress;

    #[test]
    fn pointers_to_function_starts_become_roots() {
        // f0 at 0x80000000; f1 after `jr ra; addiu sp`; f2 after `jr ra; nop; nop`;
        // 0x80000010 is mid-function
        let words = vec![
            0x27bd_ffe8,
            JR_RA,
            0x27bd_0018,
            0x2402_0001,
            0x2402_0002,
            JR_RA,
            0,
            0,
            0x2402_0003,
        ];
        let image = CodeImage {
            base: CodeAddress {
                pc: GuestAddr(0x8000_0000),
                image: "roots".into(),
                generation: 0,
            },
            words,
            rom_offset: None,
            physical_start: None,
            holes: Vec::new(),
        };
        let data: Vec<u8> = [
            0x8000_0000u32,
            0x8000_000c,
            0x8000_0010,
            0x8000_0020,
            0x8000_0022,
            0x8000_0100,
            7,
        ]
        .iter()
        .flat_map(|w| w.to_be_bytes())
        .collect();
        assert_eq!(
            scan(&data, &image),
            BTreeSet::from([
                GuestAddr(0x8000_0000),
                GuestAddr(0x8000_000c),
                GuestAddr(0x8000_0020)
            ])
        );
    }

    #[test]
    fn yaz0_streams_contribute_decoded_words_not_compressed_bytes() {
        let image = CodeImage {
            base: CodeAddress {
                pc: GuestAddr(0x8000_0000),
                image: "roots".into(),
                generation: 0,
            },
            words: vec![
                0x27bd_ffe8,
                JR_RA,
                0x27bd_0018,
                0x2402_0001,
                0x2402_0002,
                JR_RA,
                0,
                0,
                0x2402_0003,
                JR_RA,
                0,
            ],
            rom_offset: None,
            physical_start: None,
            holes: Vec::new(),
        };
        let mut rom = b"Yaz0".to_vec();
        rom.extend(16u32.to_be_bytes());
        rom.extend([0; 8]);
        // the aligned compressed word at 20 reads 0x80000000; decoded, it is not data
        rom.extend([0xff, 0, 0, 0, 0x80, 0, 0, 0, 0]);
        // decoded word 2 is 0x80000020, which sits unaligned in the stream
        rom.extend([0xff, 0x80, 0, 0, 0x20, 0, 0, 0, 0]);
        rom.extend([0, 0]); // the 34-byte stream ends; scanning resumes at 36
        rom.extend(0x8000_000cu32.to_be_bytes());
        assert_eq!(
            rom_words(&rom, &image, &BTreeSet::new()),
            BTreeSet::from([GuestAddr(0x8000_000c), GuestAddr(0x8000_0020)])
        );
    }

    #[test]
    fn layout_roots_follow_returns_but_skip_decoded_code_and_dead_epilogues() {
        let words = vec![
            0x2402_0001, // f0 (decoded from the entry)
            JR_RA,
            0,
            0x2402_0002, // f1: nothing references it
            JR_RA,
            0,
            JR_RA, // IDO's dead duplicate epilogue
            0,
            0x2402_0003, // f2
            JR_RA,
            0,
        ];
        let image = CodeImage {
            base: CodeAddress {
                pc: GuestAddr(0x8000_0000),
                image: "layout".into(),
                generation: 0,
            },
            words,
            rom_offset: None,
            physical_start: None,
            holes: Vec::new(),
        };
        let rom = crate::program::RomIdentity {
            sha256: "a".repeat(64),
            size: 4096,
        };
        let map = crate::discovery::direct_cfg(rom, &image, &[image.base.pc], 100)
            .unwrap()
            .map;
        assert_eq!(
            layout(&image, &map),
            BTreeSet::from([GuestAddr(0x8000_000c), GuestAddr(0x8000_0020)])
        );
    }

    #[test]
    fn a_body_that_jumps_outside_the_image_is_not_plausible() {
        let image = |first: u32| CodeImage {
            base: CodeAddress {
                pc: GuestAddr(0x8000_0000),
                image: "jumps".into(),
                generation: 0,
            },
            words: vec![first, 0, JR_RA, 0],
            rom_offset: None,
            physical_start: None,
            holes: Vec::new(),
        };
        // b +8 stays in the image; j 0x84001068 (RSP boot code) does not
        assert!(plausible(&image(0x1000_0001), GuestAddr(0x8000_0000)));
        assert!(!plausible(&image(0x0900_041a), GuestAddr(0x8000_0000)));
    }

    #[test]
    fn a_declared_load_begins_with_a_function() {
        // a load packed right after another load's data: no `jr ra` and no
        // hole before its first word (ADR-0182)
        let image = CodeImage {
            base: CodeAddress {
                pc: GuestAddr(0x8000_0000),
                image: "packed".into(),
                generation: 0,
            },
            words: vec![0x2402_0001, JR_RA, 0, 0x1234_5678, 0x2402_0002, JR_RA, 0],
            rom_offset: None,
            physical_start: None,
            holes: Vec::new(),
        };
        let second = GuestAddr(0x8000_0010);
        assert!(!plausible(&image, second));
        assert!(plausible_at(&image, second, &BTreeSet::from([second.0])));
    }
}
