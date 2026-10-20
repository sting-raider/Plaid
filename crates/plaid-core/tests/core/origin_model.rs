use plaid_core::{EvidenceKind, GuestAddr, merge::merge_maps, program::*};
use serde::Serialize;
use std::collections::BTreeSet;

fn rom() -> RomIdentity {
    RomIdentity {
        sha256: "a".repeat(64),
        size: 4096,
    }
}

fn addr(pc: u32) -> CodeAddress {
    CodeAddress {
        pc: GuestAddr(pc),
        image: "image".into(),
        generation: 2,
    }
}

#[derive(Serialize)]
#[serde(deny_unknown_fields)]
struct EntryDerivationFixture<'a> {
    entry: &'a CodeAddress,
    sources: &'a BTreeSet<CodeAddress>,
}

fn derivation_ref(target: &CodeAddress, sources: &BTreeSet<CodeAddress>) -> (String, Evidence) {
    let detail = serde_json::to_string(&EntryDerivationFixture {
        entry: target,
        sources,
    })
    .unwrap();
    let id = format!(
        "derived-entry:{}",
        plaid_core::rom::sha256(detail.as_bytes())
    );
    (
        id,
        Evidence {
            kind: EvidenceKind::Static,
            producer: "plaid-derived-entry/v0".into(),
            revision: "0".into(),
            detail,
        },
    )
}

fn set_derived_entry(map: &mut ProgramMap, target: CodeAddress, sources: BTreeSet<CodeAddress>) {
    let (id, evidence) = derivation_ref(&target, &sources);
    map.evidence.insert(id.clone(), evidence);
    map.entries.insert(target.clone(), [id].into());
    map.derived_entries.insert(target, sources);
}

fn map_with_origin(source_pc: u32) -> ProgramMap {
    let mut map = ProgramMap::new(rom());
    map.evidence.insert(
        "e".into(),
        Evidence {
            kind: EvidenceKind::Static,
            producer: "synthetic".into(),
            revision: "v1".into(),
            detail: "origin fixture".into(),
        },
    );
    let source = addr(source_pc);
    let target = addr(0x80000020);
    map.entries.insert(target.clone(), ["e".into()].into());
    map.indirect_sites.insert(IndirectSite {
        site: source.clone(),
        link_register: None,
        delay_slot: DelaySlot::Always,
        candidates: [(target.clone(), ["e".into()].into())].into(),
        observed: Default::default(),
        closed_proof: None,
        evidence: ["e".into()].into(),
    });
    set_derived_entry(&mut map, target, [source].into());
    map
}

#[test]
fn derived_entry_roundtrips_and_empty_field_preserves_legacy_json() {
    let empty = ProgramMap::new(rom());
    assert!(empty.derived_entries.is_empty());
    let json = empty.to_json().unwrap();
    assert!(!json.contains("derived_entries"));
    let mut legacy: serde_json::Value = serde_json::from_str(&json).unwrap();
    legacy.as_object_mut().unwrap().remove("derived_entries");
    assert_eq!(ProgramMap::from_json(&legacy.to_string()).unwrap(), empty);

    let map = map_with_origin(0x80000010);
    assert_eq!(ProgramMap::from_json(&map.to_json().unwrap()).unwrap(), map);
}

#[test]
fn derived_entry_requires_a_valid_nonlink_candidate_relation() {
    let valid = map_with_origin(0x80000010);
    valid.validate().unwrap();

    let mut bad = valid.clone();
    bad.entries.clear();
    assert!(bad.validate().is_err(), "missing entry target");

    let mut bad = valid.clone();
    bad.indirect_sites.clear();
    assert!(bad.validate().is_err(), "missing source site");

    let mut bad = valid.clone();
    let mut site = bad.indirect_sites.pop_first().unwrap();
    site.candidates.clear();
    bad.indirect_sites.insert(site);
    assert!(bad.validate().is_err(), "missing candidate");

    let mut bad = valid.clone();
    let mut site = bad.indirect_sites.pop_first().unwrap();
    site.link_register = Some(31);
    bad.indirect_sites.insert(site);
    assert!(bad.validate().is_err(), "linking site");

    let mut bad = valid.clone();
    let target = bad.derived_entries.keys().next().unwrap().clone();
    let mut source = bad.derived_entries[&target].first().unwrap().clone();
    source.generation += 1;
    bad.derived_entries.insert(target.clone(), [source].into());
    assert!(bad.validate().is_err(), "generation mismatch");

    let mut bad = valid.clone();
    let target = bad.derived_entries.keys().next().unwrap().clone();
    let mut source = bad.derived_entries[&target].first().unwrap().clone();
    source.image = "other-image".into();
    bad.derived_entries.insert(target, [source].into());
    assert!(bad.validate().is_err(), "image mismatch");

    let mut bad = valid.clone();
    bad.derived_entries
        .insert(addr(0x80000020), BTreeSet::new());
    assert!(bad.validate().is_err(), "empty source set");

    let mut bad = valid.clone();
    let target = addr(0x80000020);
    bad.entries.insert(target.clone(), ["e".into()].into());
    assert!(
        bad.validate().is_err(),
        "ordinary entry evidence cannot be erased by a tag"
    );

    let mut bad = valid.clone();
    let target = addr(0x80000020);
    let id = bad.entries[&target].first().unwrap().clone();
    bad.evidence.get_mut(&id).unwrap().detail.push(' ');
    assert!(bad.validate().is_err(), "witness hash mismatch");

    let mut bad = valid.clone();
    let target = addr(0x80000024);
    let source = addr(0x80000010);
    let id = bad.entries[&addr(0x80000020)].first().unwrap().clone();
    bad.entries.insert(target.clone(), [id].into());
    bad.derived_entries.insert(target.clone(), [source].into());
    let mut site = bad.indirect_sites.pop_first().unwrap();
    site.candidates.insert(target.clone(), ["e".into()].into());
    bad.indirect_sites.insert(site);
    assert!(bad.validate().is_err(), "witness copied to another target");

    let mut bad = valid.clone();
    let target = addr(0x80000020);
    let sources = bad.derived_entries[&target].clone();
    let (id, mut evidence) = derivation_ref(&target, &sources);
    evidence.detail = "not an entry derivation".into();
    let bad_id = format!(
        "derived-entry:{}",
        plaid_core::rom::sha256(evidence.detail.as_bytes())
    );
    bad.evidence.remove(&id);
    bad.evidence.insert(bad_id.clone(), evidence);
    bad.entries.insert(target, [bad_id].into());
    assert!(bad.validate().is_err(), "malformed witness payload");

    let mut bad = valid.clone();
    let target = addr(0x80000020);
    let second_source = addr(0x80000018);
    bad.indirect_sites.insert(IndirectSite {
        site: second_source.clone(),
        link_register: None,
        delay_slot: DelaySlot::Always,
        candidates: [(target.clone(), ["e".into()].into())].into(),
        observed: Default::default(),
        closed_proof: None,
        evidence: ["e".into()].into(),
    });
    let mut expanded_sources = bad.derived_entries[&target].clone();
    expanded_sources.insert(second_source);
    bad.derived_entries.insert(target, expanded_sources);
    assert!(
        bad.validate().is_err(),
        "metadata cannot claim unwitnessed parents"
    );

    let mut bad = valid;
    bad.address_taken
        .insert(addr(0x80000020), ["e".into()].into());
    assert!(bad.validate().is_err(), "address-taken target");
}

