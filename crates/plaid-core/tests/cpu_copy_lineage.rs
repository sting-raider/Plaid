use plaid_core::{
    cpu_copy::{self, CpuCopyLineageReport},
    rom::sha256,
};
use serde_json::{Value, json};

const KSEG1: u64 = 0xffff_ffff_a000_0000;
const A: u32 = 0x1111_1111;
const B: u32 = 0x2222_2222;
const C: u32 = 0x3333_3333;

struct Builder {
    instructions: Vec<Value>,
    effects: Vec<Value>,
    regs: [u64; 32],
    ordinal: u64,
    pc: u64,
    phase: u32,
}

impl Builder {
    fn new() -> Self {
        let mut regs = [0u64; 32];
        regs[16] = KSEG1 | 0x1000;
        regs[17] = KSEG1 | 0x1004;
        Self {
            instructions: Vec::new(),
            effects: Vec::new(),
            regs,
            ordinal: 1,
            pc: KSEG1 | 0x6000,
            phase: 1,
        }
    }

    fn instruction(
        &mut self,
        word: u32,
        after: [u64; 32],
        effect: Option<(bool, u32, u32)>,
    ) {
        let context = self.ordinal;
        self.instructions.push(json!({
            "begin": true,
            "ordinal": self.ordinal,
            "context": context,
            "phase": self.phase,
            "pc": self.pc,
            "word": word,
            "gpr": self.regs,
        }));
        self.ordinal += 1;
        if let Some((write, address, value)) = effect {
            self.effects.push(json!({
                "ordinal": self.ordinal,
                "context": context,
                "phase": self.phase,
                "pc": self.pc,
                "write": write,
                "address": address,
                "bytes": 4,
                "uncached_cpu": true,
                "value": value,
            }));
            self.ordinal += 1;
        }
        self.instructions.push(json!({
            "begin": false,
            "ordinal": self.ordinal,
            "context": context,
            "phase": self.phase,
            "pc": self.pc,
            "word": word,
            "gpr": after,
        }));
        self.ordinal += 1;
        self.pc += 4;
        self.regs = after;
    }

    fn load(&mut self, offset: u16, value: u32) {
        let mut after = self.regs;
        after[8] = (value as i32 as i64) as u64;
        self.instruction(
            0x8e08_0000 | u32::from(offset),
            after,
            Some((false, 0x1000 + u32::from(offset), value)),
        );
    }

    fn store(&mut self, offset: u16) {
        let value = self.regs[8] as u32;
        self.instruction(
            0xae28_0000 | u32::from(offset),
            self.regs,
            Some((true, 0x1004 + u32::from(offset), value)),
        );
    }

    fn raw_store(&mut self, register: usize, offset: u16, value: u32) {
        let word = 0xac00_0000
            | (17u32 << 21)
            | ((register as u32) << 16)
            | u32::from(offset);
        self.instruction(
            word,
            self.regs,
            Some((true, 0x1004 + u32::from(offset), value)),
        );
    }

    fn next_phase(&mut self) {
        self.phase += 1;
        self.pc = KSEG1 | 0x7000;
    }

    fn finish(self) -> Value {
        json!({
            "format": cpu_copy::FORMAT,
            "instruction_events": self.instructions,
            "scalar_events": self.effects,
        })
    }
}

fn overlap(forward: bool, equal: bool) -> Value {
    let mut b = Builder::new();
    let steps: &[(u16, u32)] = if forward {
        if equal {
            &[(0, A), (4, A), (8, A)]
        } else {
            // The later loads observe the earlier overlapping stores.
            &[(0, A), (4, A), (8, A)]
        }
    } else if equal {
        &[(8, A), (4, A), (0, A)]
    } else {
        &[(8, C), (4, B), (0, A)]
    };
    for &(offset, value) in steps {
        b.load(offset, value);
        b.store(offset);
    }
    b.finish()
}

fn inspect(value: &Value) -> (Vec<u8>, String, CpuCopyLineageReport) {
    let bytes = serde_json::to_vec(value).unwrap();
    let digest = sha256(&bytes);
    let report = cpu_copy::inspect_cpu_copy_lineage(&bytes, &digest).unwrap();
    (bytes, digest, report)
}

