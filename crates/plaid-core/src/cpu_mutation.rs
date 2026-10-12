//! Bounded normalization of completed VR4300 COP1 store mutations.
//!
//! This module turns an independently observed, completed SWC1/SDC1 effect into
//! a source-normalized mutation witness. It deliberately does not infer that an
//! instruction mutated storage merely because it executed, and it does not turn
//! cache-resident mutation into a backing write.
use crate::program::{GuestVirtualAddr, PhysicalAddr};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Cop1StoreKind {
    Swc1,
    Sdc1,
}

impl Cop1StoreKind {
    fn width(self) -> usize {
        match self {
            Self::Swc1 => 4,
            Self::Sdc1 => 8,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DecodedCop1Store {
    pub kind: Cop1StoreKind,
    pub base_register: u8,
    pub requested_ft: u8,
    pub immediate: i16,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Cop1SourceLane {
    Low32,
    High32,
    Whole64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CpuMutationDomain {
    CacheResident,
    Backing,
}

/// A completed concrete effect supplied by a lower storage/cache observer.
///
/// `payload` is the semantic guest-order store payload. `physical_destination`
/// is retained as observed identity; this verifier does not reconstruct a TLB,
/// alias, or endian mapping from the virtual address.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CompletedCop1StoreEffect {
    pub effect_ordinal: u64,
    pub virtual_destination: GuestVirtualAddr,
    pub physical_destination: PhysicalAddr,
    pub domain: CpuMutationDomain,
    pub payload: Vec<u8>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Cop1StoreSource {
    pub fr: bool,
    pub requested_ft: u8,
    /// Named raw FPR storage selected after FR-mode aliasing.
    pub storage_fpr: u8,
    pub lane: Cop1SourceLane,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Cop1MutationWitness {
    pub effect_ordinal: u64,
    pub kind: Cop1StoreKind,
    pub source: Cop1StoreSource,
    pub virtual_destination: GuestVirtualAddr,
    pub physical_destination: PhysicalAddr,
    pub domain: CpuMutationDomain,
    pub payload: Vec<u8>,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

/// Decode only the two COP1 store families covered by the validated contract.
pub fn decode_cop1_store(word: u32) -> Option<DecodedCop1Store> {
    let kind = match word >> 26 {
        0x39 => Cop1StoreKind::Swc1,
        0x3d => Cop1StoreKind::Sdc1,
        _ => return None,
    };
    Some(DecodedCop1Store {
        kind,
        base_register: ((word >> 21) & 31) as u8,
        requested_ft: ((word >> 16) & 31) as u8,
        immediate: word as i16,
    })
}

fn select_source(
    kind: Cop1StoreKind,
    requested_ft: u8,
    fr: bool,
    raw_fprs: &[u64; 32],
) -> (Cop1StoreSource, Vec<u8>) {
    let (storage_fpr, lane) = match (kind, fr, requested_ft & 1) {
        (Cop1StoreKind::Swc1, false, 0) => (requested_ft & !1u8, Cop1SourceLane::Low32),
        (Cop1StoreKind::Swc1, false, _) => (requested_ft & !1u8, Cop1SourceLane::High32),
        (Cop1StoreKind::Swc1, true, _) => (requested_ft, Cop1SourceLane::Low32),
        (Cop1StoreKind::Sdc1, false, _) => (requested_ft & !1u8, Cop1SourceLane::Whole64),
        (Cop1StoreKind::Sdc1, true, _) => (requested_ft, Cop1SourceLane::Whole64),
    };
    let raw = raw_fprs[usize::from(storage_fpr)];
    let payload = match lane {
        Cop1SourceLane::Low32 => (raw as u32).to_be_bytes().to_vec(),
        Cop1SourceLane::High32 => ((raw >> 32) as u32).to_be_bytes().to_vec(),
        Cop1SourceLane::Whole64 => raw.to_be_bytes().to_vec(),
    };
    (
        Cop1StoreSource {
            fr,
            requested_ft,
            storage_fpr,
            lane,
        },
        payload,
    )
}

/// Verify one completed SWC1/SDC1 effect against captured architectural state.
///
/// `None` means no successful concrete effect was observed and therefore no
/// mutation witness is created. This is the required outcome for faulting or
/// otherwise failed stores. The caller must independently authenticate capture
/// completeness, physical mapping identity, effect ordering, and FPR ancestry.
pub fn verify_cop1_store_effect(
    instruction_word: u32,
    gpr: &[u64; 32],
    raw_fprs: &[u64; 32],
    fr: bool,
    effect: Option<&CompletedCop1StoreEffect>,
) -> Result<Option<Cop1MutationWitness>, String> {
    let decoded = decode_cop1_store(instruction_word).ok_or("not a supported COP1 store")?;
    require(gpr[0] == 0, "nonzero architectural zero register")?;
    let Some(effect) = effect else {
        return Ok(None);
    };

    require(effect.effect_ordinal != 0, "invalid COP1 effect ordinal")?;
    let expected_virtual = GuestVirtualAddr(
        gpr[usize::from(decoded.base_register)].wrapping_add_signed(i64::from(decoded.immediate)),
    );
    require(
        effect.virtual_destination == expected_virtual,
        "COP1 store virtual destination mismatch",
    )?;

    let width = decoded.kind.width();
    require(
        effect.virtual_destination.0.is_multiple_of(width as u64),
        "completed COP1 effect is misaligned",
    )?;
    require(
        effect.physical_destination.0.is_multiple_of(width as u32),
        "completed COP1 physical effect is misaligned",
    )?;
    require(
        u64::from(effect.physical_destination.0) + width as u64 <= 0x0080_0000,
        "COP1 effect outside bounded RDRAM",
    )?;

    let (source, payload) = select_source(decoded.kind, decoded.requested_ft, fr, raw_fprs);
    require(effect.payload.len() == width, "COP1 effect width mismatch")?;
    require(
        effect.payload == payload,
        "COP1 store payload/source mismatch",
    )?;

    Ok(Some(Cop1MutationWitness {
        effect_ordinal: effect.effect_ordinal,
        kind: decoded.kind,
        source,
        virtual_destination: effect.virtual_destination,
        physical_destination: effect.physical_destination,
        domain: effect.domain,
        payload,
    }))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn encode(kind: Cop1StoreKind, base: u8, ft: u8, immediate: i16) -> u32 {
        let opcode = match kind {
            Cop1StoreKind::Swc1 => 0x39,
            Cop1StoreKind::Sdc1 => 0x3d,
        };
        (opcode << 26)
            | (u32::from(base) << 21)
            | (u32::from(ft) << 16)
            | u32::from(immediate as u16)
    }

    fn state() -> ([u64; 32], [u64; 32]) {
        let mut gpr = [0; 32];
        gpr[1] = 0xffff_ffff_a000_2000;
        let mut fpr = [0; 32];
        fpr[0] = 0x1122_3344_5566_7788;
        fpr[1] = 0x99aa_bbcc_ddee_ff00;
        fpr[2] = 0x0123_4567_89ab_cdef;
        fpr[3] = 0xfedc_ba98_7654_3210;
        (gpr, fpr)
    }

    fn effect(domain: CpuMutationDomain, payload: &[u8]) -> CompletedCop1StoreEffect {
        CompletedCop1StoreEffect {
            effect_ordinal: 7,
            virtual_destination: GuestVirtualAddr(0xffff_ffff_a000_2000),
            physical_destination: PhysicalAddr(0x2000),
            domain,
            payload: payload.to_vec(),
        }
    }

    #[test]
    fn fr0_swc1_odd_selects_high_lane_of_even_pair() {
        let (gpr, fpr) = state();
        let witness = verify_cop1_store_effect(
            encode(Cop1StoreKind::Swc1, 1, 1, 0),
            &gpr,
            &fpr,
            false,
            Some(&effect(
                CpuMutationDomain::Backing,
                &[0x11, 0x22, 0x33, 0x44],
            )),
        )
        .unwrap()
        .unwrap();
        assert_eq!(witness.source.storage_fpr, 0);
        assert_eq!(witness.source.lane, Cop1SourceLane::High32);
        assert_eq!(witness.payload, [0x11, 0x22, 0x33, 0x44]);
    }

    #[test]
    fn fr0_swc1_even_selects_low_lane_of_even_pair() {
        let (gpr, fpr) = state();
        let witness = verify_cop1_store_effect(
            encode(Cop1StoreKind::Swc1, 1, 0, 0),
            &gpr,
            &fpr,
            false,
            Some(&effect(
                CpuMutationDomain::Backing,
                &[0x55, 0x66, 0x77, 0x88],
            )),
        )
        .unwrap()
        .unwrap();
        assert_eq!(witness.source.storage_fpr, 0);
        assert_eq!(witness.source.lane, Cop1SourceLane::Low32);
    }

    #[test]
    fn fr1_swc1_uses_named_register() {
        let (gpr, fpr) = state();
        let witness = verify_cop1_store_effect(
            encode(Cop1StoreKind::Swc1, 1, 1, 0),
            &gpr,
            &fpr,
            true,
            Some(&effect(
                CpuMutationDomain::Backing,
                &[0xdd, 0xee, 0xff, 0x00],
            )),
        )
        .unwrap()
        .unwrap();
        assert_eq!(witness.source.storage_fpr, 1);
        assert_eq!(witness.source.lane, Cop1SourceLane::Low32);
    }

    #[test]
    fn fr0_sdc1_odd_aliases_even_pair() {
        let (gpr, fpr) = state();
        let witness = verify_cop1_store_effect(
            encode(Cop1StoreKind::Sdc1, 1, 1, 0),
            &gpr,
            &fpr,
            false,
            Some(&effect(
                CpuMutationDomain::Backing,
                &[0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88],
            )),
        )
        .unwrap()
        .unwrap();
        assert_eq!(witness.source.storage_fpr, 0);
        assert_eq!(witness.source.lane, Cop1SourceLane::Whole64);
    }

    #[test]
    fn fr1_sdc1_uses_named_register() {
        let (gpr, fpr) = state();
        let witness = verify_cop1_store_effect(
            encode(Cop1StoreKind::Sdc1, 1, 1, 0),
            &gpr,
            &fpr,
            true,
            Some(&effect(
                CpuMutationDomain::Backing,
                &[0x99, 0xaa, 0xbb, 0xcc, 0xdd, 0xee, 0xff, 0x00],
            )),
        )
        .unwrap()
        .unwrap();
        assert_eq!(witness.source.storage_fpr, 1);
    }

    #[test]
    fn absent_completed_effect_creates_no_writer() {
        let (gpr, fpr) = state();
        assert_eq!(
            verify_cop1_store_effect(
                encode(Cop1StoreKind::Swc1, 1, 0, 1),
                &gpr,
                &fpr,
                false,
                None,
            )
            .unwrap(),
            None
        );
    }

    #[test]
    fn equal_payload_from_wrong_fr_source_is_rejected() {
        let (gpr, fpr) = state();
        let wrong = effect(CpuMutationDomain::Backing, &[0x11, 0x22, 0x33, 0x44]);
        assert_eq!(
            verify_cop1_store_effect(
                encode(Cop1StoreKind::Swc1, 1, 1, 0),
                &gpr,
                &fpr,
                true,
                Some(&wrong),
            )
            .unwrap_err(),
            "COP1 store payload/source mismatch"
        );
    }

    #[test]
    fn resident_and_backing_effects_remain_distinct() {
        let (gpr, fpr) = state();
        let resident_effect = effect(CpuMutationDomain::CacheResident, &[0x55, 0x66, 0x77, 0x88]);
        let backing_effect = effect(CpuMutationDomain::Backing, &[0x55, 0x66, 0x77, 0x88]);
        let resident = verify_cop1_store_effect(
            encode(Cop1StoreKind::Swc1, 1, 0, 0),
            &gpr,
            &fpr,
            false,
            Some(&resident_effect),
        )
        .unwrap()
        .unwrap();
        let backing = verify_cop1_store_effect(
            encode(Cop1StoreKind::Swc1, 1, 0, 0),
            &gpr,
            &fpr,
            false,
            Some(&backing_effect),
        )
        .unwrap()
        .unwrap();
        assert_ne!(resident.domain, backing.domain);
        assert_eq!(resident.payload, backing.payload);
    }

    #[test]
    fn destination_forgery_is_rejected() {
        let (gpr, fpr) = state();
        let mut forged = effect(CpuMutationDomain::Backing, &[0x55, 0x66, 0x77, 0x88]);
        forged.virtual_destination = GuestVirtualAddr(0xffff_ffff_a000_3000);
        assert_eq!(
            verify_cop1_store_effect(
                encode(Cop1StoreKind::Swc1, 1, 0, 0),
                &gpr,
                &fpr,
                false,
                Some(&forged),
            )
            .unwrap_err(),
            "COP1 store virtual destination mismatch"
        );
    }

    #[test]
    fn completed_misaligned_effect_is_rejected() {
        let (gpr, fpr) = state();
        let mut gpr = gpr;
        gpr[1] += 1;
        let mut forged = effect(CpuMutationDomain::Backing, &[0x55, 0x66, 0x77, 0x88]);
        forged.virtual_destination = GuestVirtualAddr(0xffff_ffff_a000_2001);
        forged.physical_destination = PhysicalAddr(0x2001);
        assert_eq!(
            verify_cop1_store_effect(
                encode(Cop1StoreKind::Swc1, 1, 0, 0),
                &gpr,
                &fpr,
                false,
                Some(&forged),
            )
            .unwrap_err(),
            "completed COP1 effect is misaligned"
        );
    }

    #[test]
    fn out_of_rdram_effect_is_rejected() {
        let (gpr, fpr) = state();
        let mut forged = effect(CpuMutationDomain::Backing, &[0x55, 0x66, 0x77, 0x88]);
        forged.physical_destination = PhysicalAddr(0x0080_0000);
        assert_eq!(
            verify_cop1_store_effect(
                encode(Cop1StoreKind::Swc1, 1, 0, 0),
                &gpr,
                &fpr,
                false,
                Some(&forged),
            )
            .unwrap_err(),
            "COP1 effect outside bounded RDRAM"
        );
    }

    #[test]
    fn integer_store_is_outside_this_contract() {
        let (gpr, fpr) = state();
        assert_eq!(
            verify_cop1_store_effect(0xac22_0000, &gpr, &fpr, false, None).unwrap_err(),
            "not a supported COP1 store"
        );
    }
}