#[test]
fn merge_keeps_external_origins_in_both_orders_and_unions_derived_sources() {
    let derived = map_with_origin(0x80000010);
    let mut other_derived = map_with_origin(0x80000014);
    other_derived.evidence.insert(
        "e2".into(),
        Evidence {
            kind: EvidenceKind::Static,
            producer: "synthetic".into(),
            revision: "v1".into(),
            detail: "second origin fixture".into(),
        },
    );
    let target = addr(0x80000020);
    let mut site = other_derived.indirect_sites.pop_first().unwrap();
    site.evidence = ["e2".into()].into();
    site.candidates.insert(target.clone(), ["e2".into()].into());
    other_derived.indirect_sites.insert(site);
    set_derived_entry(
        &mut other_derived,
        target.clone(),
        [addr(0x80000014)].into(),
    );

    let merged = merge_maps(&derived, &other_derived).unwrap();
    assert_eq!(merged.derived_entries[&target].len(), 2);
    assert_eq!(merged.entries[&target].len(), 2);
    assert!(merged.validate().is_ok());
    assert_eq!(merged, merge_maps(&other_derived, &derived).unwrap());

    let mut external = ProgramMap::new(rom());
    external
        .evidence
        .insert("e".into(), derived.evidence["e"].clone());
    external.entries.insert(target.clone(), ["e".into()].into());
    for (left, right) in [(&derived, &external), (&external, &derived)] {
        let merged = merge_maps(left, right).unwrap();
        assert!(!merged.derived_entries.contains_key(&target));
        assert!(merged.entries[&target].contains("e"));
    }
}

#[test]
fn merged_explicit_root_cannot_be_reclassified_with_a_valid_candidate_witness() {
    let derived = map_with_origin(0x80000010);
    let target = addr(0x80000020);
    let mut external = ProgramMap::new(rom());
    external.evidence.insert(
        "external".into(),
        Evidence {
            kind: EvidenceKind::Static,
            producer: "explicit-root".into(),
            revision: "1".into(),
            detail: "independent input entry".into(),
        },
    );
    external
        .entries
        .insert(target.clone(), ["external".into()].into());

    let mut merged = merge_maps(&derived, &external).unwrap();
    assert!(!merged.derived_entries.contains_key(&target));
    assert!(merged.validate().is_ok());

    let source = addr(0x80000010);
    merged
        .derived_entries
        .insert(target.clone(), [source].into());
    assert!(merged.entries[&target].contains("external"));
    assert!(merged.validate().is_err());
}

#[test]
fn address_taken_without_an_entry_row_wins_in_either_merge_order() {
    let derived = map_with_origin(0x80000010);
    let target = addr(0x80000020);
    let mut taken = ProgramMap::new(rom());
    taken
        .evidence
        .insert("e".into(), derived.evidence["e"].clone());
    taken
        .address_taken
        .insert(target.clone(), ["e".into()].into());
    derived.validate().unwrap();
    taken.validate().unwrap();
    assert!(!taken.entries.contains_key(&target));
    for (left, right) in [(&derived, &taken), (&taken, &derived)] {
        let merged = merge_maps(left, right).unwrap();
        assert!(merged.address_taken.contains_key(&target));
        assert!(!merged.derived_entries.contains_key(&target));
        merged.validate().unwrap();
    }
}