fn source_generations(report: &CpuCopyLineageReport) -> Vec<Option<u64>> {
    report
        .word_lineage
        .iter()
        .map(|edge| edge.captured_source_generation.map(|g| g.generation))
        .collect()
}

#[test]
fn forward_overlap_self_feeds_captured_generations_but_backward_copy_does_not() {
    let (_, _, forward) = inspect(&overlap(true, false));
    let (_, _, backward) = inspect(&overlap(false, false));
    assert_eq!(source_generations(&forward), vec![None, Some(1), Some(2)]);
    assert_eq!(source_generations(&backward), vec![None, None, None]);
    assert_eq!(
        forward
            .word_lineage
            .iter()
            .map(|edge| edge.destination_generation.generation)
            .collect::<Vec<_>>(),
        vec![1, 2, 3]
    );
    assert_eq!(forward.captured_word_writes.len(), 3);
    assert_eq!(backward.captured_word_writes.len(), 3);
}

#[test]
fn equal_payload_histories_remain_causally_distinct() {
    let (_, _, forward) = inspect(&overlap(true, true));
    let (_, _, backward) = inspect(&overlap(false, true));
    assert!(forward.word_lineage.iter().all(|e| e.witness.source_word == A));
    assert!(backward.word_lineage.iter().all(|e| e.witness.source_word == A));
    assert!(forward.word_lineage.iter().all(|e| e.witness.result_word == A));
    assert!(backward.word_lineage.iter().all(|e| e.witness.result_word == A));
    assert_eq!(source_generations(&forward), vec![None, Some(1), Some(2)]);
    assert_eq!(source_generations(&backward), vec![None, None, None]);
}

#[test]
fn same_value_noncopy_store_mints_a_generation_consumed_by_later_load() {
    let mut b = Builder::new();
    b.regs[9] = A as u64;
    b.raw_store(9, 0, A);
    b.load(4, A);
    b.store(4);
    let (_, _, report) = inspect(&b.finish());
    assert_eq!(report.captured_word_writes.len(), 2);
    assert_eq!(report.word_lineage.len(), 1);
    let edge = &report.word_lineage[0];
    let source = edge.captured_source_generation.unwrap();
    assert_eq!((source.phase, source.generation), (1, 1));
    assert_eq!(source.write_ordinal, report.captured_word_writes[0].identity.write_ordinal);
    assert_eq!(edge.destination_generation.generation, 2);
}

#[test]
fn phase_boundary_does_not_invent_cross_segment_storage_ancestry() {
    let mut b = Builder::new();
    b.regs[9] = A as u64;
    b.raw_store(9, 0, A);
    b.next_phase();
    b.load(4, A);
    b.store(4);
    let (_, _, report) = inspect(&b.finish());
    assert_eq!(report.word_lineage.len(), 1);
    assert_eq!(report.word_lineage[0].captured_source_generation, None);
    assert_eq!(report.word_lineage[0].destination_generation.phase, 2);
    assert_eq!(report.word_lineage[0].destination_generation.generation, 1);
}

#[test]
fn lineage_receipts_are_rederived_and_never_upgrade_capture_completeness() {
    let value = overlap(true, true);
    let (bytes, digest, report) = inspect(&value);
    cpu_copy::verify_cpu_copy_lineage_report(&report, &bytes, &digest).unwrap();
    assert!(
        !report.source_storage_ancestry_certified
            && !report.mutation_coverage_certified
            && !report.executable_lifetime_certified
            && !report.native_complete
    );

    let mut forged = report.clone();
    forged.word_lineage[1].captured_source_generation = None;
    assert!(cpu_copy::verify_cpu_copy_lineage_report(&forged, &bytes, &digest).is_err());

    let mut forged = report.clone();
    forged.captured_word_writes[0].identity.generation = 99;
    assert!(cpu_copy::verify_cpu_copy_lineage_report(&forged, &bytes, &digest).is_err());

    let mut forged = report.clone();
    forged.word_lineage[0].destination_generation.write_ordinal += 1;
    assert!(cpu_copy::verify_cpu_copy_lineage_report(&forged, &bytes, &digest).is_err());

    let mut forged = report;
    forged.source_storage_ancestry_certified = true;
    assert!(cpu_copy::verify_cpu_copy_lineage_report(&forged, &bytes, &digest).is_err());
}
