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
}
