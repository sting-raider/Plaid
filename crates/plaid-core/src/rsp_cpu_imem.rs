//! Source-bound composition of decoded RSP writers and CPU IMEM installation.
//! Captured scalar/vector operands are inputs, not ultimate register ancestry.
//! The controlled profile has CPU register/control continuity, explicit RSP
//! reentry phases and no modeled cache, TLB or restore interleavings. Controlled
//! v4 separately binds completed DMEM DMA Word writes to uncached CPU fetches
//! and decoder contexts; it grants no request lifetime or mutation census.
use crate::{
    exception_roots::{
        ExceptionClass, ExceptionRootInput, ExceptionRootReceipt, KernelAddressMode,
        resolve_exception_root,
    },
    program::{FetchAccess, FetchCacheLine, GuestVirtualAddr, PhysicalAddr},
    rom::sha256,
    rsp_cpu_tlb::{
        Initial as InitialTlb, Observation as TlbObservation, Replay as TlbReplay,
        State as TlbState, Witness as TlbWitness,
    },
    tlb_history::TlbwiGeneration,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub const FORMAT: &str = "plaid-rsp-cpu-imem-history-v0";
pub const PROFILE: &str =
    "ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-rsp-cpu-imem-scalar-sbv2e0-v0";
pub const DEFINITION_FORMAT: &str = "plaid-rsp-cpu-imem-history-v1";
pub const DEFINITION_PROFILE: &str =
    "ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-rsp-cpu-imem-scalar-definitions-sbv2e0-v1";
pub const READ_FORMAT: &str = "plaid-rsp-cpu-imem-history-v2";
pub const READ_PROFILE: &str =
    "ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-rsp-cpu-imem-word-read-definitions-sbv2e0-v2";
pub const EXECUTION_FORMAT: &str = "plaid-rsp-cpu-imem-history-v3";
pub const EXECUTION_PROFILE: &str =
    "ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-rsp-cpu-imem-controlled-consumption-v3";
pub const DMA_FORMAT: &str = "plaid-rsp-cpu-imem-history-v4";
pub const DMA_PROFILE: &str =
    "ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-rsp-dmem-dma-cpu-consumption-v4";
pub const DMA_LIFECYCLE_FORMAT: &str = "plaid-rsp-cpu-imem-history-v5";
pub const DMA_LIFECYCLE_PROFILE: &str =
    "ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-promoted-dmem-dma-cpu-consumption-v5";
pub const DMA_ROUNDTRIP_FORMAT: &str = "plaid-rsp-cpu-imem-history-v6";
pub const DMA_ROUNDTRIP_PROFILE: &str =
    "ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-rsp-dmem-ram-imem-dma-consumption-v6";
pub const DMEM_INGRESS_FORMAT: &str = "plaid-rsp-cpu-imem-history-v7";
pub const DMEM_INGRESS_PROFILE: &str =
    "ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-rsp-dmem-ram-dmem-imem-consumption-v7";
pub const PENDING_DMA_FORMAT: &str = "plaid-rsp-cpu-imem-history-v8";
pub const PENDING_DMA_PROFILE: &str =
    "ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-mutable-pending-dma-consumption-v8";
pub const DECODED_DMA_FORMAT: &str = "plaid-rsp-cpu-imem-history-v9";
pub const DECODED_DMA_PROFILE: &str =
    "ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-decoded-mmio-dma-consumption-v9";
pub const CACHED_DMA_FORMAT: &str = "plaid-rsp-cpu-imem-history-v10";
pub const CACHED_DMA_PROFILE: &str =
    "ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-dma-cached-cpu-consumption-v10";
pub const INVALIDATION_FORMAT: &str = "plaid-rsp-cpu-imem-history-v11";
pub const INVALIDATION_PROFILE: &str =
    "ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-dma-cached-cpu-invalidation-v11";
pub const CPU_RAM_FORMAT: &str = "plaid-rsp-cpu-imem-history-v12";
pub const CPU_RAM_PROFILE: &str =
    "ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-cpu-copy-ram-cached-consumption-v12";
pub const CPU_TRANSFORM_FORMAT: &str = "plaid-rsp-cpu-imem-history-v13";
pub const CPU_TRANSFORM_PROFILE: &str =
    "ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-cpu-xori-ram-cached-consumption-v13";
pub const EXCEPTION_FORMAT: &str = "plaid-rsp-cpu-imem-history-v14";
pub const EXCEPTION_PROFILE: &str =
    "ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-writer-break-handler-consumption-v14";
pub const MAPPED_FORMAT: &str = "plaid-rsp-cpu-imem-history-v18";
pub const MAPPED_PROFILE: &str =
    "ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-tlbwi-mapped-cache-root-return-v18";
pub const EPC_TARGET_FORMAT: &str = "plaid-rsp-cpu-imem-history-v17";
pub const EPC_TARGET_PROFILE: &str =
    "ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-epc-transform-target-consumption-v17";
pub const EPC_FORMAT: &str = "plaid-rsp-cpu-imem-history-v16";
pub const EPC_PROFILE: &str =
    "ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-guest-epc-return-consumption-v16";
pub const RETURN_FORMAT: &str = "plaid-rsp-cpu-imem-history-v15";
pub const RETURN_PROFILE: &str =
    "ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-live-epc-handler-return-consumption-v15";

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct History {
    format: String,
    profile: String,
    initial_dmem: Vec<u8>,
    initial_imem: Vec<u8>,
    final_dmem: Vec<u8>,
    final_imem: Vec<u8>,
    steps: Vec<CpuStep>,
    events: Vec<Row>,
    #[serde(default)]
    ram: Option<RamSnapshot>,
    #[serde(default)]
    initial_pending: Option<PendingDmaSnapshot>,
    #[serde(default)]
    initial_tlb: Option<InitialTlb>,
}
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct RamSnapshot {
    start: PhysicalAddr,
    initial: Vec<u8>,
    final_bytes: Vec<u8>,
}
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct CpuStep {
    phase: u32,
    index: u32,
    word: u32,
    pc: u64,
    before: Vec<u64>,
    after: Vec<u64>,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "snake_case")]
