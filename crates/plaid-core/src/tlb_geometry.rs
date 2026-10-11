//! Bounded VR4300 TLB PageMask geometry for already-selected mappings.
//!
//! This module deliberately does **not** select a TLB entry, authenticate a mapping
//! generation, check ASID/global/valid/dirty/CCA state, or establish executable
//! provenance. It only derives the even/odd half and in-page offset once an entry
//! has already been selected by separately trusted evidence.
//!
//! The v0 production scope accepts only the 4 KiB, 16 KiB and 64 KiB PageMask
//! encodings exercised by the exact-pinned reference fixture. Larger legal page
//! sizes and malformed encodings remain unsupported rather than being normalized
//! from one emulator's implementation behavior.

use crate::program::GuestVirtualAddr;
use serde::{Deserialize, Serialize};
use std::{error::Error, fmt};

/// Page sizes with exact executed evidence in the bounded PageMask fixture.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ValidatedTlbPageSize {
    Page4Kib,
    Page16Kib,
    Page64Kib,
}

impl ValidatedTlbPageSize {
    pub const fn page_mask(self) -> u32 {
        match self {
            Self::Page4Kib => 0x0000,
            Self::Page16Kib => 0x6000,
            Self::Page64Kib => 0x1e000,
        }
    }

    pub const fn bytes(self) -> u64 {
        match self {
            Self::Page4Kib => 0x1000,
            Self::Page16Kib => 0x4000,
            Self::Page64Kib => 0x10000,
        }
    }
}

/// Geometry derived from one supported PageMask value.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TlbPageGeometry {
    pub page_size: ValidatedTlbPageSize,
    pub page_mask: u32,
    /// Virtual-address bit selecting EntryLo0/even versus EntryLo1/odd.
    pub half_select_mask: u64,
    /// Mask selecting the byte offset within the selected half.
    pub in_page_offset_mask: u64,
}

/// Which EntryLo half an already-selected mapping uses for this virtual address.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TlbEntryHalf {
    Even,
    Odd,
}

/// Bounded derivation result. This is geometry, not a mapping/provenance certificate.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TlbPageOffsetReceipt {
    pub vaddr: GuestVirtualAddr,
    pub geometry: TlbPageGeometry,
    pub selected_half: TlbEntryHalf,
    pub in_page_offset: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct UnsupportedTlbPageMask {
    pub page_mask: u32,
}

impl fmt::Display for UnsupportedTlbPageMask {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "unsupported or unvalidated VR4300 PageMask 0x{:x}",
            self.page_mask
        )
    }
}

impl Error for UnsupportedTlbPageMask {}

/// Decode only PageMask encodings with exact executed evidence in the v0 scope.
///
/// In particular, this function intentionally rejects malformed masks instead of
/// applying the normalization observed in a pinned emulator, and it rejects larger
/// legal page sizes whose current Plaid evidence is model-only.
pub fn validated_tlb_page_geometry(
    page_mask: u32,
) -> Result<TlbPageGeometry, UnsupportedTlbPageMask> {
    let page_size = match page_mask {
        0x0000 => ValidatedTlbPageSize::Page4Kib,
        0x6000 => ValidatedTlbPageSize::Page16Kib,
        0x1e000 => ValidatedTlbPageSize::Page64Kib,
        _ => return Err(UnsupportedTlbPageMask { page_mask }),
    };
    let bytes = page_size.bytes();
    Ok(TlbPageGeometry {
        page_size,
        page_mask,
        half_select_mask: bytes,
        in_page_offset_mask: bytes - 1,
    })
}

