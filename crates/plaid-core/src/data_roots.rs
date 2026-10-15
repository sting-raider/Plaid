//! Discovery roots from function pointers stored as data (ADR-0152).
//!
//! Most of a data-driven game's code is reached only through pointers in its
//! data: SM64's behavior scripts, geo layouts and level scripts all name
//! functions by address, and code takes other functions' addresses with
//! `lui`/`addiu` pairs. This scan proposes discovery roots, not closure
//! facts. A wrong root decodes junk whose blockers keep the map OPEN; it
//! never closes anything.
use crate::{GuestAddr, discovery::CodeImage, program::ProgramMap};
use std::collections::BTreeSet;

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
