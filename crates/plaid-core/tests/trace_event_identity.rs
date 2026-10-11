use plaid_core::{
    EvidenceKind, GuestAddr,
    merge::merge_maps,
    program::{
        CodeAddress, Evidence, EvidenceRefs, GuestRange, LoadMapping, ObservedDma,
        ObservedEntryVerification, ObservedIndirect, ObservedWordStore, PhysicalAddr, ProgramMap,
        Region, RomIdentity, RomOffset,
    },
};

const EVENT: &str = "trace:synthetic:7";
const UNIT: &str = "trace:synthetic:1";

fn trace(detail: &str) -> Evidence {
    Evidence {
        kind: EvidenceKind::Trace,
        producer: "synthetic-trace".into(),
        revision: "0".into(),
        detail: detail.into(),
    }
}

fn base_map() -> ProgramMap {
    let mut map = ProgramMap::new(RomIdentity {
        sha256: "a".repeat(64),
        size: 256,
    });
    map.evidence.insert(EVENT.into(), trace("one concrete trace event"));
    map.evidence.insert(UNIT.into(), trace("one concrete CompileBegin event"));
    map
}

fn store(destination: u32) -> ObservedWordStore {
    ObservedWordStore {
        site: GuestAddr(0x8000_1000),
        destination: GuestAddr(destination),
        value: 0x1122_3344,
        generation: 0,
        evidence: [EVENT.to_string()].into(),
    }
}

fn indirect(target: u32, event: &str, source_unit: Option<&str>) -> ObservedIndirect {
    ObservedIndirect {
        site: GuestAddr(0x8000_2000),
        target: GuestAddr(target),
        delay_slot_pc: Some(GuestAddr(0x8000_2004)),
        generation: 0,
        source_unit: source_unit.map(str::to_string),
        evidence: [event.to_string()].into(),
    }
}

fn entry() -> CodeAddress {
    CodeAddress {
        pc: GuestAddr(0x8000_3000),
        image: "image".into(),
        generation: 0,
    }
}

fn verification(mask: u32) -> ObservedEntryVerification {
    ObservedEntryVerification {
        entry: entry(),
        register_mask: mask,
        source_unit: UNIT.into(),
        generation: 0,
        evidence: [EVENT.to_string()].into(),
    }
}

fn add_copy(map: &mut ProgramMap, image: &str, guest: u32, rom: u64, physical: u32) {
    let evidence: EvidenceRefs = [EVENT.to_string()].into();
    map.dma_observations.insert(ObservedDma {
        rom_offset: RomOffset(rom),
        physical_destination: PhysicalAddr(physical),
        size: 8,
        evidence: evidence.clone(),
    });
    map.regions.insert(Region {
        image: image.into(),
        generation: 0,
        range: GuestRange {
            start: GuestAddr(guest),
            size: 8,
        },
        rom_offset: Some(RomOffset(rom)),
        physical_start: Some(PhysicalAddr(physical)),
        overlay: None,
        evidence: evidence.clone(),
    });
    map.loads.insert(LoadMapping {
        rom_offset: RomOffset(rom),
        destination: GuestRange {
            start: GuestAddr(guest),
            size: 8,
        },
        image: image.into(),
        generation: 0,
        copy_event: Some(EVENT.into()),
        evidence,
    });
}

#[test]
fn one_copy_event_cannot_name_two_dma_transactions() {
    let mut map = base_map();
    add_copy(&mut map, "a", 0x8000_0000, 64, 0);
    add_copy(&mut map, "b", 0x8000_0020, 80, 32);
    assert!(map.validate().is_err());
}

#[test]
fn one_store_event_cannot_fork_semantics() {
    let mut map = base_map();
    map.word_store_observations.insert(store(0x8000_0100));
    map.word_store_observations.insert(store(0x8000_0104));
    assert!(map.validate().is_err());
}

#[test]
fn one_indirect_event_cannot_fork_semantics() {
    let mut map = base_map();
    map.indirect_observations
        .insert(indirect(0x8000_4000, EVENT, None));
    map.indirect_observations
        .insert(indirect(0x8000_4040, EVENT, None));
    assert!(map.validate().is_err());
}

#[test]
fn one_entry_verification_event_cannot_fork_semantics() {
    let mut map = base_map();
    map.entries.insert(entry(), [UNIT.to_string()].into());
    map.entry_verifications.insert(verification(0));
    map.entry_verifications.insert(verification(1));
    assert!(map.validate().is_err());
}

#[test]
fn one_event_cannot_cross_primitive_roles() {
    let mut map = base_map();
    map.word_store_observations.insert(store(0x8000_0100));
    map.indirect_observations
        .insert(indirect(0x8000_4000, EVENT, None));
    assert!(map.validate().is_err());
}

#[test]
fn copy_event_cannot_masquerade_as_store_event() {
    let mut map = base_map();
    add_copy(&mut map, "a", 0x8000_0000, 64, 0);
    map.word_store_observations.insert(store(0x8000_0100));
    assert!(map.validate().is_err());
}

#[test]
fn copy_event_cannot_masquerade_as_source_unit() {
    let mut map = base_map();
    add_copy(&mut map, "a", 0x8000_0000, 64, 0);
    map.indirect_observations
        .insert(indirect(0x8000_4000, UNIT, Some(EVENT)));
    assert!(map.validate().is_err());
}

#[test]
fn merge_cannot_launder_cross_role_event_identity() {
    let mut left = base_map();
    left.word_store_observations.insert(store(0x8000_0100));
    left.validate().unwrap();

    let mut right = base_map();
    right
        .indirect_observations
        .insert(indirect(0x8000_4000, EVENT, None));
    right.validate().unwrap();

    assert!(merge_maps(&left, &right).is_err());
}

#[test]
fn source_unit_context_may_be_shared_and_carried_as_provenance() {
    let mut map = base_map();
    map.indirect_observations.insert(ObservedIndirect {
        site: GuestAddr(0x8000_2000),
        target: GuestAddr(0x8000_4000),
        delay_slot_pc: Some(GuestAddr(0x8000_2004)),
        generation: 0,
        source_unit: Some(UNIT.into()),
        evidence: [EVENT.to_string(), UNIT.to_string()].into(),
    });
    map.evidence
        .insert("trace:synthetic:8".into(), trace("another indirect event"));
    map.indirect_observations.insert(ObservedIndirect {
        site: GuestAddr(0x8000_2000),
        target: GuestAddr(0x8000_4040),
        delay_slot_pc: Some(GuestAddr(0x8000_2004)),
        generation: 0,
        source_unit: Some(UNIT.into()),
        evidence: ["trace:synthetic:8".into(), UNIT.to_string()].into(),
    });
    map.validate().unwrap();
}
