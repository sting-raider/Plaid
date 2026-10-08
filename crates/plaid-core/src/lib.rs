//! Core data types for Plaid.
//!
//! Keep this crate free of ROM assets and game-specific assumptions.

pub mod discovery;
pub mod indirect;
mod indirect_chain;
pub mod loads;
pub mod merge;
pub mod pipeline;
pub mod program;
pub mod rom;
pub mod solver;
pub mod trace;

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[serde(transparent)]
pub struct GuestAddr(pub u32);

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EvidenceKind {
    Static,
    Trace,
    Signature,
    TestOracle,
}
