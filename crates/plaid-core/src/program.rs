//! Versioned, portable executable facts. Collection order never affects JSON.
use crate::{EvidenceKind, GuestAddr};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

pub type EvidenceRefs = BTreeSet<String>;
pub const SCHEMA_VERSION: u32 = 0;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(transparent)]
pub struct RomOffset(pub u64);

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(transparent)]
pub struct PhysicalAddr(pub u32);

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RomIdentity {
    pub sha256: String,
    pub size: u64,
}

impl RomIdentity {
    pub fn validate(&self) -> Result<(), String> {
        if self.sha256.len() != 64
            || !self
                .sha256
                .bytes()
                .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
            || self.size < 64
        {
            return Err("invalid canonical ROM identity".into());
        }
        Ok(())
    }
}

/// An address alone does not distinguish different code loaded at the same PC.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CodeAddress {
    pub pc: GuestAddr,
    pub image: String,
    pub generation: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct GuestRange {
    pub start: GuestAddr,
    pub size: u32,
}
impl GuestRange {
    pub fn end(&self) -> u64 {
        u64::from(self.start.0) + u64::from(self.size)
    }
    pub fn validate(&self, code: bool) -> Result<(), String> {
        if self.size == 0
            || self.end() > 1u64 << 32
            || (code && (!self.start.0.is_multiple_of(4) || !self.size.is_multiple_of(4)))
        {
            return Err("invalid guest range".into());
        }
        Ok(())
    }
    pub fn contains(&self, pc: GuestAddr) -> bool {
        u64::from(pc.0) >= u64::from(self.start.0) && u64::from(pc.0) < self.end()
    }
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Evidence {
    pub kind: EvidenceKind,
    pub producer: String,
    pub revision: String,
    pub detail: String,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Region {
    pub image: String,
    pub generation: u64,
    pub range: GuestRange,
    pub rom_offset: Option<RomOffset>,
    pub physical_start: Option<PhysicalAddr>,
    pub overlay: Option<String>,
    pub evidence: EvidenceRefs,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct BasicBlock {
    pub start: CodeAddress,
    pub size: u32,
    pub delay_slot_entry: bool,
    pub evidence: EvidenceRefs,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EdgeKind {
    Branch,
    Call,
    Jump,
    Fallthrough,
    ReturnContinuation,
    Exception,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DelaySlot {
    None,
    Always,
    TakenOnly,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DirectEdge {
    pub site: CodeAddress,
    pub target: CodeAddress,
    pub kind: EdgeKind,
    pub delay_slot: DelaySlot,
    pub evidence: EvidenceRefs,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct IndirectSite {
    pub site: CodeAddress,
    pub link_register: Option<u8>,
    pub delay_slot: DelaySlot,
    #[serde(with = "pairs")]
    pub candidates: BTreeMap<CodeAddress, EvidenceRefs>,
    #[serde(with = "pairs")]
    pub observed: BTreeMap<CodeAddress, EvidenceRefs>,
    /// Proof reference, never set merely by observing finite samples.
    pub closed_proof: Option<String>,
    pub evidence: EvidenceRefs,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Overlay {
    pub image: String,
    pub rom_offset: RomOffset,
    pub size: u32,
    pub load_address: GuestAddr,
    pub candidate: bool,
    pub evidence: EvidenceRefs,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LoadMapping {
    pub rom_offset: RomOffset,
    pub destination: GuestRange,
    pub image: String,
    pub generation: u64,
    /// Reference to the observed transfer, separate from compilation/snapshot.
    /// Older maps without this identity cannot establish distinct reload events.
    #[serde(default)]
    pub copy_event: Option<String>,
    pub evidence: EvidenceRefs,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ObservedDma {
    pub rom_offset: RomOffset,
    pub physical_destination: PhysicalAddr,
    pub size: u32,
    pub evidence: EvidenceRefs,
}

pub(crate) fn copy_covers(
    dma: &ObservedDma,
    copy: &str,
    offset: RomOffset,
    size: u32,
    physical: Option<PhysicalAddr>,
) -> bool {
    let Some(delta) = offset.0.checked_sub(dma.rom_offset.0) else {
        return false;
    };
    dma.evidence.contains(copy)
        && delta
            .checked_add(u64::from(size))
            .is_some_and(|end| end <= u64::from(dma.size))
        && physical.is_some_and(|p| u64::from(p.0) == u64::from(dma.physical_destination.0) + delta)
}

/// Raw source-correlated execution evidence survives missing/ambiguous image
/// identities. Generation is the importing trace's conservative invalidation epoch.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ObservedIndirect {
    pub site: GuestAddr,
    pub target: GuestAddr,
    pub delay_slot_pc: Option<GuestAddr>,
    pub generation: u64,
    /// Session-qualified evidence ID of the source unit's CompileBegin event.
    /// This is compilation provenance, never a host pointer or a closure proof.
    #[serde(default)]
    pub source_unit: Option<String>,
    pub evidence: EvidenceRefs,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ObservedWordStore {
    pub site: GuestAddr,
    pub destination: GuestAddr,
    pub value: u32,
    pub generation: u64,
    pub evidence: EvidenceRefs,
}

/// A reference sensor's byte-equality check for an existing installed entry.
/// Generation is the verification epoch, not the unit's compilation generation.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ObservedEntryVerification {
    pub entry: CodeAddress,
    pub register_mask: u32,
    pub source_unit: String,
    pub generation: u64,
    pub evidence: EvidenceRefs,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Relocation {
    pub site: CodeAddress,
    pub kind: String,
    pub target: GuestAddr,
    pub evidence: EvidenceRefs,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum WriteKind {
    Unknown,
    Relocation,
    OverlayReload,
    InstructionPatch,
    GeneratedCode,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ExecutableWrite {
    /// None represents global invalidation, not an empty write.
    pub range: Option<GuestRange>,
    pub kind: WriteKind,
    pub evidence: EvidenceRefs,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Microcode {
    pub sha256: String,
    pub imem_start: u16,
    pub size: u16,
    pub evidence: EvidenceRefs,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Unresolved {
    pub kind: String,
    pub site: Option<CodeAddress>,
    pub detail: String,
    pub evidence: EvidenceRefs,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ProgramMap {
    pub schema_version: u32,
    pub rom: RomIdentity,
    #[serde(with = "unique_map")]
    pub evidence: BTreeMap<String, Evidence>,
    pub regions: BTreeSet<Region>,
    pub blocks: BTreeSet<BasicBlock>,
    #[serde(with = "pairs")]
    pub entries: BTreeMap<CodeAddress, EvidenceRefs>,
    pub direct_edges: BTreeSet<DirectEdge>,
    pub indirect_sites: BTreeSet<IndirectSite>,
    #[serde(with = "unique_map")]
    pub overlays: BTreeMap<String, Overlay>,
    pub loads: BTreeSet<LoadMapping>,
    pub dma_observations: BTreeSet<ObservedDma>,
    #[serde(default)]
    pub indirect_observations: BTreeSet<ObservedIndirect>,
    #[serde(default)]
    pub entry_verifications: BTreeSet<ObservedEntryVerification>,
    #[serde(default)]
    pub word_store_observations: BTreeSet<ObservedWordStore>,
    pub relocations: BTreeSet<Relocation>,
    pub executable_writes: BTreeSet<ExecutableWrite>,
    pub rsp_microcodes: BTreeSet<Microcode>,
    pub unresolved: BTreeSet<Unresolved>,
}

impl ProgramMap {
    pub fn new(rom: RomIdentity) -> Self {
        Self {
            schema_version: SCHEMA_VERSION,
            rom,
            evidence: BTreeMap::new(),
            regions: BTreeSet::new(),
            blocks: BTreeSet::new(),
            entries: BTreeMap::new(),
            direct_edges: BTreeSet::new(),
            indirect_sites: BTreeSet::new(),
            overlays: BTreeMap::new(),
            loads: BTreeSet::new(),
            dma_observations: BTreeSet::new(),
            indirect_observations: BTreeSet::new(),
            entry_verifications: BTreeSet::new(),
            word_store_observations: BTreeSet::new(),
            relocations: BTreeSet::new(),
            executable_writes: BTreeSet::new(),
            rsp_microcodes: BTreeSet::new(),
            unresolved: BTreeSet::new(),
        }
    }

    pub fn validate(&self) -> Result<(), String> {
        if self.schema_version != SCHEMA_VERSION {
            return Err("unsupported ProgramMap version".into());
        }
        self.rom.validate()?;
        for (id, e) in &self.evidence {
            if id.is_empty()
                || e.producer.is_empty()
                || e.revision.is_empty()
                || e.detail.is_empty()
            {
                return Err("incomplete evidence".into());
            }
        }
        let refs = |r: &EvidenceRefs| -> Result<(), String> {
            if r.is_empty() || r.iter().any(|id| !self.evidence.contains_key(id)) {
                return Err("missing provenance".into());
            }
            Ok(())
        };
        let address = |a: &CodeAddress| -> Result<(), String> {
            if !a.pc.0.is_multiple_of(4) || a.image.is_empty() {
                return Err("invalid execution identity".into());
            }
            Ok(())
        };
        let rom_range = |offset: RomOffset, size: u32| -> Result<(), String> {
            if size == 0
                || offset
                    .0
                    .checked_add(u64::from(size))
                    .is_none_or(|end| end > self.rom.size)
            {
                return Err("ROM source outside canonical image".into());
            }
            Ok(())
        };
        for r in &self.regions {
            r.range.validate(true)?;
            refs(&r.evidence)?;
            if r.image.is_empty() {
                return Err("region has no image identity".into());
            }
            if let Some(o) = r.rom_offset {
                rom_range(o, r.range.size)?;
            }
            if let Some(o) = &r.overlay
                && self.overlays.get(o).is_none_or(|x| x.image != r.image)
            {
                return Err("unknown or mismatched overlay".into());
            }
        }
        for b in &self.blocks {
            address(&b.start)?;
            refs(&b.evidence)?;
            GuestRange {
                start: b.start.pc,
                size: b.size,
            }
            .validate(true)?;
        }
        for (a, e) in &self.entries {
            address(a)?;
            refs(e)?;
        }
        for e in &self.direct_edges {
            address(&e.site)?;
            address(&e.target)?;
            refs(&e.evidence)?;
        }
        for i in &self.indirect_sites {
            address(&i.site)?;
            refs(&i.evidence)?;
            if i.link_register.is_some_and(|r| r > 31) {
                return Err("invalid link register".into());
            }
            for (a, e) in i.candidates.iter().chain(&i.observed) {
                address(a)?;
                refs(e)?;
            }
            if let Some(p) = &i.closed_proof {
                refs(&[p.clone()].into())?;
            }
        }
        for (id, o) in &self.overlays {
            if id.is_empty() || o.image.is_empty() {
                return Err("invalid overlay identity".into());
            }
            rom_range(o.rom_offset, o.size)?;
            refs(&o.evidence)?;
            GuestRange {
                start: o.load_address,
                size: o.size,
            }
            .validate(true)?;
        }
        for l in &self.loads {
            l.destination.validate(true)?;
            rom_range(l.rom_offset, l.destination.size)?;
            refs(&l.evidence)?;
            if let Some(copy) = &l.copy_event
                && (!l.evidence.contains(copy)
                    || self
                        .evidence
                        .get(copy)
                        .is_none_or(|e| e.kind != EvidenceKind::Trace))
            {
                return Err("load copy event lacks trace provenance".into());
            }
            if let Some(copy) = &l.copy_event
                && !self.regions.iter().any(|r| {
                    r.image == l.image
                        && r.generation == l.generation
                        && r.range == l.destination
                        && r.rom_offset == Some(l.rom_offset)
                        && self.dma_observations.iter().any(|d| {
                            copy_covers(d, copy, l.rom_offset, l.destination.size, r.physical_start)
                        })
                })
            {
                return Err("load copy event has no covering observed DMA/mapping".into());
            }
            if l.image.is_empty() {
                return Err("load has no image identity".into());
            }
        }
        for d in &self.dma_observations {
            rom_range(d.rom_offset, d.size)?;
            refs(&d.evidence)?;
            if u64::from(d.physical_destination.0) + u64::from(d.size) > 1u64 << 32 {
                return Err("DMA destination overflow".into());
            }
        }
        for o in &self.indirect_observations {
            if !o.site.0.is_multiple_of(4) || !o.target.0.is_multiple_of(4) {
                return Err("unaligned indirect observation".into());
            }
            if o.delay_slot_pc
                .is_some_and(|ds| o.site.0.checked_add(4) != Some(ds.0))
            {
                return Err("incorrect observed delay slot PC".into());
            }
            if let Some(unit) = &o.source_unit
                && !self
                    .evidence
                    .get(unit)
                    .is_some_and(|e| e.kind == EvidenceKind::Trace)
            {
                return Err("missing indirect source-unit trace provenance".into());
            }
            refs(&o.evidence)?;
        }
        for store in &self.word_store_observations {
            if !store.site.0.is_multiple_of(4)
                || !store.destination.0.is_multiple_of(4)
                || !(0x80000000..0x80800000).contains(&store.destination.0)
            {
                return Err("invalid observed cached RDRAM word store".into());
            }
            refs(&store.evidence)?;
        }
        for verification in &self.entry_verifications {
            address(&verification.entry)?;
            refs(&verification.evidence)?;
            if !self.entries.contains_key(&verification.entry)
                || !self
                    .evidence
                    .get(&verification.source_unit)
                    .is_some_and(|e| e.kind == EvidenceKind::Trace)
            {
                return Err("verified entry missing installed identity or unit provenance".into());
            }
        }
        for r in &self.relocations {
            address(&r.site)?;
            refs(&r.evidence)?;
            if r.kind.is_empty() {
                return Err("untyped relocation".into());
            }
        }
        for w in &self.executable_writes {
            if let Some(r) = &w.range {
                r.validate(false)?;
            }
            refs(&w.evidence)?;
        }
        for m in &self.rsp_microcodes {
            RomIdentity {
                sha256: m.sha256.clone(),
                size: 64,
            }
            .validate()?;
            if m.size == 0 || u32::from(m.imem_start) + u32::from(m.size) > 4096 {
                return Err("invalid RSP IMEM range".into());
            }
            refs(&m.evidence)?;
        }
        for u in &self.unresolved {
            if let Some(a) = &u.site {
                address(a)?;
            }
            if u.kind.is_empty() || u.detail.is_empty() {
                return Err("empty unresolved diagnostic".into());
            }
            refs(&u.evidence)?;
        }
        Ok(())
    }

    pub fn to_json(&self) -> Result<String, String> {
        self.validate()?;
        // JSON cannot represent object keys that are structured guest identities.
        // The custom entries adapter below serializes maps as sorted pairs.
        serde_json::to_string_pretty(self).map_err(|e| e.to_string())
    }
    pub fn from_json(json: &str) -> Result<Self, String> {
        let map: Self = serde_json::from_str(json).map_err(|e| e.to_string())?;
        map.validate()?;
        Ok(map)
    }
}

/// Stable pair arrays for structured keys; reject duplicate keys on input.
pub mod pairs {
    use serde::{Deserialize, Deserializer, Serialize, Serializer, de::Error};
    use std::collections::BTreeMap;
    pub fn serialize<K: Serialize + Ord, V: Serialize, S: Serializer>(
        map: &BTreeMap<K, V>,
        s: S,
    ) -> Result<S::Ok, S::Error> {
        map.iter().collect::<Vec<_>>().serialize(s)
    }
    pub fn deserialize<
        'de,
        K: Deserialize<'de> + Ord,
        V: Deserialize<'de>,
        D: Deserializer<'de>,
    >(
        d: D,
    ) -> Result<BTreeMap<K, V>, D::Error> {
        let mut out = BTreeMap::new();
        for (k, v) in Vec::<(K, V)>::deserialize(d)? {
            if out.insert(k, v).is_some() {
                return Err(D::Error::custom("duplicate structured key"));
            }
        }
        Ok(out)
    }
}

mod unique_map {
    use serde::{
        Deserialize, Deserializer, Serialize, Serializer,
        de::{Error, MapAccess, Visitor},
    };
    use std::{collections::BTreeMap, marker::PhantomData};
    pub fn serialize<K: Serialize + Ord, V: Serialize, S: Serializer>(
        map: &BTreeMap<K, V>,
        s: S,
    ) -> Result<S::Ok, S::Error> {
        map.serialize(s)
    }
    pub fn deserialize<
        'de,
        K: Deserialize<'de> + Ord,
        V: Deserialize<'de>,
        D: Deserializer<'de>,
    >(
        d: D,
    ) -> Result<BTreeMap<K, V>, D::Error> {
        struct Unique<K, V>(PhantomData<(K, V)>);
        impl<'de, K: Deserialize<'de> + Ord, V: Deserialize<'de>> Visitor<'de> for Unique<K, V> {
            type Value = BTreeMap<K, V>;
            fn expecting(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
                f.write_str("map with unique identities")
            }
            fn visit_map<A: MapAccess<'de>>(self, mut a: A) -> Result<Self::Value, A::Error> {
                let mut out = BTreeMap::new();
                while let Some((k, v)) = a.next_entry()? {
                    if out.insert(k, v).is_some() {
                        return Err(A::Error::custom("duplicate evidence/overlay identity"));
                    }
                }
                Ok(out)
            }
        }
        d.deserialize_map(Unique(PhantomData))
    }
}
