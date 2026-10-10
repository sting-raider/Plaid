use plaid_core::{EvidenceKind, GuestAddr, merge::merge_maps, program::*};

const COPY: &str = "trace:synthetic:7";

fn trace_evidence(detail: &str) -> Evidence {
    Evidence {
        kind: EvidenceKind::Trace,
        producer: "synthetic-trace".into(),
        revision: "0".into(),
        detail: detail.into(),
    }
}

fn empty_map() -> ProgramMap {
    ProgramMap::new(RomIdentity {
        sha256: "a".repeat(64),
        size: 256,
    })
}

fn add_copy(map: &mut ProgramMap) {
    map.evidence.insert(
        COPY.into(),
        trace_evidence("one concrete RomDmaObserved event"),
    );
    let evidence: EvidenceRefs = [COPY.to_string()].into();
    map.dma_observations.insert(ObservedDma {
        rom_offset: RomOffset(64),
        physical_destination: PhysicalAddr(0),
        size: 8,
        evidence: evidence.clone(),
    });
    map.regions.insert(Region {
        image: "copied-image".into(),
        generation: 0,
        range: GuestRange {
            start: GuestAddr(0x8000_0000),
            size: 8,
        },
        rom_offset: Some(RomOffset(64)),
        physical_start: Some(PhysicalAddr(0)),
        overlay: None,
        evidence: evidence.clone(),
    });
    map.loads.insert(LoadMapping {
        rom_offset: RomOffset(64),
        destination: GuestRange {
            start: GuestAddr(0x8000_0000),
            size: 8,
        },
        image: "copied-image".into(),
        generation: 0,
        copy_event: Some(COPY.into()),
        evidence,
    });
}

#[test]
fn copy_event_cannot_also_be_cpu_store_event() {
    let mut map = empty_map();
    add_copy(&mut map);
    map.word_store_observations.insert(ObservedWordStore {
        site: GuestAddr(0x8000_1000),
        destination: GuestAddr(0x8000_0000),
        value: 0x1122_3344,
        generation: 0,
        evidence: [COPY.into()].into(),
    });

    assert!(
        map.validate().is_err(),
        "one raw trace event identity cannot be both RomDmaObserved and CpuWordStoreObserved"
    );
}

#[test]
fn copy_event_cannot_also_be_raw_indirect_event() {
    let mut map = empty_map();
    add_copy(&mut map);
    map.indirect_observations.insert(ObservedIndirect {
        site: GuestAddr(0x8000_1000),
        target: GuestAddr(0x8000_2000),
        delay_slot_pc: Some(GuestAddr(0x8000_1004)),
        generation: 0,
        source_unit: None,
        evidence: [COPY.into()].into(),
    });

    assert!(
        map.validate().is_err(),
        "one raw trace event identity cannot be both RomDmaObserved and an indirect execution event"
    );
}

#[test]
fn copy_event_cannot_also_be_entry_verification_event() {
    let mut map = empty_map();
    add_copy(&mut map);
    let unit = "trace:synthetic:11";
    map.evidence.insert(
        unit.into(),
        trace_evidence("one concrete CompileBegin event"),
    );
    let entry = CodeAddress {
        pc: GuestAddr(0x8000_0000),
        image: "copied-image".into(),
        generation: 0,
    };
    map.entries.insert(entry.clone(), [unit.to_string()].into());
    map.entry_verifications.insert(ObservedEntryVerification {
        entry,
        register_mask: 0,
        source_unit: unit.into(),
        generation: 0,
        evidence: [COPY.into()].into(),
    });

    assert!(
        map.validate().is_err(),
        "one raw trace event identity cannot be both RomDmaObserved and EntryBytesVerified"
    );
}

#[test]
fn distinct_primitive_event_ids_remain_valid() {
    let mut map = empty_map();
    add_copy(&mut map);
    let store = "trace:synthetic:8";
    map.evidence.insert(
        store.into(),
        trace_evidence("one concrete CpuWordStoreObserved event"),
    );
    map.word_store_observations.insert(ObservedWordStore {
        site: GuestAddr(0x8000_1000),
        destination: GuestAddr(0x8000_0000),
        value: 0x1122_3344,
        generation: 0,
        evidence: [store.to_string()].into(),
    });

    map.validate().unwrap();
}

#[test]
fn copy_event_may_propagate_into_derived_load_and_region_facts() {
    let mut map = empty_map();
    add_copy(&mut map);

    map.validate().unwrap();
}

#[test]
fn independently_valid_maps_cannot_merge_cross_kind_event_identity() {
    let mut left = empty_map();
    add_copy(&mut left);
    left.validate().unwrap();

    let mut right = empty_map();
    right.evidence.insert(
        COPY.into(),
        trace_evidence("one concrete RomDmaObserved event"),
    );
    right.word_store_observations.insert(ObservedWordStore {
        site: GuestAddr(0x8000_1000),
        destination: GuestAddr(0x8000_0000),
        value: 0x1122_3344,
        generation: 0,
        evidence: [COPY.into()].into(),
    });
    right.validate().unwrap();

    assert!(
        merge_maps(&left, &right).is_err(),
        "merge must not launder one raw event identity across primitive event kinds"
    );
    assert!(
        merge_maps(&right, &left).is_err(),
        "merge order must not change copy-event kind exclusivity"
    );
}
