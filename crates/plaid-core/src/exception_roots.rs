//! Mode-sensitive R4300 exception-vector roots for the validated bounded scope.
//!
//! This module only selects a numeric executable root from already-classified
//! exception state. It does not prove that an exception is reachable, that the
//! handler bytes have known provenance/lifetime, or that all execution roots
//! have been enumerated.
use crate::program::GuestVirtualAddr;
use serde::{Deserialize, Serialize};

const NORMAL_VECTOR_BASE: u64 = 0xffff_ffff_8000_0000;
const BEV_VECTOR_BASE: u64 = 0xffff_ffff_bfc0_0200;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ExceptionClass {
    /// Ordinary general-vector exception. Reachability is a separate proof.
    General,
    /// A matching TLB entry whose selected translation is invalid.
    TlbInvalid,
    /// A true TLB miss with no matching entry.
    TlbMiss,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum KernelAddressMode {
    Bits32,
    Bits64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ExceptionRootInput {
    pub class: ExceptionClass,
    pub bev: bool,
    pub exl: bool,
    pub kernel_mode: KernelAddressMode,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ExceptionVectorClass {
    General,
    TlbRefill,
    XtlbRefill,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ExceptionRootReceipt {
    pub input: ExceptionRootInput,
    pub vector_class: ExceptionVectorClass,
    pub root: GuestVirtualAddr,
}

/// Resolve the vector selected by the validated general/TLB root rule.
///
/// True TLB misses use the refill/XTLB vectors only while EXL is clear. TLB
/// invalid faults remain general-vector entries even though their exception code
/// is also a TLB load/store code. The returned address is a root candidate only;
/// it carries no reachability, handler-byte provenance, or lifetime certificate.
pub fn resolve_exception_root(input: ExceptionRootInput) -> ExceptionRootReceipt {
    let vector_class = match (input.class, input.exl, input.kernel_mode) {
        (ExceptionClass::TlbMiss, false, KernelAddressMode::Bits32) => {
            ExceptionVectorClass::TlbRefill
        }
        (ExceptionClass::TlbMiss, false, KernelAddressMode::Bits64) => {
            ExceptionVectorClass::XtlbRefill
        }
        (ExceptionClass::General | ExceptionClass::TlbInvalid, _, _)
        | (ExceptionClass::TlbMiss, true, _) => ExceptionVectorClass::General,
    };
    let offset = match vector_class {
        ExceptionVectorClass::TlbRefill => 0x000,
        ExceptionVectorClass::XtlbRefill => 0x080,
        ExceptionVectorClass::General => 0x180,
    };
    let base = if input.bev {
        BEV_VECTOR_BASE
    } else {
        NORMAL_VECTOR_BASE
    };
    ExceptionRootReceipt {
        input,
        vector_class,
        root: GuestVirtualAddr(base + offset),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn expected(bev: bool, offset: u64) -> GuestVirtualAddr {
        GuestVirtualAddr(
            (if bev {
                BEV_VECTOR_BASE
            } else {
                NORMAL_VECTOR_BASE
            }) + offset,
        )
    }

    #[test]
    fn reproduces_validated_28_case_root_matrix() {
        let mut cases = 0;
        for kernel_mode in [KernelAddressMode::Bits32, KernelAddressMode::Bits64] {
            for bev in [false, true] {
                for class in [ExceptionClass::General, ExceptionClass::TlbInvalid] {
                    let receipt = resolve_exception_root(ExceptionRootInput {
                        class,
                        bev,
                        exl: false,
                        kernel_mode,
                    });
                    assert_eq!(receipt.vector_class, ExceptionVectorClass::General);
                    assert_eq!(receipt.root, expected(bev, 0x180));
                    cases += 1;
                }
                for _miss_kind in 0..2 {
                    let receipt = resolve_exception_root(ExceptionRootInput {
                        class: ExceptionClass::TlbMiss,
                        bev,
                        exl: false,
                        kernel_mode,
                    });
                    let (class, offset) = match kernel_mode {
                        KernelAddressMode::Bits32 => (ExceptionVectorClass::TlbRefill, 0x000),
                        KernelAddressMode::Bits64 => (ExceptionVectorClass::XtlbRefill, 0x080),
                    };
                    assert_eq!(receipt.vector_class, class);
                    assert_eq!(receipt.root, expected(bev, offset));
                    cases += 1;
                }
                for exl in [false, true] {
                    let receipt = resolve_exception_root(ExceptionRootInput {
                        class: ExceptionClass::TlbMiss,
                        bev,
                        exl,
                        kernel_mode,
                    });
                    let (class, offset) = if exl {
                        (ExceptionVectorClass::General, 0x180)
                    } else {
                        match kernel_mode {
                            KernelAddressMode::Bits32 => {
                                (ExceptionVectorClass::TlbRefill, 0x000)
                            }
                            KernelAddressMode::Bits64 => {
                                (ExceptionVectorClass::XtlbRefill, 0x080)
                            }
                        }
                    };
                    assert_eq!(receipt.vector_class, class);
                    assert_eq!(receipt.root, expected(bev, offset));
                    cases += 1;
                }
            }
        }

        // Four delay-slot cases from the source experiment do not change vector
        // selection, so replay their root inputs without importing EPC/BD state.
        for bev in [false, true] {
            let receipt = resolve_exception_root(ExceptionRootInput {
                class: ExceptionClass::General,
                bev,
                exl: false,
                kernel_mode: KernelAddressMode::Bits32,
            });
            assert_eq!(receipt.root, expected(bev, 0x180));
            cases += 1;
        }
        for kernel_mode in [KernelAddressMode::Bits32, KernelAddressMode::Bits64] {
            let receipt = resolve_exception_root(ExceptionRootInput {
                class: ExceptionClass::TlbMiss,
                bev: false,
                exl: false,
                kernel_mode,
            });
            assert_eq!(
                receipt.root,
                expected(
                    false,
                    if kernel_mode == KernelAddressMode::Bits64 {
                        0x080
                    } else {
                        0x000
                    },
                )
            );
            cases += 1;
        }
        assert_eq!(cases, 28);
    }

    #[test]
    fn tlb_invalid_cannot_be_relabelled_as_true_miss() {
        let invalid = resolve_exception_root(ExceptionRootInput {
            class: ExceptionClass::TlbInvalid,
            bev: false,
            exl: false,
            kernel_mode: KernelAddressMode::Bits64,
        });
        let miss = resolve_exception_root(ExceptionRootInput {
            class: ExceptionClass::TlbMiss,
            bev: false,
            exl: false,
            kernel_mode: KernelAddressMode::Bits64,
        });
        assert_eq!(invalid.root, expected(false, 0x180));
        assert_eq!(miss.root, expected(false, 0x080));
        assert_ne!(invalid, miss);
    }

    #[test]
    fn nested_true_miss_uses_general_vector() {
        for kernel_mode in [KernelAddressMode::Bits32, KernelAddressMode::Bits64] {
            let receipt = resolve_exception_root(ExceptionRootInput {
                class: ExceptionClass::TlbMiss,
                bev: false,
                exl: true,
                kernel_mode,
            });
            assert_eq!(receipt.vector_class, ExceptionVectorClass::General);
            assert_eq!(receipt.root, expected(false, 0x180));
        }
    }

    #[test]
    fn bev_changes_base_without_collapsing_vector_class() {
        let normal = resolve_exception_root(ExceptionRootInput {
            class: ExceptionClass::TlbMiss,
            bev: false,
            exl: false,
            kernel_mode: KernelAddressMode::Bits64,
        });
        let bev = resolve_exception_root(ExceptionRootInput {
            class: ExceptionClass::TlbMiss,
            bev: true,
            exl: false,
            kernel_mode: KernelAddressMode::Bits64,
        });
        assert_eq!(normal.vector_class, bev.vector_class);
        assert_eq!(normal.root, expected(false, 0x080));
        assert_eq!(bev.root, expected(true, 0x080));
        assert_ne!(normal.root, bev.root);
    }
}
