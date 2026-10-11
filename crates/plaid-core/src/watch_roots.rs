//! Fail-closed VR4300 Watch exception reachability assessment for a bounded scope.
//!
//! This module does not discover or authenticate CP0 writes, physical translations,
//! BEV/EXL chronology, exception priority, or handler-byte provenance. Callers must
//! supply those facts from independently trustworthy histories. In particular,
//! equal WatchLo values do not authorize coalescing distinct register generations.

use crate::{
    exception_roots::{
        ExceptionClass, ExceptionRootInput, KernelAddressMode, resolve_exception_root,
    },
    program::GuestVirtualAddr,
};
use serde::{Deserialize, Serialize};

pub const WATCH_EXCEPTION_CODE: u8 = 23;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum WatchAccessKind {
    Load,
    Store,
    Cache,
}

/// One already-authenticated WatchLo generation.
///
/// `physical_block` is the decoded WatchLo PAddr0 match block and must be aligned
/// to eight bytes. `generation` is an operation identity supplied by a separate
/// ordered register-history proof; it is intentionally not derived from value
/// equality here.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct WatchConfig {
    pub generation: u64,
    pub physical_block: u32,
    pub trap_load: bool,
    pub trap_store: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum WatchState {
    /// Reset or otherwise unauthenticated state. The VR4300 reset value is not
    /// assumed to be a disabled zero value.
    Unknown,
    Known(WatchConfig),
}

/// Context for one reachable memory operation.
///
/// Missing values are preserved explicitly instead of guessed. `physical_address`
/// must come from a trustworthy translation/backing proof; a virtual address is not
/// an acceptable substitute. `higher_priority_exception` must come from an
/// independently trustworthy exception-classification history; `Some(false)` is
/// required before this helper can emit an immediate Watch root.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct WatchAccessInput {
    pub state: WatchState,
    pub kind: WatchAccessKind,
    pub physical_address: Option<u32>,
    pub higher_priority_exception: Option<bool>,
    pub exl: Option<bool>,
    pub bev: Option<bool>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum WatchNoImmediateReason {
    CacheExcluded,
    AccessDisabled,
    PhysicalBlockMismatch,
    HigherPriorityException,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum WatchUnresolvedReason {
    UnknownWatchState,
    MissingPhysicalAddress,
    UnknownExceptionPriority,
    UnknownExl,
    PostponedWhileExl,
    UnknownBev,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct WatchRootReceipt {
    pub watch_generation: u64,
    pub exception_code: u8,
    pub physical_block: u32,
    pub physical_address: u32,
    pub root: GuestVirtualAddr,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum WatchAssessment {
    ImmediateWatch(WatchRootReceipt),
    NoImmediateWatch {
        reason: WatchNoImmediateReason,
        watch_generation: Option<u64>,
    },
    Unresolved {
        reason: WatchUnresolvedReason,
        watch_generation: Option<u64>,
    },
}

fn validate_state(state: WatchState) -> Result<Option<WatchConfig>, String> {
    match state {
        WatchState::Unknown => Ok(None),
        WatchState::Known(config) => {
            if config.generation == 0 {
                return Err("known Watch configuration requires a nonzero generation".into());
            }
            if !config.physical_block.is_multiple_of(8) {
                return Err("Watch physical block must be eight-byte aligned".into());
            }
            Ok(Some(config))
        }
    }
}

/// Assess only the validated immediate Watch/root subset.
///
/// A matching enabled load/store with independently established absence of a
/// higher-priority exception, known EXL=false and known BEV yields an immediate
/// Watch receipt at the common general exception vector. CACHE is never a Watch
/// trigger. Matching accesses while EXL is set remain unresolved because the
/// exact postponed-entry timing is outside this validated scope.
///
/// This function is not a closure certificate. It neither proves that its inputs
/// are complete nor that the selected handler bytes have known provenance/lifetime.
pub fn assess_watch_access(input: WatchAccessInput) -> Result<WatchAssessment, String> {
    let config = validate_state(input.state)?;

    if input.kind == WatchAccessKind::Cache {
        return Ok(WatchAssessment::NoImmediateWatch {
            reason: WatchNoImmediateReason::CacheExcluded,
            watch_generation: config.map(|config| config.generation),
        });
    }

    let Some(config) = config else {
        return Ok(WatchAssessment::Unresolved {
            reason: WatchUnresolvedReason::UnknownWatchState,
            watch_generation: None,
        });
    };

    let enabled = match input.kind {
        WatchAccessKind::Load => config.trap_load,
        WatchAccessKind::Store => config.trap_store,
        WatchAccessKind::Cache => unreachable!("CACHE returned above"),
    };
    if !enabled {
        return Ok(WatchAssessment::NoImmediateWatch {
            reason: WatchNoImmediateReason::AccessDisabled,
            watch_generation: Some(config.generation),
        });
    }

    let Some(physical_address) = input.physical_address else {
        return Ok(WatchAssessment::Unresolved {
            reason: WatchUnresolvedReason::MissingPhysicalAddress,
            watch_generation: Some(config.generation),
        });
    };
    if physical_address & !7 != config.physical_block {
        return Ok(WatchAssessment::NoImmediateWatch {
            reason: WatchNoImmediateReason::PhysicalBlockMismatch,
            watch_generation: Some(config.generation),
        });
    }

    match input.higher_priority_exception {
        None => {
            return Ok(WatchAssessment::Unresolved {
                reason: WatchUnresolvedReason::UnknownExceptionPriority,
                watch_generation: Some(config.generation),
            });
        }
        Some(true) => {
            return Ok(WatchAssessment::NoImmediateWatch {
                reason: WatchNoImmediateReason::HigherPriorityException,
                watch_generation: Some(config.generation),
            });
        }
        Some(false) => {}
    }

    match input.exl {
        None => {
            return Ok(WatchAssessment::Unresolved {
                reason: WatchUnresolvedReason::UnknownExl,
                watch_generation: Some(config.generation),
            });
        }
        Some(true) => {
            return Ok(WatchAssessment::Unresolved {
                reason: WatchUnresolvedReason::PostponedWhileExl,
                watch_generation: Some(config.generation),
            });
        }
        Some(false) => {}
    }

    let Some(bev) = input.bev else {
        return Ok(WatchAssessment::Unresolved {
            reason: WatchUnresolvedReason::UnknownBev,
            watch_generation: Some(config.generation),
        });
    };

    // Watch shares the ordinary general vector. Kernel address width is immaterial
    // to that vector class; Bits32 is supplied only because the existing bounded
    // root selector requires a mode for TLB refill classification.
    let generic = resolve_exception_root(ExceptionRootInput {
        class: ExceptionClass::General,
        bev,
        exl: false,
        kernel_mode: KernelAddressMode::Bits32,
    });

    Ok(WatchAssessment::ImmediateWatch(WatchRootReceipt {
        watch_generation: config.generation,
        exception_code: WATCH_EXCEPTION_CODE,
        physical_block: config.physical_block,
        physical_address,
        root: generic.root,
    }))
}