/// Derive the EntryLo half and in-page byte offset for an already-selected entry.
///
/// The caller remains responsible for proving that this entry was the mapping used
/// by the relevant access and for composing the selected EntryLo/PFN with backing,
/// cache-residency and executable-lifetime evidence.
pub fn derive_tlb_page_offset(
    page_mask: u32,
    vaddr: GuestVirtualAddr,
) -> Result<TlbPageOffsetReceipt, UnsupportedTlbPageMask> {
    let geometry = validated_tlb_page_geometry(page_mask)?;
    let selected_half = if vaddr.0 & geometry.half_select_mask == 0 {
        TlbEntryHalf::Even
    } else {
        TlbEntryHalf::Odd
    };
    Ok(TlbPageOffsetReceipt {
        vaddr,
        geometry,
        selected_half,
        in_page_offset: vaddr.0 & geometry.in_page_offset_mask,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn derived(mask: u32, vaddr: u64) -> (TlbEntryHalf, u64) {
        let receipt = derive_tlb_page_offset(mask, GuestVirtualAddr(vaddr)).unwrap();
        (receipt.selected_half, receipt.in_page_offset)
    }

    #[test]
    fn supported_geometry_matches_executed_reference_scope() {
        let cases = [
            (0x0000, ValidatedTlbPageSize::Page4Kib, 0x1000, 0x0fff),
            (0x6000, ValidatedTlbPageSize::Page16Kib, 0x4000, 0x3fff),
            (0x1e000, ValidatedTlbPageSize::Page64Kib, 0x10000, 0xffff),
        ];
        for (mask, page_size, select, offset) in cases {
            let geometry = validated_tlb_page_geometry(mask).unwrap();
            assert_eq!(geometry.page_size, page_size);
            assert_eq!(geometry.page_mask, mask);
            assert_eq!(geometry.half_select_mask, select);
            assert_eq!(geometry.in_page_offset_mask, offset);
            assert_eq!(geometry.page_size.page_mask(), mask);
        }
    }

    #[test]
    fn large_page_cases_do_not_use_fixed_bit12_geometry() {
        // These are the exact virtual-address cases exercised by the validated
        // PageMask fixture. Several deliberately make bit 12 disagree with the
        // actual large-page half selector.
        assert_eq!(derived(0x0000, 0x0000_4000), (TlbEntryHalf::Even, 0));
        assert_eq!(
            derived(0x6000, 0x0002_1000),
            (TlbEntryHalf::Even, 0x1000)
        );
        assert_eq!(
            derived(0x6000, 0x0002_c000),
            (TlbEntryHalf::Odd, 0)
        );
        assert_eq!(
            derived(0x1e000, 0x0004_5000),
            (TlbEntryHalf::Even, 0x5000)
        );
        assert_eq!(
            derived(0x1e000, 0x0007_0000),
            (TlbEntryHalf::Odd, 0)
        );
        assert_eq!(
            derived(0x6000, 0x0008_4000),
            (TlbEntryHalf::Odd, 0)
        );
    }

    #[test]
    fn invalid_selected_half_counterexample_stays_even_at_16k() {
        // In the reference fixture bit 12 is set here, but 16 KiB geometry selects
        // the even half with bit 14. Treating bit 12 as the selector would choose a
        // valid equal-valued decoy EntryLo and fabricate a fetch source.
        assert_eq!(
            derived(0x6000, 0x0009_1000),
            (TlbEntryHalf::Even, 0x1000)
        );
    }

    #[test]
    fn page_size_changes_causal_geometry_even_when_address_is_identical() {
        let vaddr = GuestVirtualAddr(0x0002_1000);
        let page4 = derive_tlb_page_offset(0, vaddr).unwrap();
        let page16 = derive_tlb_page_offset(0x6000, vaddr).unwrap();
        assert_eq!(page4.selected_half, TlbEntryHalf::Odd);
        assert_eq!(page4.in_page_offset, 0);
        assert_eq!(page16.selected_half, TlbEntryHalf::Even);
        assert_eq!(page16.in_page_offset, 0x1000);
    }

    #[test]
    fn malformed_masks_are_not_normalized_into_supported_geometry() {
        for mask in [
            0b1 << 13,
            0b111 << 13,
            0b10 << 13,
            0b1000 << 13,
        ] {
            assert_eq!(
                validated_tlb_page_geometry(mask),
                Err(UnsupportedTlbPageMask { page_mask: mask })
            );
        }
    }

    #[test]
    fn larger_model_only_page_sizes_fail_closed() {
        for mask in [0b11_1111 << 13, 0b1111_1111 << 13] {
            assert_eq!(
                validated_tlb_page_geometry(mask),
                Err(UnsupportedTlbPageMask { page_mask: mask })
            );
        }
    }
}
