//! Decoded cached operands use the canonical primitive resident state.
use super::{
    CpuRamCopyParent, Loaded, RamByteOrigin, Row, SpByteOrigin, effect_row, require, same,
};
use crate::{
    dcache_writeback::{DcacheByteOrigin, DcacheReplay, DcacheResidentReadReport, Event},
    program::PhysicalAddr,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub(super) struct DcacheLine {
    pub slot: u16,
    pub tag: u32,
    pub index: u16,
    pub dirty: u16,
    pub words: [u32; 4],
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DcacheFillParents {
    pub read_ordinal: u64,
    pub physical_line: PhysicalAddr,
    pub source_bytes: [RamByteOrigin; 16],
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RspDcacheConsumption {
    pub cache: DcacheResidentReadReport,
    pub backing_fills: Vec<DcacheFillParents>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cpu_word_mutations: Option<Vec<CpuCachedWordMutation>>,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CpuCachedWordMutation {
    pub decoder_context: u64,
    pub mutation_ordinal: u64,
    pub destination: PhysicalAddr,
    pub source_register: u8,
    pub register_value: u64,
    pub word: u32,
    pub copy_parent: Option<CpuRamCopyParent>,
}
pub(super) struct DcacheCompose {
    state: Option<DcacheReplay>,
    fills: BTreeMap<u64, DcacheFillParents>,
    digest: String,
    writes_enabled: bool,
    mutations: Vec<CpuCachedWordMutation>,
    dirty: BTreeMap<u16, u16>,
    ending: Option<u64>,
}
impl DcacheCompose {
    pub fn new(digest: String) -> Self {
        Self {
            state: Some(DcacheReplay::new(true, false)),
            fills: BTreeMap::new(),
            digest,
            writes_enabled: false,
            mutations: Vec::new(),
            dirty: BTreeMap::new(),
            ending: None,
        }
    }
    pub fn enable_writes(&mut self) {
        self.writes_enabled = true;
    }
    pub fn finish_instruction(&mut self, begin: &Row, end: &Row) -> Result<(), String> {
        if begin.word >> 26 == 0x2b {
            require(
                self.mutations
                    .last()
                    .is_some_and(|m| m.decoder_context == begin.context),
                "cached SW lacks its actual resident mutation",
            )?;
            return Ok(());
        }
        require(
            self.ending.take() == Some(begin.context),
            "HitWritebackD lacks complete writeback",
        )?;
        let before = begin
            .dcache_cpu_line
            .as_ref()
            .ok_or("writeback lacks before CPU line")?;
        let after = end
            .dcache_cpu_line
            .as_ref()
            .ok_or("writeback lacks completed CPU line")?;
        let mut expected = before.clone();
        expected.dirty = 0;
        require(
            *after == expected
                && before.dirty != 0
                && self.state.as_ref().unwrap().resident_snapshot(after.slot)
                    == Some((
                        PhysicalAddr((after.tag & !4095) | u32::from(after.index)),
                        std::array::from_fn(|n| after.words[n / 4].to_be_bytes()[n % 4]),
                    )),
            "writeback did not preserve resident and clear actual dirty mask",
        )?;
        self.dirty.insert(after.slot, 0);
        Ok(())
    }
    fn apply(&mut self, event: Event) -> Result<(), String> {
        self.state = Some(
            self.state
                .take()
                .ok_or("D-cache state was consumed")?
                .observe(event)?,
        );
        Ok(())
    }
    pub fn backing_write(&mut self, row: &Row) -> Result<(), String> {
        require(
            row.bytes == 4 && row.value <= u64::from(u32::MAX),
            "unsupported shared D-cache backing Word",
        )?;
        self.apply(Event::BackingWordMutation {
            ordinal: row.ordinal,
            physical: PhysicalAddr(row.address),
            payload: (row.value as u32).to_be_bytes(),
        })
    }
    pub fn observe(
        &mut self,
        row: &Row,
        begin: &Row,
        ram_start: PhysicalAddr,
        ram_bytes: &[u8],
        ram_origins: &[RamByteOrigin],
        parent: Option<&Loaded>,
    ) -> Result<Option<Loaded>, String> {
        effect_row(row)?;
        require(
            same(begin, row)
                && row.cpu
                && row.address == 0
                && row.bank == 0
                && row.offset == 0
                && row.bytes == 0
                && row.value == 0,
            "D-cache primitive differs from decoded scope",
        )?;
        let event = row
            .dcache_event
            .as_ref()
            .ok_or("D-cache primitive lacks operation")?;
        require(
            event.ordinal() == row.ordinal,
            "D-cache primitive lost original ordinal",
        )?;
        let rs = ((begin.word >> 21) & 31) as usize;
        let rt = ((begin.word >> 16) & 31) as usize;
        let virtual_address = begin.gpr[rs].wrapping_add_signed(i64::from(begin.word as i16));
        require(
            (0xffffffff80000000..0xffffffff80800000).contains(&virtual_address)
                && virtual_address.is_multiple_of(4),
            "D-cache operand outside aligned direct KSEG0 RAM",
        )?;
        let physical = PhysicalAddr(virtual_address as u32 & 0x1fffffff);
        let line_address = PhysicalAddr(physical.0 & !15);
        let slot = ((physical.0 >> 4) & 511) as u16;
        let invalidating = matches!(event, Event::Invalidate { .. });
        let mutation = matches!(event, Event::ResidentWordMutation { .. });
        let writeback = matches!(
            event,
            Event::WritebackBegin { .. } | Event::BackingWrite { .. } | Event::WritebackEnd { .. }
        );
        require(
            !mutation && !writeback || self.writes_enabled,
            "D-cache writes outside explicit profile",
        )?;
        require(
            if writeback {
                begin.word >> 26 == 0x2f && rt == 25
            } else if mutation {
                begin.word >> 26 == 0x2b
            } else if invalidating {
                begin.word >> 26 == 0x2f && rt == 17
            } else {
                begin.word >> 26 == 0x23
            },
            "D-cache primitive attached to unsupported CPU operation",
        )?;
        if let Event::BackingRead {
            ordinal,
            physical_line,
            payload: bytes,
        } = event
        {
            require(
                row.dcache_line.is_none() && *physical_line == line_address,
                "D-cache backing burst differs from operand line",
            )?;
            let offset = physical_line
                .0
                .checked_sub(ram_start.0)
                .ok_or("D-cache read precedes RAM snapshot")? as usize;
            require(
                offset
                    .checked_add(16)
                    .is_some_and(|end| end <= ram_bytes.len())
                    && ram_origins.len() == ram_bytes.len()
                    && ram_bytes[offset..offset + 16] == *bytes,
                "D-cache backing burst differs from actual RAM",
            )?;
            self.fills.insert(
                *ordinal,
                DcacheFillParents {
                    read_ordinal: *ordinal,
                    physical_line: *physical_line,
                    source_bytes: std::array::from_fn(|n| ram_origins[offset + n].clone()),
                },
            );
            self.apply(event.clone())?;
            return Ok(None);
        }
        if let Event::BackingWrite { physical_line, .. } = event {
            require(
                row.dcache_line.is_none() && *physical_line == line_address,
                "writeback RAM burst differs from decoded line",
            )?;
            self.apply(event.clone())?;
            require(
                self.state
                    .as_ref()
                    .unwrap()
                    .latest_writeback()
                    .is_some_and(|r| r.backing_write_ordinal == row.ordinal),
                "writeback lacks actual export receipt",
            )?;
            return Ok(None);
        }
        let snapshot = row
            .dcache_line
            .as_ref()
            .ok_or("D-cache operation lacks full resident snapshot")?;
        let bytes: [u8; 16] = std::array::from_fn(|n| snapshot.words[n / 4].to_be_bytes()[n % 4]);
        let prior_dirty = *self.dirty.get(&slot).unwrap_or(&0);
        let expected_dirty = if mutation {
            prior_dirty | (15 << (physical.0 & 15))
        } else {
            prior_dirty
        };
        require(
            snapshot.slot == slot
                && snapshot.index == (line_address.0 & 0xff0) as u16
                && snapshot.dirty == expected_dirty
                && snapshot.tag == ((line_address.0 & !4095) | u32::from(!invalidating)),
            "D-cache snapshot differs from bounded clean identity resident",
        )?;
        match event {
            Event::Fill {
                slot: actual_slot,
                physical_line,
                payload,
                ..
            } => {
                require(
                    *actual_slot == slot && *physical_line == line_address && *payload == bytes,
                    "D-cache fill differs from actual snapshot",
                )?;
            }
            Event::CachedWordRead {
                pc,
                effective_virtual,
                physical: actual_physical,
                slot: actual_slot,
                ..
            } => {
                require(
                    pc.0 == begin.pc
                        && effective_virtual.0 == virtual_address
                        && *actual_physical == physical
                        && *actual_slot == slot,
                    "cached Word read differs from decoded LW",
                )?;
                require(
                    self.state.as_ref().unwrap().resident_snapshot(slot)
                        == Some((line_address, bytes)),
                    "cached read snapshot lost current resident generation",
                )?;
            }
            Event::Invalidate {
                slot: actual_slot, ..
            } => {
                require(
                    *actual_slot == slot
                        && self.state.as_ref().unwrap().resident_snapshot(slot)
                            == Some((line_address, bytes)),
                    "HitInvalidateD lacks the current matching resident",
                )?;
            }
            Event::ResidentWordMutation {
                slot: actual_slot,
                physical: destination,
                payload: value,
                ..
            } => {
                require(
                    *actual_slot == slot
                        && *destination == physical
                        && *value == (begin.gpr[rt] as u32).to_be_bytes(),
                    "resident mutation differs from decoded cached SW",
                )?;
                let (old_line, mut expected) = self
                    .state
                    .as_ref()
                    .unwrap()
                    .resident_snapshot(slot)
                    .ok_or("cached SW lacks prior resident")?;
                require(
                    old_line == line_address,
                    "cached SW selected wrong resident",
                )?;
                let offset = (physical.0 & 15) as usize;
                expected[offset..offset + 4].copy_from_slice(value);
                require(
                    bytes == expected,
                    "cached SW changed an untouched resident lane",
                )?;
                let copy_parent = parent
                    .map(|loaded| {
                        require(
                            loaded.register == rt && loaded.bits == begin.gpr[rt],
                            "cached SW lost held register ancestry",
                        )?;
                        Ok::<_, String>(CpuRamCopyParent {
                            load_context: loaded.context,
                            read_ordinal: loaded.read,
                            source: loaded.address,
                            source_bytes: loaded.origins.clone(),
                            transform: loaded.transform.clone(),
                        })
                    })
                    .transpose()?;
                self.mutations.push(CpuCachedWordMutation {
                    decoder_context: begin.context,
                    mutation_ordinal: row.ordinal,
                    destination: physical,
                    source_register: rt as u8,
                    register_value: begin.gpr[rt],
                    word: begin.gpr[rt] as u32,
                    copy_parent,
                });
            }
            Event::WritebackBegin {
                slot: actual_slot,
                physical_line,
                ..
            } => {
                require(
                    *actual_slot == slot
                        && *physical_line == line_address
                        && prior_dirty != 0
                        && begin.dcache_cpu_line.as_ref() == Some(snapshot)
                        && self.state.as_ref().unwrap().resident_snapshot(slot)
                            == Some((line_address, bytes)),
                    "writeback begin lost matching dirty resident",
                )?;
            }
            Event::WritebackEnd {
                slot: actual_slot, ..
            } => {
                require(
                    *actual_slot == slot
                        && self.state.as_ref().unwrap().resident_snapshot(slot)
                            == Some((line_address, bytes)),
                    "writeback end changed resident",
                )?;
                self.ending = Some(begin.context);
            }
            _ => return Err("unsupported shared D-cache primitive".into()),
        }
        self.apply(event.clone())?;
        if mutation {
            self.dirty.insert(slot, expected_dirty);
        }
        if matches!(event, Event::Fill { .. } | Event::Invalidate { .. }) {
            self.dirty.insert(slot, 0);
        }
        if !matches!(event, Event::CachedWordRead { .. }) {
            return Ok(None);
        }
        let read = self
            .state
            .as_ref()
            .unwrap()
            .latest_read()
            .ok_or("cached read lacks canonical receipt")?;
        require(
            read.read_ordinal == row.ordinal,
            "cached read selected stale canonical receipt",
        )?;
        let origins = read
            .origins
            .iter()
            .map(|origin| {
                if let DcacheByteOrigin::ResidentWordMutation {
                    mutation_ordinal,
                    byte_index,
                } = origin
                {
                    let mutation = self
                        .mutations
                        .iter()
                        .find(|m| m.mutation_ordinal == *mutation_ordinal)
                        .ok_or("cached read lacks decoded mutation parent")?;
                    require(
                        mutation.destination == physical && *byte_index < 4,
                        "cached mutation byte parent differs from read address",
                    )?;
                    return Ok(SpByteOrigin::CpuCachedMutationLoad {
                        decoder_context: begin.context,
                        read_ordinal: row.ordinal,
                        physical: PhysicalAddr(physical.0 + u32::from(*byte_index)),
                        resident_generation: read.resident_generation,
                        resident_revision: read.resident_revision,
                        mutation_ordinal: *mutation_ordinal,
                        source_offset: *byte_index,
                    });
                }
                let DcacheByteOrigin::BackingFill {
                    backing_read_ordinal,
                    physical: byte_address,
                    ..
                } = origin
                else {
                    return Err("unsupported mutated cached operand ancestry".to_owned());
                };
                let fill = self
                    .fills
                    .get(backing_read_ordinal)
                    .ok_or("cached read lacks RAM fill parents")?;
                let offset = byte_address
                    .0
                    .checked_sub(fill.physical_line.0)
                    .ok_or("cached source precedes fill")? as usize;
                let parent = fill
                    .source_bytes
                    .get(offset)
                    .ok_or("cached source escapes fill")?;
                Ok(SpByteOrigin::CpuCachedRamLoad {
                    decoder_context: begin.context,
                    read_ordinal: row.ordinal,
                    physical: *byte_address,
                    resident_generation: read.resident_generation,
                    resident_revision: read.resident_revision,
                    origin: *origin,
                    parent: parent.clone(),
                })
            })
            .collect::<Result<Vec<_>, String>>()?;
        let value = u32::from_be_bytes(read.payload);
        Ok(Some(Loaded {
            context: begin.context,
            read: row.ordinal,
            register: rt,
            bits: value as i32 as i64 as u64,
            address: physical,
            origins: origins
                .try_into()
                .map_err(|_| "cached load byte cardinality")?,
            transform: None,
        }))
    }
    pub fn finish(self) -> Result<RspDcacheConsumption, String> {
        require(self.ending.is_none(), "source ended before CPU dirty clear")?;
        Ok(RspDcacheConsumption {
            cache: self
                .state
                .ok_or("D-cache state was consumed")?
                .finish(self.digest)?,
            backing_fills: self.fills.into_values().collect(),
            cpu_word_mutations: self.writes_enabled.then_some(self.mutations),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn row(kind: &str, ordinal: u64) -> Row {
        serde_json::from_value(json!({"kind":kind,"ordinal":ordinal,"context":9,
            "pc":0xffffffffa0006000u64,"phase":1,"word":0x8e480000u32,"address":0,
            "bank":0,"offset":0,"bytes":0,"value":0,"cpu":true,"next":0,
            "halted":false,"vector_byte":0,"gpr":[],"rgpr":[]}))
        .unwrap()
    }
    #[test]
    fn cached_negative_word_keeps_unknown_fill_parents_and_full_signed_result() {
        let mut cache = DcacheCompose::new("0".repeat(64));
        let mut begin = row("cpu_begin", 9);
        begin.gpr = vec![0; 32];
        begin.gpr[18] = 0xffffffff80002000;
        let bytes = [0x80, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
        let parents =
            std::array::from_fn::<_, 16, _>(|_| RamByteOrigin::Unknown { cut_ordinal: None });
        let mut burst = row("dcache_primitive", 10);
        burst.dcache_event = Some(Event::BackingRead {
            ordinal: 10,
            physical_line: PhysicalAddr(0x2000),
            payload: bytes,
        });
        assert!(
            cache
                .observe(&burst, &begin, PhysicalAddr(0x2000), &bytes, &parents, None)
                .unwrap()
                .is_none()
        );
        let snapshot = DcacheLine {
            slot: 0,
            tag: 0x2001,
            index: 0,
            dirty: 0,
            words: [0x80000000, 0, 0, 0],
        };
        let mut fill = row("dcache_primitive", 11);
        fill.dcache_line = Some(snapshot.clone());
        fill.dcache_event = Some(Event::Fill {
            ordinal: 11,
            slot: 0,
            physical_line: PhysicalAddr(0x2000),
            payload: bytes,
        });
        cache
            .observe(&fill, &begin, PhysicalAddr(0x2000), &bytes, &parents, None)
            .unwrap();
        let mut read = row("dcache_primitive", 12);
        read.dcache_line = Some(snapshot);
        read.dcache_event = Some(Event::CachedWordRead {
            ordinal: 12,
            pc: crate::program::GuestVirtualAddr(begin.pc),
            effective_virtual: crate::program::GuestVirtualAddr(begin.gpr[18]),
            physical: PhysicalAddr(0x2000),
            slot: 0,
            payload: [0x80, 0, 0, 0],
        });
        let held = cache
            .observe(&read, &begin, PhysicalAddr(0x2000), &bytes, &parents, None)
            .unwrap()
            .unwrap();
        assert_eq!(held.bits, 0xffffffff80000000);
        assert_eq!(held.register, 8);
        assert!(held.origins.iter().all(|origin| matches!(
            origin,
            SpByteOrigin::CpuCachedRamLoad {
                read_ordinal: 12,
                resident_generation: 11,
                resident_revision: 11,
                parent: RamByteOrigin::Unknown { cut_ordinal: None },
                ..
            }
        )));
        read.ordinal = 13;
        if let Some(Event::CachedWordRead { ordinal, .. }) = read.dcache_event.as_mut() {
            *ordinal = 13;
        }
        read.dcache_line.as_mut().unwrap().words[1] = 1;
        assert!(
            cache
                .observe(&read, &begin, PhysicalAddr(0x2000), &bytes, &parents, None)
                .is_err()
        );
    }
}
