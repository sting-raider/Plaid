//! Every later stage consumes canonical big-endian bytes, never filename hints.
use crate::{GuestAddr, program::RomIdentity};
use serde::Serialize;
use sha2::{Digest, Sha256};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ByteOrder {
    BigEndian,
    ByteSwapped,
    WordReversed,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct RomHeader {
    pub bus_configuration: u32,
    pub clock_rate: u32,
    pub entry: GuestAddr,
    /// Where IPL3 copies ROM 0x1000 and jumps: `entry`, less the 1 or 2 MiB
    /// that CIC-NUS-6103 and 6106 boot code subtracts (ADR-0184)
    pub boot_address: GuestAddr,
    pub release: u32,
    pub crc1: u32,
    pub crc2: u32,
    pub title_bytes: [u8; 20],
    pub manufacturer: u8,
    pub cartridge_id: [u8; 2],
    pub country: u8,
    pub version: u8,
}

#[derive(Debug, Clone)]
pub struct CanonicalRom {
    bytes: Vec<u8>,
    pub source_order: ByteOrder,
    pub identity: RomIdentity,
    pub header: RomHeader,
}

/// The entry adjustment of the ROM's IPL3, identified as n64sym does by the
/// CRC32 of ROM 0x40..0x1000
fn boot_offset(bytes: &[u8]) -> u32 {
    match bytes.get(0x40..0x1000).map(crate::signatures::crc32) {
        Some(0x0b05_0ee0) => 0x10_0000, // CIC-NUS-6103
        Some(0xacc8_580a) => 0x20_0000, // CIC-NUS-6106
        _ => 0,
    }
}

pub fn sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

impl CanonicalRom {
    pub fn from_bytes(input: &[u8]) -> Result<Self, String> {
        if input.len() < 64 {
            return Err("ROM is shorter than the 64-byte header".into());
        }
        if !input.len().is_multiple_of(4) {
            return Err("ROM length is not word aligned".into());
        }
        let source_order = match &input[..4] {
            [0x80, 0x37, 0x12, 0x40] => ByteOrder::BigEndian,
            [0x37, 0x80, 0x40, 0x12] => ByteOrder::ByteSwapped,
            [0x40, 0x12, 0x37, 0x80] => ByteOrder::WordReversed,
            _ => return Err("unrecognized N64 byte-order signature".into()),
        };
        let mut bytes = input.to_vec();
        match source_order {
            ByteOrder::BigEndian => (),
            ByteOrder::ByteSwapped => {
                for pair in bytes.as_chunks_mut::<2>().0 {
                    pair.swap(0, 1);
                }
            }
            ByteOrder::WordReversed => {
                for word in bytes.as_chunks_mut::<4>().0 {
                    word.reverse();
                }
            }
        }
        let word = |offset| {
            u32::from_be_bytes(bytes[offset..offset + 4].try_into().expect("header bound"))
        };
        let header = RomHeader {
            bus_configuration: word(0),
            clock_rate: word(4),
            entry: GuestAddr(word(8)),
            boot_address: GuestAddr(word(8).wrapping_sub(boot_offset(&bytes))),
            release: word(12),
            crc1: word(16),
            crc2: word(20),
            title_bytes: bytes[32..52].try_into().expect("header bound"),
            manufacturer: bytes[59],
            cartridge_id: bytes[60..62].try_into().expect("header bound"),
            country: bytes[62],
            version: bytes[63],
        };
        let identity = RomIdentity {
            sha256: sha256(&bytes),
            size: bytes.len() as u64,
        };
        Ok(Self {
            bytes,
            source_order,
            identity,
            header,
        })
    }
    pub fn bytes(&self) -> &[u8] {
        &self.bytes
    }

    /// The bytes of the boot window that are the main image (ADR-0184): the
    /// libultra entry stub clears BSS from `_bssStart` before its jump to
    /// main, so the image IPL3 placed at `boot_address` ends there. `None`
    /// when the stub does not have that shape.
    pub fn boot_image_size(&self) -> Option<u32> {
        let at = self.header.boot_address.0;
        let mut value = [None::<u32>; 32];
        for k in 0..32 {
            let w = u32::from_be_bytes(
                self.bytes
                    .get(0x1000 + 4 * k..0x1004 + 4 * k)?
                    .try_into()
                    .ok()?,
            );
            let (op, rs, rt, imm) = (
                w >> 26,
                (w >> 21 & 31) as usize,
                (w >> 16 & 31) as usize,
                w & 0xffff,
            );
            match op {
                15 => value[rt] = Some(imm << 16), // lui
                9 => value[rt] = value[rs].map(|v| v.wrapping_add((imm as i16) as u32)), // addiu
                13 => value[rt] = value[rs].map(|v| v | imm), // ori
                // the first `sw zero, 0(base)` is the clear loop
                43 if rt == 0 && imm == 0 => {
                    let start = value[rs]?;
                    return (start > at && start - at <= 0x10_0000).then(|| start - at);
                }
                _ if w >> 26 == 0 && w & 63 == 8 => return None, // jr before any clear
                _ => {}
            }
        }
        None
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn the_entry_stub_bss_clear_bounds_the_boot_image() {
        // lui t0,0x8010; addiu t0,t0,-0x10; lui t1,2; sw zero,0(t0); ...
        let mut rom = vec![0u8; 0x2000];
        rom[..4].copy_from_slice(&[0x80, 0x37, 0x12, 0x40]);
        rom[8..12].copy_from_slice(&0x8000_0400u32.to_be_bytes());
        for (k, w) in [0x3c08_8010u32, 0x2508_fff0, 0x3c09_0002, 0xad00_0000]
            .iter()
            .enumerate()
        {
            rom[0x1000 + 4 * k..0x1004 + 4 * k].copy_from_slice(&w.to_be_bytes());
        }
        let parsed = super::CanonicalRom::from_bytes(&rom).unwrap();
        assert_eq!(
            parsed.boot_image_size(),
            Some(0x8010_0000 - 0x10 - 0x8000_0400)
        );
        // a jump before any clear is not the libultra stub
        rom[0x100c..0x1010].copy_from_slice(&0x0100_0008u32.to_be_bytes());
        assert_eq!(
            super::CanonicalRom::from_bytes(&rom)
                .unwrap()
                .boot_image_size(),
            None
        );
    }

    #[test]
    fn other_boot_code_keeps_the_header_entry() {
        assert_eq!(super::boot_offset(&[0; 0x1000]), 0);
        assert_eq!(super::boot_offset(&[0; 64]), 0);
    }
}
