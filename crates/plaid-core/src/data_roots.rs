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

/// Whether `pc` starts a function by layout: the image start, or right after
/// a `jr ra` and its delay slot, possibly followed by zero padding.
fn after_return(image: &CodeImage, pc: GuestAddr) -> bool {
    if pc == image.base.pc {
        return true;
    }
    let word = |back: u32| {
        pc.0.checked_sub(back)
            .and_then(|a| image.word(GuestAddr(a)))
    };
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

fn function_start(image: &CodeImage, pc: GuestAddr) -> bool {
    pc.0.is_multiple_of(4)
        && image
            .word(pc)
            .is_some_and(|w| w != 0 && crate::discovery::decode(w, pc).is_valid())
        && after_return(image, pc)
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
        .filter(|&pc| function_start(image, pc))
        .collect()
}

/// Whether the words from `pc` to its first `jr ra` and delay slot can be
/// CPU code: every word decodes and none is a COP2 or COP3 access, which
/// the VR4300 lacks (RSP microcode is the usual impostor).
fn cpu_code(image: &CodeImage, pc: GuestAddr) -> bool {
    let mut at = pc.0;
    for _ in 0..4096 {
        let Some(w) = image.word(GuestAddr(at)) else {
            return false;
        };
        if matches!(w >> 26, 18 | 19 | 50 | 54 | 58 | 62)
            || !crate::discovery::decode(w, GuestAddr(at)).is_valid()
        {
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
    function_start(image, pc) && cpu_code(image, pc)
}

/// Address-taken roots from data (ADR-0153): aligned words of `bytes` that
/// name a function start in `image` whose body can be CPU code.
pub fn rom_words(bytes: &[u8], image: &CodeImage) -> BTreeSet<GuestAddr> {
    bytes
        .as_chunks::<4>()
        .0
        .iter()
        .map(|w| GuestAddr(u32::from_be_bytes(*w)))
        .filter(|&pc| plausible(image, pc))
        .collect()
}

/// Address constants (`lui r, hi` then `addiu`/`ori` from `r`) built inside
/// one decoded block of `map`, as `(function start, lui site)`. Constants in
/// undecoded bytes, such as a runtime function's body, do not count.
pub fn block_constants(image: &CodeImage, map: &ProgramMap) -> BTreeMap<GuestAddr, GuestAddr> {
    let mut out = BTreeMap::new();
    for b in map
        .blocks
        .iter()
        .filter(|b| b.start.image == image.base.image)
    {
        let words: Vec<u32> = (0..b.size / 4)
            .map_while(|i| image.word(GuestAddr(b.start.pc.0 + 4 * i)))
            .collect();
        for (i, &w) in words.iter().enumerate() {
            let rt = (w >> 16) & 31;
            if w >> 26 != 15 || rt == 0 {
                continue;
            }
            let hi = (w & 0xffff) << 16;
            for &x in &words[i + 1..] {
                if matches!(x >> 26, 9 | 13) && (x >> 21) & 31 == rt {
                    let value = if x >> 26 == 13 {
                        hi | (x & 0xffff)
                    } else {
                        hi.wrapping_add(x as i16 as u32)
                    };
                    let pc = GuestAddr(value);
                    if plausible(image, pc) {
                        out.entry(pc)
                            .or_insert(GuestAddr(b.start.pc.0 + 4 * i as u32));
                    }
                }
                if crate::discovery::decode(x, GuestAddr(0)).destination_gpr() == Some(rt) {
                    break;
                }
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
        .filter(|&pc| function_start(image, pc))
        .collect()
}

/// Producer of the address-taken evidence (ADR-0153).
pub const ADDRESS_TAKEN: &str = "plaid-address-taken/v0";

/// Discovery whose roots also include the address-taken functions: ROM words
/// first, then constants from decoded blocks, until no new function appears.
/// The set is recorded in `address_taken`; its functions stay map entries.
/// Declared runtime functions are a boundary and never join the set.
pub fn discover_address_taken(
    rom: crate::program::RomIdentity,
    bytes: &[u8],
    image: &CodeImage,
    entries: &[GuestAddr],
    runtime: &[(GuestAddr, String, Vec<u8>)],
    evidence: Option<(String, crate::program::Evidence)>,
    budget: usize,
) -> Result<crate::discovery::Discovery, String> {
    let runtime_entries: BTreeSet<GuestAddr> = runtime.iter().map(|(a, _, _)| *a).collect();
    let mut taken: BTreeSet<GuestAddr> = rom_words(bytes, image)
        .into_iter()
        .filter(|a| !runtime_entries.contains(a))
        .collect();
    loop {
        let roots: Vec<_> = entries.iter().chain(&taken).copied().collect();
        let mut d = crate::pipeline::discover_image_with_runtime(
            rom.clone(),
            image,
            &roots,
            runtime,
            evidence.clone(),
            budget,
        )?;
        let before = taken.len();
        taken.extend(
            block_constants(image, &d.map)
                .into_keys()
                .filter(|a| !runtime_entries.contains(a)),
        );
        if taken.len() == before {
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
}
