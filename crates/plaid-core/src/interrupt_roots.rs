//! Bounded maskable VR4300 interrupt gating for executable-root discovery.
//!
//! This module evaluates one already-authenticated architectural boundary state.
//! A successful receipt is only a root candidate. It does not prove which device
//! or guest operation produced a pending bit, when an asynchronous producer became
//! visible, that the handler bytes have known provenance/lifetime, or that the
//! interrupt-root universe is complete.

use crate::exception_roots::{
    ExceptionClass, ExceptionRootInput, ExceptionVectorClass, KernelAddressMode,
    resolve_exception_root,
};
use crate::program::GuestVirtualAddr;
use serde::{Deserialize, Serialize};

/// Complete normalized state needed by the validated maskable-interrupt gate.
///
/// `pending` is Cause.IP and `mask` is Status.IM, each normalized to the eight
/// architectural interrupt bits. The values do not carry producer provenance.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MaskableInterruptRootInput {
    pub pending: u8,
    pub mask: u8,
    pub ie: bool,
    pub exl: bool,
    pub erl: bool,
    pub bev: bool,
}

/// Receipt for one architectural boundary at which the maskable interrupt gate
/// is satisfied.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MaskableInterruptRootReceipt {
    pub input: MaskableInterruptRootInput,
    /// Exact Cause.IP bits that are both pending and enabled by Status.IM.
    pub matched_pending: u8,
    /// BEV-sensitive general exception vector selected for this admitted state.
    pub root: GuestVirtualAddr,
}

/// Evaluate the validated maskable VR4300 interrupt gate for one boundary state.
///
/// The bounded reference contract admits an interrupt only when at least one
/// pending bit is enabled and `IE=1, EXL=0, ERL=0`. An admitted state always uses
/// the ordinary BEV-sensitive general vector (`base + 0x180`). Returning `None`
/// means only that this supplied state is suppressed; it is not a scope-wide
/// proof that the interrupt root is unreachable.
pub fn resolve_maskable_interrupt_root(
    input: MaskableInterruptRootInput,
) -> Option<MaskableInterruptRootReceipt> {
    let matched_pending = input.pending & input.mask;
    if matched_pending == 0 || !input.ie || input.exl || input.erl {
        return None;
    }

    // Kernel address mode is irrelevant for the general vector. Reuse the
    // canonical exception-root selector rather than duplicating vector constants.
    let general = resolve_exception_root(ExceptionRootInput {
        class: ExceptionClass::General,
        bev: input.bev,
        exl: false,
        kernel_mode: KernelAddressMode::Bits32,
    });
    debug_assert_eq!(general.vector_class, ExceptionVectorClass::General);

    Some(MaskableInterruptRootReceipt {
        input,
        matched_pending,
        root: general.root,
    })
}

/// Reconstruct every receipt field from an independently authenticated boundary.
/// This rechecks the gate state, not its producer chronology or handler lifetime.
pub fn verify_maskable_interrupt_root_receipt(
    receipt: &MaskableInterruptRootReceipt,
    input: MaskableInterruptRootInput,
) -> Result<(), String> {
    if resolve_maskable_interrupt_root(input).as_ref() == Some(receipt) {
        Ok(())
    } else {
        Err("interrupt root receipt disagrees with boundary state".into())
    }
}
