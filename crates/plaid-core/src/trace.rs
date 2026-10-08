//! Trace v0 uses one JSON object per line. Sequence is execution order.
//! Compilation units are not automatically guest basic blocks or functions.
use crate::{
    GuestAddr,
    program::{GuestRange, PhysicalAddr, RomIdentity, RomOffset},
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

pub const TRACE_VERSION: u32 = 0;
pub const MAX_RECORD_BYTES: usize = 1024 * 1024;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TraceHeader {
    pub schema_version: u32,
    pub rom: RomIdentity,
    pub engine: String,
    pub revision: String,
    /// Capabilities declare sensors, not coverage or closed-world proofs.
    pub capabilities: BTreeSet<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "event", rename_all = "snake_case", deny_unknown_fields)]
pub enum TraceEvent {
    /// Successful aligned SW, limited sensor; never complete write coverage.
    CpuWordStoreObserved {
        site: GuestAddr,
        destination: GuestAddr,
        value: u32,
    },
    RomDmaObserved {
        rom_offset: RomOffset,
        physical_destination: PhysicalAddr,
        size: u32,
    },
    CompileBegin {
        unit: u64,
        start: GuestAddr,
        physical_start: Option<PhysicalAddr>,
        delay_slot_entry: bool,
    },
    UnitCompiled {
        unit: u64,
        start: GuestAddr,
        words: Vec<u32>,
    },
    /// A dirty-entry lookup compared current memory to this completed unit.
    /// This records a snapshot check, not execution or a new compilation.
    EntryBytesVerified {
        unit: u64,
        pc: GuestAddr,
        register_mask: u32,
        words: Vec<u32>,
    },
    EntryInstalled {
        unit: u64,
        pc: GuestAddr,
        register_mask: u32,
    },
    /// A target lookup cannot establish which JR/JALR site caused it.
    TargetLookup {
        target: GuestAddr,
        delay_slot_entry: bool,
    },
    IndirectTargetObserved {
        site: GuestAddr,
        target: GuestAddr,
        delay_slot_pc: Option<GuestAddr>,
        /// Trace-local compilation identity embedded in the executing host unit.
        /// Older producers lack this context and retain conservative epoch joins.
        #[serde(default)]
        source_unit: Option<u64>,
    },
    RuntimeLink {
        target: GuestAddr,
    },
    Invalidate {
        range: Option<GuestRange>,
    },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct EventRecord {
    pub seq: u64,
    pub data: TraceEvent,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DiscoveryTrace {
    pub header: TraceHeader,
    pub events: Vec<EventRecord>,
}

#[derive(Serialize, Deserialize)]
#[serde(tag = "record", rename_all = "snake_case", deny_unknown_fields)]
enum WireRecord {
    Header { header: TraceHeader },
    Event { seq: u64, data: TraceEvent },
    End { event_count: u64 },
}

struct UnitState {
    start: GuestAddr,
    words: Option<Vec<u32>>,
    entries: BTreeSet<(GuestAddr, u32)>,
}

impl DiscoveryTrace {
    pub fn validate(&self) -> Result<(), String> {
        if self.header.schema_version != TRACE_VERSION {
            return Err("unsupported discovery trace version".into());
        }
        self.header.rom.validate()?;
        if self.header.engine.is_empty() || self.header.revision.is_empty() {
            return Err("missing trace producer".into());
        }
        let mut units = std::collections::BTreeMap::new();
        let aligned = |pc: GuestAddr| -> Result<(), String> {
            if !pc.0.is_multiple_of(4) {
                return Err("unaligned trace PC".into());
            }
            Ok(())
        };
        for (index, event) in self.events.iter().enumerate() {
            if event.seq != index as u64 {
                return Err("non-contiguous trace sequence".into());
            }
            match &event.data {
                TraceEvent::CpuWordStoreObserved {
                    site, destination, ..
                } => {
                    aligned(*site)?;
                    aligned(*destination)?;
                    if !(0x80000000..0x80800000).contains(&destination.0) {
                        return Err(
                            "word-store sensor destination outside declared cached RDRAM".into(),
                        );
                    }
                }
                TraceEvent::RomDmaObserved {
                    rom_offset,
                    physical_destination,
                    size,
                } => {
                    if *size == 0
                        || rom_offset
                            .0
                            .checked_add(u64::from(*size))
                            .is_none_or(|end| end > self.header.rom.size)
                        || u64::from(physical_destination.0) + u64::from(*size) > 1u64 << 32
                    {
                        return Err("invalid observed ROM DMA range".into());
                    }
                }
                TraceEvent::CompileBegin { unit, start, .. } => {
                    aligned(*start)?;
                    if units
                        .insert(
                            *unit,
                            UnitState {
                                start: *start,
                                words: None,
                                entries: BTreeSet::new(),
                            },
                        )
                        .is_some()
                    {
                        return Err("duplicate compilation unit".into());
                    }
                }
                TraceEvent::UnitCompiled { unit, start, words } => {
                    let size = u32::try_from(words.len())
                        .ok()
                        .and_then(|n| n.checked_mul(4))
                        .ok_or("unit too large")?;
                    GuestRange {
                        start: *start,
                        size,
                    }
                    .validate(true)?;
                    let state = units.get_mut(unit).ok_or("unit completion without begin")?;
                    if state.start != *start || state.words.replace(words.clone()).is_some() {
                        return Err("mismatched unit completion".into());
                    }
                }
                TraceEvent::EntryInstalled {
                    unit,
                    pc,
                    register_mask,
                } => {
                    aligned(*pc)?;
                    units
                        .get_mut(unit)
                        .ok_or("entry without compilation unit")?
                        .entries
                        .insert((*pc, *register_mask));
                }
                TraceEvent::EntryBytesVerified {
                    unit,
                    pc,
                    register_mask,
                    words,
                } => {
                    let state = units.get(unit).ok_or("verified entry without unit")?;
                    if state.words.as_ref() != Some(words) {
                        return Err("verified entry bytes differ from completed unit".into());
                    }
                    if !state.entries.contains(&(*pc, *register_mask)) {
                        return Err("verified entry/mask was not installed".into());
                    }
                }
                TraceEvent::TargetLookup { target, .. } | TraceEvent::RuntimeLink { target } => {
                    aligned(*target)?;
                }
                TraceEvent::IndirectTargetObserved {
                    site,
                    target,
                    delay_slot_pc,
                    source_unit,
                } => {
                    aligned(*site)?;
                    aligned(*target)?;
                    if let Some(ds) = delay_slot_pc
                        && site.0.checked_add(4) != Some(ds.0)
                    {
                        return Err("incorrect delay slot PC".into());
                    }
                    if let Some(unit) = source_unit {
                        let state = units.get(unit).ok_or("unknown indirect source unit")?;
                        let range = GuestRange {
                            start: state.start,
                            size: state
                                .words
                                .as_ref()
                                .ok_or("indirect source unit not completed")?
                                .len() as u32
                                * 4,
                        };
                        if !range.contains(*site) {
                            return Err("indirect site outside source unit".into());
                        }
                    }
                }
                TraceEvent::Invalidate { range } => {
                    if let Some(r) = range {
                        r.validate(false)?;
                    }
                }
            }
        }
        for state in units.values() {
            let range = GuestRange {
                start: state.start,
                size: state
                    .words
                    .as_ref()
                    .ok_or("unfinished compilation unit")?
                    .len() as u32
                    * 4,
            };
            if state.entries.iter().any(|(pc, _)| !range.contains(*pc)) {
                return Err("entry outside compilation unit".into());
            }
        }
        Ok(())
    }

    pub fn to_ndjson(&self) -> Result<String, String> {
        self.validate()?;
        let mut lines = vec![
            serde_json::to_string(&WireRecord::Header {
                header: self.header.clone(),
            })
            .map_err(|e| e.to_string())?,
        ];
        for e in &self.events {
            lines.push(
                serde_json::to_string(&WireRecord::Event {
                    seq: e.seq,
                    data: e.data.clone(),
                })
                .map_err(|e| e.to_string())?,
            );
        }
        lines.push(
            serde_json::to_string(&WireRecord::End {
                event_count: self.events.len() as u64,
            })
            .map_err(|e| e.to_string())?,
        );
        if lines.iter().any(|l| l.len() > MAX_RECORD_BYTES) {
            return Err("trace record exceeds size limit".into());
        }
        Ok(lines.join("\n") + "\n")
    }

    pub fn from_ndjson(input: &str) -> Result<Self, String> {
        let mut header = None;
        let mut events = Vec::new();
        let mut ended = false;
        for (index, line) in input.lines().enumerate() {
            if ended {
                return Err("record after trace end".into());
            }
            if line.len() > MAX_RECORD_BYTES {
                return Err("trace record exceeds size limit".into());
            }
            let record: WireRecord =
                serde_json::from_str(line).map_err(|e| format!("trace line {}: {e}", index + 1))?;
            match record {
                WireRecord::Header { header: h } if index == 0 => {
                    header = Some(h);
                }
                WireRecord::Event { seq, data } if header.is_some() => {
                    events.push(EventRecord { seq, data });
                }
                WireRecord::End { event_count } if header.is_some() => {
                    if event_count != events.len() as u64 {
                        return Err("incorrect trace event count".into());
                    }
                    ended = true;
                }
                _ => {
                    return Err("trace header missing or repeated".into());
                }
            }
        }
        if !ended {
            return Err("truncated discovery trace: missing end record".into());
        }
        let trace = Self {
            header: header.ok_or("missing header")?,
            events,
        };
        trace.validate()?;
        Ok(trace)
    }
}
