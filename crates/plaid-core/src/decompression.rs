//! Fail-closed replay for bounded dictionary/LZ-style decompression receipts.
//!
//! This module verifies causal consistency inside an already source-bound transform
//! receipt. It does not discover guest decompressors, certify invocation freshness,
//! prove a complete mutation/effect census, or establish executable lifetime.
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{collections::BTreeMap, num::NonZeroU64};

pub const FORMAT: &str = "plaid-decompression-receipt-v1";
pub const MAX_SOURCE_BYTES: usize = 8 * 1024 * 1024;
pub const MAX_OUTPUT_BYTES: usize = 8 * 1024 * 1024;
pub const MAX_OPERATIONS: usize = 1_000_000;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct StorageGeneration {
    pub namespace: NonZeroU64,
    pub ordinal: NonZeroU64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TransformInvocationId {
    pub namespace: NonZeroU64,
    pub ordinal: NonZeroU64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[serde(tag = "origin", rename_all = "snake_case", deny_unknown_fields)]
pub enum ByteGeneration {
    Storage {
        generation: StorageGeneration,
    },
    Transform {
        invocation: TransformInvocationId,
        sequence: NonZeroU64,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ByteSpan {
    pub start: u32,
    pub len: u32,
}

impl ByteSpan {
    fn checked_end(self) -> Option<u32> {
        self.start.checked_add(self.len)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct InitialByte {
    pub address: u32,
    pub value: u8,
    pub generation: ByteGeneration,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum DecompressionOp {
    Literal { source_offset: u32 },
    Backreference { distance: u32, length: u32 },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ByteWriteReceipt {
    pub sequence: NonZeroU64,
    pub op_index: u32,
    pub destination: u32,
    pub value: u8,
    pub parent_address: u32,
    pub parent_generation: ByteGeneration,
    pub output_generation: ByteGeneration,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DecompressionReceipt {
    pub format: String,
    /// Digest of the independently authenticated upstream history supplying the
    /// starting storage generations. This verifier carries the binding but does
    /// not authenticate that upstream history itself.
    pub source_history_sha256: [u8; 32],
    pub invocation: TransformInvocationId,
    pub source: ByteSpan,
    pub output: ByteSpan,
    /// Exact starting bytes for the declared source span, in ascending address
    /// order. Output writes may later replace these cells when spans overlap.
    pub initial_source: Vec<InitialByte>,
    /// Separately authenticated transform semantics are represented here as the
    /// bounded literal/backreference operation stream.
    pub operations: Vec<DecompressionOp>,
    pub operation_stream_sha256: [u8; 32],
    /// One completed destination effect per produced byte, in execution order.
    pub writes: Vec<ByteWriteReceipt>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub struct VerifiedOutputByte {
    pub address: u32,
    pub value: u8,
    pub generation: ByteGeneration,
    pub parent_address: u32,
    pub parent_generation: ByteGeneration,
}

/// Result of causal replay. This object intentionally cannot be deserialized or
/// constructed outside this module; downstream proof code must start from a
/// successfully replayed receipt rather than trusting a serialized "verified"
/// label.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct VerifiedDecompression {
    invocation: TransformInvocationId,
    source_history_sha256: [u8; 32],
    operation_stream_sha256: [u8; 32],
    receipt_sha256: [u8; 32],
    output_sha256: [u8; 32],
    outputs: Vec<VerifiedOutputByte>,
}

impl VerifiedDecompression {
    pub fn invocation(&self) -> TransformInvocationId {
        self.invocation
    }

    pub fn source_history_sha256(&self) -> [u8; 32] {
        self.source_history_sha256
    }

    pub fn operation_stream_sha256(&self) -> [u8; 32] {
        self.operation_stream_sha256
    }

    pub fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    pub fn output_sha256(&self) -> [u8; 32] {
        self.output_sha256
    }

    pub fn outputs(&self) -> &[VerifiedOutputByte] {
        &self.outputs
    }

    /// Freshness belongs to an authenticated invocation census, which this
    /// bounded replay deliberately does not claim to provide.
    pub fn invocation_freshness_certified(&self) -> bool {
        false
    }

    /// The supplied operation stream is hash-bound and semantically replayed,
    /// but its completeness relative to all guest execution remains external.
    pub fn operation_census_certified(&self) -> bool {
        false
    }

    /// Exact supplied writes are replayed; exhaustive mutation sensing is a
    /// separate whole-system obligation.
    pub fn effect_census_certified(&self) -> bool {
        false
    }

    pub fn executable_lifetime_certified(&self) -> bool {
        false
    }

    pub fn native_complete(&self) -> bool {
        false
    }
}

#[derive(Debug, Clone, Copy)]
struct Cell {
    value: u8,
    generation: ByteGeneration,
}

fn sha256(bytes: &[u8]) -> [u8; 32] {
    Sha256::digest(bytes).into()
}

fn json_sha256<T: Serialize + ?Sized>(value: &T) -> Result<[u8; 32], String> {
    serde_json::to_vec(value)
        .map(|bytes| sha256(&bytes))
        .map_err(|error| format!("cannot canonicalize decompression receipt: {error}"))
}

fn usize_len(len: u32, limit: usize, label: &str) -> Result<usize, String> {
    let len = usize::try_from(len).map_err(|_| format!("{label} length does not fit usize"))?;
    if len == 0 || len > limit {
        return Err(format!("{label} length outside supported bounds"));
    }
    Ok(len)
}

fn output_generation(invocation: TransformInvocationId, sequence: NonZeroU64) -> ByteGeneration {
    ByteGeneration::Transform {
        invocation,
        sequence,
    }
}

#[allow(clippy::too_many_arguments)]
fn apply_write(
    receipt: &DecompressionReceipt,
    memory: &mut BTreeMap<u32, Cell>,
    verified: &mut Vec<VerifiedOutputByte>,
    cursor: usize,
    op_index: u32,
    parent_address: u32,
) -> Result<(), String> {
    let write = receipt
        .writes
        .get(cursor)
        .ok_or_else(|| "decompression history ended before expected write".to_string())?;
    let sequence_value = u64::try_from(cursor)
        .ok()
        .and_then(|value| value.checked_add(1))
        .and_then(NonZeroU64::new)
        .ok_or_else(|| "decompression write sequence overflow".to_string())?;
    let destination_offset = u32::try_from(cursor)
        .map_err(|_| "decompression destination offset overflow".to_string())?;
    let destination = receipt
        .output
        .start
        .checked_add(destination_offset)
        .ok_or_else(|| "decompression destination overflow".to_string())?;
    let parent = memory
        .get(&parent_address)
        .copied()
        .ok_or_else(|| "decompression parent generation is not present".to_string())?;
    let generation = output_generation(receipt.invocation, sequence_value);

    if write.sequence != sequence_value
        || write.op_index != op_index
        || write.destination != destination
        || write.value != parent.value
        || write.parent_address != parent_address
        || write.parent_generation != parent.generation
        || write.output_generation != generation
    {
        return Err("decompression write does not match causal replay".into());
    }

    memory.insert(
        destination,
        Cell {
            value: write.value,
            generation,
        },
    );
    verified.push(VerifiedOutputByte {
        address: destination,
        value: write.value,
        generation,
        parent_address,
        parent_generation: parent.generation,
    });
    Ok(())
}

/// Replays a complete bounded literal/backreference receipt.
///
/// Hash equality is used only to bind the supplied operation stream and receipt;
/// all provenance decisions come from ordered generation-bearing reads/writes.
pub fn verify(receipt: &DecompressionReceipt) -> Result<VerifiedDecompression, String> {
    if receipt.format != FORMAT {
        return Err("unsupported decompression receipt format".into());
    }
    let source_len = usize_len(receipt.source.len, MAX_SOURCE_BYTES, "source")?;
    let output_len = usize_len(receipt.output.len, MAX_OUTPUT_BYTES, "output")?;
    if receipt.source.checked_end().is_none() || receipt.output.checked_end().is_none() {
        return Err("decompression span overflows address space".into());
    }
    if receipt.operations.is_empty() || receipt.operations.len() > MAX_OPERATIONS {
        return Err("decompression operation count outside supported bounds".into());
    }
    if receipt.initial_source.len() != source_len {
        return Err("decompression source snapshot is incomplete".into());
    }
    if receipt.writes.len() != output_len {
        return Err("decompression write history is incomplete".into());
    }
    if json_sha256(&receipt.operations)? != receipt.operation_stream_sha256 {
        return Err("decompression operation stream digest mismatch".into());
    }

    let mut memory = BTreeMap::new();
    for (index, byte) in receipt.initial_source.iter().enumerate() {
        let offset = u32::try_from(index)
            .map_err(|_| "decompression source snapshot offset overflow".to_string())?;
        let expected = receipt
            .source
            .start
            .checked_add(offset)
            .ok_or_else(|| "decompression source address overflow".to_string())?;
        if byte.address != expected {
            return Err("decompression source snapshot is not exact and ordered".into());
        }
        if matches!(
            byte.generation,
            ByteGeneration::Transform { invocation, .. } if invocation == receipt.invocation
        ) {
            return Err("current invocation generation already exists in source snapshot".into());
        }
        if memory
            .insert(
                byte.address,
                Cell {
                    value: byte.value,
                    generation: byte.generation,
                },
            )
            .is_some()
        {
            return Err("duplicate decompression source address".into());
        }
    }

    let mut cursor = 0usize;
    let mut verified = Vec::with_capacity(output_len);
    for (op_position, operation) in receipt.operations.iter().enumerate() {
        let op_index = u32::try_from(op_position)
            .map_err(|_| "decompression operation index overflow".to_string())?;
        match *operation {
            DecompressionOp::Literal { source_offset } => {
                if source_offset >= receipt.source.len {
                    return Err("decompression literal reads outside declared source".into());
                }
                let parent_address = receipt
                    .source
                    .start
                    .checked_add(source_offset)
                    .ok_or_else(|| "decompression literal source overflow".to_string())?;
                apply_write(
                    receipt,
                    &mut memory,
                    &mut verified,
                    cursor,
                    op_index,
                    parent_address,
                )?;
                cursor = cursor
                    .checked_add(1)
                    .ok_or_else(|| "decompression write cursor overflow".to_string())?;
            }
            DecompressionOp::Backreference { distance, length } => {
                if distance == 0 || length == 0 {
                    return Err("decompression backreference must be nonempty".into());
                }
                let produced = u32::try_from(cursor)
                    .map_err(|_| "decompression produced-byte count overflow".to_string())?;
                if distance > produced {
                    return Err("decompression backreference precedes available output".into());
                }
                for _ in 0..length {
                    let destination_offset = u32::try_from(cursor)
                        .map_err(|_| "decompression destination offset overflow".to_string())?;
                    let destination = receipt
                        .output
                        .start
                        .checked_add(destination_offset)
                        .ok_or_else(|| "decompression destination overflow".to_string())?;
                    let parent_address = destination.checked_sub(distance).ok_or_else(|| {
                        "decompression backreference source underflow".to_string()
                    })?;
                    if parent_address < receipt.output.start {
                        return Err("decompression backreference escapes prior output".into());
                    }
                    apply_write(
                        receipt,
                        &mut memory,
                        &mut verified,
                        cursor,
                        op_index,
                        parent_address,
                    )?;
                    cursor = cursor
                        .checked_add(1)
                        .ok_or_else(|| "decompression write cursor overflow".to_string())?;
                    if cursor > output_len {
                        return Err("decompression operations exceed declared output".into());
                    }
                }
            }
        }
    }
    if cursor != output_len {
        return Err("decompression operations do not cover declared output".into());
    }

    let output_values: Vec<u8> = verified.iter().map(|byte| byte.value).collect();
    Ok(VerifiedDecompression {
        invocation: receipt.invocation,
        source_history_sha256: receipt.source_history_sha256,
        operation_stream_sha256: receipt.operation_stream_sha256,
        receipt_sha256: json_sha256(receipt)?,
        output_sha256: sha256(&output_values),
        outputs: verified,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn nz(value: u64) -> NonZeroU64 {
        NonZeroU64::new(value).expect("test IDs are nonzero")
    }

    fn storage(ordinal: u64) -> ByteGeneration {
        ByteGeneration::Storage {
            generation: StorageGeneration {
                namespace: nz(1),
                ordinal: nz(ordinal),
            },
        }
    }

    fn invocation(ordinal: u64) -> TransformInvocationId {
        TransformInvocationId {
            namespace: nz(9),
            ordinal: nz(ordinal),
        }
    }

    fn transformed(id: TransformInvocationId, sequence: u64) -> ByteGeneration {
        ByteGeneration::Transform {
            invocation: id,
            sequence: nz(sequence),
        }
    }

    fn op_digest(operations: &[DecompressionOp]) -> [u8; 32] {
        json_sha256(operations).expect("test operation serialization")
    }

    fn overlapping_receipt() -> DecompressionReceipt {
        let id = invocation(1);
        let operations = vec![
            DecompressionOp::Literal { source_offset: 0 },
            DecompressionOp::Backreference {
                distance: 1,
                length: 3,
            },
        ];
        DecompressionReceipt {
            format: FORMAT.into(),
            source_history_sha256: [0x51; 32],
            invocation: id,
            source: ByteSpan {
                start: 0x1000,
                len: 1,
            },
            output: ByteSpan {
                start: 0x2000,
                len: 4,
            },
            initial_source: vec![InitialByte {
                address: 0x1000,
                value: 0x41,
                generation: storage(1),
            }],
            operation_stream_sha256: op_digest(&operations),
            operations,
            writes: vec![
                ByteWriteReceipt {
                    sequence: nz(1),
                    op_index: 0,
                    destination: 0x2000,
                    value: 0x41,
                    parent_address: 0x1000,
                    parent_generation: storage(1),
                    output_generation: transformed(id, 1),
                },
                ByteWriteReceipt {
                    sequence: nz(2),
                    op_index: 1,
                    destination: 0x2001,
                    value: 0x41,
                    parent_address: 0x2000,
                    parent_generation: transformed(id, 1),
                    output_generation: transformed(id, 2),
                },
                ByteWriteReceipt {
                    sequence: nz(3),
                    op_index: 1,
                    destination: 0x2002,
                    value: 0x41,
                    parent_address: 0x2001,
                    parent_generation: transformed(id, 2),
                    output_generation: transformed(id, 3),
                },
                ByteWriteReceipt {
                    sequence: nz(4),
                    op_index: 1,
                    destination: 0x2003,
                    value: 0x41,
                    parent_address: 0x2002,
                    parent_generation: transformed(id, 3),
                    output_generation: transformed(id, 4),
                },
            ],
        }
    }

    #[test]
    fn overlapping_backreference_tracks_self_feeding_generations() {
        let receipt = overlapping_receipt();
        let verified = verify(&receipt).expect("valid overlapping receipt");
        assert_eq!(verified.outputs().len(), 4);
        assert_eq!(
            verified.outputs()[2].parent_generation,
            transformed(invocation(1), 2)
        );
        assert!(!verified.invocation_freshness_certified());
        assert!(!verified.operation_census_certified());
        assert!(!verified.effect_census_certified());
        assert!(!verified.executable_lifetime_certified());
        assert!(!verified.native_complete());
    }

    #[test]
    fn equal_payload_flattening_cannot_replace_backreference_ancestry() {
        let mut forged = overlapping_receipt();
        forged.writes[2].parent_address = 0x1000;
        forged.writes[2].parent_generation = storage(1);
        assert!(verify(&forged).is_err());
    }

    #[test]
    fn in_place_same_value_write_replaces_future_literal_generation() {
        let id = invocation(2);
        let operations = vec![
            DecompressionOp::Literal { source_offset: 0 },
            DecompressionOp::Literal { source_offset: 1 },
        ];
        let receipt = DecompressionReceipt {
            format: FORMAT.into(),
            source_history_sha256: [0x52; 32],
            invocation: id,
            source: ByteSpan {
                start: 0x1000,
                len: 2,
            },
            output: ByteSpan {
                start: 0x1001,
                len: 2,
            },
            initial_source: vec![
                InitialByte {
                    address: 0x1000,
                    value: 7,
                    generation: storage(1),
                },
                InitialByte {
                    address: 0x1001,
                    value: 7,
                    generation: storage(2),
                },
            ],
            operation_stream_sha256: op_digest(&operations),
            operations,
            writes: vec![
                ByteWriteReceipt {
                    sequence: nz(1),
                    op_index: 0,
                    destination: 0x1001,
                    value: 7,
                    parent_address: 0x1000,
                    parent_generation: storage(1),
                    output_generation: transformed(id, 1),
                },
                ByteWriteReceipt {
                    sequence: nz(2),
                    op_index: 1,
                    destination: 0x1002,
                    value: 7,
                    parent_address: 0x1001,
                    parent_generation: transformed(id, 1),
                    output_generation: transformed(id, 2),
                },
            ],
        };
        verify(&receipt).expect("read-after-equal-write uses new generation");

        let mut forged = receipt;
        forged.writes[1].parent_generation = storage(2);
        assert!(verify(&forged).is_err());
    }

    #[test]
    fn distinct_same_value_invocations_remain_distinct_generations() {
        let first = overlapping_receipt();
        let mut second = first.clone();
        second.invocation = invocation(2);
        for (index, write) in second.writes.iter_mut().enumerate() {
            let sequence = u64::try_from(index + 1).expect("small test index");
            write.output_generation = transformed(second.invocation, sequence);
            if index > 0 {
                write.parent_generation = transformed(second.invocation, sequence - 1);
            }
        }
        let first = verify(&first).expect("first invocation");
        let second = verify(&second).expect("second invocation");
        assert_ne!(
            first.outputs()[0].generation,
            second.outputs()[0].generation
        );
        assert_eq!(first.output_sha256(), second.output_sha256());
    }

    #[test]
    fn deletion_reordering_and_equal_value_generation_forgery_fail_closed() {
        let receipt = overlapping_receipt();

        let mut deleted = receipt.clone();
        deleted.writes.remove(1);
        assert!(verify(&deleted).is_err());

        let mut reordered = receipt.clone();
        reordered.writes.swap(1, 2);
        assert!(verify(&reordered).is_err());

        let mut wrong_generation = receipt;
        wrong_generation.writes[1].parent_generation = storage(99);
        assert!(verify(&wrong_generation).is_err());
    }

    #[test]
    fn malformed_operation_boundaries_are_rejected() {
        let mut literal_oob = overlapping_receipt();
        literal_oob.operations[0] = DecompressionOp::Literal { source_offset: 1 };
        literal_oob.operation_stream_sha256 = op_digest(&literal_oob.operations);
        assert!(verify(&literal_oob).is_err());

        let mut empty_backref = overlapping_receipt();
        empty_backref.operations[1] = DecompressionOp::Backreference {
            distance: 1,
            length: 0,
        };
        empty_backref.operation_stream_sha256 = op_digest(&empty_backref.operations);
        assert!(verify(&empty_backref).is_err());
    }

    #[test]
    fn operation_digest_and_strict_types_bind_input_schema() {
        let mut changed = overlapping_receipt();
        changed.operations[1] = DecompressionOp::Backreference {
            distance: 1,
            length: 2,
        };
        assert!(verify(&changed).is_err());

        let json = r#"{
            "format":"plaid-decompression-receipt-v1",
            "source_history_sha256":[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
            "invocation":{"namespace":true,"ordinal":1},
            "source":{"start":4096,"len":1},
            "output":{"start":8192,"len":1},
            "initial_source":[],
            "operations":[],
            "operation_stream_sha256":[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
            "writes":[]
        }"#;
        assert!(serde_json::from_str::<DecompressionReceipt>(json).is_err());
    }

    #[test]
    fn current_invocation_cannot_be_smuggled_in_as_starting_generation() {
        let mut receipt = overlapping_receipt();
        receipt.initial_source[0].generation = transformed(receipt.invocation, 77);
        receipt.writes[0].parent_generation = transformed(receipt.invocation, 77);
        assert!(verify(&receipt).is_err());
    }
}
