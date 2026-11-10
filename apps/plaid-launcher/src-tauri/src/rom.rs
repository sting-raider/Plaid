//! N64 ROM detection: byte order, header fields and the names Plaid derives from a file.

use std::fs::File;
use std::io::Read;
use std::path::Path;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Order {
    /// Big-endian, what Plaid reads.
    Z64,
    /// 16-bit byte-swapped.
    V64,
    /// 32-bit little-endian.
    N64,
}

pub fn order(first: [u8; 4]) -> Option<Order> {
    match first {
        [0x80, 0x37, 0x12, 0x40] => Some(Order::Z64),
        [0x37, 0x80, 0x40, 0x12] => Some(Order::V64),
        [0x40, 0x12, 0x37, 0x80] => Some(Order::N64),
        _ => None,
    }
}

/// Rewrites `bytes` in place into big-endian (.z64) order.
pub fn to_z64(bytes: &mut [u8], from: Order) {
    match from {
        Order::Z64 => {}
        Order::V64 => bytes
            .as_chunks_mut::<2>()
            .0
            .iter_mut()
            .for_each(|c| c.swap(0, 1)),
        Order::N64 => bytes
            .as_chunks_mut::<4>()
            .0
            .iter_mut()
            .for_each(|c| c.reverse()),
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Header {
    pub internal_name: String,
    pub game_code: String,
    pub version: u8,
    pub region: &'static str,
}

/// Parses the first 0x40 bytes of a big-endian ROM.
pub fn header(z64: &[u8; 0x40]) -> Header {
    let text = |r: std::ops::Range<usize>| {
        z64[r]
            .iter()
            .map(|&b| {
                if b.is_ascii_graphic() || b == b' ' {
                    b as char
                } else {
                    ' '
                }
            })
            .collect::<String>()
            .trim()
            .to_string()
    };
    let region = match z64[0x3e] {
        b'E' => "USA",
        b'J' => "Japan",
        b'P' | b'X' | b'Y' => "Europe",
        b'U' => "Australia",
        b'D' => "Germany",
        b'F' => "France",
        b'I' => "Italy",
        b'S' => "Spain",
        b'A' => "World",
        _ => "Unknown",
    };
    Header {
        internal_name: text(0x20..0x34),
        game_code: text(0x3b..0x3f),
        version: z64[0x3f],
        region,
    }
}

/// Reads byte order and header without loading the whole ROM.
pub fn probe(path: &Path) -> Option<(Order, Header)> {
    let mut head = [0u8; 0x40];
    File::open(path).ok()?.read_exact(&mut head).ok()?;
    let order = order([head[0], head[1], head[2], head[3]])?;
    to_z64(&mut head, order);
    Some((order, header(&head)))
}

/// The output name `scripts/native.py` derives from a ROM file stem.
pub fn native_name(stem: &str) -> String {
    stem.chars()
        .filter(|c| c.is_alphanumeric())
        .flat_map(char::to_lowercase)
        .take(32)
        .collect()
}

/// A display title from a file name: tags dropped, "Legend of Zelda, The" -> "The Legend of Zelda".
pub fn display_title(stem: &str) -> String {
    let base = stem.split(['(', '[']).next().unwrap_or(stem).trim();
    let mut parts: Vec<String> = base.split(" - ").map(str::to_string).collect();
    if let Some(first) = parts.first_mut()
        && let Some(rest) = first.strip_suffix(", The")
    {
        *first = format!("The {rest}");
    }
    parts.join(" - ")
}

/// Letters and digits only, lowercased: the key titles are matched on.
pub fn match_key(s: &str) -> String {
    s.chars()
        .filter(|c| c.is_alphanumeric())
        .flat_map(char::to_lowercase)
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn byte_orders_round_trip_to_z64() {
        let z64 = [0x80, 0x37, 0x12, 0x40, 1, 2, 3, 4];
        let mut v64 = [0x37, 0x80, 0x40, 0x12, 2, 1, 4, 3];
        let mut n64 = [0x40, 0x12, 0x37, 0x80, 4, 3, 2, 1];
        assert_eq!(order([v64[0], v64[1], v64[2], v64[3]]), Some(Order::V64));
        assert_eq!(order([n64[0], n64[1], n64[2], n64[3]]), Some(Order::N64));
        to_z64(&mut v64, Order::V64);
        to_z64(&mut n64, Order::N64);
        assert_eq!(v64, z64);
        assert_eq!(n64, z64);
        assert_eq!(order([0, 0, 0, 0]), None);
    }

    #[test]
    fn header_fields() {
        let mut h = [0u8; 0x40];
        h[0x20..0x2a].copy_from_slice(b"STARFOX64 ");
        h[0x3b..0x3f].copy_from_slice(b"NFXE");
        h[0x3f] = 1;
        let parsed = header(&h);
        assert_eq!(
            (
                parsed.internal_name.as_str(),
                parsed.game_code.as_str(),
                parsed.version,
                parsed.region
            ),
            ("STARFOX64", "NFXE", 1, "USA")
        );
    }

    #[test]
    fn names_match_native_py() {
        assert_eq!(native_name("Star Fox 64 (USA) (Rev 1)"), "starfox64usarev1");
        assert_eq!(
            native_name("Legend of Zelda, The - Majora's Mask (USA)"),
            "legendofzeldathemajorasmaskusa"
        );
        assert_eq!(
            display_title("Legend of Zelda, The - Ocarina of Time (U) (V1.2) [!]"),
            "The Legend of Zelda - Ocarina of Time"
        );
        assert_eq!(display_title("Mario Party 2 (USA)"), "Mario Party 2");
    }
}
