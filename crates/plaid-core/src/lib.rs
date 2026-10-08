//! Core data types for Plaid.
//!
//! Keep this crate free of ROM assets and game-specific assumptions.

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct GuestAddr(pub u32);

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EvidenceKind {
    Static,
    Trace,
    Signature,
    TestOracle,
}
