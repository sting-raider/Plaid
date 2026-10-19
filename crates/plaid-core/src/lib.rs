//! Core data types for Plaid.
//!
//! Keep this crate free of ROM assets and game-specific assumptions.

pub mod cop1_lineage;
pub mod copy_calls;
pub mod copy_catalogs;
pub mod cpu_copy;
#[path = "cpu_mutation.rs"]
mod cpu_mutation_impl;
pub mod cpu_sp_conditional;
pub mod cpu_sp_subword;
pub mod data_roots;
pub mod dcache_writeback;
pub mod cpu_mutation {
    pub use super::cpu_mutation_impl::{
        CompletedCop1StoreEffect, Cop1MutationWitness, Cop1SourceLane, Cop1StoreKind,
        Cop1StoreSource, CpuMutationDomain, DecodedCop1Store, decode_cop1_store,
    };

    /// Verify one independently observed completed SWC1/SDC1 effect.
    ///
    /// CU1 is part of the captured architectural context: a completed sink cannot
    /// be paired with a CU1-disabled instruction. Absence of an effect creates no
    /// writer. Mapping identity, lower-observer completeness and FPR ancestry
    /// remain separate proof obligations.
    pub fn verify_cop1_store_effect(
        instruction_word: u32,
        gpr: &[u64; 32],
        raw_fprs: &[u64; 32],
        fr: bool,
        cu1: bool,
        effect: Option<&CompletedCop1StoreEffect>,
    ) -> Result<Option<Cop1MutationWitness>, String> {
        if !cu1 && effect.is_some() {
            return Err("completed COP1 effect while CU1 disabled".into());
        }
        super::cpu_mutation_impl::verify_cop1_store_effect(
            instruction_word,
            gpr,
            raw_fprs,
            fr,
            effect,
        )
    }
}
pub mod ares_boot;
pub mod boot_execution;
pub mod callbacks;
pub mod declared_loads;
pub mod discovery;
pub mod evidence_manifest;
pub mod exception_pif;
pub mod exception_root_generation;
pub mod exception_roots;
pub mod fetch;
pub mod history;
pub mod indirect;
mod indirect_chain;
pub mod interrupt_roots;
pub mod llsc_mutation;
pub mod loads;
pub mod merge;
pub mod overlays;
pub mod paired_streams;
pub mod pi_fetch_lineage;
pub mod pi_history;
pub mod pi_interrupt_history;
pub mod pi_queue_history;
pub mod pif_history;
pub mod pipeline;
pub mod program;
mod raw_sp_dma_egress;
pub mod recall;
pub mod reset_cache_lifetime;
pub mod returns;
pub mod rom;
pub mod root_policy;
pub mod root_provenance;
pub mod rsp_cpu_imem;
pub mod rsp_cpu_tlb;
pub mod rsp_rom;
pub mod segments;
pub mod signatures;
pub mod software_interrupt;
pub mod solver;
pub mod sp_dma_egress;
pub mod sp_history;
pub mod store_mutation;
pub mod tables;
pub mod tail_cells;
pub mod timer_interrupt;
pub mod tlb_catalogs;
pub mod tlb_fetch;
pub mod tlb_geometry;
pub mod tlb_history;
pub mod tlbr_history;
pub mod tlbwr_history;
pub mod trace;
pub mod trace_projection;
pub mod watch_roots;

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
