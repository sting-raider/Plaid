use plaid_core::decompression::{
    ByteGeneration, ByteSpan, ByteWriteReceipt, DecompressionOp, DecompressionReceipt, InitialByte,
    StorageGeneration, TransformInvocationId, verify,
};
use sha2::{Digest, Sha256};
use std::num::NonZeroU64;

fn nz(value: u64) -> NonZeroU64 {
    NonZeroU64::new(value).expect("test identifiers are nonzero")
}

#[test]
fn public_receipt_replay_requires_exact_parent_generation() {
    let invocation = TransformInvocationId {
        namespace: nz(7),
        ordinal: nz(1),
    };
    let source_generation = ByteGeneration::Storage {
        generation: StorageGeneration {
            namespace: nz(3),
            ordinal: nz(9),
        },
    };
    let output_generation = ByteGeneration::Transform {
        invocation,
        sequence: nz(1),
    };
    let operations = vec![DecompressionOp::Literal { source_offset: 0 }];
    let operation_stream_sha256 =
        Sha256::digest(serde_json::to_vec(&operations).expect("test operation serialization"))
            .into();

    let receipt = DecompressionReceipt {
        format: plaid_core::decompression::FORMAT.into(),
        source_history_sha256: [0x31; 32],
        invocation,
        source: ByteSpan {
            start: 0x1000,
            len: 1,
        },
        output: ByteSpan {
            start: 0x2000,
            len: 1,
        },
        initial_source: vec![InitialByte {
            address: 0x1000,
            value: 0x5a,
            generation: source_generation,
        }],
        operations,
        operation_stream_sha256,
        writes: vec![ByteWriteReceipt {
            sequence: nz(1),
            op_index: 0,
            destination: 0x2000,
            value: 0x5a,
            parent_address: 0x1000,
            parent_generation: source_generation,
            output_generation,
        }],
    };

    let verified = verify(&receipt).expect("exact generation-bearing receipt should replay");
    assert_eq!(verified.outputs()[0].generation, output_generation);
    assert!(!verified.invocation_freshness_certified());
    assert!(!verified.operation_census_certified());
    assert!(!verified.effect_census_certified());
    assert!(!verified.native_complete());

    let mut forged = receipt;
    forged.writes[0].parent_generation = ByteGeneration::Storage {
        generation: StorageGeneration {
            namespace: nz(3),
            ordinal: nz(10),
        },
    };
    assert!(verify(&forged).is_err());
}
