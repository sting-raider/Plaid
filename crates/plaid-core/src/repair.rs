//! Bounded runtime observations, never a certificate of executable completeness.
use crate::{GuestAddr, discovery::CodeImage, program::CodeAddress, rom::sha256};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RepairRecord {
    pub schema: String,
    pub stop_kind: String,
    pub site_pc: String,
    pub target_pc: String,
    pub vi: u64,
    pub window_base: u32,
    pub window_size: u32,
    pub bytes: String,
    pub sha256: String,
    pub pi_dma: Option<()>,
}

impl RepairRecord {
    pub fn target(&self) -> Result<u32, String> {
        for address in [&self.site_pc, &self.target_pc] {
            if address.len() != 8
                || !address
                    .bytes()
                    .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
            {
                return Err("invalid repair address".into());
            }
        }
        u32::from_str_radix(&self.target_pc, 16).map_err(|e| e.to_string())
    }

    pub fn data(&self) -> Result<Vec<u8>, String> {
        let target = self.target()?;
        let physical = target & 0x1fff_ffff;
        if self.schema != "plaid-repair-v1"
            || !matches!(self.stop_kind.as_str(), "indirect_target" | "local_trap")
            || (self.stop_kind == "local_trap" && self.site_pc != self.target_pc)
            || self.pi_dma.is_some()
            || !(0x8000_0000..0xc000_0000).contains(&target)
            || target & 3 != 0
            || self.window_base & 3 != 0
            || self.window_size & 3 != 0
            || self.window_size == 0
            || self.window_size > 0x20000
            || u64::from(self.window_base) + u64::from(self.window_size) > 0x800000
            || physical < self.window_base
            || physical - self.window_base >= self.window_size
            || self.bytes.len() != self.window_size as usize * 2
        {
            return Err("invalid observed repair window".into());
        }
        let bytes = self
            .bytes
            .as_bytes()
            .as_chunks::<2>()
            .0
            .iter()
            .map(|pair| {
                let digit = |b| match b {
                    b'0'..=b'9' => Ok(b - b'0'),
                    b'a'..=b'f' => Ok(b - b'a' + 10),
                    _ => Err("invalid repair bytes"),
                };
                Ok(digit(pair[0])? * 16 + digit(pair[1])?)
            })
            .collect::<Result<Vec<u8>, &str>>()?;
        if sha256(&bytes) != self.sha256 {
            return Err("observed repair SHA-256 mismatch".into());
        }
        Ok(bytes)
    }

    pub fn image(&self, generation: u64) -> Result<CodeImage, String> {
        if generation == 0 {
            return Err("observed generation must be nonzero".into());
        }
        Ok(CodeImage {
            base: CodeAddress {
                pc: GuestAddr((self.target()? & 0xe000_0000) | self.window_base),
                image: self.sha256.clone(),
                generation,
            },
            words: self
                .data()?
                .as_chunks::<4>()
                .0
                .iter()
                .map(|w| u32::from_be_bytes(*w))
                .collect(),
            rom_offset: None,
            physical_start: Some(crate::program::PhysicalAddr(self.window_base)),
            holes: Vec::new(),
            slots: Default::default(),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn record() -> RepairRecord {
        RepairRecord {
            schema: "plaid-repair-v1".into(),
            stop_kind: "local_trap".into(),
            site_pc: "80000020".into(),
            target_pc: "80000020".into(),
            vi: 10,
            window_base: 32,
            window_size: 8,
            bytes: "2402000703e00008".into(),
            sha256: sha256(&[0x24, 2, 0, 7, 3, 0xe0, 0, 8]),
            pi_dma: None,
        }
    }

    #[test]
    fn equal_payloads_keep_distinct_observed_generations() {
        let r = record();
        let first = r.image(1).unwrap();
        let second = r.image(2).unwrap();
        assert_eq!(first.words, second.words);
        assert_ne!(first.base, second.base);
        assert_eq!(first.base.image, r.sha256);
        assert!(first.rom_offset.is_none());
        assert_eq!(first.physical_start.unwrap().0, 32);
        assert!(r.image(0).is_err());
    }

    #[test]
    fn malformed_or_unauthenticated_records_never_supply_code() {
        for mutation in 0..7 {
            let mut r = record();
            match mutation {
                0 => r.bytes.replace_range(0..2, "ff"),
                1 => r.window_base = u32::MAX,
                2 => r.window_size = 0,
                3 => r.target_pc = "80000021".into(),
                4 => r.target_pc = "a0001000".into(),
                5 => r.bytes = "é".repeat(8),
                _ => r.schema = "plaid-repair-v2".into(),
            }
            assert!(r.image(1).is_err());
        }
    }
}