enum Kind {
    CpuBegin,
    CpuEnd,
    RspBegin,
    RspEnd,
    RspSink,
    RspRead,
    OpaqueImemSeed,
    ForeignSink,
    SpRead,
    SpWrite,
    RamWrite,
    RamRead,
    RamFetchBegin,
    RamFetchEnd,
    DmaPromote,
    DmaComplete,
    ImemDmaRead,
    ImemDmaWrite,
    DmemDmaRead,
    DmemDmaWrite,
    DmaPendingWrite,
    CacheBurstRead,
    CacheFill,
    CpuReentry,
    CacheOperation,
    CpuRamWrite,
    ExceptionTransfer,
    ReturnTransfer,
    EpcRead,
    EpcWrite,
    TlbWrite,
}
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
struct Row {
    kind: Kind,
    ordinal: u64,
    context: u64,
    pc: u64,
    phase: u32,
    word: u32,
    address: u32,
    bank: u32,
    offset: u32,
    bytes: u32,
    value: u64,
    cpu: bool,
    next: u32,
    halted: bool,
    vector_byte: u32,
    gpr: Vec<u64>,
    rgpr: Vec<u32>,
    #[serde(default)]
    dma: Option<DmemDmaDescriptor>,
    #[serde(default)]
    fetch: Option<RamFetchAccess>,
    #[serde(default)]
    dma_direction: Option<SpDmaDirection>,
    #[serde(default)]
    pending_full: Option<bool>,
    #[serde(default)]
    cache_line: Option<FetchCacheLine>,
    #[serde(default)]
    cache_operation: Option<DmaCacheOperation>,
    #[serde(default)]
    exception_state: Option<CpuExceptionState>,
    #[serde(default)]
    return_state: Option<CpuReturnState>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    epc_state: Option<CpuReturnState>,
    #[serde(default)]
    tlb_state: Option<TlbState>,
    #[serde(default)]
    mapping: Option<TlbObservation>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CpuReturnState {
    pub state: CpuExceptionState,
    pub interrupt_enable: bool,
    pub llbit: bool,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CpuEretReturn {
    pub epc_transfer_ordinal: u64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub epc_write_ordinal: Option<u64>,
    pub decoder_context: u64,
    pub transfer_ordinal: u64,
    pub before: CpuReturnState,
    pub after: CpuReturnState,
    pub fetch_context: u64,
    pub target_decoder_context: u64,
}
fn eret_transfer(
    begin: &Row,
    row: &Row,
    producer: &CpuExceptionRoot,
    current_write: Option<&CpuEpcWrite>,
) -> Result<CpuEretReturn, String> {
    effect_row(row)?;
    let before = begin
        .return_state
        .as_ref()
        .ok_or("ERET lacks selected-register state")?;
    let after = row
        .return_state
        .as_ref()
        .ok_or("ERET lacks completed state")?;
    let expected_before = CpuExceptionState {
        pc: GuestVirtualAddr(begin.pc),
        ..current_write
            .map_or(&producer.after, |write| &write.after.state)
            .clone()
    };
    require(
        begin.word == 0x42000018
            && same(begin, row)
            && row.cpu
            && row.address == 0
            && row.bank == 0
            && row.offset == 0
            && row.bytes == 0
            && row.value == 0
            && !before.interrupt_enable
            && before.state == expected_before,
        "ERET lacks uncut selected EPC generation or supported state",
    )?;
    let expected = CpuReturnState {
        state: CpuExceptionState {
            pc: before.state.epc,
            exl: false,
            ..before.state.clone()
        },
        interrupt_enable: false,
        llbit: false,
    };
    require(
        *after == expected,
        "ERET target/EXL/LLbit differs from selected EPC",
    )?;
    Ok(CpuEretReturn {
        epc_transfer_ordinal: producer.transfer_ordinal,
        epc_write_ordinal: current_write.map(|write| write.write_ordinal),
        decoder_context: begin.context,
        transfer_ordinal: row.ordinal,
        before: before.clone(),
        after: after.clone(),
        fetch_context: 0,
        target_decoder_context: 0,
    })
}

// EPC ancestry is separate from physical-memory load ancestry. Equal writes
// replace the selected generation; a held read of an older generation cannot
// witness a new write merely because its bits still agree.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CpuEpcRead {
    pub decoder_context: u64,
    pub read_ordinal: u64,
    pub register: u8,
    pub value: u64,
    pub epc_transfer_ordinal: u64,
    pub epc_write_ordinal: Option<u64>,
    pub before: CpuReturnState,
    pub after: CpuReturnState,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CpuEpcWrite {
    pub decoder_context: u64,
    pub write_ordinal: u64,
    pub register: u8,
    pub value: u64,
    pub read_parent: CpuEpcRead,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub transform: Option<CpuXorTransform>,
    pub before: CpuReturnState,
    pub after: CpuReturnState,
}
fn epc_instruction(word: u32) -> bool {
    // MFC0/MTC0, rd=EPC, no select/reserved bits, nonzero GPR.
    matches!(word & 0xffe0ffff, 0x40007000 | 0x40807000) && (word >> 16) & 31 != 0
}
fn epc_access(
    begin: &Row,
    row: &Row,
    producer: &CpuExceptionRoot,
    current_write: Option<&CpuEpcWrite>,
) -> Result<(CpuReturnState, CpuReturnState), String> {
    effect_row(row)?;
    let before = begin
        .epc_state
        .as_ref()
        .ok_or("EPC access lacks before state")?;
    let after = row
        .epc_state
        .as_ref()
        .ok_or("EPC access lacks completed state")?;
    let expected = CpuExceptionState {
        pc: GuestVirtualAddr(begin.pc),
        ..current_write
            .map_or(&producer.after, |write| &write.after.state)
            .clone()
    };
    require(
        epc_instruction(begin.word)
            && same(begin, row)
            && row.cpu
            && row.address == 0
            && row.bank == 0
            && row.offset == 0
            && row.bytes == 0
            && row.value == 0
            && !before.interrupt_enable
            && before.state == expected,
        "unsupported EPC access or cut producer state",
    )?;
    // End observer runs after epilogue, before pipeline.end advances ipu.pc.
    let mut expected_after = before.clone();
    if row.kind == Kind::EpcWrite {
        expected_after.state.epc = GuestVirtualAddr(begin.gpr[((begin.word >> 16) & 31) as usize]);
    }
    require(
        *after == expected_after,
        "EPC access changed unsupported architectural state",
    )?;
    Ok((before.clone(), after.clone()))
}
fn epc_read(
    begin: &Row,
    row: &Row,
    producer: &CpuExceptionRoot,
    current_write: Option<&CpuEpcWrite>,
) -> Result<CpuEpcRead, String> {
    let (before, after) = epc_access(begin, row, producer, current_write)?;
    require(
        row.kind == Kind::EpcRead && begin.word & 0xffe0ffff == 0x40007000,
        "EPC read differs from decoded MFC0",
    )?;
    Ok(CpuEpcRead {
        decoder_context: begin.context,
        read_ordinal: row.ordinal,
        register: ((begin.word >> 16) & 31) as u8,
        value: sign32(before.state.epc.0 as u32),
        epc_transfer_ordinal: producer.transfer_ordinal,
        epc_write_ordinal: current_write.map(|write| write.write_ordinal),
        before,
        after,
    })
}
fn epc_write(
    begin: &Row,
    row: &Row,
    producer: &CpuExceptionRoot,
    current_write: Option<&CpuEpcWrite>,
    held: Option<&EpcHeld>,
    target_enabled: bool,
) -> Result<CpuEpcWrite, String> {
    let (before, after) = epc_access(begin, row, producer, current_write)?;
    let rt = ((begin.word >> 16) & 31) as usize;
    let held = held.ok_or("MTC0 lacks held current EPC read")?;
    let parent = &held.read;
    require(
        row.kind == Kind::EpcWrite
            && begin.word & 0xffe0ffff == 0x40807000
            && parent.register as usize == rt
            && held.value() == begin.gpr[rt]
            && (target_enabled || (held.transform.is_none() && parent.value == before.state.epc.0))
            && parent.epc_transfer_ordinal == producer.transfer_ordinal
            && parent.epc_write_ordinal == current_write.map(|write| write.write_ordinal),
        "MTC0 cannot borrow an equal value or past EPC read generation",
    )?;
    Ok(CpuEpcWrite {
        decoder_context: begin.context,
        write_ordinal: row.ordinal,
        register: rt as u8,
        value: begin.gpr[rt],
        read_parent: parent.clone(),
        transform: held.transform.clone(),
        before,
        after,
    })
}

#[derive(Clone)]
struct EpcHeld {
    read: CpuEpcRead,
    transform: Option<CpuXorTransform>,
}
impl EpcHeld {
    fn value(&self) -> u64 {
        self.transform
            .as_ref()
            .map_or(self.read.value, |transform| transform.result_value)
    }
    fn xori(parent: Option<Self>, begin: &Row) -> Result<Option<Self>, String> {
        let rs = ((begin.word >> 21) & 31) as usize;
        let rt = ((begin.word >> 16) & 31) as usize;
        let Some(mut held) = parent else {
            return Ok(None);
        };
        require(
            held.read.register as usize == rs && held.value() == begin.gpr[rs],
            "XORI source lost held EPC read definition",
        )?;
        if rs != rt || held.transform.is_some() {
            return Ok(None);
        }
        held.transform = Some(CpuXorTransform {
            decoder_context: begin.context,
            pc: GuestVirtualAddr(begin.pc),
            word: begin.word,
            source_value: held.value(),
            result_value: held.value() ^ u64::from(begin.word as u16),
        });
        Ok(Some(held))
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CpuExceptionState {
    pub pc: GuestVirtualAddr,
    pub bev: bool,
    pub exl: bool,
    pub erl: bool,
    pub kernel_mode: KernelAddressMode,
    pub kernel: bool,
    pub cause: u32,
    pub branch_delay: bool,
    pub epc: GuestVirtualAddr,
    pub delay_slot: bool,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CpuExceptionRoot {
    pub trigger_context: u64,
    pub transfer_ordinal: u64,
    pub before: CpuExceptionState,
    pub after: CpuExceptionState,
    pub root: ExceptionRootReceipt,
    pub fetch_context: u64,
    pub decoder_context: u64,
}
fn break_word(word: u32) -> bool {
    word & 0xfc00003f == 13
}
fn break_transfer(begin: &Row, row: &Row) -> Result<CpuExceptionRoot, String> {
    effect_row(row)?;
    let before = begin
        .exception_state
        .as_ref()
        .ok_or("BREAK lacks pre-transfer state")?;
    let after = row
        .exception_state
        .as_ref()
        .ok_or("exception transfer lacks state")?;
    require(
        break_word(begin.word)
            && same(begin, row)
            && row.cpu
            && row.bank == 0
            && row.address == 0
            && row.offset == 0
            && row.bytes == 0
            && row.value == 0
            && before.pc.0 == begin.pc
            && !before.bev
            && !before.exl
            && !before.erl
            && before.kernel
            && before.kernel_mode == KernelAddressMode::Bits32
            && !before.delay_slot
            && before.cause == 0
            && !before.branch_delay,
        "unsupported or unscoped BREAK exception state",
    )?;
    let root = resolve_exception_root(ExceptionRootInput {
        class: ExceptionClass::General,
        bev: before.bev,
        exl: before.exl,
        kernel_mode: before.kernel_mode,
    });
    let expected = CpuExceptionState {
        pc: root.root,
        exl: true,
        cause: 9,
        epc: GuestVirtualAddr(begin.pc),
        ..before.clone()
    };
    require(
        *after == expected,
        "BREAK exception result differs from architectural root/EPC/EXL",
    )?;
    Ok(CpuExceptionRoot {
        trigger_context: begin.context,
        transfer_ordinal: row.ordinal,
        before: before.clone(),
        after: after.clone(),
        root,
        fetch_context: 0,
        decoder_context: 0,
    })
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DmaCacheOperation {
    pub virtual_address: GuestVirtualAddr,
    pub operation: u8,
    pub before: FetchCacheLine,
    pub after: FetchCacheLine,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DmaCacheInvalidation {
    pub decoder_context: u64,
    pub ordinal: u64,
    pub physical: PhysicalAddr,
    pub operation: DmaCacheOperation,
    pub hit: bool,
    pub ended_fill: Option<u64>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PendingDmaSnapshot {
    pub descriptor: DmemDmaDescriptor,
    pub bank: u32,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PendingDmaProvenance {
    pub commit_ordinal: u64,
    pub pbus_write_ordinal: Option<u64>,
    pub dram_write_ordinal: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub commit_decoder_context: Option<u64>,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PendingDmaCommit {
    pub commit_ordinal: u64,
    pub superseded_commit: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub decoder_context: Option<u64>,
}
struct PendingDmaReplay {
    snapshot: PendingDmaSnapshot,
    direction: Option<SpDmaDirection>,
    commit: Option<u64>,
    pbus_writer: Option<u64>,
    dram_writer: Option<u64>,
    commits: Vec<PendingDmaCommit>,
    commit_decoder: Option<u64>,
}
impl PendingDmaReplay {
    fn write(&mut self, row: &Row, decoded: Option<&Row>) -> Result<(), String> {
        effect_row(row)?;
        if let Some(begin) = decoded {
            let rs = ((begin.word >> 21) & 31) as usize;
            let rt = ((begin.word >> 16) & 31) as usize;
            let address = begin.gpr[rs].wrapping_add_signed(i64::from(begin.word as i16));
            require(
                same(begin, row)
                    && begin.word >> 26 == 0x2b
                    && (0xffffffffa4040000..=0xffffffffa404000c).contains(&address)
                    && address.is_multiple_of(4)
                    && row.address == (address as u32 & 31) >> 2
                    && row.value == u64::from(begin.gpr[rt] as u32),
                "pending DMA effect differs from decoded direct-KSEG1 SW",
            )?;
        } else {
            require(
                row.context == row.ordinal && row.word == 0,
                "unscoped pending DMA has decoder metadata",
            )?;
        }
        require(
            row.cpu
                && row.bytes == 4
                && row.value <= u32::MAX as u64
                && row.gpr.is_empty()
                && row.rgpr.is_empty()
                && row.bank <= 1,
            "invalid pending DMA write scope",
        )?;
        let value = row.value as u32;
        match row.address {
            0 => {
                self.snapshot.descriptor.pbus = value & 0xff8;
                self.snapshot.bank = (value >> 12) & 1;
                self.pbus_writer = Some(row.ordinal);
                if let Some(direction) = &mut self.direction {
                    require(
                        *direction != SpDmaDirection::DmemEgress || self.snapshot.bank == 0,
                        "unsupported pending IMEM egress",
                    )?;
                    if *direction != SpDmaDirection::DmemEgress {
                        *direction = if self.snapshot.bank == 1 {
                            SpDmaDirection::ImemIngress
                        } else {
                            SpDmaDirection::DmemIngress
                        };
                    }
                }
            }
            1 => {
                self.snapshot.descriptor.dram = PhysicalAddr(value & 0xfffff8);
                self.dram_writer = Some(row.ordinal);
            }
            2 | 3 => {
                self.snapshot.descriptor.length = value & 0xff8;
                self.snapshot.descriptor.count = (value >> 12) & 255;
                self.snapshot.descriptor.skip = (value >> 20) & 0xff8;
                require(
                    row.address != 3 || self.snapshot.bank == 0,
                    "unsupported pending IMEM egress",
                )?;
                self.direction = Some(if row.address == 3 {
                    SpDmaDirection::DmemEgress
                } else if self.snapshot.bank == 1 {
                    SpDmaDirection::ImemIngress
                } else {
                    SpDmaDirection::DmemIngress
                });
                self.commits.push(PendingDmaCommit {
                    commit_ordinal: row.ordinal,
                    superseded_commit: self.commit.replace(row.ordinal),
                    decoder_context: decoded.map(|begin| begin.context),
                });
                self.commit_decoder = decoded.map(|begin| begin.context);
            }
            _ => return Err("unsupported pending DMA register".into()),
        }
        require(
            row.dma.as_ref() == Some(&self.snapshot.descriptor)
                && row.offset == self.snapshot.descriptor.pbus
                && row.bank == self.snapshot.bank
                && row.pending_full == Some(self.commit.is_some())
                && row.dma_direction == self.direction,
            "pending DMA mutation disagrees with masked register state",
        )
    }
    fn promote(&mut self, row: &Row) -> Result<PendingDmaProvenance, String> {
        require(
            row.dma.as_ref() == Some(&self.snapshot.descriptor)
                && row.bank == self.snapshot.bank
                && row.dma_direction == self.direction,
            "DMA promotion disagrees with latest mutable pending state",
        )?;
        let commit_ordinal = self
            .commit
            .take()
            .ok_or("DMA promotion lacks pending length commit")?;
        self.direction = None;
        Ok(PendingDmaProvenance {
            commit_ordinal,
            pbus_write_ordinal: self.pbus_writer,
            dram_write_ordinal: self.dram_writer,
            commit_decoder_context: self.commit_decoder.take(),
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DmemDmaDescriptor {
    pub pbus: u32,
    pub dram: PhysicalAddr,
    pub length: u32,
    pub count: u32,
    pub skip: u32,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RamFetchAccess {
    pub physical: PhysicalAddr,
    pub cached: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum RamByteOrigin {
    Unknown {
        cut_ordinal: Option<u64>,
    },
    SpDma {
        write_ordinal: u64,
        source_offset: u16,
    },
    CpuCopy {
        write_ordinal: u64,
        source_offset: u8,
    },
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CpuRamCopyParent {
    pub load_context: u64,
    pub read_ordinal: u64,
    pub source: PhysicalAddr,
    pub source_bytes: [SpByteOrigin; 4],
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub transform: Option<CpuXorTransform>,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CpuXorTransform {
    pub decoder_context: u64,
    pub pc: GuestVirtualAddr,
    pub word: u32,
    pub source_value: u64,
    pub result_value: u64,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CpuRamWord {
    pub decoder_context: u64,
    pub write_ordinal: u64,
    pub destination: PhysicalAddr,
    pub source_register: u8,
    pub register_value: u64,
    pub word: u32,
    pub copy_parent: Option<CpuRamCopyParent>,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DmemDmaWord {
    pub write_ordinal: u64,
    pub destination: PhysicalAddr,
    pub descriptor: DmemDmaDescriptor,
    pub source_offset: u16,
    pub word: u32,
    pub source_bytes: [SpByteOrigin; 4],
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub promote_context: Option<u64>,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PromotedDmemDmaRequest {
    pub promote_context: u64,
    pub complete_ordinal: u64,
    pub descriptor: DmemDmaDescriptor,
    pub write_ordinals: Vec<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub direction: Option<SpDmaDirection>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub pending_provenance: Option<PendingDmaProvenance>,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SpDmaDirection {
    DmemEgress,
    ImemIngress,
    DmemIngress,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RamToDmemDmaWord {
    pub promote_context: u64,
    pub read_ordinal: u64,
    pub write_ordinal: u64,
    pub descriptor: DmemDmaDescriptor,
    pub source: PhysicalAddr,
    pub offset: u16,
    pub value: u32,
    pub source_bytes: [RamByteOrigin; 4],
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RamToImemDmaInstall {
    pub promote_context: u64,
    pub read_ordinal: u64,
    pub write_ordinal: u64,
    pub descriptor: DmemDmaDescriptor,
    pub value: u64,
    pub source_bytes: [RamByteOrigin; 8],
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DmaCpuFetch {
    pub fetch_context: u64,
    pub read_ordinal: u64,
    pub decoder_context: u64,
    pub pc: GuestVirtualAddr,
    pub physical: PhysicalAddr,
    pub word: u32,
    pub origins: [RamByteOrigin; 4],
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DmaCacheFill {
    pub fetch_context: u64,
    pub burst_ordinal: u64,
    pub fill_ordinal: u64,
    pub physical_line: PhysicalAddr,
    pub cache_line: FetchCacheLine,
    pub source_bytes: [RamByteOrigin; 32],
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CachedDmaCpuFetch {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub mapping: Option<TlbWitness>,
    pub fetch_context: u64,
    pub end_ordinal: u64,
    pub decoder_context: u64,
    pub pc: GuestVirtualAddr,
    pub physical: PhysicalAddr,
    pub word: u32,
    pub burst_ordinal: u64,
    pub fill_ordinal: u64,
    pub origins: [RamByteOrigin; 4],
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DmemDmaConsumption {
    pub ram_start: PhysicalAddr,
    pub ram_bytes: usize,
    pub initial_ram_sha256: String,
    pub final_ram_sha256: String,
    pub writes: Vec<DmemDmaWord>,
    pub fetches: Vec<DmaCpuFetch>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub promoted_requests: Option<Vec<PromotedDmemDmaRequest>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub imem_installs: Option<Vec<RamToImemDmaInstall>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub dmem_installs: Option<Vec<RamToDmemDmaWord>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub pending_commits: Option<Vec<PendingDmaCommit>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cache_fills: Option<Vec<DmaCacheFill>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cached_fetches: Option<Vec<CachedDmaCpuFetch>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cache_invalidations: Option<Vec<DmaCacheInvalidation>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cpu_writes: Option<Vec<CpuRamWord>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tlb_generations: Option<Vec<TlbwiGeneration>>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum SpByteOrigin {
    DmemDma {
        promote_context: u64,
        read_ordinal: u64,
        write_ordinal: u64,
        source: PhysicalAddr,
        parent: RamByteOrigin,
    },
    ImemDma {
        promote_context: u64,
        read_ordinal: u64,
        write_ordinal: u64,
        source: PhysicalAddr,
        parent: RamByteOrigin,
    },
    Rsp {
        context: u64,
        pc: u16,
        word: u32,
        write_ordinal: u64,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        source_definition: Option<u64>,
    },
    Cpu {
        context: u64,
        pc: GuestVirtualAddr,
        word: u32,
        write_ordinal: u64,
    },
    Unknown {
        cut_ordinal: Option<u64>,
    },
}

/// Parent identity at the actual decoded instruction boundary. Captured inputs
/// remain opaque; equal bits never substitute for an earlier definition.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum RspRegisterParent {
    ArchitecturalZero,
    Definition { context: u64 },
    CapturedInput { register: u8, value: u32 },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum RspDefinitionExpression {
    Ori {
        source: RspRegisterParent,
        immediate: u16,
    },
    Addu {
        left: RspRegisterParent,
        right: RspRegisterParent,
    },
    DmemWordLoad(Box<RspDmemWordRead>),
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RspDmemWordRead {
    pub read_ordinal: u64,
    pub address: u32,
    pub offset: u16,
    pub payload: [u8; 4],
    pub origins: [SpByteOrigin; 4],
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RspRegisterDefinition {
    pub context: u64,
    pub phase: u32,
    pub pc: u16,
    pub word: u32,
    pub register: u8,
    pub value: u32,
    pub expression: RspDefinitionExpression,
}

/// One actually decoded IMEM word, not a continuous image lifetime. Byte
/// parents are the latest captured writes in this complete controlled source.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RspImemFetch {
    pub context: u64,
    pub pc: u16,
    pub word: u32,
    pub origins: [SpByteOrigin; 4],
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ImemCopyChain {
    pub phase: u32,
    pub load_context: u64,
    pub read_ordinal: u64,
    pub store_context: u64,
    pub write_ordinal: u64,
    pub source_register: u8,
    pub source: PhysicalAddr,
    pub destination: PhysicalAddr,
    pub word: u32,
    pub source_bytes: [SpByteOrigin; 4],
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RspCpuImemReport {
    pub format: String,
    pub profile: String,
    pub source_sha256: String,
    pub records: usize,
    pub cpu_instructions: usize,
    pub rsp_instructions: usize,
    pub copies: Vec<ImemCopyChain>,
    pub final_imem_writers: Vec<SpByteOrigin>,
    pub final_dmem_sha256: String,
    pub final_imem_sha256: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rsp_definitions: Option<Vec<RspRegisterDefinition>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub imem_fetches: Option<Vec<RspImemFetch>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub dma_consumption: Option<DmemDmaConsumption>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub exception_roots: Option<Vec<CpuExceptionRoot>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub eret_returns: Option<Vec<CpuEretReturn>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub epc_reads: Option<Vec<CpuEpcRead>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub epc_writes: Option<Vec<CpuEpcWrite>>,
    pub source_ancestry_certified: bool,
    pub mutation_coverage_certified: bool,
    pub imem_execution_certified: bool,
    pub executable_lifetime_certified: bool,
    pub native_complete: bool,
}
#[derive(Clone)]
struct Loaded {
    context: u64,
    read: u64,
    register: usize,
    bits: u64,
    address: PhysicalAddr,
    origins: [SpByteOrigin; 4],
    transform: Option<CpuXorTransform>,
}
impl Loaded {
    fn xori(parent: Option<Self>, begin: &Row) -> Result<Option<Self>, String> {
        let rs = ((begin.word >> 21) & 31) as usize;
        let rt = ((begin.word >> 16) & 31) as usize;
        let Some(mut loaded) = parent else {
            return Ok(None);
        };
        require(
            loaded.register == rs && loaded.bits == begin.gpr[rs],
            "XORI source lost held CPU load definition",
        )?;
        if rs != rt || loaded.transform.is_some() {
            return Ok(None);
        }
        let result_value = loaded.bits ^ u64::from(begin.word as u16);
        loaded.transform = Some(CpuXorTransform {
            decoder_context: begin.context,
            pc: GuestVirtualAddr(begin.pc),
            word: begin.word,
            source_value: loaded.bits,
            result_value,
        });
        loaded.bits = result_value;
        Ok(Some(loaded))
    }
}
fn effect_row(row: &Row) -> Result<(), String> {
    require(
        row.gpr.is_empty()
            && row.rgpr.is_empty()
            && row.next == 0
            && !row.halted
            && row.vector_byte == 0,
        "invalid completed-effect metadata",
    )
}
enum Active {
    Cpu {
        begin: Row,
        read: Option<Loaded>,
        written: bool,
    },
    Rsp {
        begin: Row,
        lanes: Vec<(u16, u8)>,
        consumed: usize,
        breaking: bool,
        expected_gpr: Vec<u32>,
        definition: Option<RspRegisterDefinition>,
        read: bool,
    },
}

struct RamReplay {
    start: PhysicalAddr,
    initial_sha256: String,
    bytes: Vec<u8>,
    origins: Vec<RamByteOrigin>,
    final_bytes: Vec<u8>,
    writes: Vec<DmemDmaWord>,
    fetches: Vec<DmaCpuFetch>,
    active: Option<(Row, Option<DmaCpuFetch>)>,
    pending: Option<PendingFetch>,
    lifecycle: bool,
    request: Option<ActiveDmemDma>,
    requests: Vec<PromotedDmemDmaRequest>,
    ingress: bool,
    ingress_read: Option<(Row, [RamByteOrigin; 8])>,
    installs: Vec<RamToImemDmaInstall>,
    dmem_ingress: bool,
    dmem_reads: Vec<(Row, [RamByteOrigin; 4])>,
    dmem_installs: Vec<RamToDmemDmaWord>,
    pending_dma: Option<PendingDmaReplay>,
    cached: bool,
    cache_burst: Option<(Row, [RamByteOrigin; 32])>,
    cache_fills: Vec<DmaCacheFill>,
    cache_slots: BTreeMap<u16, usize>,
    cached_fetches: Vec<CachedDmaCpuFetch>,
    invalidation_enabled: bool,
    cache_state: BTreeMap<u16, FetchCacheLine>,
    cache_invalidations: Vec<DmaCacheInvalidation>,
    cpu_ram_enabled: bool,
    cpu_writes: Vec<CpuRamWord>,
    tlb: Option<TlbReplay>,
}
enum PendingFetch {
    Uncached(usize),
    Cached(usize),
}
struct ActiveDmemDma {
    context: u64,
    descriptor: DmemDmaDescriptor,
    writes: Vec<u64>,
    direction: SpDmaDirection,
    pending_provenance: Option<PendingDmaProvenance>,
}
impl ActiveDmemDma {
    fn fragments_per_block(&self) -> u64 {
        if self.direction == SpDmaDirection::ImemIngress {
            1
        } else {
            2
        }
    }
    fn total_words(&self) -> u64 {
        u64::from((self.descriptor.length + 8) / 8)
            * u64::from(self.descriptor.count + 1)
            * self.fragments_per_block()
    }
    fn current(&self, block: u64) -> DmemDmaDescriptor {
        let row = block / u64::from((self.descriptor.length + 8) / 8);
        DmemDmaDescriptor {
            pbus: ((u64::from(self.descriptor.pbus) + block * 8) & 4095) as u32,
            dram: PhysicalAddr(
                ((u64::from(self.descriptor.dram.0)
                    + block * 8
                    + row * u64::from(self.descriptor.skip))
                    & 0xffffff) as u32,
            ),
            length: self.descriptor.length,
            count: self.descriptor.count - row as u32,
            skip: self.descriptor.skip,
        }
    }
}
fn valid_dmem_dma_descriptor(descriptor: &DmemDmaDescriptor) -> bool {
    descriptor.pbus < 4096
        && descriptor.pbus.is_multiple_of(8)
        && descriptor.dram.0 < 0x800000
        && descriptor.dram.0.is_multiple_of(8)
        && descriptor.length <= 0xff8
        && descriptor.length.is_multiple_of(8)
        && descriptor.count <= 255
        && descriptor.skip <= 4095
        && descriptor.skip.is_multiple_of(8)
}
impl RamReplay {
    fn new(
        snapshot: RamSnapshot,
        lifecycle: bool,
        ingress: bool,
        dmem_ingress: bool,
    ) -> Result<Self, String> {
        require(
            !snapshot.initial.is_empty()
                && snapshot.initial.len() <= 65536
                && snapshot.initial.len().is_multiple_of(4)
                && snapshot.start.0.is_multiple_of(4)
                && u64::from(snapshot.start.0) + snapshot.initial.len() as u64 <= 0x800000
                && snapshot.initial.len() == snapshot.final_bytes.len(),
            "invalid controlled RAM snapshot",
        )?;
        Ok(Self {
            start: snapshot.start,
            initial_sha256: sha256(&snapshot.initial),
            origins: vec![RamByteOrigin::Unknown { cut_ordinal: None }; snapshot.initial.len()],
            bytes: snapshot.initial,
            final_bytes: snapshot.final_bytes,
            writes: Vec::new(),
            fetches: Vec::new(),
            active: None,
            pending: None,
            lifecycle,
            request: None,
            requests: Vec::new(),
            ingress,
            ingress_read: None,
            installs: Vec::new(),
            dmem_ingress,
            dmem_reads: Vec::new(),
            dmem_installs: Vec::new(),
            pending_dma: None,
            cached: false,
            cache_burst: None,
            cache_fills: Vec::new(),
            cache_slots: BTreeMap::new(),
            cached_fetches: Vec::new(),
            invalidation_enabled: false,
            cache_state: BTreeMap::new(),
            tlb: None,
            cache_invalidations: Vec::new(),
            cpu_ram_enabled: false,
            cpu_writes: Vec::new(),
        })
    }
    fn offset(&self, address: u32, width: usize) -> Result<usize, String> {
        let offset = address
            .checked_sub(self.start.0)
            .ok_or("RAM access precedes snapshot")? as usize;
        require(
            offset
                .checked_add(width)
                .is_some_and(|end| end <= self.bytes.len()),
            "RAM access escapes declared snapshot",
        )?;
        Ok(offset)
    }
    fn cpu_write(&mut self, row: &Row, begin: &Row, parent: Option<&Loaded>) -> Result<(), String> {
        effect_row(row)?;
        let rs = ((begin.word >> 21) & 31) as usize;
        let rt = ((begin.word >> 16) & 31) as usize;
        let address = begin.gpr[rs].wrapping_add_signed(i64::from(begin.word as i16));
        require(
            self.cpu_ram_enabled
                && same(begin, row)
                && begin.word >> 26 == 0x2b
                && (0xffffffffa0000000..0xffffffffa0800000).contains(&address)
                && address.is_multiple_of(4)
                && row.address == address as u32 & 0x1fffffff
                && row.value == u64::from(begin.gpr[rt] as u32)
                && row.cpu
                && row.bank == 0
                && row.offset == 0
                && row.bytes == 4
                && self.active.is_none()
                && self.pending.is_none()
                && self.request.is_none(),
            "RAM write differs from decoded direct-KSEG1 SW",
        )?;
        let copy_parent = parent
            .map(|loaded| {
                require(
                    loaded.register == rt && loaded.bits == begin.gpr[rt],
                    "RAM store source lost held CPU load definition",
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
        let offset = self.offset(row.address, 4)?;
        self.bytes[offset..offset + 4].copy_from_slice(&(row.value as u32).to_be_bytes());
        for n in 0..4 {
            self.origins[offset + n] = if copy_parent.is_some() {
                RamByteOrigin::CpuCopy {
                    write_ordinal: row.ordinal,
                    source_offset: n as u8,
                }
            } else {
                RamByteOrigin::Unknown {
                    cut_ordinal: Some(row.ordinal),
                }
            };
        }
        self.cpu_writes.push(CpuRamWord {
            decoder_context: begin.context,
            write_ordinal: row.ordinal,
            destination: PhysicalAddr(row.address),
            source_register: rt as u8,
            register_value: begin.gpr[rt],
            word: row.value as u32,
            copy_parent,
        });
        Ok(())
    }
    fn observe(&mut self, row: Row, dmem: &[u8], dorig: &[SpByteOrigin]) -> Result<(), String> {
        effect_row(&row)?;
        require(
            (row.bank == 0
                || (self.ingress
                    && matches!(row.kind, Kind::DmaPromote | Kind::DmaComplete)
                    && row.bank == 1))
                && row.gpr.is_empty()
                && row.rgpr.is_empty()
                && row.word == 0,
            "invalid RAM observation metadata",
        )?;
        match row.kind {
            Kind::DmaPromote => {
                let descriptor = row.dma.as_ref().ok_or("DMA promotion lacks descriptor")?;
                require(
                    self.lifecycle
                        && self.request.is_none()
                        && !row.cpu
                        && row.context == row.ordinal
                        && row.bytes == 0
                        && row.value == 0
                        && row.address == descriptor.dram.0
                        && row.offset == descriptor.pbus
                        && valid_dmem_dma_descriptor(descriptor),
                    "invalid promoted DMEM DMA request",
                )?;
                let direction = if self.dmem_ingress {
                    let direction = row.dma_direction.ok_or("DMA promotion lacks direction")?;
                    require(
                        row.bank == u32::from(direction == SpDmaDirection::ImemIngress),
                        "DMA bank/direction mismatch",
                    )?;
                    direction
                } else if row.bank == 1 {
                    SpDmaDirection::ImemIngress
                } else {
                    SpDmaDirection::DmemEgress
                };
                self.request = Some(ActiveDmemDma {
                    context: row.context,
                    descriptor: descriptor.clone(),
                    writes: Vec::new(),
                    direction,
                    pending_provenance: self
                        .pending_dma
                        .as_mut()
                        .map(|pending| pending.promote(&row))
                        .transpose()?,
                });
            }
            Kind::DmaComplete => {
                let request = self
                    .request
                    .take()
                    .ok_or("DMA completion lacks promotion")?;
                let blocks = request.total_words() / request.fragments_per_block();
                let end_pbus = ((u64::from(request.descriptor.pbus) + blocks * 8) & 4095) as u32;
                let end_dram = ((u64::from(request.descriptor.dram.0)
                    + blocks * 8
                    + u64::from(request.descriptor.count) * u64::from(request.descriptor.skip))
                    & 0xffffff) as u32;
                require(
                    self.lifecycle
                        && !row.cpu
                        && row.context == request.context
                        && row.bytes == 0
                        && row.value == 0
                        && row.dma.is_none()
                        && row.bank == u32::from(request.direction == SpDmaDirection::ImemIngress)
                        && (!self.dmem_ingress || row.dma_direction == Some(request.direction))
                        && request.writes.len() as u64 == request.total_words()
                        && row.address == end_dram
                        && row.offset == end_pbus,
                    "DMA completion disagrees with complete descriptor progression",
                )?;
                self.requests.push(PromotedDmemDmaRequest {
                    promote_context: request.context,
                    complete_ordinal: row.ordinal,
                    descriptor: request.descriptor,
                    write_ordinals: request.writes,
                    direction: self.ingress.then_some(request.direction),
                    pending_provenance: request.pending_provenance,
                });
            }
            Kind::RamWrite => {
                require(
                    self.active.is_none()
                        && self.pending.is_none()
                        && !row.cpu
                        && row.bytes == 4
                        && row.address.is_multiple_of(4),
                    "invalid controlled RAM write scope",
                )?;
                let offset = self.offset(row.address, 4)?;
                let data = payload(row.value, 4)?;
                let origins: [RamByteOrigin; 4] = if let Some(descriptor) = &row.dma {
                    require(
                        valid_dmem_dma_descriptor(descriptor),
                        "invalid completed DMEM DMA descriptor",
                    )?;
                    let lane = row
                        .address
                        .checked_sub(descriptor.dram.0)
                        .ok_or("DMA write precedes descriptor")?;
                    require(
                        lane == 0 || lane == 4,
                        "DMA Word is not a current descriptor lane",
                    )?;
                    let source = (descriptor.pbus + lane) & 4095;
                    if self.lifecycle {
                        let request = self
                            .request
                            .as_mut()
                            .ok_or("DMA Word lacks actual promotion")?;
                        let index = request.writes.len() as u64;
                        require(
                            request.direction == SpDmaDirection::DmemEgress,
                            "RAM write attached to ingress request",
                        )?;
                        require(
                            index < request.total_words(),
                            "DMA request has excess Word effects",
                        )?;
                        require(
                            row.context == request.context
                                && *descriptor == request.current(index / 2)
                                && lane == (index % 2) as u32 * 4,
                            "DMA Word disagrees with promoted descriptor progression",
                        )?;
                        request.writes.push(row.ordinal);
                    } else {
                        require(row.context == 0, "unpromoted DMA Word has request identity")?;
                    }
                    require(row.offset == source, "DMA source does not match descriptor")?;
                    let values: [u8; 4] =
                        std::array::from_fn(|n| dmem[(source as usize + n) & 4095]);
                    require(
                        values.as_slice() == data,
                        "DMA payload disagrees with current DMEM",
                    )?;
                    self.writes.push(DmemDmaWord {
                        write_ordinal: row.ordinal,
                        destination: PhysicalAddr(row.address),
                        descriptor: descriptor.clone(),
                        source_offset: source as u16,
                        word: row.value as u32,
                        source_bytes: std::array::from_fn(|n| {
                            dorig[(source as usize + n) & 4095].clone()
                        }),
                        promote_context: self.lifecycle.then_some(row.context),
                    });
                    std::array::from_fn(|n| RamByteOrigin::SpDma {
                        write_ordinal: row.ordinal,
                        source_offset: ((source as usize + n) & 4095) as u16,
                    })
                } else {
                    require(
                        row.offset == 0 && row.context == 0,
                        "opaque RAM writer has source/request identity",
                    )?;
                    std::array::from_fn(|_| RamByteOrigin::Unknown {
                        cut_ordinal: Some(row.ordinal),
                    })
                };
                self.bytes[offset..offset + 4].copy_from_slice(&data);
                self.origins[offset..offset + 4].clone_from_slice(&origins);
            }
            Kind::RamFetchBegin => {
                let access = row
                    .fetch
                    .as_ref()
                    .ok_or("RAM fetch lacks access metadata")?;
                let direct = if let Some(observation) = &row.mapping {
                    require(access.cached, "mapped stream requires cached fetch")?;
                    self.tlb
                        .as_ref()
                        .ok_or("mapped fetch lacks TLB profile")?
                        .fetch(row.pc, access.physical, observation)?;
                    true
                } else {
                    (if access.cached {
                        0xffffffff80000000..0xffffffff80800000
                    } else {
                        0xffffffffa0000000..0xffffffffa0800000
                    })
                    .contains(&row.pc)
                        && row.pc & 0x1fffffff == u64::from(row.address)
                };
                require(
                    self.active.is_none()
                        && self.pending.is_none()
                        && row.context == row.ordinal
                        && row.cpu
                        && row.bytes == 0
                        && row.value == 0
                        && row.offset == 0
                        && (!access.cached || self.cached)
                        && access.physical.0 == row.address
                        && direct
                        && row.pc.is_multiple_of(4),
                    "invalid controlled direct RAM fetch",
                )?;
                self.offset(row.address, 4)?;
                self.active = Some((row, None));
            }
            Kind::RamRead => {
                let offset = self.offset(row.address, 4)?;
                let (begin, read) = self.active.as_mut().ok_or("unscoped RAM fetch read")?;
                require(
                    read.is_none()
                        && begin.fetch.as_ref().is_some_and(|access| !access.cached)
                        && row.cpu
                        && row.context == begin.context
                        && row.pc == begin.pc
                        && row.phase == begin.phase
                        && row.address == begin.address
                        && row.bytes == 4
                        && row.offset == 0
                        && payload(row.value, 4)? == self.bytes[offset..offset + 4],
                    "RAM fetch read differs from current backing/scope",
                )?;
                *read = Some(DmaCpuFetch {
                    fetch_context: begin.context,
                    read_ordinal: row.ordinal,
                    decoder_context: 0,
                    pc: GuestVirtualAddr(row.pc),
                    physical: PhysicalAddr(row.address),
                    word: row.value as u32,
                    origins: std::array::from_fn(|n| self.origins[offset + n].clone()),
                });
            }
            Kind::RamFetchEnd => {
                let (begin, read) = self.active.take().ok_or("RAM fetch end lacks begin")?;
                if begin.fetch.as_ref().is_some_and(|access| access.cached) {
                    self.cached_end(&begin, &row, read.is_none())?;
                    return Ok(());
                }
                let read = read.ok_or("RAM fetch lacks actual completed read")?;
                require(
                    row.cpu
                        && row.context == begin.context
                        && row.pc == begin.pc
                        && row.phase == begin.phase
                        && row.address == begin.address
                        && row.bytes == 0
                        && row.offset == 0
                        && row.fetch == begin.fetch
                        && row.value == u64::from(read.word),
                    "RAM fetch result differs from actual read",
                )?;
                self.pending = Some(PendingFetch::Uncached(self.fetches.len()));
                self.fetches.push(read);
            }
            _ => unreachable!(),
        }
        Ok(())
    }
    fn bind(&mut self, row: &Row) -> Result<(), String> {
        require(
            self.active.is_none(),
            "decoder began before fetch completed",
        )?;
        let index = self
            .pending
            .take()
            .ok_or("CPU decoder lacks completed RAM fetch")?;
        let (pc, word, context) = match index {
            PendingFetch::Uncached(index) => {
                let fetched = &mut self.fetches[index];
                (fetched.pc, fetched.word, &mut fetched.decoder_context)
            }
            PendingFetch::Cached(index) => {
                let fetched = &mut self.cached_fetches[index];
                (fetched.pc, fetched.word, &mut fetched.decoder_context)
            }
        };
        require(
            pc.0 == row.pc && word == row.word,
            "CPU decoder disagrees with fetched RAM word",
        )?;
        *context = row.context;
        Ok(())
    }
    fn cache(&mut self, row: Row) -> Result<(), String> {
        effect_row(&row)?;
        let frame = row.cache_line.ok_or("cache observation lacks snapshot")?;
        let (begin, read) = self
            .active
            .as_ref()
            .ok_or("cache observation lacks fetch scope")?;
        require(
            self.cached
                && begin.fetch.as_ref().is_some_and(|a| a.cached)
                && read.is_none()
                && row.context == begin.context
                && row.pc == begin.pc
                && row.phase == begin.phase
                && row.cpu
                && row.word == 0
                && row.bank == 0
                && row.offset == 0
                && row.bytes == 32
                && row.value == 0
                && row.gpr.is_empty()
                && row.rgpr.is_empty()
                && row.address == begin.address & !31,
            "invalid completed I-cache observation scope",
        )?;
        frame.validate(
            GuestVirtualAddr(begin.pc),
            FetchAccess {
                physical: PhysicalAddr(begin.address),
                cached: true,
            },
            frame.words[((begin.address >> 2) & 7) as usize],
        )?;
        if row.kind == Kind::CacheBurstRead {
            require(
                self.cache_burst.is_none()
                    && self.cache_slots.get(&frame.slot).is_none_or(|index| {
                        self.cache_fills[*index].cache_line.tag_key != frame.tag_key
                    }),
                "cache burst duplicated or emitted on modeled resident hit",
            )?;
            let offset = self.offset(row.address, 32)?;
            let values: Vec<_> = frame
                .words
                .iter()
                .flat_map(|word| word.to_be_bytes())
                .collect();
            require(
                values == self.bytes[offset..offset + 32],
                "cache burst differs from captured backing image",
            )?;
            self.cache_burst = Some((
                row,
                std::array::from_fn(|n| self.origins[offset + n].clone()),
            ));
        } else {
            let (burst, origins) = self
                .cache_burst
                .take()
                .ok_or("cache fill lacks completed burst")?;
            require(
                burst.ordinal.checked_add(1) == Some(row.ordinal)
                    && burst.cache_line == Some(frame),
                "cache fill disagrees with preceding completed burst",
            )?;
            self.cache_slots.insert(frame.slot, self.cache_fills.len());
            self.cache_state.insert(frame.slot, frame);
            self.cache_fills.push(DmaCacheFill {
                fetch_context: begin.context,
                burst_ordinal: burst.ordinal,
                fill_ordinal: row.ordinal,
                physical_line: PhysicalAddr(row.address),
                cache_line: frame,
                source_bytes: origins,
            });
        }
        Ok(())
    }
    fn invalidate(&mut self, row: &Row, begin: &Row) -> Result<(), String> {
        effect_row(row)?;
        let operation = row
            .cache_operation
            .as_ref()
            .ok_or("cache operation lacks snapshots")?;
        let address = begin.gpr[((begin.word >> 21) & 31) as usize]
            .wrapping_add_signed(i64::from(begin.word as i16));
        require(
            self.invalidation_enabled
                && same(begin, row)
                && begin.word >> 26 == 0x2f
                && ((begin.word >> 16) & 31) == 16
                && operation.operation == 16
                && (0xffffffff80000000..0xffffffff80800000).contains(&address)
                && address.is_multiple_of(4)
                && operation.virtual_address.0 == address
                && row.address == address as u32 & 0x1fffffff
                && row.cpu
                && row.bank == 0
                && row.offset == 0
                && row.bytes == 0
                && row.value == 0
                && self.active.is_none()
                && self.pending.is_none()
                && self.request.is_none()
                && self.cache_burst.is_none(),
            "cache operation differs from decoded direct-KSEG0 HitInvalidateI",
        )?;
        let slot = ((address >> 5) & 511) as u16;
        let initial = FetchCacheLine {
            slot,
            tag_key: 0,
            index: (slot << 5) & 0xfe0,
            words: [0; 8],
        };
        require(
            operation.before == *self.cache_state.get(&slot).unwrap_or(&initial),
            "cache operation before snapshot differs from tracked resident state",
        )?;
        let hit = operation.before.tag_key == (row.address & !4095) | 1;
        let mut after = operation.before;
        if hit {
            after.tag_key &= !1;
        }
        require(
            operation.after == after,
            "invalid HitInvalidateI cache transition",
        )?;
        let ended_fill = if hit {
            self.cache_slots
                .remove(&slot)
                .map(|index| self.cache_fills[index].fill_ordinal)
        } else {
            None
        };
        self.cache_state.insert(slot, after);
        self.cache_invalidations.push(DmaCacheInvalidation {
            decoder_context: begin.context,
            ordinal: row.ordinal,
            physical: PhysicalAddr(row.address),
            operation: operation.clone(),
            hit,
            ended_fill,
        });
        Ok(())
    }
    fn cached_end(&mut self, begin: &Row, row: &Row, no_scalar: bool) -> Result<(), String> {
        let frame = row
            .cache_line
            .ok_or("cached fetch lacks selected resident snapshot")?;
        require(
            self.cached
                && no_scalar
                && self.cache_burst.is_none()
                && row.context == begin.context
                && row.pc == begin.pc
                && row.phase == begin.phase
                && row.address == begin.address
                && row.cpu
                && row.bytes == 0
                && row.offset == 0
                && row.fetch == begin.fetch
                && row.mapping == begin.mapping
                && row.value <= u32::MAX as u64,
            "cached fetch completion differs from scope",
        )?;
        frame.validate(
            GuestVirtualAddr(row.pc),
            FetchAccess {
                physical: PhysicalAddr(row.address),
                cached: true,
            },
            row.value as u32,
        )?;
        let fill = self
            .cache_slots
            .get(&frame.slot)
            .map(|index| &self.cache_fills[*index])
            .ok_or("cached fetch lacks captured resident fill")?;
        require(
            fill.cache_line == frame,
            "cached fetch snapshot differs from resident fill",
        )?;
        let lane = row.address as usize & 31;
        self.pending = Some(PendingFetch::Cached(self.cached_fetches.len()));
        let mapping = begin
            .mapping
            .as_ref()
            .map(|observation| {
                self.tlb
                    .as_ref()
                    .ok_or("mapped consumption lacks TLB profile")?
                    .fetch(begin.pc, PhysicalAddr(begin.address), observation)
            })
            .transpose()?;
        self.cached_fetches.push(CachedDmaCpuFetch {
            mapping,
            fetch_context: begin.context,
            end_ordinal: row.ordinal,
            decoder_context: 0,
            pc: GuestVirtualAddr(row.pc),
            physical: PhysicalAddr(row.address),
            word: row.value as u32,
            burst_ordinal: fill.burst_ordinal,
            fill_ordinal: fill.fill_ordinal,
            origins: std::array::from_fn(|n| fill.source_bytes[lane + n].clone()),
        });
        Ok(())
    }
    fn imem_ingress(
        &mut self,
        row: Row,
        imem: &mut [u8],
        origins: &mut [SpByteOrigin],
    ) -> Result<(), String> {
        effect_row(&row)?;
        require(
            self.ingress
                && row.bank == 1
                && !row.cpu
                && row.word == 0
                && row.bytes == 8
                && row.gpr.is_empty()
                && row.rgpr.is_empty(),
            "invalid IMEM ingress observation",
        )?;
        let descriptor = row.dma.as_ref().ok_or("IMEM ingress lacks descriptor")?;
        let request = self
            .request
            .as_ref()
            .ok_or("IMEM ingress lacks promotion")?;
        let index = request.writes.len() as u64;
        require(
            request.direction == SpDmaDirection::ImemIngress
                && row.context == request.context
                && index < request.total_words()
                && *descriptor == request.current(index)
                && row.address == descriptor.dram.0
                && row.offset == descriptor.pbus,
            "IMEM ingress disagrees with promoted progression",
        )?;
        if row.kind == Kind::ImemDmaRead {
            require(self.ingress_read.is_none(), "duplicate IMEM DMA read")?;
            let offset = self.offset(row.address, 8)?;
            require(
                payload(row.value, 8)? == self.bytes[offset..offset + 8],
                "IMEM DMA read disagrees with current RAM",
            )?;
            let parents = std::array::from_fn(|n| self.origins[offset + n].clone());
            self.ingress_read = Some((row, parents));
        } else {
            let (read, parents) = self
                .ingress_read
                .take()
                .ok_or("IMEM sink lacks actual RAM read")?;
            require(
                row.context == read.context
                    && row.phase == read.phase
                    && row.address == read.address
                    && row.offset == read.offset
                    && row.dma == read.dma
                    && row.value == read.value,
                "IMEM sink differs from actual DMA read",
            )?;
            let data = payload(row.value, 8)?;
            for (n, value) in data.iter().enumerate() {
                store(
                    imem,
                    origins,
                    (row.offset + n as u32) & 4095,
                    &[*value],
                    SpByteOrigin::ImemDma {
                        promote_context: row.context,
                        read_ordinal: read.ordinal,
                        write_ordinal: row.ordinal,
                        source: PhysicalAddr(row.address + n as u32),
                        parent: parents[n].clone(),
                    },
                )?;
            }
            self.installs.push(RamToImemDmaInstall {
                promote_context: row.context,
                read_ordinal: read.ordinal,
                write_ordinal: row.ordinal,
                descriptor: descriptor.clone(),
                value: row.value,
                source_bytes: parents,
            });
            self.request.as_mut().unwrap().writes.push(row.ordinal);
        }
        Ok(())
    }
    fn dmem_ingress(
        &mut self,
        row: Row,
        dmem: &mut [u8],
        origins: &mut [SpByteOrigin],
    ) -> Result<(), String> {
        effect_row(&row)?;
        require(
            self.dmem_ingress
                && row.bank == 0
                && !row.cpu
                && row.word == 0
                && row.bytes == 4
                && row.gpr.is_empty()
                && row.rgpr.is_empty(),
            "invalid DMEM ingress observation",
        )?;
        let descriptor = row.dma.as_ref().ok_or("DMEM ingress lacks descriptor")?;
        let request = self
            .request
            .as_ref()
            .ok_or("DMEM ingress lacks promotion")?;
        let index = request.writes.len() as u64;
        require(
            request.direction == SpDmaDirection::DmemIngress
                && row.context == request.context
                && index < request.total_words()
                && *descriptor == request.current(index / 2),
            "DMEM ingress disagrees with promoted progression",
        )?;
        if row.kind == Kind::DmemDmaRead {
            require(
                index.is_multiple_of(2) && self.dmem_reads.len() < 2,
                "out-of-order DMEM DMA read",
            )?;
            let lane = self.dmem_reads.len() as u32 * 4;
            require(
                row.address == descriptor.dram.0 + lane
                    && row.offset == (descriptor.pbus + lane) & 4095,
                "DMEM read lane differs from descriptor",
            )?;
            if let Some((previous, _)) = self.dmem_reads.first() {
                require(
                    row.phase == previous.phase && row.pc == previous.pc,
                    "DMEM reads crossed controlled scope",
                )?;
            }
            let offset = self.offset(row.address, 4)?;
            require(
                payload(row.value, 4)? == self.bytes[offset..offset + 4],
                "DMEM DMA read disagrees with current RAM",
            )?;
            let parents = std::array::from_fn(|n| self.origins[offset + n].clone());
            self.dmem_reads.push((row, parents));
        } else {
            require(
                self.dmem_reads.len() == 2,
                "DMEM sink lacks both actual source reads",
            )?;
            let (read, parents) = &self.dmem_reads[(index % 2) as usize];
            require(
                row.phase == read.phase
                    && row.pc == read.pc
                    && row.address == read.address
                    && row.offset == read.offset
                    && row.dma == read.dma
                    && row.value == read.value,
                "DMEM sink differs from its exact source read",
            )?;
            let data = payload(row.value, 4)?;
            for (n, value) in data.iter().enumerate() {
                store(
                    dmem,
                    origins,
                    (row.offset + n as u32) & 4095,
                    &[*value],
                    SpByteOrigin::DmemDma {
                        promote_context: row.context,
                        read_ordinal: read.ordinal,
                        write_ordinal: row.ordinal,
                        source: PhysicalAddr(row.address + n as u32),
                        parent: parents[n].clone(),
                    },
                )?;
            }
            self.dmem_installs.push(RamToDmemDmaWord {
                promote_context: row.context,
                read_ordinal: read.ordinal,
                write_ordinal: row.ordinal,
                descriptor: descriptor.clone(),
                source: PhysicalAddr(row.address),
                offset: row.offset as u16,
                value: row.value as u32,
                source_bytes: parents.clone(),
            });
            self.request.as_mut().unwrap().writes.push(row.ordinal);
            if index % 2 == 1 {
                self.dmem_reads.clear();
            }
        }
        Ok(())
    }
    fn finish(self) -> Result<DmemDmaConsumption, String> {
        require(
            self.active.is_none()
                && self.pending.is_none()
                && self.request.is_none()
                && self.ingress_read.is_none()
                && self.dmem_reads.is_empty()
                && self.cache_burst.is_none()
                && self
                    .pending_dma
                    .as_ref()
                    .is_none_or(|pending| pending.commit.is_none())
                && self.bytes == self.final_bytes,
            "incomplete RAM fetch/decoder or contradictory final snapshot",
        )?;
        Ok(DmemDmaConsumption {
            ram_start: self.start,
            ram_bytes: self.bytes.len(),
            initial_ram_sha256: self.initial_sha256,
            final_ram_sha256: sha256(&self.bytes),
            writes: self.writes,
            fetches: self.fetches,
            promoted_requests: self.lifecycle.then_some(self.requests),
            imem_installs: self.ingress.then_some(self.installs),
            dmem_installs: self.dmem_ingress.then_some(self.dmem_installs),
            pending_commits: self.pending_dma.map(|pending| pending.commits),
            cache_fills: self.cached.then_some(self.cache_fills),
            cached_fetches: self.cached.then_some(self.cached_fetches),
            cache_invalidations: self
                .invalidation_enabled
                .then_some(self.cache_invalidations),
            cpu_writes: self.cpu_ram_enabled.then_some(self.cpu_writes),
            tlb_generations: self.tlb.map(|tlb| tlb.generations),
        })
    }
}
fn require(ok: bool, why: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(why.into()) }
}
fn sign32(word: u32) -> u64 {
    (word as i32 as i64) as u64
}
fn same(begin: &Row, row: &Row) -> bool {
    (begin.context, begin.pc, begin.phase, begin.word) == (row.context, row.pc, row.phase, row.word)
}
fn boundary(row: &Row, cpu: bool) -> Result<(), String> {
    require(
        row.bytes == 0
            && row.value == 0
            && row.address == 0
            && row.bank == 0
            && row.offset == 0
            && row.cpu == cpu,
        "invalid instruction-boundary metadata",
    )?;
    if cpu {
        require(
            row.gpr.len() == 32
                && row.gpr[0] == 0
                && row.rgpr.is_empty()
                && row.pc.is_multiple_of(4)
                && row.next == 0
                && !row.halted
                && row.vector_byte == 0,
            "invalid CPU architectural snapshot",
        )
    } else {
        require(
            row.rgpr.len() == 32
                && row.rgpr[0] == 0
                && row.gpr.is_empty()
                && row.pc <= 0xffc
                && row.pc.is_multiple_of(4)
                && row.vector_byte <= 255,
            "invalid RSP architectural snapshot",
        )
    }
}
fn payload(value: u64, width: u32) -> Result<Vec<u8>, String> {
    require(
        matches!(width, 1 | 2 | 4 | 8),
        "unsupported completed byte effect width",
    )?;
    require(
        width == 8 || value < (1u64 << (width * 8)),
        "effect value exceeds width",
    )?;
    Ok(value.to_be_bytes()[8 - width as usize..].to_vec())
}
fn store(
    memory: &mut [u8],
    origins: &mut [SpByteOrigin],
    offset: u32,
    data: &[u8],
    origin: SpByteOrigin,
) -> Result<(), String> {
    require(offset < 4096, "SP byte offset outside bank")?;
    for (index, value) in data.iter().copied().enumerate() {
        let address = (offset as usize + index) & 4095;
        require(
            address < memory.len(),
            "effect escapes declared backing snapshot",
        )?;
        memory[address] = value;
        origins[address] = origin.clone();
    }
    Ok(())
}
fn rsp_lanes(row: &Row) -> Result<(Vec<(u16, u8)>, bool), String> {
    let op = row.word >> 26;
    let rs = ((row.word >> 21) & 31) as usize;
    let rt = ((row.word >> 16) & 31) as usize;
    if row.word == 0 || row.word == 13 {
        return Ok((Vec::new(), row.word == 13));
    }
    let (address, data) = match op {
        0x28 | 0x29 | 0x2b => {
            let width = match op {
                0x28 => 1,
                0x29 => 2,
                _ => 4,
            };
            (
                row.rgpr[rs].wrapping_add_signed(i32::from(row.word as i16)),
                payload(u64::from(row.rgpr[rt]) & ((1u64 << (width * 8)) - 1), width)?,
            )
        }
        0x3a => {
            require(
                rt == 2 && (row.word >> 11) & 31 == 0 && (row.word >> 7) & 15 == 0,
                "unsupported vector store source/element",
            )?;
            let immediate = ((row.word & 127) as i32 ^ 64) - 64;
            (
                row.rgpr[rs].wrapping_add_signed(immediate),
                vec![row.vector_byte as u8],
            )
        }
        _ => return Err("unsupported RSP producer instruction".into()),
    };
    Ok((
        data.into_iter()
            .enumerate()
            .map(|(i, value)| (((address.wrapping_add(i as u32)) & 4095) as u16, value))
            .collect(),
        false,
    ))
}

fn is_definition(word: u32) -> bool {
    word >> 26 == 0x0d || (word >> 26 == 0 && word & 63 == 0x21 && (word >> 6) & 31 == 0)
}

fn rsp_definition(row: &Row, registers: &[Option<u64>; 32]) -> Option<RspRegisterDefinition> {
    let rs = ((row.word >> 21) & 31) as usize;
    let rt = ((row.word >> 16) & 31) as usize;
    let parent = |r: usize| {
        if r == 0 {
            RspRegisterParent::ArchitecturalZero
        } else if let Some(context) = registers[r] {
            RspRegisterParent::Definition { context }
        } else {
            RspRegisterParent::CapturedInput {
                register: r as u8,
                value: row.rgpr[r],
            }
        }
    };
    let (register, value, expression) = if row.word >> 26 == 0x0d {
        (
            rt,
            row.rgpr[rs] | u32::from(row.word as u16),
            RspDefinitionExpression::Ori {
                source: parent(rs),
                immediate: row.word as u16,
            },
        )
    } else {
        (
            ((row.word >> 11) & 31) as usize,
            row.rgpr[rs].wrapping_add(row.rgpr[rt]),
            RspDefinitionExpression::Addu {
                left: parent(rs),
                right: parent(rt),
            },
        )
    };
    (register != 0).then_some(RspRegisterDefinition {
        context: row.context,
        phase: row.phase,
        pc: row.pc as u16,
        word: row.word,
        register: register as u8,
        value,
        expression,
    })
}

/// Verify a complete externally committed controlled chronology. No fixture
/// phase numbers, fixed code PCs, payloads or certificate counts are assumed.
pub fn inspect_rsp_cpu_imem_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<RspCpuImemReport, String> {
    require(
        source.len() <= 64 * 1024 * 1024,
        "composed source exceeds supported bound",
    )?;
    let digest = sha256(source);
    require(
        digest == expected_sha256,
        "RSP/CPU composition source receipt mismatch",
    )?;
    let h: History = serde_json::from_slice(source).map_err(|e| e.to_string())?;
    let mapped_enabled = h.format == MAPPED_FORMAT && h.profile == MAPPED_PROFILE;
    let target_enabled =
        mapped_enabled || (h.format == EPC_TARGET_FORMAT && h.profile == EPC_TARGET_PROFILE);
    let epc_enabled = target_enabled || (h.format == EPC_FORMAT && h.profile == EPC_PROFILE);
    let return_enabled = epc_enabled || (h.format == RETURN_FORMAT && h.profile == RETURN_PROFILE);
    let exception_enabled =
        return_enabled || (h.format == EXCEPTION_FORMAT && h.profile == EXCEPTION_PROFILE);
    let transform_enabled = exception_enabled
        || (h.format == CPU_TRANSFORM_FORMAT && h.profile == CPU_TRANSFORM_PROFILE);
    let cpu_ram_enabled =
        transform_enabled || (h.format == CPU_RAM_FORMAT && h.profile == CPU_RAM_PROFILE);
    let invalidation_enabled =
        cpu_ram_enabled || (h.format == INVALIDATION_FORMAT && h.profile == INVALIDATION_PROFILE);
    let cached_enabled =
        invalidation_enabled || (h.format == CACHED_DMA_FORMAT && h.profile == CACHED_DMA_PROFILE);
    let decoded_dma_enabled =
        cached_enabled || (h.format == DECODED_DMA_FORMAT && h.profile == DECODED_DMA_PROFILE);
    let pending_enabled =
        decoded_dma_enabled || (h.format == PENDING_DMA_FORMAT && h.profile == PENDING_DMA_PROFILE);
    let dmem_ingress_enabled =
        pending_enabled || (h.format == DMEM_INGRESS_FORMAT && h.profile == DMEM_INGRESS_PROFILE);
    let ingress_enabled = dmem_ingress_enabled
        || (h.format == DMA_ROUNDTRIP_FORMAT && h.profile == DMA_ROUNDTRIP_PROFILE);
    let lifecycle_enabled =
        ingress_enabled || (h.format == DMA_LIFECYCLE_FORMAT && h.profile == DMA_LIFECYCLE_PROFILE);
    let dma_enabled = lifecycle_enabled || (h.format == DMA_FORMAT && h.profile == DMA_PROFILE);
    let execution_enabled =
        dma_enabled || (h.format == EXECUTION_FORMAT && h.profile == EXECUTION_PROFILE);
    let reads_enabled = execution_enabled || (h.format == READ_FORMAT && h.profile == READ_PROFILE);
    let definitions_enabled =
        reads_enabled || (h.format == DEFINITION_FORMAT && h.profile == DEFINITION_PROFILE);
    require(
        (h.format == FORMAT && h.profile == PROFILE) || definitions_enabled,
        "unsupported RSP/CPU composition profile",
    )?;
    require(
        !h.events.is_empty() && h.events.len() <= 1_000_000,
        "invalid composed event count",
    )?;
    require(
        [h.initial_dmem.len(), h.initial_imem.len()]
            .into_iter()
            .all(|len| (4..=4096).contains(&len) && len.is_multiple_of(4)),
        "invalid declared backing snapshots",
    )?;
    require(
        !execution_enabled || h.initial_imem.len() == 4096,
        "IMEM consumption requires the complete initial bank",
    )?;
    require(
        !dma_enabled || h.initial_dmem.len() == 4096,
        "DMA composition requires the complete DMEM bank",
    )?;
    require(
        dma_enabled == h.ram.is_some(),
        "RAM snapshot does not match source profile",
    )?;
    let mut ram = h
        .ram
        .map(|snapshot| {
            RamReplay::new(
                snapshot,
                lifecycle_enabled,
                ingress_enabled,
                dmem_ingress_enabled,
            )
        })
        .transpose()?;
    if let Some(ram) = &mut ram {
        ram.cached = cached_enabled;
        ram.invalidation_enabled = invalidation_enabled;
        ram.cpu_ram_enabled = cpu_ram_enabled;
    }
    require(
        pending_enabled == h.initial_pending.is_some(),
        "pending DMA seed outside profile or missing",
    )?;
    if let Some(snapshot) = h.initial_pending {
        require(
            snapshot.bank <= 1 && valid_dmem_dma_descriptor(&snapshot.descriptor),
            "invalid initial pending DMA state",
        )?;
        ram.as_mut()
            .ok_or("pending DMA lacks RAM profile")?
            .pending_dma = Some(PendingDmaReplay {
            snapshot,
            direction: None,
            commit: None,
            pbus_writer: None,
            dram_writer: None,
            commits: Vec::new(),
            commit_decoder: None,
        });
    }
    require(
        mapped_enabled == h.initial_tlb.is_some(),
        "initial TLB state does not match profile",
    )?;
    if let Some(initial) = h.initial_tlb {
        ram.as_mut().ok_or("TLB composition lacks RAM profile")?.tlb =
            Some(TlbReplay::new(initial)?);
    }
    let records = h.events.len();
    let mut dmem = h.initial_dmem;
    let mut imem = h.initial_imem;
    let unknown = SpByteOrigin::Unknown { cut_ordinal: None };
    let mut dorig = vec![unknown.clone(); dmem.len()];
    let mut iorig = vec![unknown; imem.len()];
    let mut registers: [Option<Loaded>; 32] = std::array::from_fn(|_| None);
    let mut active: Option<Active> = None;
    let mut previous_cpu: Option<Row> = None;
    let mut exception_roots: Vec<CpuExceptionRoot> = Vec::new();
    let mut pending_exception = None;
    let mut await_root: Option<usize> = None;
    let mut live_exception: Option<usize> = None;
    let mut current_epc_write: Option<usize> = None;
    let mut epc_registers: [Option<EpcHeld>; 32] = std::array::from_fn(|_| None);
    let mut epc_reads = Vec::new();
    let mut epc_writes = Vec::new();
    let mut pending_epc: Option<(Kind, usize)> = None;
    let mut pending_tlb = false;
    let mut eret_returns: Vec<CpuEretReturn> = Vec::new();
    let mut pending_return: Option<usize> = None;
    let mut await_return: Option<usize> = None;
    let mut cpu_reentry: Option<Row> = None;
    let mut previous_rsp: Option<Row> = None;
    let mut rsp_registers = [None; 32];
    let mut rsp_definitions = Vec::new();
    let mut imem_fetches = Vec::new();
    let mut phase = 0;
    let mut copies = Vec::new();
    let mut cpu_instructions = 0;
    let mut rsp_instructions = 0;
    for (index, row) in h.events.into_iter().enumerate() {
        require(
            row.ordinal == index as u64 + 1 && row.phase != 0 && row.phase >= phase,
            "noncontiguous event identity or phase order",
        )?;
        phase = row.phase;
        require(
            row.tlb_state.is_none()
                || (mapped_enabled
                    && (row.kind == Kind::TlbWrite
                        || (row.kind == Kind::CpuBegin && row.word == 0x42000002))),
            "TLB state outside decoded TLBWI boundary",
        )?;
        require(
            row.mapping.is_none()
                || (mapped_enabled
                    && matches!(row.kind, Kind::RamFetchBegin | Kind::RamFetchEnd)
                    && row.fetch.as_ref().is_some_and(|access| access.cached)),
            "mapping observation outside fetch boundary",
        )?;
        require(
            !pending_tlb || row.kind == Kind::CpuEnd,
            "TLBWI write not immediately completed",
        )?;
        require(
            row.epc_state.is_none()
                || (epc_enabled
                    && (matches!(row.kind, Kind::EpcRead | Kind::EpcWrite)
                        || (row.kind == Kind::CpuBegin && epc_instruction(row.word)))),
            "EPC metadata outside controlled CP0 boundary",
        )?;
        require(
            pending_epc.is_none() || row.kind == Kind::CpuEnd,
            "EPC access was not immediately completed by decoder",
        )?;
        require(
            row.return_state.is_none()
                || (return_enabled
                    && (row.kind == Kind::ReturnTransfer
                        || (row.kind == Kind::CpuBegin && row.word == 0x42000018))),
            "return state outside controlled ERET boundary",
        )?;
        require(
            pending_return.is_none() || row.kind == Kind::CpuEnd,
            "return transfer was not immediately completed by its decoder",
        )?;
        if let Some(index) = await_return {
            require(
                matches!(
                    row.kind,
                    Kind::RamFetchBegin
                        | Kind::CacheBurstRead
                        | Kind::CacheFill
                        | Kind::RamFetchEnd
                        | Kind::CpuBegin
                ) && row.pc == eret_returns[index].after.state.pc.0,
                "ERET target was not immediately fetched and decoded",
            )?;
        }
        require(
            row.exception_state.is_none()
                || (exception_enabled
                    && (row.kind == Kind::ExceptionTransfer
                        || (row.kind == Kind::CpuBegin && break_word(row.word)))),
            "exception state outside controlled BREAK boundary",
        )?;
        require(
            pending_exception.is_none() || row.kind == Kind::CpuEnd,
            "exception transfer was not immediately completed by its decoder",
        )?;
        if let Some(index) = await_root {
            require(
                matches!(
                    row.kind,
                    Kind::RamFetchBegin
                        | Kind::CacheBurstRead
                        | Kind::CacheFill
                        | Kind::RamFetchEnd
                        | Kind::CpuBegin
                ) && row.pc == exception_roots[index].root.root.0,
                "exception root was not immediately fetched and decoded",
            )?;
        }
        require(
            row.cache_operation.is_none()
                || (invalidation_enabled && row.kind == Kind::CacheOperation),
            "cache operation metadata outside decoded operation boundary",
        )?;
        require(
            row.cache_line.is_none()
                || (cached_enabled
                    && (matches!(row.kind, Kind::CacheBurstRead | Kind::CacheFill)
                        || (row.kind == Kind::RamFetchEnd
                            && row.fetch.as_ref().is_some_and(|access| access.cached)))),
            "cache snapshot outside controlled cache boundary",
        )?;
        require(
            cpu_reentry.is_none()
                || (cpu_ram_enabled && row.kind == Kind::RamRead)
                || matches!(
                    row.kind,
                    Kind::RamFetchBegin
                        | Kind::RamFetchEnd
                        | Kind::CacheBurstRead
                        | Kind::CacheFill
                        | Kind::CpuBegin
                ),
            "actor interleaved opaque CPU control seed",
        )?;
        require(
            row.dma.is_none()
                || (dma_enabled && row.kind == Kind::RamWrite)
                || (lifecycle_enabled && row.kind == Kind::DmaPromote)
                || (pending_enabled && row.kind == Kind::DmaPendingWrite)
                || (ingress_enabled && matches!(row.kind, Kind::ImemDmaRead | Kind::ImemDmaWrite))
                || (dmem_ingress_enabled
                    && matches!(row.kind, Kind::DmemDmaRead | Kind::DmemDmaWrite)),
            "DMA metadata outside completed RAM write",
        )?;
        require(
            row.fetch.is_none()
                || (dma_enabled && matches!(row.kind, Kind::RamFetchBegin | Kind::RamFetchEnd)),
            "fetch metadata outside RAM boundary",
        )?;
        require(
            row.dma_direction.is_none()
                || (dmem_ingress_enabled
                    && matches!(row.kind, Kind::DmaPromote | Kind::DmaComplete))
                || (pending_enabled && row.kind == Kind::DmaPendingWrite),
            "DMA direction outside lifecycle boundary",
        )?;
        require(
            row.pending_full.is_none() || (pending_enabled && row.kind == Kind::DmaPendingWrite),
            "pending FULL outside register write",
        )?;
        if let Some(ram) = &ram {
            require(
                ram.request.is_some()
                    || ram
                        .pending_dma
                        .as_ref()
                        .is_none_or(|pending| pending.commit.is_none())
                    || row.kind == Kind::DmaPromote,
                "idle FULL pending DMA was not immediately promoted",
            )?;
            require(
                ram.dmem_reads.len() != 1 || row.kind == Kind::DmemDmaRead,
                "DMEM sink/actor preceded second source read",
            )?;
            require(
                ram.dmem_reads.len() != 2 || row.kind == Kind::DmemDmaWrite,
                "interleaved DMEM source reads/sinks",
            )?;
            require(
                ram.ingress_read.is_none() || row.kind == Kind::ImemDmaWrite,
                "interleaved IMEM DMA read/sink",
            )?;
            require(
                ram.active.is_none()
                    || matches!(
                        row.kind,
                        Kind::RamRead | Kind::RamFetchEnd | Kind::CacheBurstRead | Kind::CacheFill
                    ),
                "interleaved controlled RAM fetch",
            )?;
            require(
                ram.pending.is_none() || row.kind == Kind::CpuBegin,
                "completed RAM fetch was not immediately decoded",
            )?;
        }
        match row.kind {
            Kind::TlbWrite => {
                effect_row(&row)?;
                let Some(Active::Cpu {
                    begin,
                    read,
                    written,
                }) = &mut active
                else {
                    return Err("TLB write lacks CPU decoder".into());
                };
                require(
                    mapped_enabled
                        && !*written
                        && read.is_none()
                        && same(begin, &row)
                        && begin.word == 0x42000002
                        && row.cpu
                        && row.address
                            == begin
                                .tlb_state
                                .as_ref()
                                .map_or(u32::MAX, |state| state.index)
                        && row.bank == 0
                        && row.offset == 0
                        && row.bytes == 0
                        && row.value == 0,
                    "duplicate, unscoped or unsupported TLBWI write",
                )?;
                ram.as_mut()
                    .and_then(|ram| ram.tlb.as_mut())
                    .ok_or("TLB write lacks profile")?
                    .write(
                        begin.pc,
                        begin.context,
                        row.ordinal,
                        begin.tlb_state.as_ref().ok_or("TLBWI lacks before state")?,
                        row.tlb_state
                            .as_ref()
                            .ok_or("TLBWI lacks completed table")?,
                    )?;
                *written = true;
                pending_tlb = true;
            }
            Kind::EpcRead | Kind::EpcWrite => {
                let Some(Active::Cpu {
                    begin,
                    read,
                    written,
                }) = &mut active
                else {
                    return Err("EPC access lacks CPU decoder".into());
                };
                require(
                    epc_enabled && read.is_none() && !*written,
                    "duplicate or unsupported EPC effect",
                )?;
                let producer = live_exception.ok_or("EPC producer generation is unknown")?;
                let current = current_epc_write.map(|index| &epc_writes[index]);
                let index = if row.kind == Kind::EpcRead {
                    let receipt = epc_read(begin, &row, &exception_roots[producer], current)?;
                    epc_reads.push(receipt);
                    epc_reads.len() - 1
                } else {
                    let rt = ((begin.word >> 16) & 31) as usize;
                    let receipt = epc_write(
                        begin,
                        &row,
                        &exception_roots[producer],
                        current,
                        epc_registers[rt].as_ref(),
                        target_enabled,
                    )?;
                    epc_writes.push(receipt);
                    current_epc_write = Some(epc_writes.len() - 1);
                    epc_writes.len() - 1
                };
                pending_epc = Some((row.kind, index));
                *written = true;
            }
            Kind::ReturnTransfer => {
                let Some(Active::Cpu {
                    begin,
                    read,
                    written,
                }) = &mut active
                else {
                    return Err("return transfer lacks CPU decoder".into());
                };
                require(
                    return_enabled && read.is_none() && !*written,
                    "duplicate or unsupported ERET transfer",
                )?;
                let producer = live_exception
                    .take()
                    .ok_or("ERET selected EPC generation is unknown")?;
                let receipt = eret_transfer(
                    begin,
                    &row,
                    &exception_roots[producer],
                    current_epc_write.map(|index| &epc_writes[index]),
                )?;
                current_epc_write = None;
                epc_registers.fill(None);
                pending_return = Some(eret_returns.len());
                eret_returns.push(receipt);
                *written = true;
            }
            Kind::ExceptionTransfer => {
                let Some(Active::Cpu {
                    begin,
                    read,
                    written,
                }) = &mut active
                else {
                    return Err("exception transfer lacks CPU decoder".into());
                };
                require(
                    exception_enabled && read.is_none() && !*written && await_root.is_none(),
                    "duplicate or unsupported exception transfer",
                )?;
                let receipt = break_transfer(begin, &row)?;
                pending_exception = Some(exception_roots.len());
                live_exception = pending_exception;
                current_epc_write = None;
                epc_registers.fill(None);
                exception_roots.push(receipt);
                *written = true;
            }
            Kind::CpuRamWrite => {
                let Some(Active::Cpu {
                    begin,
                    read,
                    written,
                }) = &mut active
                else {
                    return Err("CPU RAM write lacks decoder scope".into());
                };
                require(
                    cpu_ram_enabled && read.is_none() && !*written,
                    "duplicate or unsupported CPU RAM store effect",
                )?;
                let rt = ((begin.word >> 16) & 31) as usize;
                ram.as_mut()
                    .ok_or("CPU RAM write lacks RAM profile")?
                    .cpu_write(&row, begin, registers[rt].as_ref())?;
                *written = true;
            }
            Kind::CacheOperation => {
                let Some(Active::Cpu {
                    begin,
                    read,
                    written,
                }) = &mut active
                else {
                    return Err("cache operation lacks CPU decoder scope".into());
                };
                require(
                    invalidation_enabled && read.is_none() && !*written,
                    "duplicate or unsupported cache operation effect",
                )?;
                ram.as_mut()
                    .ok_or("cache operation lacks RAM profile")?
                    .invalidate(&row, begin)?;
                *written = true;
            }
            Kind::CpuReentry => {
                boundary(&row, true)?;
                require(
                    cached_enabled
                        && active.is_none()
                        && row.word == 0
                        && row.context == row.ordinal
                        && previous_cpu
                            .as_ref()
                            .is_some_and(|previous| previous.gpr == row.gpr)
                        && ram.as_ref().is_some_and(|ram| {
                            ram.active.is_none() && ram.pending.is_none() && ram.request.is_none()
                        }),
                    "invalid opaque CPU control reentry",
                )?;
                registers.fill(None);
                live_exception = None;
                current_epc_write = None;
                epc_registers.fill(None);
                previous_cpu = None;
                cpu_reentry = Some(row);
            }
            Kind::CacheBurstRead | Kind::CacheFill => {
                require(
                    cached_enabled && active.is_none(),
                    "cache observation interleaves decoder or lacks profile",
                )?;
                ram.as_mut()
                    .ok_or("cache observation lacks RAM")?
                    .cache(row)?;
            }
            Kind::DmaPendingWrite => {
                require(
                    pending_enabled,
                    "pending DMA write outside controlled profile",
                )?;
                let decoded = match &mut active {
                    Some(Active::Cpu {
                        begin,
                        read,
                        written,
                    }) => {
                        require(
                            decoded_dma_enabled && read.is_none() && !*written,
                            "invalid decoded pending DMA effect scope",
                        )?;
                        *written = true;
                        Some(&*begin)
                    }
                    None => None,
                    _ => return Err("pending DMA write inside RSP instruction".into()),
                };
                ram.as_mut()
                    .and_then(|ram| ram.pending_dma.as_mut())
                    .ok_or("pending DMA state missing")?
                    .write(&row, decoded)?;
            }
            Kind::DmemDmaRead | Kind::DmemDmaWrite => {
                require(
                    active.is_none(),
                    "DMEM ingress interleaves decoded instruction",
                )?;
                ram.as_mut()
                    .ok_or("DMEM ingress outside profile")?
                    .dmem_ingress(row, &mut dmem, &mut dorig)?;
            }
            Kind::ImemDmaRead | Kind::ImemDmaWrite => {
                require(
                    active.is_none(),
                    "IMEM ingress interleaves decoded instruction",
                )?;
                ram.as_mut()
                    .ok_or("IMEM ingress outside profile")?
                    .imem_ingress(row, &mut imem, &mut iorig)?;
            }
            Kind::RamWrite
            | Kind::RamRead
            | Kind::RamFetchBegin
            | Kind::RamFetchEnd
            | Kind::DmaPromote
            | Kind::DmaComplete => {
                if let Some(Active::Cpu {
                    begin,
                    written,
                    read,
                }) = &active
                {
                    require(
                        decoded_dma_enabled
                            && row.kind == Kind::DmaPromote
                            && *written
                            && read.is_none()
                            && row.pc == begin.pc
                            && row.phase == begin.phase
                            && ram
                                .as_ref()
                                .and_then(|ram| ram.pending_dma.as_ref())
                                .is_some_and(|pending| {
                                    pending.commit == row.ordinal.checked_sub(1)
                                        && pending.commit_decoder == Some(begin.context)
                                }),
                        "DMA promotion lacks synchronous decoded length-write scope",
                    )?;
                } else {
                    require(
                        active.is_none(),
                        "RAM observation interleaves decoded instruction",
                    )?;
                }
                ram.as_mut()
                    .ok_or("RAM observation outside DMA profile")?
                    .observe(row, &dmem, &dorig)?;
            }
            Kind::OpaqueImemSeed => {
                effect_row(&row)?;
                require(
                    execution_enabled
                        && active.is_none()
                        && row.context == 0
                        && !row.cpu
                        && row.word == 0
                        && row.bank == 1
                        && row.bytes == 4
                        && row.address == row.offset
                        && row.offset < 4096
                        && row.offset.is_multiple_of(4),
                    "invalid controlled opaque IMEM initialization",
                )?;
                store(
                    &mut imem,
                    &mut iorig,
                    row.offset,
                    &payload(row.value, row.bytes)?,
                    SpByteOrigin::Unknown {
                        cut_ordinal: Some(row.ordinal),
                    },
                )?;
            }
            Kind::CpuBegin => {
                require(
                    active.is_none() && row.context == row.ordinal,
                    "invalid CPU begin context",
                )?;
                boundary(&row, true)?;
                require(
                    row.word != 0x42000018 || (return_enabled && row.return_state.is_some()),
                    "ERET lacks controlled return profile/state",
                )?;
                require(
                    !break_word(row.word) || (exception_enabled && row.exception_state.is_some()),
                    "BREAK lacks controlled exception profile/state",
                )?;
                if let Some(seed) = cpu_reentry.take() {
                    require(
                        row.pc == seed.pc && row.phase == seed.phase && row.gpr == seed.gpr,
                        "CPU decoder differs from opaque control seed",
                    )?;
                }
                if let Some(index) = await_root.take() {
                    let ram = ram.as_ref().ok_or("exception root lacks RAM profile")?;
                    let fetch_context = match ram
                        .pending
                        .as_ref()
                        .ok_or("exception handler lacks completed fetch")?
                    {
                        PendingFetch::Cached(index) => ram.cached_fetches[*index].fetch_context,
                        PendingFetch::Uncached(_) => {
                            return Err("controlled exception handler must use cached root".into());
                        }
                    };
                    exception_roots[index].fetch_context = fetch_context;
                    exception_roots[index].decoder_context = row.context;
                }
                if let Some(index) = await_return.take() {
                    let ram = ram.as_ref().ok_or("ERET target lacks RAM profile")?;
                    let fetch_context = match ram
                        .pending
                        .as_ref()
                        .ok_or("ERET target lacks completed fetch")?
                    {
                        PendingFetch::Cached(index) => ram.cached_fetches[*index].fetch_context,
                        PendingFetch::Uncached(_) => {
                            return Err("controlled ERET target must be cached".into());
                        }
                    };
                    eret_returns[index].fetch_context = fetch_context;
                    eret_returns[index].target_decoder_context = row.context;
                }
                if let Some(ram) = &mut ram {
                    ram.bind(&row)?;
                }
                if let Some(previous) = &previous_cpu {
                    let next_pc = if break_word(previous.word) {
                        exception_roots.last().map(|receipt| receipt.root.root.0)
                    } else if previous.word == 0x42000018 {
                        eret_returns.last().map(|receipt| receipt.after.state.pc.0)
                    } else {
                        previous.pc.checked_add(4)
                    };
                    require(
                        row.gpr == previous.gpr && next_pc == Some(row.pc),
                        "CPU register/control continuity mismatch",
                    )?;
                }
                active = Some(Active::Cpu {
                    begin: row,
                    read: None,
                    written: false,
                });
            }
            Kind::RspBegin => {
                require(
                    active.is_none() && row.context == row.ordinal,
                    "invalid RSP begin context",
                )?;
                boundary(&row, false)?;
                if execution_enabled {
                    let offset = row.pc as usize;
                    let observed: [u8; 4] = imem[offset..offset + 4]
                        .try_into()
                        .expect("bounded aligned RSP PC");
                    require(
                        u32::from_be_bytes(observed) == row.word,
                        "RSP decoded word disagrees with current IMEM bytes",
                    )?;
                    imem_fetches.push(RspImemFetch {
                        context: row.context,
                        pc: row.pc as u16,
                        word: row.word,
                        origins: std::array::from_fn(|n| iorig[offset + n].clone()),
                    });
                }
                require(
                    !row.halted && u64::from(row.next) == row.pc,
                    "RSP begin is not an active decoded instruction",
                )?;
                if let Some(previous) = &previous_rsp
                    && previous.phase == row.phase
                {
                    require(
                        row.rgpr == previous.rgpr && row.pc == u64::from(previous.next),
                        "RSP same-phase continuity mismatch",
                    )?;
                }
                if previous_rsp
                    .as_ref()
                    .is_none_or(|previous| previous.phase != row.phase)
                {
                    rsp_registers.fill(None);
                }
                let mut expected_gpr = row.rgpr.clone();
                let (lanes, breaking, definition) = if reads_enabled && row.word >> 26 == 0x23 {
                    (Vec::new(), false, None)
                } else if definitions_enabled && is_definition(row.word) {
                    let definition = rsp_definition(&row, &rsp_registers);
                    if let Some(d) = &definition {
                        expected_gpr[d.register as usize] = d.value;
                    }
                    (Vec::new(), false, definition)
                } else {
                    let (lanes, breaking) = rsp_lanes(&row)?;
                    (lanes, breaking, None)
                };
                active = Some(Active::Rsp {
                    begin: row,
                    lanes,
                    consumed: 0,
                    breaking,
                    expected_gpr,
                    definition,
                    read: false,
                });
            }
            Kind::RspRead => {
                effect_row(&row)?;
                let Some(Active::Rsp {
                    begin,
                    expected_gpr,
                    definition,
                    read,
                    ..
                }) = &mut active
                else {
                    return Err("unscoped RSP DMEM read".into());
                };
                let rs = ((begin.word >> 21) & 31) as usize;
                let rt = ((begin.word >> 16) & 31) as usize;
                let address = begin.rgpr[rs].wrapping_add_signed(i32::from(begin.word as i16));
                require(
                    reads_enabled
                        && begin.word >> 26 == 0x23
                        && !*read
                        && same(begin, &row)
                        && !row.cpu
                        && row.bank == 0
                        && row.bytes == 4
                        && row.address == address
                        && row.offset == address & 4095,
                    "RSP read does not match decoded LW/context/address",
                )?;
                let offsets: [usize; 4] =
                    std::array::from_fn(|n| ((address.wrapping_add(n as u32)) & 4095) as usize);
                require(
                    offsets.iter().all(|n| *n < dmem.len()),
                    "RSP read escapes declared DMEM snapshot",
                )?;
                let payload: [u8; 4] = std::array::from_fn(|n| dmem[offsets[n]]);
                require(
                    row.value == u64::from(u32::from_be_bytes(payload)),
                    "RSP completed read disagrees with modeled byte state",
                )?;
                *read = true;
                if rt != 0 {
                    expected_gpr[rt] = row.value as u32;
                    *definition = Some(RspRegisterDefinition {
                        context: begin.context,
                        phase: begin.phase,
                        pc: begin.pc as u16,
                        word: begin.word,
                        register: rt as u8,
                        value: row.value as u32,
                        expression: RspDefinitionExpression::DmemWordLoad(Box::new(
                            RspDmemWordRead {
                                read_ordinal: row.ordinal,
                                address,
                                offset: row.offset as u16,
                                payload,
                                origins: std::array::from_fn(|n| dorig[offsets[n]].clone()),
                            },
                        )),
                    });
                }
            }
            Kind::RspSink => {
                effect_row(&row)?;
                require(
                    row.bytes == 1,
                    "RSP profile requires actual Byte sink callbacks",
                )?;
                let Some(Active::Rsp {
                    begin,
                    lanes,
                    consumed,
                    ..
                }) = &mut active
                else {
                    return Err("RSP sink lacks instruction context".into());
                };
                require(
                    same(begin, &row)
                        && !row.cpu
                        && row.bank == 0
                        && row.address == row.offset
                        && row.gpr.is_empty()
                        && row.rgpr.is_empty(),
                    "RSP sink context/domain mismatch",
                )?;
                let data = payload(row.value, row.bytes)?;
                require(
                    *consumed + data.len() <= lanes.len(),
                    "RSP sink exceeds decoded store",
                )?;
                for (n, value) in data.iter().copied().enumerate() {
                    require(
                        lanes[*consumed + n] == (((row.offset + n as u32) & 4095) as u16, value),
                        "RSP sink differs from decoded operand/lane",
                    )?;
                }
                store(
                    &mut dmem,
                    &mut dorig,
                    row.offset,
                    &data,
                    SpByteOrigin::Rsp {
                        context: row.context,
                        pc: row.pc as u16,
                        word: row.word,
                        write_ordinal: row.ordinal,
                        source_definition: if definitions_enabled
                            && matches!(row.word >> 26, 0x28 | 0x29 | 0x2b)
                        {
                            rsp_registers[((row.word >> 16) & 31) as usize]
                        } else {
                            None
                        },
                    },
                )?;
                *consumed += data.len();
            }
            Kind::ForeignSink => {
                effect_row(&row)?;
                require(
                    !row.cpu
                        && row.bank == 0
                        && row.address == row.offset
                        && row.gpr.is_empty()
                        && row.rgpr.is_empty(),
                    "invalid foreign DMEM sink",
                )?;
                match &active {
                    Some(Active::Cpu { begin, written, .. }) => {
                        require(
                            same(begin, &row) && begin.word >> 26 == 0x2b && !*written,
                            "foreign sink CPU context mismatch",
                        )?;
                        let rs = ((begin.word >> 21) & 31) as usize;
                        let rt = ((begin.word >> 16) & 31) as usize;
                        let address =
                            begin.gpr[rs].wrapping_add_signed(i64::from(begin.word as i16));
                        require(
                            (0xffffffffa4000000..=0xffffffffa403ffff).contains(&address)
                                && address & 3 == 0
                                && address & 0x1000 == 0
                                && row.offset == (address as u32 & 0xffc)
                                && row.bytes == 4
                                && row.value == u64::from(begin.gpr[rt] as u32),
                            "foreign CPU DMEM sink differs from decoded store",
                        )?;
                    }
                    None => require(
                        row.context == 0 && row.word == 0,
                        "foreign sink has stale context",
                    )?,
                    _ => return Err("foreign mutation inside RSP instruction".into()),
                }
                store(
                    &mut dmem,
                    &mut dorig,
                    row.offset,
                    &payload(row.value, row.bytes)?,
                    SpByteOrigin::Unknown {
                        cut_ordinal: Some(row.ordinal),
                    },
                )?;
            }
            Kind::SpRead | Kind::SpWrite => {
                effect_row(&row)?;
                require(
                    row.cpu
                        && row.bytes == 4
                        && row.value <= u64::from(u32::MAX)
                        && (0x04000000..=0x0403ffff).contains(&row.address)
                        && row.address.is_multiple_of(4)
                        && row.bank == (row.address >> 12) & 1
                        && row.offset == row.address & 0xffc
                        && row.gpr.is_empty()
                        && row.rgpr.is_empty(),
                    "invalid normalized CPU SP Word effect",
                )?;
                let mut rt = 0;
                if let Some(Active::Cpu {
                    begin,
                    read,
                    written,
                }) = &mut active
                {
                    require(same(begin, &row), "CPU SP effect context mismatch")?;
                    let op = begin.word >> 26;
                    let rs = ((begin.word >> 21) & 31) as usize;
                    rt = ((begin.word >> 16) & 31) as usize;
                    let virtual_address =
                        begin.gpr[rs].wrapping_add_signed(i64::from(begin.word as i16));
                    require(
                        (0xffffffffa4000000..=0xffffffffa403ffff).contains(&virtual_address)
                            && (virtual_address & 0x1fffffff) == u64::from(row.address),
                        "SP effect does not match decoded direct KSEG1 address",
                    )?;
                    if row.kind == Kind::SpRead {
                        require(
                            op == 0x23 && read.is_none() && !*written,
                            "invalid decoded SP load effect",
                        )?;
                    } else {
                        require(
                            op == 0x2b
                                && read.is_none()
                                && !*written
                                && row.value == u64::from(begin.gpr[rt] as u32),
                            "invalid decoded SP store effect",
                        )?;
                        *written = true;
                    }
                } else {
                    require(
                        active.is_none()
                            && row.kind == Kind::SpWrite
                            && row.context == 0
                            && row.word == 0,
                        "unscoped SP read or stale instruction attribution",
                    )?;
                }
                let (memory, origins) = if row.bank == 0 {
                    (&mut dmem, &mut dorig)
                } else {
                    (&mut imem, &mut iorig)
                };
                let offset = row.offset as usize;
                require(
                    offset + 4 <= memory.len(),
                    "CPU Word escapes declared backing snapshot",
                )?;
                if row.kind == Kind::SpRead {
                    require(
                        memory[offset..offset + 4] == (row.value as u32).to_be_bytes(),
                        "CPU load differs from observed backing",
                    )?;
                    let loaded = Loaded {
                        context: row.context,
                        read: row.ordinal,
                        register: rt,
                        bits: sign32(row.value as u32),
                        address: PhysicalAddr(row.address),
                        origins: std::array::from_fn(|i| origins[offset + i].clone()),
                        transform: None,
                    };
                    if let Some(Active::Cpu { read, .. }) = &mut active {
                        *read = Some(loaded);
                    }
                } else {
                    let origin = if row.context == 0 {
                        SpByteOrigin::Unknown {
                            cut_ordinal: Some(row.ordinal),
                        }
                    } else {
                        SpByteOrigin::Cpu {
                            context: row.context,
                            pc: GuestVirtualAddr(row.pc),
                            word: row.word,
                            write_ordinal: row.ordinal,
                        }
                    };
                    store(
                        memory,
                        origins,
                        row.offset,
                        &(row.value as u32).to_be_bytes(),
                        origin,
                    )?;
                    if row.bank == 1
                        && row.context != 0
                        && let Some(parent) = &registers[rt]
                        && parent.transform.is_none()
                    {
                        let Some(Active::Cpu { begin, .. }) = &active else {
                            unreachable!()
                        };
                        require(
                            begin.gpr[rt] == parent.bits,
                            "store source lost captured register definition",
                        )?;
                        copies.push(ImemCopyChain {
                            phase: row.phase,
                            load_context: parent.context,
                            read_ordinal: parent.read,
                            store_context: row.context,
                            write_ordinal: row.ordinal,
                            source_register: rt as u8,
                            source: parent.address,
                            destination: PhysicalAddr(row.address),
                            word: row.value as u32,
                            source_bytes: parent.origins.clone(),
                        });
                    }
                }
            }
            Kind::CpuEnd => {
                boundary(&row, true)?;
                let Some(Active::Cpu {
                    begin,
                    read,
                    written,
                }) = active.take()
                else {
                    return Err("CPU end lacks begin".into());
                };
                require(same(&begin, &row), "CPU end context mismatch")?;
                let mut expected = begin.gpr.clone();
                let op = begin.word >> 26;
                if begin.word == 0x42000002 {
                    require(
                        mapped_enabled && pending_tlb && written && read.is_none(),
                        "TLBWI lacks actual slot write",
                    )?;
                    ram.as_mut()
                        .and_then(|ram| ram.tlb.as_mut())
                        .ok_or("TLBWI lacks profile")?
                        .finish(begin.context, row.ordinal)?;
                    pending_tlb = false;
                } else if epc_instruction(begin.word) {
                    require(
                        epc_enabled && written && read.is_none(),
                        "CP0 instruction lacks completed EPC effect",
                    )?;
                    let (kind, index) = pending_epc
                        .take()
                        .ok_or("CP0 instruction lacks EPC identity")?;
                    let rt = ((begin.word >> 16) & 31) as usize;
                    if kind == Kind::EpcRead {
                        expected[rt] = epc_reads[index].value;
                        registers[rt] = None;
                        epc_registers[rt] = Some(EpcHeld {
                            read: epc_reads[index].clone(),
                            transform: None,
                        });
                    }
                } else if begin.word == 0x42000018 {
                    require(
                        return_enabled && written && read.is_none(),
                        "ERET lacks completed return transfer",
                    )?;
                    await_return = Some(
                        pending_return
                            .take()
                            .ok_or("ERET lacks transfer identity")?,
                    );
                } else if break_word(begin.word) {
                    require(
                        exception_enabled && written && read.is_none(),
                        "BREAK lacks its completed exception transfer",
                    )?;
                    await_root = Some(
                        pending_exception
                            .take()
                            .ok_or("BREAK lacks transfer identity")?,
                    );
                } else if op == 0x23 {
                    let load = read.ok_or("CPU load lacks completed read")?;
                    require(!written, "load has store effect")?;
                    if load.register != 0 {
                        expected[load.register] = load.bits;
                        let register = load.register;
                        registers[register] = Some(load);
                        epc_registers[register] = None;
                    }
                } else if op == 0x2b {
                    require(
                        written && read.is_none(),
                        "CPU store lacks its completed sink",
                    )?;
                } else if op == 0x2f {
                    require(
                        invalidation_enabled && written && read.is_none(),
                        "CACHE lacks its completed validated operation",
                    )?;
                } else if op == 0x0e {
                    require(
                        transform_enabled && read.is_none() && !written,
                        "unsupported XORI or scalar effect on transform",
                    )?;
                    let rs = ((begin.word >> 21) & 31) as usize;
                    let rt = ((begin.word >> 16) & 31) as usize;
                    if rt != 0 {
                        expected[rt] = begin.gpr[rs] ^ u64::from(begin.word as u16);
                        registers[rt] = Loaded::xori(registers[rs].clone(), &begin)?;
                        epc_registers[rt] = if target_enabled {
                            EpcHeld::xori(epc_registers[rs].clone(), &begin)?
                        } else {
                            None
                        };
                    }
                } else {
                    require(
                        read.is_none() && !written,
                        "scalar effect on CPU register instruction",
                    )?;
                    if begin.word != 0 {
                        require(
                            op == 0 && begin.word & 63 == 0x21 && (begin.word >> 6) & 31 == 0,
                            "unsupported CPU register instruction",
                        )?;
                        let rs = ((begin.word >> 21) & 31) as usize;
                        let rt = ((begin.word >> 16) & 31) as usize;
                        let rd = ((begin.word >> 11) & 31) as usize;
                        if rd != 0 {
                            expected[rd] =
                                sign32((begin.gpr[rs] as u32).wrapping_add(begin.gpr[rt] as u32));
                            registers[rd] = None;
                            epc_registers[rd] = None;
                        }
                    }
                }
                require(row.gpr == expected, "CPU instruction result mismatch")?;
                let step = h
                    .steps
                    .get(cpu_instructions)
                    .ok_or("CPU instruction lacks independent step snapshot")?;
                require(
                    step.index as usize == cpu_instructions
                        && (step.phase, step.word, step.pc) == (begin.phase, begin.word, begin.pc)
                        && step.before == begin.gpr
                        && step.after == row.gpr,
                    "CPU decoder snapshots disagree with independent step",
                )?;
                cpu_instructions += 1;
                previous_cpu = Some(row);
            }
            Kind::RspEnd => {
                boundary(&row, false)?;
                let Some(Active::Rsp {
                    begin,
                    lanes,
                    consumed,
                    breaking,
                    expected_gpr,
                    definition,
                    read,
                }) = active.take()
                else {
                    return Err("RSP end lacks begin".into());
                };
                require(
                    same(&begin, &row)
                        && consumed == lanes.len()
                        && row.rgpr == expected_gpr
                        && row.vector_byte == begin.vector_byte
                        && row.next == ((begin.pc as u32 + 4) & 4095)
                        && row.halted == breaking,
                    "RSP result/effect census mismatch",
                )?;
                require(
                    read == (reads_enabled && begin.word >> 26 == 0x23),
                    "RSP LW lacks its actual completed read",
                )?;
                if let Some(definition) = definition {
                    rsp_registers[definition.register as usize] = Some(definition.context);
                    rsp_definitions.push(definition);
                }
                rsp_instructions += 1;
                previous_rsp = Some(row);
            }
        }
    }
    require(
        active.is_none()
            && cpu_reentry.is_none()
            && pending_exception.is_none()
            && await_root.is_none()
            && pending_return.is_none()
            && await_return.is_none(),
        "truncated RSP/CPU instruction or control seed",
    )?;
    require(
        cpu_instructions == h.steps.len(),
        "extra independent CPU step",
    )?;
    require(
        dmem == h.final_dmem && imem == h.final_imem,
        "modeled effects disagree with final backing snapshots",
    )?;
    Ok(RspCpuImemReport {
        format: h.format,
        profile: h.profile,
        source_sha256: digest,
        records,
        cpu_instructions,
        rsp_instructions,
        copies,
        final_imem_writers: iorig,
        final_dmem_sha256: sha256(&dmem),
        final_imem_sha256: sha256(&imem),
        rsp_definitions: definitions_enabled.then_some(rsp_definitions),
        imem_fetches: execution_enabled.then_some(imem_fetches),
        dma_consumption: ram.map(RamReplay::finish).transpose()?,
        exception_roots: exception_enabled.then_some(exception_roots),
        eret_returns: return_enabled.then_some(eret_returns),
        epc_reads: epc_enabled.then_some(epc_reads),
        epc_writes: epc_enabled.then_some(epc_writes),
        source_ancestry_certified: false,
        mutation_coverage_certified: false,
        imem_execution_certified: false,
        executable_lifetime_certified: false,
        native_complete: false,
    })
}
pub fn verify_rsp_cpu_imem_report(
    report: &RspCpuImemReport,
    source: &[u8],
    expected_sha256: &str,
) -> Result<(), String> {
    require(
        *report == inspect_rsp_cpu_imem_history(source, expected_sha256)?,
        "RSP/CPU IMEM report differs from complete source",
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{Value, json};
    fn row(kind: &str, ordinal: u64, context: u64) -> Value {
        json!({"kind":kind,"ordinal":ordinal,"context":context,"pc":0xffff_ffff_a000_6000u64,
            "phase":1,"word":0,"address":0,"bank":0,"offset":0,"bytes":0,"value":0,
            "cpu":false,"next":0,"halted":false,"vector_byte":0,"gpr":[],"rgpr":[]})
    }
    fn fixture() -> Value {
        let mut rsp = [0u32; 32];
        rsp[1] = 0x1000;
        rsp[2] = 0x11223344;
        let mut cpu = [0u64; 32];
        cpu[16] = 0xffff_ffff_a400_0000;
        let mut rows = Vec::new();
        let mut begin = row("rsp_begin", 1, 1);
        begin["pc"] = json!(0xffc);
        begin["next"] = json!(0xffc);
        begin["word"] = json!(0xac220000u32);
        begin["rgpr"] = json!(rsp);
        rows.push(begin.clone());
        for (index, value) in [0x11, 0x22, 0x33, 0x44].into_iter().enumerate() {
            let mut sink = row("rsp_sink", index as u64 + 2, 1);
            sink["pc"] = json!(0xffc);
            sink["word"] = json!(0xac220000u32);
            sink["address"] = json!(index);
            sink["offset"] = json!(index);
            sink["bytes"] = json!(1);
            sink["value"] = json!(value);
            rows.push(sink);
        }
        begin["kind"] = json!("rsp_end");
        begin["ordinal"] = json!(6);
        begin["next"] = json!(0);
        rows.push(begin);
        let mut load = row("cpu_begin", 7, 7);
        load["word"] = json!(0x8e080000u32);
        load["cpu"] = json!(true);
        load["gpr"] = json!(cpu);
        rows.push(load.clone());
        let mut read = row("sp_read", 8, 7);
        read["word"] = load["word"].clone();
        read["cpu"] = json!(true);
        read["address"] = json!(0x04000000);
        read["bytes"] = json!(4);
        read["value"] = json!(0x11223344);
        rows.push(read);
        cpu[8] = 0x11223344;
        load["kind"] = json!("cpu_end");
        load["ordinal"] = json!(9);
        load["gpr"] = json!(cpu);
        rows.push(load);
        let mut store = row("cpu_begin", 10, 10);
        store["pc"] = json!(0xffff_ffff_a000_6004u64);
        store["word"] = json!(0xae081000u32);
        store["cpu"] = json!(true);
        store["gpr"] = json!(cpu);
        rows.push(store.clone());
        let mut sink = row("sp_write", 11, 10);
        sink["pc"] = store["pc"].clone();
        sink["word"] = store["word"].clone();
        sink["cpu"] = json!(true);
        sink["address"] = json!(0x04001000);
        sink["bank"] = json!(1);
        sink["bytes"] = json!(4);
        sink["value"] = json!(0x11223344);
        rows.push(sink);
        store["kind"] = json!("cpu_end");
        store["ordinal"] = json!(12);
        rows.push(store);
        let starts: Vec<_> = rows.iter().filter(|r| r["kind"] == "cpu_begin").collect();
        let ends: Vec<_> = rows.iter().filter(|r| r["kind"] == "cpu_end").collect();
        let steps:Vec<_>=starts.into_iter().zip(ends).enumerate().map(|(index,(start,end))|json!({
            "phase":start["phase"],"index":index,"word":start["word"],"pc":start["pc"],"before":start["gpr"],"after":end["gpr"]
        })).collect();
        json!({"format":FORMAT,"profile":PROFILE,"initial_dmem":[0,0,0,0],"initial_imem":[0,0,0,0],
            "final_dmem":[17,34,51,68],"final_imem":[17,34,51,68],"steps":steps,"events":rows})
    }
    fn inspect(data: &Value) -> Result<RspCpuImemReport, String> {
        let bytes = serde_json::to_vec(data).unwrap();
        inspect_rsp_cpu_imem_history(&bytes, &sha256(&bytes))
    }
    #[test]
    fn decoded_rsp_address_bit_twelve_still_writes_dmem_then_cpu_installs_imem() {
        let report = inspect(&fixture()).unwrap();
        assert_eq!(report.copies.len(), 1);
        assert_eq!(report.copies[0].read_ordinal, 8);
        assert!(
            report.copies[0]
                .source_bytes
                .iter()
                .all(|origin| matches!(origin, SpByteOrigin::Rsp { context: 1, .. }))
        );
        assert!(!report.imem_execution_certified && !report.native_complete);
    }
    #[test]
    fn breakpoint_or_zero_register_forgery_cannot_claim_a_store() {
        let mut breakpoint = fixture();
        breakpoint["events"][0]["word"] = json!(13);
        breakpoint["events"][5]["word"] = json!(13);
        assert!(inspect(&breakpoint).is_err());
        let mut zero = fixture();
        zero["events"][0]["rgpr"][0] = json!(1);
        assert!(inspect(&zero).is_err());
        let mut cpu_zero = fixture();
        cpu_zero["events"][6]["gpr"][0] = json!(1);
        assert!(inspect(&cpu_zero).is_err());
    }
    #[test]
    fn source_report_and_instruction_effect_deletion_are_bound() {
        let data = fixture();
        let bytes = serde_json::to_vec(&data).unwrap();
        let digest = sha256(&bytes);
        let mut report = inspect_rsp_cpu_imem_history(&bytes, &digest).unwrap();
        report.copies[0].read_ordinal = 1;
        assert!(verify_rsp_cpu_imem_report(&report, &bytes, &digest).is_err());
        assert!(inspect_rsp_cpu_imem_history(&bytes, &"0".repeat(64)).is_err());
        let mut deleted = data;
        deleted["events"].as_array_mut().unwrap().remove(3);
        assert!(inspect(&deleted).is_err());
    }

    fn defined_fixture(repeat: bool) -> Value {
        let mut data = fixture();
        data["format"] = json!(DEFINITION_FORMAT);
        data["profile"] = json!(DEFINITION_PROFILE);
        fn replace(value: &mut Value) {
            match value {
                Value::Array(values) => values.iter_mut().for_each(replace),
                Value::Object(values) => values.values_mut().for_each(replace),
                _ if value.as_u64() == Some(0x11223344) => *value = json!(0x3344),
                _ => {}
            }
        }
        replace(&mut data);
        data["final_dmem"] = json!([0, 0, 0x33, 0x44]);
        data["final_imem"] = data["final_dmem"].clone();
        data["events"][1]["value"] = json!(0);
        data["events"][2]["value"] = json!(0);
        let mut words = vec![0x34023344u32];
        if repeat {
            words.push(0x34023344);
        }
        words.extend([0x00401821, 0x00601021]);
        let mut regs = [0u32; 32];
        regs[1] = 0x1000;
        regs[2] = 0x5555;
        let mut prefix = Vec::new();
        for (n, word) in words.iter().copied().enumerate() {
            let ordinal = prefix.len() as u64 + 1;
            let pc = 0xffc - (words.len() - n) as u32 * 4;
            let mut begin = row("rsp_begin", ordinal, ordinal);
            begin["pc"] = json!(pc);
            begin["next"] = json!(pc);
            begin["word"] = json!(word);
            begin["rgpr"] = json!(regs);
            prefix.push(begin.clone());
            if word >> 26 == 0x0d {
                regs[2] = 0x3344;
            } else if (word >> 11) & 31 == 3 {
                regs[3] = regs[2];
            } else {
                regs[2] = regs[3];
            }
            begin["kind"] = json!("rsp_end");
            begin["ordinal"] = json!(ordinal + 1);
            begin["next"] = json!(pc + 4);
            begin["rgpr"] = json!(regs);
            prefix.push(begin);
        }
        let shift = prefix.len() as u64;
        for r in data["events"].as_array_mut().unwrap() {
            r["ordinal"] = json!(r["ordinal"].as_u64().unwrap() + shift);
            r["context"] = json!(r["context"].as_u64().unwrap() + shift);
            if r["kind"] == "rsp_begin" || r["kind"] == "rsp_end" {
                r["rgpr"] = json!(regs);
            }
            prefix.push(r.clone());
        }
        data["events"] = json!(prefix);
        data
    }

    #[test]
    fn rsp_literal_and_same_value_definitions_reach_imem_on_the_original_clock() {
        for repeat in [false, true] {
            let data = defined_fixture(repeat);
            let report = inspect(&data).unwrap();
            let definitions = report.rsp_definitions.as_ref().unwrap();
            assert_eq!(definitions.len(), if repeat { 4 } else { 3 });
            assert!(matches!(
                definitions[0].expression,
                RspDefinitionExpression::Ori {
                    source: RspRegisterParent::ArchitecturalZero,
                    immediate: 0x3344
                }
            ));
            let last = definitions.last().unwrap();
            assert_eq!(last.value, 0x3344);
            assert!(matches!(last.expression, RspDefinitionExpression::Addu {
                left: RspRegisterParent::Definition { context }, right: RspRegisterParent::ArchitecturalZero
            } if context == definitions[definitions.len() - 2].context));
            assert!(report.copies[0].source_bytes.iter().all(|b| matches!(b,
                SpByteOrigin::Rsp { source_definition: Some(context), .. } if *context == last.context)));
            if repeat {
                assert_ne!(definitions[0].context, definitions[1].context);
            }
            assert!(
                !report.source_ancestry_certified
                    && !report.mutation_coverage_certified
                    && !report.imem_execution_certified
                    && !report.native_complete
            );
        }
    }

    #[test]
    fn rsp_reentry_cuts_definitions_even_when_scalar_values_are_identical() {
        let mut data = defined_fixture(false);
        for r in data["events"].as_array_mut().unwrap().iter_mut().skip(6) {
            r["phase"] = json!(2);
        }
        for step in data["steps"].as_array_mut().unwrap() {
            step["phase"] = json!(2);
        }
        let report = inspect(&data).unwrap();
        assert_eq!(report.rsp_definitions.as_ref().unwrap().len(), 3);
        assert!(report.copies[0].source_bytes.iter().all(|b| matches!(
            b,
            SpByteOrigin::Rsp {
                source_definition: None,
                ..
            }
        )));
    }

    #[test]
    fn rsp_definition_snapshots_profiles_parents_and_store_tags_are_rechecked() {
        let data = defined_fixture(false);
        for mode in 0..4 {
            let mut forged = data.clone();
            match mode {
                0 => forged["events"][1]["rgpr"][2] = json!(0x3345),
                1 => forged["events"][3]["rgpr"][10] = json!(1),
                2 => forged["events"][2]["word"] = json!(0x00401861u32),
                _ => forged["profile"] = json!(PROFILE),
            }
            assert!(inspect(&forged).is_err(), "mode {mode}");
        }
        let bytes = serde_json::to_vec(&data).unwrap();
        let digest = sha256(&bytes);
        let report = inspect(&data).unwrap();
        let mut forged = report.clone();
        if let RspDefinitionExpression::Addu { left, .. } =
            &mut forged.rsp_definitions.as_mut().unwrap()[2].expression
        {
            *left = RspRegisterParent::Definition { context: 999999 };
        }
        assert!(verify_rsp_cpu_imem_report(&forged, &bytes, &digest).is_err());
        let mut forged = report;
        if let SpByteOrigin::Rsp {
            source_definition, ..
        } = &mut forged.copies[0].source_bytes[0]
        {
            *source_definition = None;
        }
        assert!(verify_rsp_cpu_imem_report(&forged, &bytes, &digest).is_err());
        let mut legacy = data;
        legacy["format"] = json!(FORMAT);
        legacy["profile"] = json!(PROFILE);
        assert!(inspect(&legacy).is_err());
    }

    #[test]
    fn rsp_definitions_keep_opaque_incoming_operands_distinct_from_zero() {
        let mut data = defined_fixture(false);
        for index in [0, 1] {
            data["events"][index]["word"] = json!(0x34222344u32);
        }
        let report = inspect(&data).unwrap();
        assert!(matches!(
            report.rsp_definitions.as_ref().unwrap()[0].expression,
            RspDefinitionExpression::Ori {
                source: RspRegisterParent::CapturedInput {
                    register: 1,
                    value: 0x1000
                },
                immediate: 0x2344
            }
        ));
        assert!(!report.source_ancestry_certified);
        let mut encoded = serde_json::to_value(&report).unwrap();
        encoded["rsp_definitions"][0]["expression"]["source"]["invented_root"] = json!(true);
        assert!(serde_json::from_value::<RspCpuImemReport>(encoded).is_err());
    }

    fn read_fixture(target: usize) -> Value {
        let mut data = defined_fixture(false);
        data["format"] = json!(READ_FORMAT);
        data["profile"] = json!(READ_PROFILE);
        let mut regs = [0u32; 32];
        regs[1] = 0x1000;
        regs[2] = 0x3344;
        regs[3] = 0x3344;
        let word = (0x23u32 << 26) | (1 << 21) | ((target as u32) << 16);
        let mut begin = row("rsp_begin", 13, 13);
        begin["pc"] = json!(0);
        begin["next"] = json!(0);
        begin["word"] = json!(word);
        begin["rgpr"] = json!(regs);
        let mut read = row("rsp_read", 14, 13);
        read["pc"] = json!(0);
        read["word"] = json!(word);
        read["address"] = json!(0x1000);
        read["bytes"] = json!(4);
        read["value"] = json!(0x3344);
        let mut inserted = vec![begin.clone(), read];
        if target != 0 {
            regs[target] = 0x3344;
        }
        begin["kind"] = json!("rsp_end");
        begin["ordinal"] = json!(15);
        begin["next"] = json!(4);
        begin["rgpr"] = json!(regs);
        inserted.push(begin);
        if target == 4 {
            let mut begin = row("rsp_begin", 16, 16);
            begin["pc"] = json!(4);
            begin["next"] = json!(4);
            begin["word"] = json!(0xac240000u32);
            begin["rgpr"] = json!(regs);
            inserted.push(begin.clone());
            for (n, value) in [0u8, 0, 0x33, 0x44].into_iter().enumerate() {
                let mut sink = row("rsp_sink", 17 + n as u64, 16);
                sink["pc"] = json!(4);
                sink["word"] = json!(0xac240000u32);
                sink["address"] = json!(n);
                sink["offset"] = json!(n);
                sink["bytes"] = json!(1);
                sink["value"] = json!(value);
                inserted.push(sink);
            }
            begin["kind"] = json!("rsp_end");
            begin["ordinal"] = json!(21);
            begin["next"] = json!(8);
            inserted.push(begin);
        }
        let rows = data["events"].as_array_mut().unwrap();
        for r in rows.iter_mut().skip(12) {
            r["ordinal"] = json!(r["ordinal"].as_u64().unwrap() + inserted.len() as u64);
            r["context"] = json!(r["context"].as_u64().unwrap() + inserted.len() as u64);
        }
        rows.splice(12..12, inserted);
        data
    }

    #[test]
    fn actual_rsp_word_read_keeps_each_writer_parent_through_a_later_imem_copy() {
        let report = inspect(&read_fixture(4)).unwrap();
        let definitions = report.rsp_definitions.as_ref().unwrap();
        let RspDefinitionExpression::DmemWordLoad(read) = &definitions[3].expression else {
            panic!("missing read parent");
        };
        assert_eq!(
            (read.read_ordinal, read.address, read.offset),
            (14, 0x1000, 0)
        );
        for (n, parent) in read.origins.iter().enumerate() {
            assert!(
                matches!(parent, SpByteOrigin::Rsp { context: 7, write_ordinal, source_definition: Some(5), .. } if *write_ordinal == 8 + n as u64)
            );
        }
        assert!(report.copies[0].source_bytes.iter().all(|b| matches!(
            b,
            SpByteOrigin::Rsp {
                context: 16,
                source_definition: Some(13),
                ..
            }
        )));
        assert!(
            !report.source_ancestry_certified
                && !report.mutation_coverage_certified
                && !report.native_complete
        );
    }

    #[test]
    fn rsp_word_read_binds_the_prewrite_base_and_requires_even_discarded_reads() {
        for target in [0, 1] {
            let data = read_fixture(target);
            let report = inspect(&data).unwrap();
            assert_eq!(
                report.rsp_definitions.as_ref().unwrap().len(),
                if target == 0 { 3 } else { 4 }
            );
            let mut missing = data;
            missing["events"].as_array_mut().unwrap().remove(13);
            assert!(inspect(&missing).is_err());
        }
    }

    #[test]
    fn same_value_decoy_read_and_forged_read_parents_cannot_repair_source_identity() {
        let data = read_fixture(4);
        let mut decoy = data.clone();
        decoy["initial_dmem"] = json!([0, 0, 0, 0, 0, 0, 0x33, 0x44]);
        decoy["final_dmem"] = json!([0, 0, 0x33, 0x44, 0, 0, 0x33, 0x44]);
        decoy["events"][13]["address"] = json!(0x1004);
        decoy["events"][13]["offset"] = json!(4);
        assert!(inspect(&decoy).is_err());
        for field in ["context", "word", "value", "bytes", "cpu"] {
            let mut forged = data.clone();
            forged["events"][13][field] = if field == "cpu" {
                json!(true)
            } else {
                json!(999)
            };
            assert!(inspect(&forged).is_err(), "{field}");
        }
        let bytes = serde_json::to_vec(&data).unwrap();
        let digest = sha256(&bytes);
        let mut forged = inspect(&data).unwrap();
        if let RspDefinitionExpression::DmemWordLoad(read) =
            &mut forged.rsp_definitions.as_mut().unwrap()[3].expression
            && let SpByteOrigin::Rsp {
                source_definition, ..
            } = &mut read.origins[0]
        {
            *source_definition = Some(3);
        }
        assert!(verify_rsp_cpu_imem_report(&forged, &bytes, &digest).is_err());
        let mut downgraded = data;
        downgraded["format"] = json!(DEFINITION_FORMAT);
        downgraded["profile"] = json!(DEFINITION_PROFILE);
        assert!(inspect(&downgraded).is_err());
    }

    #[test]
    fn duplicate_or_missing_read_callbacks_fail_after_reclocking_complete_sources() {
        for duplicate in [false, true] {
            let mut data = read_fixture(4);
            let rows = data["events"].as_array_mut().unwrap();
            if duplicate {
                rows.insert(14, rows[13].clone());
            } else {
                rows.remove(13);
            }
            let mut active = 0;
            for (index, row) in rows.iter_mut().enumerate() {
                let ordinal = index as u64 + 1;
                row["ordinal"] = json!(ordinal);
                if row["kind"] == "rsp_begin" || row["kind"] == "cpu_begin" {
                    active = ordinal;
                }
                row["context"] = json!(active);
                if row["kind"] == "rsp_end" || row["kind"] == "cpu_end" {
                    active = 0;
                }
            }
            assert!(inspect(&data).is_err(), "duplicate {duplicate}");
        }
    }

    fn execution_fixture(opaque_replace: bool) -> Value {
        let mut data = read_fixture(4);
        data["format"] = json!(EXECUTION_FORMAT);
        data["profile"] = json!(EXECUTION_PROFILE);
        fn zero(value: &mut Value) {
            match value {
                Value::Array(values) => values.iter_mut().for_each(zero),
                Value::Object(values) => values.values_mut().for_each(zero),
                _ if value.as_u64() == Some(0x3344) => *value = json!(0),
                _ if value.as_u64() == Some(0x34023344) => *value = json!(0x34020000),
                _ => {}
            }
        }
        zero(&mut data);
        data["final_dmem"] = json!([0, 0, 0, 0]);
        for r in data["events"].as_array_mut().unwrap() {
            if r["kind"] == "rsp_sink" {
                r["value"] = json!(0);
            }
        }
        let mut image = vec![0u8; 4096];
        data["initial_imem"] = json!(image);
        let mut rows = Vec::new();
        let mut last_rsp = Value::Null;
        for r in data["events"].as_array().unwrap() {
            if r["kind"] == "rsp_begin" {
                let address = r["pc"].as_u64().unwrap() as usize;
                let word = r["word"].as_u64().unwrap() as u32;
                let mut seed = row("opaque_imem_seed", 0, 0);
                seed["address"] = json!(address);
                seed["offset"] = json!(address);
                seed["bank"] = json!(1);
                seed["bytes"] = json!(4);
                seed["value"] = json!(word);
                rows.push(seed);
                image[address..address + 4].copy_from_slice(&word.to_be_bytes());
            }
            if r["kind"] == "rsp_end" {
                last_rsp = r.clone();
            }
            if r["kind"] == "sp_write" && r["bank"] == 1 {
                let address = r["offset"].as_u64().unwrap() as usize;
                image[address..address + 4]
                    .copy_from_slice(&(r["value"].as_u64().unwrap() as u32).to_be_bytes());
            }
            rows.push(r.clone());
        }
        if opaque_replace {
            let mut seed = row("opaque_imem_seed", 0, 0);
            seed["phase"] = json!(2);
            seed["bank"] = json!(1);
            seed["bytes"] = json!(4);
            rows.push(seed);
        }
        last_rsp["phase"] = json!(2);
        last_rsp["kind"] = json!("rsp_begin");
        last_rsp["word"] = json!(0);
        last_rsp["pc"] = json!(0);
        last_rsp["next"] = json!(0);
        rows.push(last_rsp.clone());
        last_rsp["kind"] = json!("rsp_end");
        last_rsp["next"] = json!(4);
        rows.push(last_rsp);
        let mut active = 0;
        for (n, r) in rows.iter_mut().enumerate() {
            r["ordinal"] = json!(n + 1);
            if r["kind"] == "rsp_begin" || r["kind"] == "cpu_begin" {
                active = n + 1;
            }
            r["context"] = json!(active);
            if r["kind"] == "rsp_end" || r["kind"] == "cpu_end" {
                active = 0;
            }
        }
        data["events"] = json!(rows);
        data["final_imem"] = json!(image);
        data
    }

    #[test]
    fn captured_cpu_install_reaches_actual_rsp_consumption_without_lifetime_promotion() {
        let data = execution_fixture(false);
        let report = inspect(&data).unwrap();
        let fetched = report.imem_fetches.as_ref().unwrap().last().unwrap();
        assert_eq!((fetched.pc, fetched.word), (0, 0));
        let writer = data["events"]
            .as_array()
            .unwrap()
            .iter()
            .find(|r| r["kind"] == "sp_write" && r["bank"] == 1)
            .unwrap()["ordinal"]
            .as_u64()
            .unwrap();
        assert!(
            fetched.origins.iter().all(
                |o| matches!(o,SpByteOrigin::Cpu { write_ordinal,.. } if *write_ordinal==writer)
            )
        );
        assert!(
            !report.imem_execution_certified
                && !report.executable_lifetime_certified
                && !report.native_complete
        );
    }

    #[test]
    fn equal_opaque_install_cuts_cpu_origin_and_fetch_state_report_changes_reject() {
        let report = inspect(&execution_fixture(true)).unwrap();
        assert!(
            report
                .imem_fetches
                .as_ref()
                .unwrap()
                .last()
                .unwrap()
                .origins
                .iter()
                .all(|o| matches!(
                    o,
                    SpByteOrigin::Unknown {
                        cut_ordinal: Some(_)
                    }
                ))
        );
        let data = execution_fixture(false);
        let bytes = serde_json::to_vec(&data).unwrap();
        let mut forged = inspect(&data).unwrap();
        forged
            .imem_fetches
            .as_mut()
            .unwrap()
            .last_mut()
            .unwrap()
            .origins[0] = SpByteOrigin::Unknown { cut_ordinal: None };
        assert!(verify_rsp_cpu_imem_report(&forged, &bytes, &sha256(&bytes)).is_err());
        let mut wrong = data.clone();
        let n = wrong["events"].as_array().unwrap().len();
        wrong["events"][n - 2]["word"] = json!(13);
        wrong["events"][n - 1]["word"] = json!(13);
        wrong["events"][n - 1]["halted"] = json!(true);
        assert!(inspect(&wrong).is_err());
        let mut partial = data;
        partial["initial_imem"] = json!([0, 0, 0, 0]);
        assert!(inspect(&partial).is_err());
    }

    fn dma_fixture(opaque_replace: bool) -> Value {
        let mut data = execution_fixture(false);
        data["format"] = json!(DMA_FORMAT);
        data["profile"] = json!(DMA_PROFILE);
        for field in ["initial_dmem", "final_dmem"] {
            data[field].as_array_mut().unwrap().resize(4096, json!(0));
        }
        let mut initial = Vec::new();
        for step in data["steps"].as_array().unwrap() {
            initial.extend_from_slice(&(step["word"].as_u64().unwrap() as u32).to_be_bytes());
        }
        initial.extend_from_slice(&[0; 8]);
        data["ram"] = json!({"start":0x6000,"initial":initial,"final_bytes":initial});
        let mut rows = data["events"].as_array().unwrap().clone();
        let last_cpu = rows
            .iter()
            .rfind(|r| r["kind"] == "cpu_end")
            .unwrap()
            .clone();
        for lane in [0, 4] {
            let mut write = row("ram_write", 0, 0);
            write["phase"] = json!(2);
            write["address"] = json!(0x6008 + lane);
            write["offset"] = json!(lane);
            write["bytes"] = json!(4);
            write["dma"] = json!({"pbus":0,"dram":0x6008,"length":0,"count":0,"skip":0});
            rows.push(write);
        }
        if opaque_replace {
            let mut cut = rows[rows.len() - 2].clone();
            cut["dma"] = Value::Null;
            cut["address"] = json!(0x6008);
            cut["offset"] = json!(0);
            rows.push(cut);
        }
        let mut begin = last_cpu;
        begin["kind"] = json!("cpu_begin");
        begin["phase"] = json!(2);
        begin["pc"] = json!(0xffffffffa0006008u64);
        begin["word"] = json!(0);
        let mut end = begin.clone();
        end["kind"] = json!("cpu_end");
        data["steps"].as_array_mut().unwrap().push(json!({"phase":2,"index":2,"word":0,"pc":0xffffffffa0006008u64,"before":begin["gpr"],"after":end["gpr"]}));
        rows.extend([begin, end]);
        let mut result = Vec::new();
        for r in rows {
            if r["kind"] == "cpu_begin" {
                let pc = r["pc"].as_u64().unwrap();
                let mut fetch = row("ram_fetch_begin", 0, 0);
                fetch["phase"] = r["phase"].clone();
                fetch["pc"] = json!(pc);
                fetch["cpu"] = json!(true);
                fetch["address"] = json!(pc as u32 & 0x1fffffff);
                fetch["fetch"] = json!({"physical":pc as u32 & 0x1fffffff,"cached":false});
                let mut read = fetch.clone();
                read["fetch"] = Value::Null;
                read["kind"] = json!("ram_read");
                read["bytes"] = json!(4);
                read["value"] = r["word"].clone();
                let mut end = fetch.clone();
                end["kind"] = json!("ram_fetch_end");
                end["value"] = r["word"].clone();
                result.extend([fetch, read, end]);
            }
            result.push(r);
        }
        let mut active = 0;
        for (n, r) in result.iter_mut().enumerate() {
            r["ordinal"] = json!(n + 1);
            if matches!(
                r["kind"].as_str(),
                Some("cpu_begin" | "rsp_begin" | "ram_fetch_begin")
            ) {
                active = n + 1;
            }
            r["context"] = json!(active);
            if matches!(
                r["kind"].as_str(),
                Some("cpu_end" | "rsp_end" | "ram_fetch_end")
            ) {
                active = 0;
            }
        }
        data["events"] = json!(result);
        data
    }

    #[test]
    fn rsp_definition_dma_write_and_cpu_decoded_word_compose_on_the_original_clock() {
        let report = inspect(&dma_fixture(false)).unwrap();
        let graph = report.dma_consumption.as_ref().unwrap();
        let writer = &graph.writes[0];
        assert!(writer.source_bytes.iter().all(|o| matches!(
            o,
            SpByteOrigin::Rsp {
                source_definition: Some(_),
                ..
            }
        )));
        let fetched = graph.fetches.last().unwrap();
        assert_eq!(fetched.word, 0);
        assert!(fetched.origins.iter().all(|o| matches!(o,RamByteOrigin::SpDma { write_ordinal,.. } if *write_ordinal==writer.write_ordinal)));
        assert!(fetched.decoder_context > fetched.read_ordinal);
        let report = inspect(&dma_fixture(true)).unwrap();
        assert!(
            report
                .dma_consumption
                .unwrap()
                .fetches
                .last()
                .unwrap()
                .origins
                .iter()
                .all(|o| matches!(
                    o,
                    RamByteOrigin::Unknown {
                        cut_ordinal: Some(_)
                    }
                ))
        );
    }

    #[test]
    fn dma_source_descriptor_fetch_decoder_and_report_forgeries_fail_closed() {
        let source = dma_fixture(false);
        for mode in 0..8 {
            let mut forged = source.clone();
            let rows = forged["events"].as_array_mut().unwrap();
            let write = rows.iter_mut().find(|r| r["kind"] == "ram_write").unwrap();
            match mode {
                0 => write["offset"] = json!(4),
                1 => write["dma"]["pbus"] = json!(0x1000),
                2 => write["dma"]["skip"] = json!(1),
                3 => write["value"] = json!(1),
                4 => {
                    rows.iter_mut().find(|r| r["kind"] == "ram_read").unwrap()["address"] =
                        json!(0x6004)
                }
                5 => {
                    rows.iter_mut()
                        .find(|r| r["kind"] == "ram_fetch_begin")
                        .unwrap()["fetch"]["cached"] = json!(true)
                }
                6 => {
                    rows.iter_mut()
                        .find(|r| r["kind"] == "ram_fetch_end")
                        .unwrap()["value"] = json!(1)
                }
                _ => forged["ram"]["final_bytes"][0] = json!(255),
            }
            assert!(inspect(&forged).is_err(), "mode {mode}");
        }
        let bytes = serde_json::to_vec(&source).unwrap();
        let mut forged = inspect(&source).unwrap();
        forged
            .dma_consumption
            .as_mut()
            .unwrap()
            .fetches
            .last_mut()
            .unwrap()
            .decoder_context = 1;
        assert!(verify_rsp_cpu_imem_report(&forged, &bytes, &sha256(&bytes)).is_err());
    }

    #[test]
    fn dma_equal_decoy_and_byte_local_unknown_writers_preserve_source_cuts() {
        let mut decoy = dma_fixture(false);
        for r in decoy["events"].as_array_mut().unwrap() {
            if r["kind"] == "ram_write" {
                r["dma"]["pbus"] = json!(8);
                r["offset"] = json!(r["offset"].as_u64().unwrap() + 8);
            }
        }
        let report = inspect(&decoy).unwrap();
        assert!(
            report.dma_consumption.unwrap().writes[0]
                .source_bytes
                .iter()
                .all(|o| matches!(o, SpByteOrigin::Unknown { cut_ordinal: None }))
        );

        let mut mixed = dma_fixture(false);
        let rows = mixed["events"].as_array_mut().unwrap();
        let index = rows.iter().position(|r| r["kind"] == "ram_write").unwrap();
        let mut cut = row("foreign_sink", 0, 0);
        cut["phase"] = json!(2);
        cut["address"] = json!(1);
        cut["offset"] = json!(1);
        cut["bytes"] = json!(1);
        rows.insert(index, cut);
        let mut active = 0;
        for (n, r) in rows.iter_mut().enumerate() {
            r["ordinal"] = json!(n + 1);
            if matches!(
                r["kind"].as_str(),
                Some("cpu_begin" | "rsp_begin" | "ram_fetch_begin")
            ) {
                active = n + 1;
            }
            r["context"] = json!(active);
            if matches!(
                r["kind"].as_str(),
                Some("cpu_end" | "rsp_end" | "ram_fetch_end")
            ) {
                active = 0;
            }
        }
        let report = inspect(&mixed).unwrap();
        let graph = report.dma_consumption.unwrap();
        assert!(matches!(
            graph.writes[0].source_bytes[1],
            SpByteOrigin::Unknown {
                cut_ordinal: Some(_)
            }
        ));
        for n in [0, 2, 3] {
            assert!(matches!(
                graph.writes[0].source_bytes[n],
                SpByteOrigin::Rsp { .. }
            ));
        }
        assert!(graph.fetches.last().unwrap().origins.iter().all(|o| matches!(o,RamByteOrigin::SpDma {write_ordinal,..} if *write_ordinal==graph.writes[0].write_ordinal)));
    }

    fn reclock_promoted(data: &mut Value) {
        let mut active = 0;
        let mut request = 0;
        for (n, row) in data["events"]
            .as_array_mut()
            .unwrap()
            .iter_mut()
            .enumerate()
        {
            row["ordinal"] = json!(n + 1);
            let kind = row["kind"].as_str().unwrap();
            if matches!(kind, "cpu_begin" | "rsp_begin" | "ram_fetch_begin") {
                active = n + 1;
            }
            if kind == "dma_promote" {
                request = n + 1;
            }
            let owned = matches!(
                kind,
                "dma_promote"
                    | "dma_complete"
                    | "imem_dma_read"
                    | "imem_dma_write"
                    | "dmem_dma_read"
                    | "dmem_dma_write"
            ) || (kind == "ram_write" && row["dma"].is_object());
            let end = matches!(kind, "cpu_end" | "rsp_end" | "ram_fetch_end");
            let completed = kind == "dma_complete";
            row["context"] = json!(if kind == "dma_pending_write" {
                n + 1
            } else if owned {
                request
            } else {
                active
            });
            if end {
                active = 0;
            }
            if completed {
                request = 0;
            }
        }
    }
    fn promoted_fixture() -> Value {
        let mut data = dma_fixture(false);
        data["format"] = json!(DMA_LIFECYCLE_FORMAT);
        data["profile"] = json!(DMA_LIFECYCLE_PROFILE);
        let rows = data["events"].as_array_mut().unwrap();
        let first = rows.iter().position(|r| r["kind"] == "ram_write").unwrap();
        let mut promote = rows[first].clone();
        promote["kind"] = json!("dma_promote");
        promote["bytes"] = json!(0);
        rows.insert(first, promote);
        let mut complete = rows[first].clone();
        complete["kind"] = json!("dma_complete");
        complete["dma"] = Value::Null;
        complete["address"] = json!(0x6010);
        complete["offset"] = json!(8);
        rows.insert(first + 3, complete);
        reclock_promoted(&mut data);
        data
    }

    #[test]
    fn promoted_dma_identity_reaches_decoder_without_merging_word_writers() {
        let data = promoted_fixture();
        let report = inspect(&data).unwrap();
        let graph = report.dma_consumption.unwrap();
        let request = &graph.promoted_requests.unwrap()[0];
        assert_eq!(
            request.write_ordinals,
            graph
                .writes
                .iter()
                .map(|w| w.write_ordinal)
                .collect::<Vec<_>>()
        );
        assert!(
            graph
                .writes
                .iter()
                .all(|w| w.promote_context == Some(request.promote_context))
        );
        assert_ne!(graph.writes[0].write_ordinal, graph.writes[1].write_ordinal);
        assert!(graph.fetches.last().unwrap().origins.iter().all(|o|matches!(o,RamByteOrigin::SpDma {write_ordinal,..} if *write_ordinal==graph.writes[0].write_ordinal)));
    }

    #[test]
    fn incomplete_declared_dma_progression_cannot_acquire_completion_receipt() {
        for (length, count, skip) in [(8, 0, 0), (0, 1, 8), (16, 0, 0)] {
            let mut data = promoted_fixture();
            for r in data["events"].as_array_mut().unwrap() {
                if r["dma"].is_object() {
                    r["dma"]["length"] = json!(length);
                    r["dma"]["count"] = json!(count);
                    r["dma"]["skip"] = json!(skip);
                }
                if r["kind"] == "dma_complete" {
                    r["address"] = json!(0x6008 + (length + 8) * (count + 1) + count * skip);
                    r["offset"] = json!((length + 8) * (count + 1));
                }
            }
            assert!(inspect(&data).is_err(), "length {length} count {count}");
        }
        let source = promoted_fixture();
        for kind in ["dma_promote", "dma_complete"] {
            let mut missing = source.clone();
            missing["events"]
                .as_array_mut()
                .unwrap()
                .retain(|r| r["kind"] != kind);
            reclock_promoted(&mut missing);
            assert!(inspect(&missing).is_err(), "missing {kind}");
        }
        let mut wrong = source.clone();
        let write = wrong["events"]
            .as_array_mut()
            .unwrap()
            .iter_mut()
            .find(|r| r["kind"] == "ram_write")
            .unwrap();
        write["context"] = json!(1);
        assert!(inspect(&wrong).is_err());
        let mut wrong = source.clone();
        let rows = wrong["events"].as_array_mut().unwrap();
        let first = rows.iter().position(|r| r["kind"] == "ram_write").unwrap();
        rows.swap(first, first + 1);
        reclock_promoted(&mut wrong);
        assert!(inspect(&wrong).is_err());
        let bytes = serde_json::to_vec(&source).unwrap();
        let mut forged = inspect(&source).unwrap();
        forged
            .dma_consumption
            .as_mut()
            .unwrap()
            .promoted_requests
            .as_mut()
            .unwrap()[0]
            .write_ordinals
            .pop();
        assert!(verify_rsp_cpu_imem_report(&forged, &bytes, &sha256(&bytes)).is_err());
    }

    #[test]
    fn promoted_progression_preserves_count_skip_and_pbus_wrap() {
        let request = ActiveDmemDma {
            context: 1,
            descriptor: DmemDmaDescriptor {
                pbus: 0xff8,
                dram: PhysicalAddr(0x1000),
                length: 8,
                count: 1,
                skip: 8,
            },
            writes: Vec::new(),
            direction: SpDmaDirection::DmemEgress,
            pending_provenance: None,
        };
        assert_eq!(request.total_words(), 8);
        for (block, pbus, dram, count) in [
            (0, 0xff8, 0x1000, 1),
            (1, 0, 0x1008, 1),
            (2, 8, 0x1018, 0),
            (3, 16, 0x1020, 0),
        ] {
            let current = request.current(block);
            assert_eq!(
                (current.pbus, current.dram.0, current.count),
                (pbus, dram, count)
            );
        }
    }

    #[test]
    fn complete_count_skip_wrap_and_immediate_handoff_keep_distinct_requests() {
        let mut ram = RamReplay::new(
            RamSnapshot {
                start: PhysicalAddr(0x1000),
                initial: vec![0; 40],
                final_bytes: vec![0; 40],
            },
            true,
            false,
            false,
        )
        .unwrap();
        let dmem = vec![0; 4096];
        let origins = vec![SpByteOrigin::Unknown { cut_ordinal: None }; 4096];
        let mut ordinal = 1;
        for _ in 0..2 {
            let request = ordinal;
            let mut promote = row("dma_promote", ordinal, request);
            promote["address"] = json!(0x1000);
            promote["offset"] = json!(0xff8);
            promote["dma"] = json!({"pbus":0xff8,"dram":0x1000,"length":8,"count":1,"skip":8});
            ram.observe(serde_json::from_value(promote).unwrap(), &dmem, &origins)
                .unwrap();
            ordinal += 1;
            for (pbus, dram, count, lane) in [
                (0xff8, 0x1000, 1, 0),
                (0xff8, 0x1000, 1, 4),
                (0, 0x1008, 1, 0),
                (0, 0x1008, 1, 4),
                (8, 0x1018, 0, 0),
                (8, 0x1018, 0, 4),
                (16, 0x1020, 0, 0),
                (16, 0x1020, 0, 4),
            ] {
                let mut write = row("ram_write", ordinal, request);
                write["address"] = json!(dram + lane);
                write["offset"] = json!((pbus + lane) & 4095);
                write["bytes"] = json!(4);
                write["dma"] = json!({"pbus":pbus,"dram":dram,"length":8,"count":count,"skip":8});
                ram.observe(serde_json::from_value(write).unwrap(), &dmem, &origins)
                    .unwrap();
                ordinal += 1;
            }
            let mut complete = row("dma_complete", ordinal, request);
            complete["address"] = json!(0x1028);
            complete["offset"] = json!(24);
            ram.observe(serde_json::from_value(complete).unwrap(), &dmem, &origins)
                .unwrap();
            ordinal += 1;
        }
        let graph = ram.finish().unwrap();
        let requests = graph.promoted_requests.unwrap();
        assert_eq!(
            requests
                .iter()
                .map(|r| r.write_ordinals.len())
                .collect::<Vec<_>>(),
            [8, 8]
        );
        assert_eq!(
            requests[1].promote_context,
            requests[0].complete_ordinal + 1
        );
        assert_ne!(
            graph.writes[0].promote_context,
            graph.writes[8].promote_context
        );
        assert_eq!(graph.writes[2].source_offset, 0);
        assert_eq!(graph.writes[4].destination, PhysicalAddr(0x1018));
    }

    fn roundtrip_fixture(opaque_replace: bool) -> Value {
        let mut data = promoted_fixture();
        data["format"] = json!(DMA_ROUNDTRIP_FORMAT);
        data["profile"] = json!(DMA_ROUNDTRIP_PROFILE);
        let rows = data["events"].as_array_mut().unwrap();
        let mut promote = row("dma_promote", 0, 0);
        promote["phase"] = json!(3);
        promote["bank"] = json!(1);
        promote["address"] = json!(0x6008);
        promote["offset"] = json!(0x300);
        promote["dma"] = json!({"pbus":0x300,"dram":0x6008,"length":0,"count":0,"skip":0});
        let mut read = promote.clone();
        read["kind"] = json!("imem_dma_read");
        read["bytes"] = json!(8);
        let mut write = read.clone();
        write["kind"] = json!("imem_dma_write");
        let mut complete = promote.clone();
        complete["kind"] = json!("dma_complete");
        complete["dma"] = Value::Null;
        complete["address"] = json!(0x6010);
        complete["offset"] = json!(0x308);
        let mut begin = rows
            .iter()
            .rfind(|r| r["kind"] == "rsp_end")
            .unwrap()
            .clone();
        begin["kind"] = json!("rsp_begin");
        begin["phase"] = json!(4);
        begin["pc"] = json!(0x300);
        begin["next"] = json!(0x300);
        let mut end = begin.clone();
        end["kind"] = json!("rsp_end");
        end["next"] = json!(0x304);
        rows.extend([promote, read, write, complete]);
        if opaque_replace {
            let mut cut = row("opaque_imem_seed", 0, 0);
            cut["phase"] = json!(3);
            cut["bank"] = json!(1);
            cut["address"] = json!(0x300);
            cut["offset"] = json!(0x300);
            cut["bytes"] = json!(4);
            rows.push(cut);
        }
        rows.extend([begin, end]);
        reclock_promoted(&mut data);
        data
    }

    #[test]
    fn rsp_data_dma_ram_and_imem_ingress_reach_actual_rsp_consumption() {
        let report = inspect(&roundtrip_fixture(false)).unwrap();
        let graph = report.dma_consumption.as_ref().unwrap();
        let requests = graph.promoted_requests.as_ref().unwrap();
        assert_eq!(
            requests.iter().map(|r| r.direction).collect::<Vec<_>>(),
            [
                Some(SpDmaDirection::DmemEgress),
                Some(SpDmaDirection::ImemIngress)
            ]
        );
        let install = &graph.imem_installs.as_ref().unwrap()[0];
        let fetched = report.imem_fetches.as_ref().unwrap().last().unwrap();
        assert_eq!((fetched.pc, fetched.word), (0x300, 0));
        for (n, origin) in fetched.origins.iter().enumerate() {
            assert!(
                matches!(origin,SpByteOrigin::ImemDma {write_ordinal,parent:RamByteOrigin::SpDma {write_ordinal:ram_writer,..},source,..}
                if *write_ordinal==install.write_ordinal && *ram_writer==graph.writes[0].write_ordinal && source.0==0x6008+n as u32)
            );
        }
        assert!(graph.writes[0].source_bytes.iter().all(|o| matches!(
            o,
            SpByteOrigin::Rsp {
                source_definition: Some(_),
                ..
            }
        )));
        assert!(
            graph.writes[1]
                .source_bytes
                .iter()
                .all(|o| matches!(o, SpByteOrigin::Unknown { cut_ordinal: None }))
        );
        let report = inspect(&roundtrip_fixture(true)).unwrap();
        assert!(
            report
                .imem_fetches
                .unwrap()
                .last()
                .unwrap()
                .origins
                .iter()
                .all(|o| matches!(
                    o,
                    SpByteOrigin::Unknown {
                        cut_ordinal: Some(_)
                    }
                ))
        );
    }

    #[test]
    fn imem_install_requires_exact_completed_read_bank_descriptor_and_parents() {
        let source = roundtrip_fixture(false);
        for kind in ["imem_dma_read", "imem_dma_write"] {
            let mut missing = source.clone();
            missing["events"]
                .as_array_mut()
                .unwrap()
                .retain(|r| r["kind"] != kind);
            reclock_promoted(&mut missing);
            assert!(inspect(&missing).is_err(), "missing {kind}");
        }
        for mode in 0..4 {
            let mut data = source.clone();
            let rows = data["events"].as_array_mut().unwrap();
            let read = rows
                .iter_mut()
                .find(|r| r["kind"] == "imem_dma_read")
                .unwrap();
            match mode {
                0 => read["bank"] = json!(0),
                1 => read["address"] = json!(0x6000),
                2 => read["value"] = json!(1),
                _ => {
                    rows.iter_mut()
                        .find(|r| r["kind"] == "imem_dma_write")
                        .unwrap()["dma"]["pbus"] = json!(0x308)
                }
            }
            assert!(inspect(&data).is_err(), "mode {mode}");
        }
        let mut data = source.clone();
        let rows = data["events"].as_array_mut().unwrap();
        let index = rows
            .iter()
            .position(|r| r["kind"] == "imem_dma_read")
            .unwrap();
        rows.insert(index, rows[index].clone());
        reclock_promoted(&mut data);
        assert!(inspect(&data).is_err());
        let bytes = serde_json::to_vec(&source).unwrap();
        let mut report = inspect(&source).unwrap();
        report
            .dma_consumption
            .as_mut()
            .unwrap()
            .imem_installs
            .as_mut()
            .unwrap()[0]
            .source_bytes[0] = RamByteOrigin::Unknown { cut_ordinal: None };
        assert!(verify_rsp_cpu_imem_report(&report, &bytes, &sha256(&bytes)).is_err());
    }

    #[test]
    fn dual_imem_progression_counts_installs_and_preserves_count_skip_wrap() {
        let mut ram = RamReplay::new(
            RamSnapshot {
                start: PhysicalAddr(0x1000),
                initial: vec![0; 40],
                final_bytes: vec![0; 40],
            },
            true,
            true,
            false,
        )
        .unwrap();
        let dmem = vec![0; 4096];
        let dorig = vec![SpByteOrigin::Unknown { cut_ordinal: None }; 4096];
        let mut imem = vec![0; 4096];
        let mut origins = dorig.clone();
        let mut promote = row("dma_promote", 1, 1);
        promote["bank"] = json!(1);
        promote["address"] = json!(0x1000);
        promote["offset"] = json!(0xff8);
        promote["dma"] = json!({"pbus":0xff8,"dram":0x1000,"length":8,"count":1,"skip":8});
        ram.observe(serde_json::from_value(promote).unwrap(), &dmem, &dorig)
            .unwrap();
        let mut ordinal = 2;
        for (pbus, dram, count) in [
            (0xff8, 0x1000, 1),
            (0, 0x1008, 1),
            (8, 0x1018, 0),
            (16, 0x1020, 0),
        ] {
            for kind in ["imem_dma_read", "imem_dma_write"] {
                let mut event = row(kind, ordinal, 1);
                event["bank"] = json!(1);
                event["address"] = json!(dram);
                event["offset"] = json!(pbus);
                event["bytes"] = json!(8);
                event["dma"] = json!({"pbus":pbus,"dram":dram,"length":8,"count":count,"skip":8});
                ram.imem_ingress(
                    serde_json::from_value(event).unwrap(),
                    &mut imem,
                    &mut origins,
                )
                .unwrap();
                ordinal += 1;
            }
        }
        let mut complete = row("dma_complete", ordinal, 1);
        complete["bank"] = json!(1);
        complete["address"] = json!(0x1028);
        complete["offset"] = json!(24);
        ram.observe(serde_json::from_value(complete).unwrap(), &dmem, &dorig)
            .unwrap();
        let graph = ram.finish().unwrap();
        assert_eq!(
            graph.promoted_requests.unwrap()[0].write_ordinals,
            [3, 5, 7, 9]
        );
        let installs = graph.imem_installs.unwrap();
        assert_eq!(
            installs
                .iter()
                .map(|i| i.descriptor.pbus)
                .collect::<Vec<_>>(),
            [0xff8, 0, 8, 16]
        );
        assert_eq!(installs[2].descriptor.dram, PhysicalAddr(0x1018));
        assert!(matches!(
            origins[0],
            SpByteOrigin::ImemDma {
                write_ordinal: 5,
                ..
            }
        ));
    }

    fn dmem_ingress_fixture() -> Value {
        let mut data = roundtrip_fixture(false);
        data["format"] = json!(DMEM_INGRESS_FORMAT);
        data["profile"] = json!(DMEM_INGRESS_PROFILE);
        let rows = data["events"].as_array_mut().unwrap();
        for r in rows.iter_mut() {
            if matches!(r["kind"].as_str(), Some("dma_promote" | "dma_complete")) {
                r["dma_direction"] = json!(if r["bank"] == 1 {
                    "imem_ingress"
                } else {
                    "dmem_egress"
                });
            }
        }
        let mut promote = row("dma_promote", 0, 0);
        promote["phase"] = json!(5);
        promote["address"] = json!(0x6008);
        promote["dma"] = json!({"pbus":0,"dram":0x6008,"length":0,"count":0,"skip":0});
        promote["dma_direction"] = json!("dmem_ingress");
        rows.push(promote.clone());
        for kind in ["dmem_dma_read", "dmem_dma_write"] {
            for lane in [0, 4] {
                let mut event = promote.clone();
                event["dma_direction"] = Value::Null;
                event["kind"] = json!(kind);
                event["address"] = json!(0x6008 + lane);
                event["offset"] = json!(lane);
                event["bytes"] = json!(4);
                rows.push(event);
            }
        }
        let mut complete = promote;
        complete["kind"] = json!("dma_complete");
        complete["dma"] = Value::Null;
        complete["address"] = json!(0x6010);
        complete["offset"] = json!(8);
        rows.push(complete);
        let mut seed = row("opaque_imem_seed", 0, 0);
        seed["phase"] = json!(6);
        seed["bank"] = json!(1);
        seed["address"] = json!(0x320);
        seed["offset"] = json!(0x320);
        seed["bytes"] = json!(4);
        seed["value"] = json!(0x8c040000u32);
        rows.push(seed);
        let mut begin = rows
            .iter()
            .rfind(|r| r["kind"] == "rsp_end")
            .unwrap()
            .clone();
        begin["kind"] = json!("rsp_begin");
        begin["phase"] = json!(6);
        begin["pc"] = json!(0x320);
        begin["next"] = json!(0x320);
        begin["word"] = json!(0x8c040000u32);
        let mut read = row("rsp_read", 0, 0);
        read["phase"] = json!(6);
        read["pc"] = json!(0x320);
        read["word"] = json!(0x8c040000u32);
        read["bytes"] = json!(4);
        let mut end = begin.clone();
        end["kind"] = json!("rsp_end");
        end["next"] = json!(0x324);
        rows.extend([begin, read, end]);
        for (n, value) in 0x8c040000u32.to_be_bytes().iter().enumerate() {
            data["final_imem"][0x320 + n] = json!(value);
        }
        reclock_promoted(&mut data);
        data
    }

    #[test]
    fn dmem_ingress_keeps_each_source_read_and_ram_writer_in_rsp_load_definition() {
        let report = inspect(&dmem_ingress_fixture()).unwrap();
        let graph = report.dma_consumption.as_ref().unwrap();
        let installs = graph.dmem_installs.as_ref().unwrap();
        assert_eq!(installs.len(), 2);
        assert!(
            installs[0].read_ordinal < installs[1].read_ordinal
                && installs[1].read_ordinal < installs[0].write_ordinal
        );
        assert!(installs[0].source_bytes.iter().all(|o|matches!(o,RamByteOrigin::SpDma {write_ordinal,..} if *write_ordinal==graph.writes[0].write_ordinal)));
        assert!(installs[1].source_bytes.iter().all(|o|matches!(o,RamByteOrigin::SpDma {write_ordinal,..} if *write_ordinal==graph.writes[1].write_ordinal)));
        let load = &report
            .rsp_definitions
            .as_ref()
            .unwrap()
            .last()
            .unwrap()
            .expression;
        let RspDefinitionExpression::DmemWordLoad(load) = load else {
            panic!("missing load")
        };
        assert!(load.origins.iter().all(|o|matches!(o,SpByteOrigin::DmemDma {read_ordinal,write_ordinal,parent:RamByteOrigin::SpDma {write_ordinal:ram_writer,..},..}
            if *read_ordinal==installs[0].read_ordinal && *write_ordinal==installs[0].write_ordinal && *ram_writer==graph.writes[0].write_ordinal)));
    }

    #[test]
    fn dmem_two_reads_precede_writes_and_decoys_direction_or_parents_cannot_replace_them() {
        let source = dmem_ingress_fixture();
        for mode in 0..5 {
            let mut data = source.clone();
            let rows = data["events"].as_array_mut().unwrap();
            let reads = rows
                .iter()
                .enumerate()
                .filter_map(|(n, r)| (r["kind"] == "dmem_dma_read").then_some(n))
                .collect::<Vec<_>>();
            let write = rows
                .iter()
                .position(|r| r["kind"] == "dmem_dma_write")
                .unwrap();
            match mode {
                0 => {
                    rows.remove(reads[1]);
                }
                1 => rows.swap(reads[1], write),
                2 => rows[reads[0]]["address"] = json!(0x600c),
                3 => rows[write]["value"] = json!(1),
                _ => {
                    rows.iter_mut()
                        .rfind(|r| r["kind"] == "dma_promote")
                        .unwrap()["dma_direction"] = json!("dmem_egress")
                }
            }
            reclock_promoted(&mut data);
            assert!(inspect(&data).is_err(), "mode {mode}");
        }
        let bytes = serde_json::to_vec(&source).unwrap();
        let mut report = inspect(&source).unwrap();
        report
            .dma_consumption
            .as_mut()
            .unwrap()
            .dmem_installs
            .as_mut()
            .unwrap()[0]
            .source_bytes[0] = RamByteOrigin::Unknown { cut_ordinal: None };
        assert!(verify_rsp_cpu_imem_report(&report, &bytes, &sha256(&bytes)).is_err());
    }

    #[test]
    fn dmem_ingress_count_skip_wrap_preserves_two_reads_then_two_stores_per_block() {
        let mut ram = RamReplay::new(
            RamSnapshot {
                start: PhysicalAddr(0x1000),
                initial: vec![0; 40],
                final_bytes: vec![0; 40],
            },
            true,
            true,
            true,
        )
        .unwrap();
        let mut dmem = vec![0; 4096];
        let mut origins = vec![SpByteOrigin::Unknown { cut_ordinal: None }; 4096];
        let mut promote = row("dma_promote", 1, 1);
        promote["dma_direction"] = json!("dmem_ingress");
        promote["address"] = json!(0x1000);
        promote["offset"] = json!(0xff8);
        promote["dma"] = json!({"pbus":0xff8,"dram":0x1000,"length":8,"count":1,"skip":8});
        ram.observe(serde_json::from_value(promote).unwrap(), &dmem, &origins)
            .unwrap();
        let mut ordinal = 2;
        for (pbus, dram, count) in [
            (0xff8, 0x1000, 1),
            (0, 0x1008, 1),
            (8, 0x1018, 0),
            (16, 0x1020, 0),
        ] {
            for kind in ["dmem_dma_read", "dmem_dma_write"] {
                for lane in [0, 4] {
                    let mut event = row(kind, ordinal, 1);
                    event["address"] = json!(dram + lane);
                    event["offset"] = json!((pbus + lane) & 4095);
                    event["bytes"] = json!(4);
                    event["dma"] =
                        json!({"pbus":pbus,"dram":dram,"length":8,"count":count,"skip":8});
                    ram.dmem_ingress(
                        serde_json::from_value(event).unwrap(),
                        &mut dmem,
                        &mut origins,
                    )
                    .unwrap();
                    ordinal += 1;
                }
            }
        }
        let mut complete = row("dma_complete", ordinal, 1);
        complete["dma_direction"] = json!("dmem_ingress");
        complete["address"] = json!(0x1028);
        complete["offset"] = json!(24);
        ram.observe(serde_json::from_value(complete).unwrap(), &dmem, &origins)
            .unwrap();
        let graph = ram.finish().unwrap();
        assert_eq!(
            graph.promoted_requests.unwrap()[0].write_ordinals,
            [4, 5, 8, 9, 12, 13, 16, 17]
        );
        let installs = graph.dmem_installs.unwrap();
        assert_eq!(
            installs.iter().map(|i| i.read_ordinal).collect::<Vec<_>>(),
            [2, 3, 6, 7, 10, 11, 14, 15]
        );
        assert_eq!(installs[4].source, PhysicalAddr(0x1018));
        assert!(matches!(
            origins[0],
            SpByteOrigin::DmemDma {
                read_ordinal: 6,
                write_ordinal: 8,
                ..
            }
        ));
    }

    #[test]
    fn equal_ram_decoy_cannot_supply_prior_dma_producer_parents() {
        let mut data = roundtrip_fixture(false);
        for field in ["initial", "final_bytes"] {
            data["ram"][field]
                .as_array_mut()
                .unwrap()
                .extend(vec![json!(0); 8]);
        }
        for r in data["events"].as_array_mut().unwrap() {
            if r["bank"] == 1
                && matches!(
                    r["kind"].as_str(),
                    Some("dma_promote" | "imem_dma_read" | "imem_dma_write")
                )
            {
                r["dma"]["dram"] = json!(0x6010);
                r["address"] = json!(0x6010);
            } else if r["bank"] == 1 && r["kind"] == "dma_complete" {
                r["address"] = json!(0x6018);
            }
        }
        let report = inspect(&data).unwrap();
        let graph = report.dma_consumption.unwrap();
        assert!(
            graph.imem_installs.unwrap()[0]
                .source_bytes
                .iter()
                .all(|o| matches!(o, RamByteOrigin::Unknown { cut_ordinal: None }))
        );
        assert!(
            report
                .imem_fetches
                .unwrap()
                .last()
                .unwrap()
                .origins
                .iter()
                .all(|o| matches!(
                    o,
                    SpByteOrigin::ImemDma {
                        parent: RamByteOrigin::Unknown { cut_ordinal: None },
                        ..
                    }
                ))
        );
    }

    fn pending_fixture() -> Value {
        let mut data = dmem_ingress_fixture();
        data["format"] = json!(PENDING_DMA_FORMAT);
        data["profile"] = json!(PENDING_DMA_PROFILE);
        let mut snapshot = json!({"pbus":0,"dram":0,"length":0,"count":0,"skip":0});
        data["initial_pending"] = json!({"bank":0,"descriptor":snapshot});
        let old = data["events"].as_array().unwrap().clone();
        let mut events = Vec::new();
        for event in old {
            if event["kind"] == "dma_promote" {
                let descriptor = &event["dma"];
                let values = [
                    descriptor["pbus"].as_u64().unwrap() | (event["bank"].as_u64().unwrap() << 12),
                    descriptor["dram"].as_u64().unwrap(),
                    descriptor["length"].as_u64().unwrap()
                        | (descriptor["count"].as_u64().unwrap() << 12)
                        | (descriptor["skip"].as_u64().unwrap() << 20),
                ];
                for (n, value) in values.into_iter().enumerate() {
                    if n == 0 {
                        snapshot["pbus"] = descriptor["pbus"].clone();
                    }
                    if n == 1 {
                        snapshot["dram"] = descriptor["dram"].clone();
                    }
                    if n == 2 {
                        snapshot = descriptor.clone();
                    }
                    let mut write = event.clone();
                    write["kind"] = json!("dma_pending_write");
                    write["address"] =
                        json!(if n == 2 && event["dma_direction"] == "dmem_egress" {
                            3
                        } else {
                            n
                        });
                    write["offset"] = snapshot["pbus"].clone();
                    write["bytes"] = json!(4);
                    write["value"] = json!(value);
                    write["cpu"] = json!(true);
                    write["dma"] = snapshot.clone();
                    write["pending_full"] = json!(n == 2);
                    if n != 2 {
                        write["dma_direction"] = Value::Null;
                    }
                    events.push(write);
                }
            }
            events.push(event);
        }
        data["events"] = json!(events);
        reclock_promoted(&mut data);
        data
    }

    #[test]
    fn pending_field_writers_and_length_commit_compose_with_consumption() {
        let data = pending_fixture();
        let report = inspect(&data).unwrap();
        let graph = report.dma_consumption.as_ref().unwrap();
        let requests = graph.promoted_requests.as_ref().unwrap();
        assert_eq!(requests.len(), 3);
        for request in requests {
            let parent = request.pending_provenance.as_ref().unwrap();
            assert_eq!(parent.commit_ordinal + 1, request.promote_context);
            assert_eq!(parent.pbus_write_ordinal, Some(parent.commit_ordinal - 2));
            assert_eq!(parent.dram_write_ordinal, Some(parent.commit_ordinal - 1));
        }
        assert_eq!(graph.pending_commits.as_ref().unwrap().len(), 3);
        let bytes = serde_json::to_vec(&data).unwrap();
        let mut forged = report.clone();
        forged
            .dma_consumption
            .as_mut()
            .unwrap()
            .promoted_requests
            .as_mut()
            .unwrap()[0]
            .pending_provenance
            .as_mut()
            .unwrap()
            .commit_ordinal += 1;
        assert!(verify_rsp_cpu_imem_report(&forged, &bytes, &sha256(&bytes)).is_err());
        assert!(
            !report.mutation_coverage_certified
                && !report.executable_lifetime_certified
                && !report.native_complete
        );
    }

    #[test]
    fn pending_source_metadata_and_idle_handoff_cannot_be_forged() {
        let source = pending_fixture();
        for mode in 0..8 {
            let mut data = source.clone();
            let rows = data["events"].as_array_mut().unwrap();
            let index = rows
                .iter()
                .position(|r| r["kind"] == "dma_pending_write")
                .unwrap();
            match mode {
                0 => {
                    rows.remove(index + 2);
                }
                1 => rows[index]["dma"]["pbus"] = json!(8),
                2 => rows[index]["pending_full"] = json!(true),
                3 => rows[index]["cpu"] = json!(false),
                4 => rows[index]["dma_direction"] = json!("imem_ingress"),
                5 => {
                    let mut decoy = rows[index].clone();
                    decoy["pending_full"] = json!(true);
                    decoy["dma_direction"] = json!("dmem_egress");
                    rows.insert(index + 3, decoy);
                }
                6 => rows[index]["value"] = json!(1_u64 << 32),
                _ => rows[index]["address"] = json!(4),
            }
            reclock_promoted(&mut data);
            assert!(inspect(&data).is_err(), "mode {mode}");
        }
        let mut data = source.clone();
        data["initial_pending"] = Value::Null;
        assert!(inspect(&data).is_err());
        let mut data = source;
        data["format"] = json!(DMEM_INGRESS_FORMAT);
        data["profile"] = json!(DMEM_INGRESS_PROFILE);
        assert!(inspect(&data).is_err());
    }

    #[test]
    fn full_pending_recommit_and_later_address_mutation_keep_separate_occurrences() {
        let mut pending = PendingDmaReplay {
            snapshot: PendingDmaSnapshot {
                bank: 1,
                descriptor: DmemDmaDescriptor {
                    pbus: 0x80,
                    dram: PhysicalAddr(0x1000),
                    length: 0,
                    count: 0,
                    skip: 0,
                },
            },
            direction: None,
            commit: None,
            pbus_writer: None,
            dram_writer: None,
            commits: Vec::new(),
            commit_decoder: None,
        };
        for ordinal in [1, 2] {
            let mut event = row("dma_pending_write", ordinal, ordinal);
            event["cpu"] = json!(true);
            event["address"] = json!(2);
            event["bank"] = json!(1);
            event["offset"] = json!(0x80);
            event["bytes"] = json!(4);
            event["pending_full"] = json!(true);
            event["dma_direction"] = json!("imem_ingress");
            event["dma"] = json!(pending.snapshot.descriptor);
            pending
                .write(&serde_json::from_value(event).unwrap(), None)
                .unwrap();
        }
        assert_eq!(pending.commits[1].superseded_commit, Some(1));
        let mut event = row("dma_pending_write", 3, 3);
        event["cpu"] = json!(true);
        event["address"] = json!(0);
        event["bank"] = json!(1);
        event["offset"] = json!(0x100);
        event["bytes"] = json!(4);
        event["value"] = json!(0xffff1107u32);
        event["pending_full"] = json!(true);
        event["dma_direction"] = json!("imem_ingress");
        let mut descriptor = pending.snapshot.descriptor.clone();
        descriptor.pbus = 0x100;
        event["dma"] = json!(descriptor);
        pending
            .write(&serde_json::from_value(event).unwrap(), None)
            .unwrap();
        let mut promote = row("dma_promote", 4, 4);
        promote["bank"] = json!(1);
        promote["dma_direction"] = json!("imem_ingress");
        promote["dma"] = json!(descriptor);
        let promote: Row = serde_json::from_value(promote).unwrap();
        let parent = pending.promote(&promote).unwrap();
        assert_eq!(parent.commit_ordinal, 2);
        assert_eq!(parent.pbus_write_ordinal, Some(3));
        assert_eq!(parent.dram_write_ordinal, None);
        assert!(pending.promote(&promote).is_err());
    }

    #[test]
    fn decoded_mmio_commit_retains_exact_sw_scope_and_rejects_equal_decoys() {
        let descriptor = DmemDmaDescriptor {
            pbus: 0x3e0,
            dram: PhysicalAddr(0x6028),
            length: 0,
            count: 0,
            skip: 0,
        };
        let make = || PendingDmaReplay {
            snapshot: PendingDmaSnapshot {
                bank: 1,
                descriptor: descriptor.clone(),
            },
            direction: None,
            commit: None,
            pbus_writer: Some(8),
            dram_writer: Some(9),
            commits: Vec::new(),
            commit_decoder: None,
        };
        let mut begin = row("cpu_begin", 11, 11);
        begin["cpu"] = json!(true);
        begin["word"] = json!(0xae200008u32);
        let mut registers = vec![0u64; 32];
        registers[17] = 0xffffffffa4040000;
        begin["gpr"] = json!(registers);
        let begin: Row = serde_json::from_value(begin).unwrap();
        let mut write = row("dma_pending_write", 12, 11);
        write["cpu"] = json!(true);
        write["word"] = json!(begin.word);
        write["address"] = json!(2);
        write["bank"] = json!(1);
        write["offset"] = json!(0x3e0);
        write["bytes"] = json!(4);
        write["dma"] = json!(descriptor);
        write["dma_direction"] = json!("imem_ingress");
        write["pending_full"] = json!(true);
        let write: Row = serde_json::from_value(write).unwrap();
        let mut pending = make();
        pending.write(&write, Some(&begin)).unwrap();
        assert_eq!(pending.commits[0].decoder_context, Some(11));
        let mut promote = row("dma_promote", 13, 13);
        promote["bank"] = json!(1);
        promote["dma"] = json!(descriptor);
        promote["dma_direction"] = json!("imem_ingress");
        let parent = pending
            .promote(&serde_json::from_value(promote).unwrap())
            .unwrap();
        assert_eq!(parent.commit_decoder_context, Some(11));
        assert_eq!(parent.commit_ordinal, 12);
        for mode in 0..5 {
            let mut decoy = write.clone();
            let mut cpu = begin.clone();
            match mode {
                0 => decoy.value = 1,
                1 => decoy.context = 12,
                2 => cpu.gpr[17] = 0xffffffff80040000,
                3 => decoy.address = 3,
                _ => cpu.word = 0xae290008,
            }
            assert!(make().write(&decoy, Some(&cpu)).is_err(), "mode {mode}");
        }
        assert!(make().write(&write, None).is_err());
    }

    fn cache_fixture() -> (RamReplay, Value) {
        let mut final_bytes = vec![0; 64];
        final_bytes[3] = 13;
        let mut ram = RamReplay::new(
            RamSnapshot {
                start: PhysicalAddr(0x1000),
                initial: vec![0; 64],
                final_bytes,
            },
            true,
            true,
            true,
        )
        .unwrap();
        ram.cached = true;
        for n in 0..4 {
            ram.origins[n] = RamByteOrigin::SpDma {
                write_ordinal: 100,
                source_offset: n as u16,
            };
        }
        let frame = json!({"slot":128,"tag_key":0x1001,"index":0,"words":vec![0u32;8]});
        (ram, frame)
    }
    fn cache_row(kind: &str, ordinal: u64, context: u64, address: u32, frame: &Value) -> Row {
        let mut event = row(kind, ordinal, context);
        event["cpu"] = json!(true);
        event["pc"] = json!(0xffffffff80001010u64);
        event["address"] = json!(address);
        if kind == "ram_fetch_begin" || kind == "ram_fetch_end" {
            event["fetch"] = json!({"physical":address,"cached":true});
        } else {
            event["bytes"] = json!(32);
        }
        if kind != "ram_fetch_begin" {
            event["cache_line"] = frame.clone();
        }
        serde_json::from_value(event).unwrap()
    }
    #[test]
    fn cached_consumption_keeps_fill_time_dma_parents_after_changed_backing() {
        let (mut ram, frame) = cache_fixture();
        let dmem = vec![0; 4096];
        let origins = vec![SpByteOrigin::Unknown { cut_ordinal: None }; 4096];
        ram.observe(
            cache_row("ram_fetch_begin", 1, 1, 0x1010, &frame),
            &dmem,
            &origins,
        )
        .unwrap();
        ram.cache(cache_row("cache_burst_read", 2, 1, 0x1000, &frame))
            .unwrap();
        ram.cache(cache_row("cache_fill", 3, 1, 0x1000, &frame))
            .unwrap();
        ram.observe(
            cache_row("ram_fetch_end", 4, 1, 0x1010, &frame),
            &dmem,
            &origins,
        )
        .unwrap();
        let mut decoded = row("cpu_begin", 5, 5);
        decoded["pc"] = json!(0xffffffff80001010u64);
        ram.bind(&serde_json::from_value(decoded).unwrap()).unwrap();
        let mut write = row("ram_write", 6, 0);
        write["address"] = json!(0x1000);
        write["bytes"] = json!(4);
        write["value"] = json!(13);
        ram.observe(serde_json::from_value(write).unwrap(), &dmem, &origins)
            .unwrap();
        let mut begin = cache_row("ram_fetch_begin", 7, 7, 0x1000, &frame);
        begin.pc = 0xffffffff80001000;
        ram.observe(begin, &dmem, &origins).unwrap();
        let mut end = cache_row("ram_fetch_end", 8, 7, 0x1000, &frame);
        end.pc = 0xffffffff80001000;
        ram.observe(end, &dmem, &origins).unwrap();
        let mut decoded = row("cpu_begin", 9, 9);
        decoded["pc"] = json!(0xffffffff80001000u64);
        ram.bind(&serde_json::from_value(decoded).unwrap()).unwrap();
        assert_eq!(
            ram.origins[0],
            RamByteOrigin::Unknown {
                cut_ordinal: Some(6)
            }
        );
        let graph = ram.finish().unwrap();
        let fetches = graph.cached_fetches.unwrap();
        assert_eq!(fetches[1].word, 0);
        assert_eq!(fetches[1].fill_ordinal, 3);
        assert_eq!(fetches[1].burst_ordinal, 2);
        assert_eq!(
            fetches[1].origins[0],
            RamByteOrigin::SpDma {
                write_ordinal: 100,
                source_offset: 0
            }
        );
        assert!(graph.fetches.is_empty());
    }
    #[test]
    fn cached_burst_fill_scope_cardinality_and_nonfetched_lanes_are_rechecked() {
        let dmem = vec![0; 4096];
        let origins = vec![SpByteOrigin::Unknown { cut_ordinal: None }; 4096];
        for mode in 0..6 {
            let (mut ram, frame) = cache_fixture();
            ram.observe(
                cache_row("ram_fetch_begin", 1, 1, 0x1010, &frame),
                &dmem,
                &origins,
            )
            .unwrap();
            if mode == 0 {
                assert!(
                    ram.cache(cache_row("cache_fill", 2, 1, 0x1000, &frame))
                        .is_err()
                );
                continue;
            }
            let mut burst = cache_row("cache_burst_read", 2, 1, 0x1000, &frame);
            match mode {
                1 => burst.cache_line.as_mut().unwrap().words[7] = 1,
                2 => burst.context = 99,
                3 => burst.address = 0x1020,
                _ => {}
            }
            if mode <= 3 {
                assert!(ram.cache(burst).is_err(), "mode {mode}");
                continue;
            }
            ram.cache(burst).unwrap();
            if mode == 4 {
                assert!(
                    ram.cache(cache_row("cache_burst_read", 3, 1, 0x1000, &frame))
                        .is_err()
                );
            } else {
                let mut fill = cache_row("cache_fill", 4, 1, 0x1000, &frame);
                fill.cache_line.as_mut().unwrap().tag_key ^= 0x1000;
                assert!(ram.cache(fill).is_err());
            }
        }
    }
    fn invalidate_fixture() -> (RamReplay, Row, Row) {
        let (mut ram, value) = cache_fixture();
        ram.invalidation_enabled = true;
        let frame: FetchCacheLine = serde_json::from_value(value).unwrap();
        ram.cache_state.insert(frame.slot, frame);
        ram.cache_slots.insert(frame.slot, 0);
        ram.cache_fills.push(DmaCacheFill {
            fetch_context: 1,
            burst_ordinal: 2,
            fill_ordinal: 3,
            physical_line: PhysicalAddr(0x1000),
            cache_line: frame,
            source_bytes: std::array::from_fn(|n| ram.origins[n].clone()),
        });
        let mut begin = row("cpu_begin", 5, 5);
        begin["word"] = json!(0xbe500000u32);
        let mut gpr = vec![0u64; 32];
        gpr[18] = 0xffffffff80001000;
        begin["gpr"] = json!(gpr);
        begin["cpu"] = json!(true);
        let mut effect = begin.clone();
        effect["kind"] = json!("cache_operation");
        effect["ordinal"] = json!(6);
        effect["address"] = json!(0x1000);
        effect["gpr"] = json!([]);
        let mut after = frame;
        after.tag_key &= !1;
        effect["cache_operation"] = json!(DmaCacheOperation {
            virtual_address: GuestVirtualAddr(gpr[18]),
            operation: 16,
            before: frame,
            after,
        });
        (
            ram,
            serde_json::from_value(begin).unwrap(),
            serde_json::from_value(effect).unwrap(),
        )
    }
    #[test]
    fn invalidation_ends_old_fill_and_equal_refill_uses_fresh_writer_parents() {
        let (mut ram, begin, effect) = invalidate_fixture();
        ram.invalidate(&effect, &begin).unwrap();
        assert!(ram.cache_slots.is_empty());
        assert_eq!(ram.cache_invalidations[0].ended_fill, Some(3));
        // An invalidation repeated against the now-invalid tuple is a miss.
        let mut repeated = effect.clone();
        let operation = repeated.cache_operation.as_mut().unwrap();
        operation.before = operation.after;
        ram.invalidate(&repeated, &begin).unwrap();
        assert!(!ram.cache_invalidations[1].hit);
        assert_eq!(ram.cache_invalidations[1].ended_fill, None);
        let dmem = vec![0; 4096];
        let origins = vec![SpByteOrigin::Unknown { cut_ordinal: None }; 4096];
        let value = serde_json::to_value(effect.cache_operation.unwrap().before).unwrap();
        ram.observe(
            cache_row("ram_fetch_begin", 8, 8, 0x1010, &value),
            &dmem,
            &origins,
        )
        .unwrap();
        let mut stale = cache_row("ram_fetch_end", 9, 8, 0x1010, &value);
        let active = ram.active.as_ref().unwrap().0.clone();
        assert!(ram.cached_end(&active, &stale, true).is_err());
        // Equal backing bits do not make writer100 the parent of this new fill.
        ram.origins[0] = RamByteOrigin::SpDma {
            write_ordinal: 200,
            source_offset: 0,
        };
        ram.cache(cache_row("cache_burst_read", 9, 8, 0x1000, &value))
            .unwrap();
        ram.cache(cache_row("cache_fill", 10, 8, 0x1000, &value))
            .unwrap();
        stale.ordinal = 11;
        ram.observe(stale, &dmem, &origins).unwrap();
        assert_eq!(
            ram.cache_fills[1].source_bytes[0],
            RamByteOrigin::SpDma {
                write_ordinal: 200,
                source_offset: 0
            }
        );
        assert_eq!(ram.cached_fetches[0].fill_ordinal, 10);
    }
    #[test]
    fn invalidate_miss_preserves_other_tag_parents_and_initial_invalid_state() {
        let (mut ram, mut begin, mut effect) = invalidate_fixture();
        begin.gpr[18] += 0x4000;
        effect.address += 0x4000;
        let operation = effect.cache_operation.as_mut().unwrap();
        operation.virtual_address.0 += 0x4000;
        operation.after = operation.before;
        ram.invalidate(&effect, &begin).unwrap();
        assert!(!ram.cache_invalidations[0].hit);
        assert_eq!(ram.cache_slots[&128], 0);
        ram.cache_state.clear();
        ram.cache_slots.clear();
        let operation = effect.cache_operation.as_mut().unwrap();
        operation.before.tag_key = 0;
        operation.after = operation.before;
        ram.invalidate(&effect, &begin).unwrap();
        assert!(!ram.cache_invalidations[1].hit);
    }
    #[test]
    fn invalidate_operand_scope_full_tuple_and_transition_forgeries_fail_closed() {
        for mode in 0..12 {
            let (mut ram, mut begin, mut effect) = invalidate_fixture();
            let operation = effect.cache_operation.as_mut().unwrap();
            match mode {
                0 => operation.before.words[7] = 1,
                1 => operation.after.words[7] = 1,
                2 => operation.after.tag_key |= 1,
                3 => operation.before.index = 32,
                4 => operation.before.slot = 129,
                5 => operation.operation = 0,
                6 => operation.virtual_address.0 += 4,
                7 => begin.gpr[18] += 4,
                8 => effect.context += 1,
                9 => effect.address += 4,
                10 => ram.invalidation_enabled = false,
                _ => effect.cpu = false,
            }
            assert!(ram.invalidate(&effect, &begin).is_err(), "mode {mode}");
        }
    }
    fn cpu_ram_fixture() -> (RamReplay, Row, Row, Loaded) {
        let (mut ram, _) = cache_fixture();
        ram.cpu_ram_enabled = true;
        let mut begin = row("cpu_begin", 20, 20);
        begin["word"] = json!(0xae680000u32);
        begin["cpu"] = json!(true);
        let mut gpr = vec![0u64; 32];
        gpr[19] = 0xffffffffa0001000;
        begin["gpr"] = json!(gpr);
        let mut effect = begin.clone();
        effect["kind"] = json!("cpu_ram_write");
        effect["ordinal"] = json!(21);
        effect["address"] = json!(0x1000);
        effect["bytes"] = json!(4);
        effect["gpr"] = json!([]);
        let parent = Loaded {
            context: 10,
            read: 11,
            register: 8,
            bits: 0,
            address: PhysicalAddr(0x04000000),
            origins: std::array::from_fn(|n| SpByteOrigin::DmemDma {
                promote_context: 1,
                read_ordinal: 2,
                write_ordinal: 3,
                source: PhysicalAddr(0x2000 + n as u32),
                parent: RamByteOrigin::SpDma {
                    write_ordinal: 4,
                    source_offset: n as u16,
                },
            }),
            transform: None,
        };
        (
            ram,
            serde_json::from_value(begin).unwrap(),
            serde_json::from_value(effect).unwrap(),
            parent,
        )
    }
    #[test]
    fn cpu_ram_copy_keeps_held_load_parents_but_unattributed_equal_store_cuts_them() {
        let (mut ram, begin, effect, parent) = cpu_ram_fixture();
        ram.cpu_write(&effect, &begin, Some(&parent)).unwrap();
        for n in 0..4 {
            assert_eq!(
                ram.origins[n],
                RamByteOrigin::CpuCopy {
                    write_ordinal: 21,
                    source_offset: n as u8
                }
            );
        }
        let copied = ram.cpu_writes[0].copy_parent.as_ref().unwrap();
        assert_eq!(copied.source_bytes, parent.origins);
        assert_eq!((copied.load_context, copied.read_ordinal), (10, 11));
        let mut equal = effect;
        equal.ordinal = 22;
        ram.cpu_write(&equal, &begin, None).unwrap();
        assert!(ram.cpu_writes[1].copy_parent.is_none());
        assert!(ram.origins[..4].iter().all(|origin| *origin
            == RamByteOrigin::Unknown {
                cut_ordinal: Some(22)
            }));
        assert_eq!(ram.bytes[..4], [0; 4]);
    }
    #[test]
    fn cpu_ram_copy_cannot_borrow_wrong_register_or_equal_low_bits_definition() {
        for mode in 0..11 {
            let (mut ram, mut begin, mut effect, mut parent) = cpu_ram_fixture();
            match mode {
                0 => parent.register = 9,
                1 => parent.bits = 1 << 32,
                2 => begin.gpr[19] = 0xffffffff80001000,
                3 => begin.gpr[19] += 1,
                4 => effect.address += 4,
                5 => effect.value = 1,
                6 => effect.bytes = 8,
                7 => effect.context += 1,
                8 => effect.cpu = false,
                9 => ram.cpu_ram_enabled = false,
                _ => effect.word ^= 1,
            }
            assert!(
                ram.cpu_write(&effect, &begin, Some(&parent)).is_err(),
                "mode {mode}"
            );
        }
    }
    #[test]
    fn xori_preserves_original_load_bytes_and_full_64_bit_result_in_ram_parent() {
        let (mut ram, mut begin, mut effect, mut parent) = cpu_ram_fixture();
        // A sign-extended LW remains sign-extended through unsigned XORI16.
        parent.bits = 0xffffffff80000000;
        begin.gpr[8] = parent.bits;
        let mut transform = begin.clone();
        transform.word = 0x3908ffff;
        transform.context = 15;
        let held = Loaded::xori(Some(parent.clone()), &transform)
            .unwrap()
            .unwrap();
        assert_eq!(held.bits, 0xffffffff8000ffff);
        assert_eq!(held.origins, parent.origins);
        begin.gpr[8] = held.bits;
        effect.value = 0x8000ffff;
        ram.cpu_write(&effect, &begin, Some(&held)).unwrap();
        let copied = ram.cpu_writes[0].copy_parent.as_ref().unwrap();
        let receipt = copied.transform.as_ref().unwrap();
        assert_eq!(receipt.decoder_context, 15);
        assert_eq!(
            (receipt.source_value, receipt.result_value),
            (parent.bits, held.bits)
        );
        assert_eq!(copied.read_ordinal, parent.read);
        assert_eq!(ram.bytes[..4], [0x80, 0, 0xff, 0xff]);
    }
    #[test]
    fn repeated_or_renamed_xori_cannot_recover_a_held_copy_parent_from_equal_bits() {
        let (_, mut begin, _, parent) = cpu_ram_fixture();
        begin.word = 0x39080021;
        let held = Loaded::xori(Some(parent), &begin).unwrap().unwrap();
        begin.gpr[8] = held.bits;
        assert!(Loaded::xori(Some(held), &begin).unwrap().is_none());
        let (_, mut begin, _, parent) = cpu_ram_fixture();
        begin.word = 0x39090021;
        assert!(
            Loaded::xori(Some(parent.clone()), &begin)
                .unwrap()
                .is_none()
        );
        assert!(Loaded::xori(None, &begin).unwrap().is_none());
        begin.gpr[8] = 1 << 32;
        assert!(Loaded::xori(Some(parent), &begin).is_err());
    }
    fn break_fixture() -> (Row, Row) {
        let mut begin: Row = serde_json::from_value(row("cpu_begin", 10, 10)).unwrap();
        begin.word = 13;
        begin.pc = 0xffffffff80001000;
        begin.cpu = true;
        begin.gpr = vec![0; 32];
        begin.exception_state = Some(CpuExceptionState {
            pc: GuestVirtualAddr(begin.pc),
            bev: false,
            exl: false,
            erl: false,
            kernel_mode: KernelAddressMode::Bits32,
            kernel: true,
            cause: 0,
            branch_delay: false,
            epc: GuestVirtualAddr(0x1234),
            delay_slot: false,
        });
        let mut transfer = begin.clone();
        transfer.kind = Kind::ExceptionTransfer;
        transfer.ordinal = 11;
        transfer.gpr.clear();
        let state = transfer.exception_state.as_mut().unwrap();
        state.pc = GuestVirtualAddr(0xffffffff80000180);
        state.exl = true;
        state.cause = 9;
        state.epc = GuestVirtualAddr(begin.pc);
        (begin, transfer)
    }
    #[test]
    fn break_transfer_derives_general_root_and_overwrites_old_epc() {
        let (begin, transfer) = break_fixture();
        let receipt = break_transfer(&begin, &transfer).unwrap();
        assert_eq!(receipt.root.root, GuestVirtualAddr(0xffffffff80000180));
        assert_eq!(receipt.after.epc, GuestVirtualAddr(begin.pc));
        assert_ne!(receipt.before.epc, receipt.after.epc);
        assert_eq!(
            (receipt.trigger_context, receipt.transfer_ordinal),
            (10, 11)
        );
        assert_eq!((receipt.fetch_context, receipt.decoder_context), (0, 0));
    }
    #[test]
    fn break_transfer_cannot_borrow_nested_delay_bev_or_wrong_result_state() {
        for mode in 0..13 {
            let (mut begin, mut transfer) = break_fixture();
            match mode {
                0 => begin.exception_state.as_mut().unwrap().exl = true,
                1 => begin.exception_state.as_mut().unwrap().bev = true,
                2 => begin.exception_state.as_mut().unwrap().erl = true,
                3 => begin.exception_state.as_mut().unwrap().delay_slot = true,
                4 => {
                    begin.exception_state.as_mut().unwrap().kernel_mode = KernelAddressMode::Bits64
                }
                5 => begin.exception_state.as_mut().unwrap().kernel = false,
                6 => transfer.exception_state.as_mut().unwrap().pc.0 += 4,
                7 => transfer.exception_state.as_mut().unwrap().epc.0 -= 4,
                8 => transfer.exception_state.as_mut().unwrap().cause = 8,
                9 => transfer.exception_state.as_mut().unwrap().exl = false,
                10 => transfer.exception_state.as_mut().unwrap().branch_delay = true,
                11 => transfer.context += 1,
                _ => begin.word = 12,
            }
            assert!(break_transfer(&begin, &transfer).is_err(), "mode {mode}");
        }
    }
    fn eret_fixture() -> (Row, Row, CpuExceptionRoot) {
        let (trigger, transfer) = break_fixture();
        let producer = break_transfer(&trigger, &transfer).unwrap();
        let mut begin = trigger;
        begin.pc = 0xffffffff80000190;
        begin.word = 0x42000018;
        begin.context = 20;
        begin.ordinal = 20;
        begin.exception_state = None;
        begin.return_state = Some(CpuReturnState {
            state: CpuExceptionState {
                pc: GuestVirtualAddr(begin.pc),
                ..producer.after.clone()
            },
            interrupt_enable: false,
            llbit: true,
        });
        let mut end = begin.clone();
        end.kind = Kind::ReturnTransfer;
        end.ordinal = 21;
        end.gpr.clear();
        let after = end.return_state.as_mut().unwrap();
        after.state.pc = after.state.epc;
        after.state.exl = false;
        after.llbit = false;
        (begin, end, producer)
    }
    #[test]
    fn eret_uses_live_epc_generation_clears_exl_and_llbit() {
        let (begin, end, producer) = eret_fixture();
        let receipt = eret_transfer(&begin, &end, &producer, None).unwrap();
        assert_eq!(receipt.epc_transfer_ordinal, producer.transfer_ordinal);
        assert_eq!(receipt.after.state.pc, producer.after.epc);
        assert!(!receipt.after.state.exl && !receipt.after.llbit);
        assert!(receipt.before.llbit);
    }
    #[test]
    fn eret_cannot_borrow_equal_past_capture_or_unsupported_selector_state() {
        for mode in 0..9 {
            let (mut begin, mut end, mut producer) = eret_fixture();
            match mode {
                0 => begin.return_state.as_mut().unwrap().state.epc.0 += 4,
                1 => producer.after.epc.0 += 4,
                2 => begin.return_state.as_mut().unwrap().state.erl = true,
                3 => begin.return_state.as_mut().unwrap().interrupt_enable = true,
                4 => end.return_state.as_mut().unwrap().llbit = true,
                5 => end.return_state.as_mut().unwrap().state.exl = true,
                6 => end.return_state.as_mut().unwrap().state.pc.0 += 4,
                7 => end.context += 1,
                _ => begin.word ^= 1,
            }
            assert!(
                eret_transfer(&begin, &end, &producer, None).is_err(),
                "mode {mode}"
            );
        }
    }
    fn epc_fixture() -> (Row, Row, CpuExceptionRoot) {
        let (mut begin, _, producer) = eret_fixture();
        begin.word = 0x40087000;
        begin.return_state.as_mut().unwrap().llbit = false;
        begin.epc_state = begin.return_state.take();
        let mut row = begin.clone();
        row.kind = Kind::EpcRead;
        row.ordinal += 1;
        row.gpr.clear();
        (begin, row, producer)
    }
    #[test]
    fn equal_epc_write_is_fresh_generation_and_eret_selects_it() {
        let (begin, read_row, producer) = epc_fixture();
        let read = epc_read(&begin, &read_row, &producer, None).unwrap();
        let mut write_begin = begin.clone();
        write_begin.word = 0x40887000;
        write_begin.ordinal += 5;
        write_begin.context = write_begin.ordinal;
        write_begin.gpr[8] = read.value;
        let mut write_row = write_begin.clone();
        write_row.ordinal += 1;
        write_row.kind = Kind::EpcWrite;
        write_row.gpr.clear();
        let write = epc_write(
            &write_begin,
            &write_row,
            &producer,
            None,
            Some(&EpcHeld {
                read: read.clone(),
                transform: None,
            }),
            false,
        )
        .unwrap();
        assert_eq!(write.value, producer.after.epc.0);
        assert_ne!(write.write_ordinal, producer.transfer_ordinal);
        let (ret, end, _) = eret_fixture();
        let receipt = eret_transfer(&ret, &end, &producer, Some(&write)).unwrap();
        assert_eq!(receipt.epc_write_ordinal, Some(write.write_ordinal));
        // An equal second write cannot borrow a read from the ended generation.
        assert!(
            epc_write(
                &write_begin,
                &write_row,
                &producer,
                Some(&write),
                Some(&EpcHeld {
                    read: read.clone(),
                    transform: None
                }),
                false
            )
            .is_err()
        );
        let fresh_read = epc_read(&begin, &read_row, &producer, Some(&write)).unwrap();
        assert_eq!(fresh_read.epc_write_ordinal, Some(write.write_ordinal));
        assert!(
            epc_write(
                &write_begin,
                &write_row,
                &producer,
                Some(&write),
                Some(&EpcHeld {
                    read: fresh_read,
                    transform: None
                }),
                false
            )
            .is_ok()
        );
    }
    #[test]
    fn epc_access_rejects_wrong_effect_operand_state_and_equal_low_bits() {
        for mode in 0..12 {
            let (mut begin, mut row, producer) = epc_fixture();
            let read = epc_read(&begin, &row, &producer, None).unwrap();
            begin.word = 0x40887000;
            begin.gpr[8] = read.value;
            row.word = begin.word;
            row.kind = Kind::EpcWrite;
            match mode {
                0 => begin.word ^= 0x800,
                1 => begin.word ^= 1,
                2 => begin.word ^= 0x10000,
                3 => begin.gpr[8] &= 0xffffffff,
                4 => row.context += 1,
                5 => row.kind = Kind::EpcRead,
                6 => row.epc_state.as_mut().unwrap().state.epc.0 += 4,
                7 => begin.epc_state.as_mut().unwrap().state.erl = true,
                8 => begin.epc_state.as_mut().unwrap().interrupt_enable = true,
                9 => row.epc_state.as_mut().unwrap().llbit = true,
                10 => row.gpr = vec![0; 32],
                _ => row.value = read.value,
            }
            assert!(
                epc_write(
                    &begin,
                    &row,
                    &producer,
                    None,
                    Some(&EpcHeld {
                        read: read.clone(),
                        transform: None
                    }),
                    false
                )
                .is_err(),
                "mode {mode}"
            );
        }
    }
    #[test]
    fn transformed_epc_writer_selects_changed_target_and_new_read_generation() {
        let (mut begin, mut row, producer) = epc_fixture();
        let read = epc_read(&begin, &row, &producer, None).unwrap();
        let held = EpcHeld {
            read,
            transform: None,
        };
        begin.word = 0x39080004;
        begin.gpr[8] = held.value();
        let held = EpcHeld::xori(Some(held), &begin).unwrap().unwrap();
        assert_eq!(held.value(), producer.after.epc.0 ^ 4);
        begin.word = 0x40887000;
        begin.gpr[8] = held.value();
        row.word = begin.word;
        row.kind = Kind::EpcWrite;
        row.epc_state.as_mut().unwrap().state.epc = GuestVirtualAddr(held.value());
        assert!(epc_write(&begin, &row, &producer, None, Some(&held), false).is_err());
        let write = epc_write(&begin, &row, &producer, None, Some(&held), true).unwrap();
        assert_eq!(write.transform.as_ref().unwrap().word, 0x39080004);
        let (mut ret, mut end, _) = eret_fixture();
        ret.return_state.as_mut().unwrap().state.epc = write.after.state.epc;
        end.return_state.as_mut().unwrap().state.epc = write.after.state.epc;
        end.return_state.as_mut().unwrap().state.pc = write.after.state.epc;
        assert!(eret_transfer(&ret, &end, &producer, None).is_err());
        let returned = eret_transfer(&ret, &end, &producer, Some(&write)).unwrap();
        assert_eq!(returned.after.state.pc, write.after.state.epc);
        let (mut read_begin, mut read_row, _) = epc_fixture();
        read_begin.epc_state.as_mut().unwrap().state.epc = write.after.state.epc;
        read_row.epc_state.as_mut().unwrap().state.epc = write.after.state.epc;
        let fresh = epc_read(&read_begin, &read_row, &producer, Some(&write)).unwrap();
        assert_eq!(fresh.value, write.value);
        assert_eq!(fresh.epc_write_ordinal, Some(write.write_ordinal));
    }
    #[test]
    fn epc_transform_repeated_renamed_or_unattributed_sources_cut_definition() {
        let (mut begin, row, producer) = epc_fixture();
        let held = EpcHeld {
            read: epc_read(&begin, &row, &producer, None).unwrap(),
            transform: None,
        };
        begin.word = 0x39088000;
        begin.gpr[8] = held.value();
        let once = EpcHeld::xori(Some(held.clone()), &begin).unwrap().unwrap();
        assert_eq!(once.value(), held.value() ^ 0x8000); // unsigned immediate/full64
        begin.gpr[8] = once.value();
        assert!(EpcHeld::xori(Some(once), &begin).unwrap().is_none());
        begin.gpr[8] = held.value();
        begin.word = 0x39090004;
        assert!(EpcHeld::xori(Some(held.clone()), &begin).unwrap().is_none());
        begin.gpr[8] &= 0xffffffff;
        assert!(EpcHeld::xori(Some(held), &begin).is_err());
        assert!(EpcHeld::xori(None, &begin).unwrap().is_none());
    }
}
