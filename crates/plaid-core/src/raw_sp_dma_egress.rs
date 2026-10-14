//! Exact reverse-SP-DMA source reads and completed identity-RAM sinks.
//! Captured SP writers are computed/source facts, never physical ROM origins.
use crate::{history, program::*, sp_history::CapturedSpByteWriter};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SpDmaEgressReceipt {
    pub read_ordinal: u64,
    pub write_ordinal: u64,
    pub completion_ordinal: u64,
    pub dram: PhysicalAddr,
    pub bank: u32,
    pub offset: u32,
    pub bytes: u32,
    pub value: u64,
    pub writers: Vec<Option<CapturedSpByteWriter>>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SpDmaEgressReport {
    pub stores: u64,
    pub samples: Vec<SpDmaEgressReceipt>,
    pub ordered_stores_sha256: String,
}

struct Pending {
    context: u64,
    pc: GuestVirtualAddr,
    receipt: SpDmaEgressReceipt,
}

#[derive(Default)]
pub(crate) struct Egress {
    reads: BTreeMap<u64, Pending>,
    scalar: Option<history::Record>,
    stores: u64,
    samples: Vec<SpDmaEgressReceipt>,
    digest: Sha256,
}

impl Egress {
    pub(crate) fn observe(&mut self, row: &history::Record) {
        // The sink callback follows the actual normalized RAM wrapper, with
        // lower storage effects preceding that wrapper on the same clock.
        self.scalar = match row {
            history::Record::Scalar {
                ordinal,
                context,
                pc,
                write,
                address,
                aligned_address,
                bytes,
                device,
                value,
            } => Some(history::Record::Scalar {
                ordinal: *ordinal,
                context: *context,
                pc: *pc,
                write: *write,
                address: *address,
                aligned_address: *aligned_address,
                bytes: *bytes,
                device: *device,
                value: *value,
            }),
            _ => None,
        };
    }

    #[allow(clippy::too_many_arguments)]
    pub(crate) fn read(
        &mut self,
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        dram: PhysicalAddr,
        bank: u32,
        offset: u32,
        bytes: u32,
        value: u64,
        writers: Vec<Option<CapturedSpByteWriter>>,
    ) -> Result<(), String> {
        if self.reads.len() >= 2
            || self.reads.contains_key(&ordinal)
            || bank > 1
            || !matches!((bank, bytes), (0, 4) | (1, 8))
            || !offset.is_multiple_of(bytes)
            || offset.checked_add(bytes).is_none_or(|end| end > 4096)
            || !dram.0.is_multiple_of(bytes)
            || dram.0.checked_add(bytes).is_none_or(|end| end > 8_388_608)
            || (bytes == 4 && value > u32::MAX as u64)
            || writers.len() != bytes as usize
        {
            return Err("invalid reverse-SP-DMA source read".into());
        }
        self.reads.insert(
            ordinal,
            Pending {
                context,
                pc,
                receipt: SpDmaEgressReceipt {
                    read_ordinal: ordinal,
                    write_ordinal: 0,
                    completion_ordinal: 0,
                    dram,
                    bank,
                    offset,
                    bytes,
                    value,
                    writers,
                },
            },
        );
        Ok(())
    }

    pub(crate) fn store(
        &mut self,
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        read_ordinal: u64,
        write_ordinal: u64,
    ) -> Result<SpDmaEgressReceipt, String> {
        let mut read = self
            .reads
            .remove(&read_ordinal)
            .ok_or("reverse-SP-DMA sink lacks unique source read")?;
        let r = &mut read.receipt;
        match self.scalar.take() {
            Some(history::Record::Scalar {
                ordinal: writer,
                context: writer_context,
                pc: writer_pc,
                write: true,
                device: 4,
                address,
                aligned_address,
                bytes,
                value,
                ..
            }) if writer == write_ordinal
                && writer.checked_add(1) == Some(ordinal)
                && read_ordinal < writer
                && context == read.context
                && pc == read.pc
                && context == writer_context
                && pc == writer_pc
                && (address, aligned_address, bytes, value)
                    == (r.dram, r.dram, r.bytes, r.value) => {}
            _ => return Err("reverse-SP-DMA completion lacks exact immediate RAM writer".into()),
        }
        r.write_ordinal = write_ordinal;
        r.completion_ordinal = ordinal;
        self.digest
            .update(serde_json::to_vec(r).map_err(|e| e.to_string())?);
        self.digest.update(b"\n");
        self.stores += 1;
        if self.samples.len() < 64 {
            self.samples.push(r.clone());
        }
        Ok(r.clone())
    }

    pub(crate) fn finish(self) -> Result<SpDmaEgressReport, String> {
        if !self.reads.is_empty() {
            return Err("unfinished reverse-SP-DMA source reads".into());
        }
        Ok(SpDmaEgressReport {
            stores: self.stores,
            samples: self.samples,
            ordered_stores_sha256: format!("{:x}", self.digest.finalize()),
        })
    }
}
