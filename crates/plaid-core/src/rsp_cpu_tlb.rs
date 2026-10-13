//! Current TLB operation facts for the unified writer/cache/execution graph.
//! Raw entry observations never mint operation generations by themselves.
use crate::tlbr_history::{TlbContextFingerprint, TlbrContextGeneration};
use crate::{
    exception_roots::KernelAddressMode,
    program::{GuestVirtualAddr, PhysicalAddr},
    rom::sha256,
    rsp_cpu_imem::CpuReturnState,
    tlb_geometry::derive_tlb_page_offset,
    tlb_history::{TlbEntryFingerprint, TlbwiGeneration},
};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Entry {
    pub global: [bool; 2],
    pub valid: [bool; 2],
    pub dirty: [bool; 2],
    pub cca: [u8; 2],
    pub physical: [u64; 2],
    pub page_mask: u32,
    pub virtual_address: u64,
    pub asid: u8,
    pub region: u8,
    pub globals: bool,
    pub mask_hi: u64,
    pub mask_lo: u64,
    pub select: u64,
}
fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}
impl Entry {
    fn validate(&self) -> Result<(), String> {
        require(
            self.page_mask == 0
                && self.region == 0
                && self.cca.iter().all(|cca| *cca <= 7)
                && self
                    .physical
                    .iter()
                    .all(|pa| *pa <= u64::from(u32::MAX) && pa.is_multiple_of(4096))
                && self.mask_hi == ((1u64 << 40) - 1) & !0x1fff
                && self.mask_lo == 0xfff
                && self.select == 0x1000
                && self.virtual_address == self.virtual_address & self.mask_hi
                && self.global == [self.globals; 2],
            "TLB entry outside normalized low-region 4KiB scope",
        )
    }
    fn fingerprint(&self) -> TlbEntryFingerprint {
        TlbEntryFingerprint {
            sha256: sha256(&serde_json::to_vec(self).expect("entry serialization")),
        }
    }
    fn matches(&self, pc: u64, asid: u8) -> bool {
        (self.globals || self.asid == asid) && pc & self.mask_hi == self.virtual_address
    }
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Initial {
    pub index: u32,
    pub staged: Entry,
    pub entries: Vec<Entry>,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct State {
    pub control: CpuReturnState,
    pub index: u32,
    pub staged: Entry,
    pub entries: Vec<Entry>,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Observation {
    pub asid: u8,
    pub kernel: bool,
    pub bits: u8,
    pub entries: Vec<Entry>,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Witness {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tlbr_load_ordinal: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub entry_lo_write_ordinal: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub context_write_ordinal: Option<u64>,
    pub write_ordinal: u64,
    pub selected_slot: u32,
    pub current_asid: u8,
    pub entry: Entry,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ContextWrite {
    pub decoder_context: u64,
    pub write_ordinal: u64,
    pub end_ordinal: u64,
    pub source_register: u8,
    pub register_value: u64,
    pub before: State,
    pub after: State,
    pub same_staged_content: bool,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ContextLoad {
    pub generation: TlbrContextGeneration,
    pub installed_write_ordinal: u64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub entry_lo_write_ordinal: Option<u64>,
}
#[derive(Clone, Copy)]
enum ContextSource {
    EntryHi(usize),
    Tlbr(usize),
}
pub(crate) struct Replay {
    initial: Initial,
    staged: Entry,
    pub context_writes: Vec<ContextWrite>,
    pub entry_lo_writes: Vec<ContextWrite>,
    pub context_loads: Vec<ContextLoad>,
    current_context: Option<ContextSource>,
    staged_page_writer: Option<u64>,
    entries: Vec<Entry>,
    writers: [Option<usize>; 32],
    page_writers: [Option<u64>; 32],
    pub generations: Vec<TlbwiGeneration>,
}
impl Replay {
    pub fn new(initial: Initial) -> Result<Self, String> {
        require(
            initial.entries.len() == 32 && initial.index < 32,
            "invalid initial TLB array/index",
        )?;
        initial.staged.validate()?;
        for entry in &initial.entries {
            entry.validate()?;
            require(
                entry.valid == [false; 2],
                "initial valid mapping lacks captured writer",
            )?;
        }
        Ok(Self {
            entries: initial.entries.clone(),
            staged: initial.staged.clone(),
            context_writes: Vec::new(),
            entry_lo_writes: Vec::new(),
            context_loads: Vec::new(),
            current_context: None,
            staged_page_writer: None,
            initial,
            writers: [None; 32],
            page_writers: [None; 32],
            generations: Vec::new(),
        })
    }
    pub fn write(
        &mut self,
        pc: u64,
        context: u64,
        ordinal: u64,
        before: &State,
        after: &State,
    ) -> Result<(), String> {
        let control = &before.control;
        require(
            control.state.pc.0 == pc
                && control.state.kernel
                && control.state.kernel_mode == KernelAddressMode::Bits32
                && !control.interrupt_enable
                && !control.state.bev
                && !control.state.exl
                && !control.state.erl
                && !control.state.delay_slot
                && !control.state.branch_delay
                && control.state.cause == 0
                && after.control == *control,
            "unsupported TLBWI privilege/state transition",
        )?;
        require(
            before.index == self.initial.index
                && after.index == before.index
                && before.staged == self.staged
                && after.staged == before.staged
                && before.entries == self.entries,
            "TLBWI lost current slot/staged/table state",
        )?;
        let slot = before.index as usize;
        require(
            self.entry_lo_writes
                .last()
                .is_none_or(|write| write.end_ordinal != 0),
            "TLBWI preceded completed EntryLo0 write",
        )?;
        let mut expected = self.entries.clone();
        expected[slot] = before.staged.clone();
        require(
            after.entries == expected,
            "TLBWI completed table differs from selected-slot write",
        )?;
        self.generations.push(TlbwiGeneration {
            operation_generation: self.generations.len() as u64 + 1,
            epoch: 1,
            context,
            pc: GuestVirtualAddr(pc),
            begin_ordinal: context,
            write_ordinal: ordinal,
            end_ordinal: 0,
            selected_slot: before.index,
            staged_entry: before.staged.fingerprint(),
            before_entry: self.entries[slot].fingerprint(),
            after_entry: expected[slot].fingerprint(),
            same_entry_content: self.entries[slot] == expected[slot],
        });
        self.writers[slot] = Some(self.generations.len() - 1);
        self.page_writers[slot] = self.staged_page_writer;
        self.entries = expected;
        Ok(())
    }
    pub fn context_write(
        &mut self,
        pc: u64,
        context: u64,
        ordinal: u64,
        source: (u8, u64),
        before: &State,
        after: &State,
    ) -> Result<(), String> {
        let (register, value) = source;
        let control = &before.control;
        require(
            control.state.pc.0 == pc
                && control.state.kernel
                && control.state.kernel_mode == KernelAddressMode::Bits32
                && !control.interrupt_enable
                && !control.state.bev
                && !control.state.exl
                && !control.state.erl
                && !control.state.delay_slot
                && !control.state.branch_delay
                && control.state.cause == 0
                && after.control == *control,
            "unsupported EntryHi privilege/state transition",
        )?;
        require(
            before.index == self.initial.index
                && after.index == before.index
                && before.staged == self.staged
                && before.entries == self.entries
                && after.entries == before.entries,
            "EntryHi context write changed or borrowed installed table/state",
        )?;
        let mut expected = self.staged.clone();
        expected.asid = value as u8;
        expected.virtual_address =
            (expected.virtual_address & 0x1fff) | (value & (((1u64 << 40) - 1) & !0x1fff));
        expected.region = ((value >> 62) & 3) as u8;
        expected.validate()?;
        require(
            register > 0 && register < 32 && after.staged == expected,
            "EntryHi masked fields differ from full source register",
        )?;
        self.context_writes.push(ContextWrite {
            decoder_context: context,
            write_ordinal: ordinal,
            end_ordinal: 0,
            source_register: register,
            register_value: value,
            before: before.clone(),
            after: after.clone(),
            same_staged_content: before.staged == after.staged,
        });
        self.current_context = Some(ContextSource::EntryHi(self.context_writes.len() - 1));
        self.staged = expected;
        Ok(())
    }
    pub fn finish_context(&mut self, context: u64, ordinal: u64) -> Result<(), String> {
        let write = self
            .context_writes
            .last_mut()
            .ok_or("EntryHi lacks write occurrence")?;
        require(
            write.decoder_context == context
                && write.end_ordinal == 0
                && write.write_ordinal.checked_add(1) == Some(ordinal),
            "EntryHi end lost context write identity",
        )?;
        write.end_ordinal = ordinal;
        Ok(())
    }
    pub fn entry_lo_write(
        &mut self,
        pc: u64,
        context: u64,
        ordinal: u64,
        source: (u8, u64),
        before: &State,
        after: &State,
    ) -> Result<(), String> {
        let (register, value) = source;
        let control = &before.control;
        require(
            control.state.pc.0 == pc
                && control.state.kernel
                && control.state.kernel_mode == KernelAddressMode::Bits32
                && !control.interrupt_enable
                && !control.state.bev
                && !control.state.exl
                && !control.state.erl
                && !control.state.delay_slot
                && !control.state.branch_delay
                && control.state.cause == 0
                && after.control == *control,
            "unsupported EntryLo0 privilege/state transition",
        )?;
        require(
            before.index == self.initial.index
                && after.index == before.index
                && before.staged == self.staged
                && before.entries == self.entries
                && after.entries == before.entries,
            "EntryLo0 write changed or borrowed installed table/state",
        )?;
        let mut expected = self.staged.clone();
        expected.global[0] = value & 1 != 0;
        expected.valid[0] = value & 2 != 0;
        expected.dirty[0] = value & 4 != 0;
        expected.cca[0] = ((value >> 3) & 7) as u8;
        let mask = 0xff_ffffu64 << 12;
        expected.physical[0] = (expected.physical[0] & !mask) | (((value >> 6) & 0xff_ffff) << 12);
        expected.validate()?;
        require(
            register > 0 && register < 32 && after.staged == expected,
            "EntryLo0 masked fields differ from full source register",
        )?;
        self.entry_lo_writes.push(ContextWrite {
            decoder_context: context,
            write_ordinal: ordinal,
            end_ordinal: 0,
            source_register: register,
            register_value: value,
            before: before.clone(),
            after: after.clone(),
            same_staged_content: before.staged == after.staged,
        });
        self.staged_page_writer = Some(ordinal);
        self.staged = expected;
        Ok(())
    }
    pub fn finish_entry_lo(&mut self, context: u64, ordinal: u64) -> Result<(), String> {
        let write = self
            .entry_lo_writes
            .last_mut()
            .ok_or("EntryLo0 lacks write occurrence")?;
        require(
            write.decoder_context == context
                && write.end_ordinal == 0
                && write.write_ordinal.checked_add(1) == Some(ordinal),
            "EntryLo0 end lost page write identity",
        )?;
        write.end_ordinal = ordinal;
        Ok(())
    }
    pub fn finish(&mut self, context: u64, ordinal: u64) -> Result<(), String> {
        let generation = self
            .generations
            .last_mut()
            .ok_or("TLBWI lacks write occurrence")?;
        require(
            generation.context == context
                && generation.end_ordinal == 0
                && generation.write_ordinal.checked_add(1) == Some(ordinal),
            "TLBWI end lost operation identity",
        )?;
        generation.end_ordinal = ordinal;
        Ok(())
    }
    pub fn load(
        &mut self,
        pc: u64,
        context: u64,
        ordinal: u64,
        before: &State,
        after: &State,
    ) -> Result<(), String> {
        let control = &before.control;
        require(
            control.state.pc.0 == pc
                && control.state.kernel
                && control.state.kernel_mode == KernelAddressMode::Bits32
                && !control.interrupt_enable
                && !control.state.bev
                && !control.state.exl
                && !control.state.erl
                && !control.state.delay_slot
                && !control.state.branch_delay
                && control.state.cause == 0
                && after.control == *control,
            "unsupported TLBR privilege/state transition",
        )?;
        require(
            before.index == self.initial.index
                && after.index == before.index
                && before.staged == self.staged
                && before.entries == self.entries
                && after.entries == before.entries,
            "TLBR lost current slot/staged/table state",
        )?;
        let slot = before.index as usize;
        require(
            after.staged == self.entries[slot],
            "TLBR did not copy selected installed entry",
        )?;
        let writer = self.writers[slot].ok_or("TLBR selected entry lacks captured writer")?;
        require(
            self.generations[writer].end_ordinal != 0,
            "TLBR preceded completed installed write",
        )?;
        let fingerprint = |entry: &Entry| TlbContextFingerprint {
            sha256: entry.fingerprint().sha256,
            asid: entry.asid,
        };
        self.context_loads.push(ContextLoad {
            generation: TlbrContextGeneration {
                operation_generation: self.context_loads.len() as u64 + 1,
                epoch: 1,
                context,
                pc: GuestVirtualAddr(pc),
                begin_ordinal: context,
                load_ordinal: ordinal,
                end_ordinal: 0,
                selected_slot: before.index,
                before_context: fingerprint(&before.staged),
                selected_entry: fingerprint(&self.entries[slot]),
                after_context: fingerprint(&after.staged),
                same_context_content: before.staged == after.staged,
            },
            installed_write_ordinal: self.generations[writer].write_ordinal,
            entry_lo_write_ordinal: self.page_writers[slot],
        });
        self.current_context = Some(ContextSource::Tlbr(self.context_loads.len() - 1));
        self.staged_page_writer = self.page_writers[slot];
        self.staged = after.staged.clone();
        Ok(())
    }
    pub fn finish_load(&mut self, context: u64, ordinal: u64) -> Result<(), String> {
        let generation = &mut self
            .context_loads
            .last_mut()
            .ok_or("TLBR lacks load occurrence")?
            .generation;
        require(
            generation.context == context
                && generation.end_ordinal == 0
                && generation.load_ordinal.checked_add(1) == Some(ordinal),
            "TLBR end lost load identity",
        )?;
        generation.end_ordinal = ordinal;
        Ok(())
    }
    pub fn fetch(
        &self,
        pc: u64,
        physical: PhysicalAddr,
        observation: &Observation,
    ) -> Result<Witness, String> {
        require(
            pc < 0x80000000
                && pc.is_multiple_of(4)
                && observation.kernel
                && observation.bits == 32
                && observation.asid == self.staged.asid
                && observation.entries == self.entries,
            "mapped fetch lost current TLB/context snapshot",
        )?;
        // Invalid matching entries also count: they can fault before another
        // matching valid entry. Reject every ambiguity rather than pick a label.
        let matches: Vec<_> = self
            .entries
            .iter()
            .enumerate()
            .filter(|(_, entry)| entry.matches(pc, observation.asid))
            .collect();
        require(
            matches.len() == 1,
            "mapped fetch has ambiguous or absent TLB entry",
        )?;
        let (slot, entry) = matches[0];
        let page = derive_tlb_page_offset(entry.page_mask, GuestVirtualAddr(pc))
            .map_err(|e| e.to_string())?;
        let half = usize::from(pc & entry.select != 0);
        require(
            entry.valid[half]
                && entry.cca[half] == 3
                && entry.physical[half] + page.in_page_offset == u64::from(physical.0),
            "mapped cached fetch differs from valid CCA3 translation",
        )?;
        let index = self.writers[slot].ok_or("mapped fetch lacks current write generation")?;
        require(
            self.context_writes
                .last()
                .is_none_or(|write| write.end_ordinal != 0),
            "mapped fetch preceded completed context write",
        )?;
        let generation = &self.generations[index];
        let (context_write_ordinal, tlbr_load_ordinal) = match self.current_context {
            None => (None, None),
            Some(ContextSource::EntryHi(n)) => (Some(self.context_writes[n].write_ordinal), None),
            Some(ContextSource::Tlbr(n)) => {
                let load = &self.context_loads[n].generation;
                require(
                    load.end_ordinal != 0,
                    "mapped fetch preceded completed TLBR",
                )?;
                (None, Some(load.load_ordinal))
            }
        };
        require(
            generation.end_ordinal != 0,
            "mapped fetch preceded completed TLBWI",
        )?;
        Ok(Witness {
            tlbr_load_ordinal,
            entry_lo_write_ordinal: self.page_writers[slot],
            context_write_ordinal,
            write_ordinal: generation.write_ordinal,
            selected_slot: slot as u32,
            current_asid: observation.asid,
            entry: entry.clone(),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::rsp_cpu_imem::CpuExceptionState;
    fn fixture() -> (Replay, State, State) {
        let blank = Entry {
            global: [false; 2],
            valid: [false; 2],
            dirty: [false; 2],
            cca: [0; 2],
            physical: [0; 2],
            page_mask: 0,
            virtual_address: 0,
            asid: 0,
            region: 0,
            globals: false,
            mask_hi: ((1u64 << 40) - 1) & !0x1fff,
            mask_lo: 0xfff,
            select: 0x1000,
        };
        let mut staged = blank.clone();
        staged.valid[0] = true;
        staged.cca = [3; 2];
        staged.physical = [0x6000, 0x7000];
        staged.virtual_address = 0x6000;
        staged.asid = 7;
        let initial = Initial {
            index: 0,
            staged,
            entries: vec![blank; 32],
        };
        let control = CpuReturnState {
            state: CpuExceptionState {
                pc: GuestVirtualAddr(0xffffffffa0006080),
                bev: false,
                exl: false,
                erl: false,
                kernel_mode: KernelAddressMode::Bits32,
                kernel: true,
                cause: 0,
                branch_delay: false,
                epc: GuestVirtualAddr(0),
                delay_slot: false,
            },
            interrupt_enable: false,
            llbit: false,
        };
        let before = State {
            control,
            index: 0,
            staged: initial.staged.clone(),
            entries: initial.entries.clone(),
        };
        let mut after = before.clone();
        after.entries[0] = after.staged.clone();
        (Replay::new(initial).unwrap(), before, after)
    }
    #[test]
    fn equal_tlbwi_replaces_operation_identity_without_snapshot_diff() {
        let (mut replay, before, after) = fixture();
        let pc = before.control.state.pc.0;
        replay.write(pc, 10, 11, &before, &after).unwrap();
        let observation = Observation {
            asid: 7,
            kernel: true,
            bits: 32,
            entries: after.entries.clone(),
        };
        assert!(
            replay
                .fetch(0x6028, PhysicalAddr(0x6028), &observation)
                .is_err()
        );
        replay.finish(10, 12).unwrap();
        assert_eq!(
            replay
                .fetch(0x6028, PhysicalAddr(0x6028), &observation)
                .unwrap()
                .write_ordinal,
            11
        );
        replay.write(pc, 20, 21, &after, &after).unwrap();
        replay.finish(20, 22).unwrap();
        assert_eq!(
            replay
                .fetch(0x602c, PhysicalAddr(0x602c), &observation)
                .unwrap()
                .write_ordinal,
            21
        );
        assert_eq!(
            replay.generations[0].after_entry,
            replay.generations[1].after_entry
        );
        assert!(
            !replay.generations[0].same_entry_content && replay.generations[1].same_entry_content
        );
    }
    #[test]
    fn slot_staged_table_and_privilege_cannot_be_borrowed() {
        for mode in 0..8 {
            let (mut replay, mut before, mut after) = fixture();
            let pc = before.control.state.pc.0;
            match mode {
                0 => before.index = 32,
                1 => before.staged.asid += 1,
                2 => before.control.state.kernel = false,
                3 => before.control.state.exl = true,
                4 => after.entries[1] = after.staged.clone(),
                5 => after.entries[0].physical[0] = 0x8000,
                6 => after.control.state.pc.0 += 4,
                _ => before.entries[0] = before.staged.clone(),
            }
            assert!(
                replay.write(pc, 10, 11, &before, &after).is_err(),
                "mode {mode}"
            );
        }
    }
    #[test]
    fn mapped_fetch_rejects_context_translation_invalid_and_ambiguous_entries() {
        for mode in 0..9 {
            let (mut replay, before, mut after) = fixture();
            if mode == 5 {
                after.entries[0].valid[0] = false;
                replay.initial.staged = after.entries[0].clone();
                replay.staged = replay.initial.staged.clone();
            }
            if mode == 6 {
                after.entries[0].cca[0] = 2;
                replay.initial.staged = after.entries[0].clone();
                replay.staged = replay.initial.staged.clone();
            }
            let mut before = before;
            before.staged = replay.initial.staged.clone();
            after.staged = replay.initial.staged.clone();
            replay
                .write(before.control.state.pc.0, 10, 11, &before, &after)
                .unwrap();
            replay.finish(10, 12).unwrap();
            if mode == 7 {
                replay.entries[1] = replay.entries[0].clone();
            }
            let mut observation = Observation {
                asid: 7,
                kernel: true,
                bits: 32,
                entries: replay.entries.clone(),
            };
            let mut physical = PhysicalAddr(0x6028);
            match mode {
                0 => observation.asid = 8,
                1 => observation.bits = 64,
                2 => observation.kernel = false,
                3 => physical.0 += 4,
                4 => observation.entries[0].physical[0] = 0x8000,
                _ => {}
            }
            assert!(
                replay
                    .fetch(
                        if mode == 8 { 0x80006028 } else { 0x6028 },
                        physical,
                        &observation
                    )
                    .is_err(),
                "mode {mode}"
            );
        }
    }
    #[test]
    fn tlbr_context_load_restores_installed_page_parent_and_latest_context() {
        let (mut replay, before, installed) = fixture();
        let pc = before.control.state.pc.0;
        replay.write(pc, 10, 11, &before, &installed).unwrap();
        replay.finish(10, 12).unwrap();
        let mut staged = installed.clone();
        staged.staged.asid = 8;
        replay
            .context_write(pc, 20, 21, (25, 0x6008), &installed, &staged)
            .unwrap();
        replay.finish_context(20, 22).unwrap();
        staged.staged.physical[0] = 0xe000;
        staged.staged.dirty[0] = true;
        let mut prior = installed.clone();
        prior.staged.asid = 8;
        replay
            .entry_lo_write(pc, 30, 31, (27, 0x39e), &prior, &staged)
            .unwrap();
        replay.finish_entry_lo(30, 32).unwrap();
        let observation = Observation {
            asid: 7,
            kernel: true,
            bits: 32,
            entries: installed.entries.clone(),
        };
        replay.load(pc, 40, 41, &staged, &installed).unwrap();
        assert!(
            replay
                .fetch(0x6028, PhysicalAddr(0x6028), &observation)
                .is_err()
        );
        replay.finish_load(40, 42).unwrap();
        replay.load(pc, 50, 51, &installed, &installed).unwrap();
        replay.finish_load(50, 52).unwrap();
        let selected = replay
            .fetch(0x6028, PhysicalAddr(0x6028), &observation)
            .unwrap();
        assert_eq!(selected.tlbr_load_ordinal, Some(51));
        assert_eq!(selected.context_write_ordinal, None);
        assert_eq!(selected.entry_lo_write_ordinal, None);
        assert_eq!(selected.write_ordinal, 11);
        assert!(replay.context_loads[1].generation.same_context_content);
        assert_eq!(replay.context_loads[0].installed_write_ordinal, 11);
        replay.write(pc, 60, 61, &installed, &installed).unwrap();
        replay.finish(60, 62).unwrap();
        assert_eq!(
            replay
                .fetch(0x6028, PhysicalAddr(0x6028), &observation)
                .unwrap()
                .entry_lo_write_ordinal,
            None
        );
        replay
            .context_write(pc, 70, 71, (26, 0x6007), &installed, &installed)
            .unwrap();
        replay.finish_context(70, 72).unwrap();
        let selected = replay
            .fetch(0x6028, PhysicalAddr(0x6028), &observation)
            .unwrap();
        assert_eq!(selected.tlbr_load_ordinal, None);
        assert_eq!(selected.context_write_ordinal, Some(71));
    }
    #[test]
    fn tlbr_cannot_borrow_a_slot_snapshot_or_modify_the_installed_table() {
        for mode in 0..7 {
            let (mut replay, before, installed) = fixture();
            let pc = before.control.state.pc.0;
            if mode != 0 {
                replay.write(pc, 10, 11, &before, &installed).unwrap();
                replay.finish(10, 12).unwrap();
            }
            let mut before = installed.clone();
            let mut after = installed;
            match mode {
                0 => before.entries = replay.entries.clone(),
                1 => after.entries[0].asid = 8,
                2 => after.staged.physical[0] = 0xe000,
                3 => before.index = 32,
                4 => before.control.state.exl = true,
                5 => after.control.state.pc.0 += 4,
                _ => before.staged.asid = 8,
            }
            assert!(
                replay.load(pc, 20, 21, &before, &after).is_err(),
                "mode {mode}"
            );
        }
    }
    #[test]
    fn staged_page_writes_need_installation_and_keep_the_installed_writer() {
        let (mut replay, before, installed) = fixture();
        let pc = before.control.state.pc.0;
        replay.write(pc, 10, 11, &before, &installed).unwrap();
        replay.finish(10, 12).unwrap();
        let mut staged = installed.clone();
        staged.staged.physical[0] = 0xe000;
        staged.staged.dirty[0] = true;
        replay
            .entry_lo_write(pc, 20, 21, (27, 0x39e), &installed, &staged)
            .unwrap();
        replay.finish_entry_lo(20, 22).unwrap();
        replay
            .entry_lo_write(pc, 30, 31, (27, 0x39e), &staged, &staged)
            .unwrap();
        replay.finish_entry_lo(30, 32).unwrap();
        assert!(replay.entry_lo_writes[1].same_staged_content);
        let mut observation = Observation {
            asid: 7,
            kernel: true,
            bits: 32,
            entries: installed.entries.clone(),
        };
        let old = replay
            .fetch(0x6028, PhysicalAddr(0x6028), &observation)
            .unwrap();
        assert_eq!(old.write_ordinal, 11);
        assert_eq!(old.entry_lo_write_ordinal, None);
        assert!(
            replay
                .fetch(0x6028, PhysicalAddr(0xe028), &observation)
                .is_err()
        );
        let mut remapped = staged.clone();
        remapped.entries[0] = remapped.staged.clone();
        replay.write(pc, 40, 41, &staged, &remapped).unwrap();
        replay.finish(40, 42).unwrap();
        observation.entries = remapped.entries.clone();
        let selected = replay
            .fetch(0x6028, PhysicalAddr(0xe028), &observation)
            .unwrap();
        assert_eq!(selected.write_ordinal, 41);
        assert_eq!(selected.entry_lo_write_ordinal, Some(31));
        let mut later_staged = remapped.clone();
        later_staged.staged.physical[0] = 0x6000;
        replay
            .entry_lo_write(pc, 50, 51, (27, 0x19e), &remapped, &later_staged)
            .unwrap();
        replay.finish_entry_lo(50, 52).unwrap();
        assert_eq!(
            replay
                .fetch(0x6028, PhysicalAddr(0xe028), &observation)
                .unwrap(),
            selected
        );
    }
    #[test]
    fn page_setter_checks_masked_fields_table_and_operation_completion() {
        for mode in 0..9 {
            let (mut replay, before, installed) = fixture();
            let pc = before.control.state.pc.0;
            replay.write(pc, 10, 11, &before, &installed).unwrap();
            replay.finish(10, 12).unwrap();
            let mut staged = installed.clone();
            staged.staged.physical[0] = 0xe000;
            staged.staged.dirty[0] = true;
            let mut operand = (27, 0x39e);
            match mode {
                0 => staged.entries[0].physical[0] = 0xe000,
                1 => staged.staged.physical[1] = 0xe000,
                2 => staged.staged.asid = 8,
                3 => staged.staged.cca[0] = 2,
                4 => staged.control.state.pc.0 += 4,
                5 => operand.0 = 0,
                6 => operand.1 ^= 0x40,
                7 => staged.staged.dirty[0] = false,
                _ => {
                    replay
                        .entry_lo_write(pc, 20, 21, operand, &installed, &staged)
                        .unwrap();
                    let mut after = staged.clone();
                    after.entries[0] = after.staged.clone();
                    assert!(replay.write(pc, 30, 31, &staged, &after).is_err());
                    assert!(replay.finish_entry_lo(21, 22).is_err());
                    assert!(replay.finish_entry_lo(20, 23).is_err());
                    continue;
                }
            }
            assert!(
                replay
                    .entry_lo_write(pc, 20, 21, operand, &installed, &staged)
                    .is_err(),
                "mode {mode}"
            );
        }
    }
    #[test]
    fn nonidentity_virtual_epc_keeps_physical_translation_separate() {
        let (mut replay, mut before, mut after) = fixture();
        replay.staged.virtual_address = 0xe000;
        before.staged = replay.staged.clone();
        after.staged = before.staged.clone();
        after.entries[0] = after.staged.clone();
        replay
            .write(before.control.state.pc.0, 10, 11, &before, &after)
            .unwrap();
        replay.finish(10, 12).unwrap();
        let observation = Observation {
            asid: 7,
            kernel: true,
            bits: 32,
            entries: after.entries.clone(),
        };
        for (virtual_pc, physical) in [(0xe028, 0x6028), (0xe02c, 0x602c)] {
            let witness = replay
                .fetch(virtual_pc, PhysicalAddr(physical), &observation)
                .unwrap();
            assert_eq!(witness.entry.virtual_address, 0xe000);
            assert_eq!(witness.entry.physical[0], 0x6000);
            assert_eq!(witness.write_ordinal, 11);
            assert!(
                replay
                    .fetch(virtual_pc, PhysicalAddr(virtual_pc as u32), &observation)
                    .is_err()
            );
        }
        assert!(
            replay
                .fetch(0x6028, PhysicalAddr(0x6028), &observation)
                .is_err()
        );
    }
    #[test]
    fn context_writers_change_matching_without_retiring_slot_generation() {
        let (mut replay, before, after) = fixture();
        let pc = before.control.state.pc.0;
        replay.write(pc, 10, 11, &before, &after).unwrap();
        replay.finish(10, 12).unwrap();
        let mut away = after.clone();
        away.staged.asid = 8;
        replay
            .context_write(pc, 20, 21, (25, 0x6008), &after, &away)
            .unwrap();
        replay.finish_context(20, 22).unwrap();
        let observation = Observation {
            asid: 8,
            kernel: true,
            bits: 32,
            entries: after.entries.clone(),
        };
        assert!(
            replay
                .fetch(0x6028, PhysicalAddr(0x6028), &observation)
                .is_err()
        );
        replay
            .context_write(pc, 30, 31, (26, 0x6007), &away, &after)
            .unwrap();
        replay.finish_context(30, 32).unwrap();
        replay
            .context_write(pc, 40, 41, (26, 0x6007), &after, &after)
            .unwrap();
        let observation = Observation {
            asid: 7,
            ..observation
        };
        assert!(
            replay
                .fetch(0x6028, PhysicalAddr(0x6028), &observation)
                .is_err()
        );
        replay.finish_context(40, 42).unwrap();
        let witness = replay
            .fetch(0x6028, PhysicalAddr(0x6028), &observation)
            .unwrap();
        assert_eq!(witness.write_ordinal, 11);
        assert_eq!(witness.context_write_ordinal, Some(41));
        assert_eq!(replay.generations.len(), 1);
        assert!(replay.context_writes[2].same_staged_content);
        assert!(!replay.context_writes[0].same_staged_content);
    }
    #[test]
    fn context_setter_preserves_table_and_rechecks_full_masked_value() {
        for mode in 0..7 {
            let (mut replay, before, after) = fixture();
            let pc = before.control.state.pc.0;
            replay.write(pc, 10, 11, &before, &after).unwrap();
            replay.finish(10, 12).unwrap();
            let mut changed = after.clone();
            changed.staged.asid = 8;
            let mut source = (25, 0x6008);
            match mode {
                0 => changed.entries[0].asid = 8,
                1 => changed.staged.virtual_address = 0x8000,
                2 => changed.staged.region = 1,
                3 => changed.index = 1,
                4 => changed.control.state.pc.0 += 4,
                5 => source.0 = 0,
                _ => source.1 = 0x6007,
            }
            assert!(
                replay
                    .context_write(pc, 20, 21, source, &after, &changed)
                    .is_err(),
                "mode {mode}"
            );
        }
    }
}
