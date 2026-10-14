//! Shared observed RSP scalar expressions and explicitly rooted raw epochs.
use super::{RspDefinitionExpression, RspRegisterDefinition, RspRegisterParent, require};
use serde::{Deserialize, Serialize};
use sha2::Digest;

pub(crate) fn is_definition(word: u32) -> bool {
    word >> 26 == 0x0d || (word >> 26 == 0 && word & 63 == 0x21 && (word >> 6) & 31 == 0)
}

pub(crate) fn scalar_rsp_definition(
    context: u64,
    phase: u32,
    pc: u16,
    word: u32,
    rgpr: &[u32],
    registers: &[Option<u64>; 32],
) -> Option<RspRegisterDefinition> {
    if !is_definition(word) || rgpr.len() != 32 {
        return None;
    }
    let rs = ((word >> 21) & 31) as usize;
    let rt = ((word >> 16) & 31) as usize;
    let parent = |r: usize| {
        if r == 0 {
            RspRegisterParent::ArchitecturalZero
        } else if let Some(context) = registers[r] {
            RspRegisterParent::Definition { context }
        } else {
            RspRegisterParent::CapturedInput {
                register: r as u8,
                value: rgpr[r],
            }
        }
    };
    let (register, value, expression) = if word >> 26 == 0x0d {
        (
            rt,
            rgpr[rs] | u32::from(word as u16),
            RspDefinitionExpression::Ori {
                source: parent(rs),
                immediate: word as u16,
            },
        )
    } else {
        (
            ((word >> 11) & 31) as usize,
            rgpr[rs].wrapping_add(rgpr[rt]),
            RspDefinitionExpression::Addu {
                left: parent(rs),
                right: parent(rt),
            },
        )
    };
    (register != 0).then_some(RspRegisterDefinition {
        context,
        phase,
        pc,
        word,
        register: register as u8,
        value,
        expression,
    })
}

/// Scalar facts in an explicitly rooted observed register epoch. The enclosing
/// source verifier owns exact IMEM-read/performed-instruction admission.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CapturedScalarRspProducer {
    pub epoch: u64,
    pub read_ordinal: u64,
    pub end_ordinal: u64,
    pub definition: RspRegisterDefinition,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ScalarRspProducerReport {
    pub roots: u64,
    pub instructions: u64,
    pub definitions: u64,
    pub opaque_instructions: u64,
    /// Bounded samples; the digest commits every complete occurrence.
    pub samples: Vec<CapturedScalarRspProducer>,
    pub ordered_producers_sha256: String,
}

struct ScalarRspPending {
    begin: u64,
    read: u64,
    word: u32,
    before: [u32; 32],
    expected: Option<[u32; 32]>,
    definition: Option<RspRegisterDefinition>,
}

pub(crate) struct ScalarRspProducers {
    epoch: Option<u64>,
    boundary: Option<([u32; 32], u32)>,
    parents: [Option<u64>; 32],
    pending: Option<ScalarRspPending>,
    roots: u64,
    instructions: u64,
    definitions: u64,
    opaque: u64,
    samples: Vec<CapturedScalarRspProducer>,
    ordered: sha2::Sha256,
}

impl ScalarRspProducers {
    pub(crate) fn new() -> Self {
        Self {
            epoch: None,
            boundary: None,
            parents: [None; 32],
            pending: None,
            roots: 0,
            instructions: 0,
            definitions: 0,
            opaque: 0,
            samples: Vec::new(),
            ordered: sha2::Sha256::new(),
        }
    }
    pub(crate) fn root(
        &mut self,
        ordinal: u64,
        epoch: u64,
        pc: u32,
        registers: [u32; 32],
    ) -> Result<(), String> {
        require(
            self.pending.is_none()
                && pc < 4096
                && registers[0] == 0
                && epoch != 0
                && self.epoch.is_none_or(|old| epoch > old),
            "invalid or reused RSP operand root",
        )?;
        self.epoch = Some(epoch);
        self.boundary = Some((registers, pc));
        self.parents.fill(None);
        self.roots += 1;
        self.ordered.update(
            serde_json::to_vec(&("root", ordinal, epoch, pc, registers))
                .map_err(|e| e.to_string())?,
        );
        Ok(())
    }
    pub(crate) fn begin(
        &mut self,
        ordinal: u64,
        read: u64,
        pc: u32,
        word: u32,
        registers: [u32; 32],
    ) -> Result<(), String> {
        require(
            self.pending.is_none()
                && self.epoch.is_some()
                && self.boundary == Some((registers, pc))
                && registers[0] == 0,
            "RSP operands lack their unchanged explicit root/boundary",
        )?;
        let scalar = is_definition(word);
        let definition =
            scalar_rsp_definition(ordinal, 0, pc as u16, word, &registers, &self.parents);
        let expected = scalar.then(|| {
            let mut result = registers;
            if let Some(d) = &definition {
                result[d.register as usize] = d.value;
            }
            result
        });
        if !scalar {
            self.parents.fill(None);
        }
        self.pending = Some(ScalarRspPending {
            begin: ordinal,
            read,
            word,
            before: registers,
            expected,
            definition,
        });
        Ok(())
    }
    pub(crate) fn end(
        &mut self,
        ordinal: u64,
        next: u32,
        registers: [u32; 32],
    ) -> Result<(), String> {
        let pending = self.pending.take().ok_or("RSP operand end lacks begin")?;
        require(
            registers[0] == 0
                && next < 4096
                && pending
                    .expected
                    .is_none_or(|expected| expected == registers),
            "RSP scalar producer register transition mismatch",
        )?;
        self.instructions += 1;
        self.opaque += u64::from(pending.expected.is_none());
        self.ordered.update(
            serde_json::to_vec(&(
                "instruction",
                self.epoch,
                pending.begin,
                pending.read,
                ordinal,
                pending.word,
                next,
                pending.before,
                registers,
                &pending.definition,
            ))
            .map_err(|e| e.to_string())?,
        );
        if let Some(definition) = pending.definition {
            self.parents[definition.register as usize] = Some(definition.context);
            self.definitions += 1;
            if self.samples.len() < 64 {
                self.samples.push(CapturedScalarRspProducer {
                    epoch: self.epoch.unwrap(),
                    read_ordinal: pending.read,
                    end_ordinal: ordinal,
                    definition,
                });
            }
        }
        self.boundary = Some((registers, next));
        Ok(())
    }
    pub(crate) fn finish(self) -> Result<ScalarRspProducerReport, String> {
        require(self.pending.is_none(), "unfinished RSP operand occurrence")?;
        Ok(ScalarRspProducerReport {
            roots: self.roots,
            instructions: self.instructions,
            definitions: self.definitions,
            opaque_instructions: self.opaque,
            samples: self.samples,
            ordered_producers_sha256: format!("{:x}", self.ordered.finalize()),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn equal_root_cut_ends_held_definition_ancestry() {
        let mut state = ScalarRspProducers::new();
        let mut registers = [0; 32];
        state.root(1, 1, 0, registers).unwrap();
        state.begin(3, 2, 0, 0x340800aa, registers).unwrap();
        registers[8] = 0xaa;
        state.end(4, 4, registers).unwrap();
        state.root(5, 2, 4, registers).unwrap();
        state.begin(7, 6, 4, 0x01084821, registers).unwrap();
        registers[9] = 0x154;
        state.end(8, 8, registers).unwrap();
        let report = state.finish().unwrap();
        let RspDefinitionExpression::Addu { left, right } =
            &report.samples[1].definition.expression
        else {
            panic!()
        };
        assert_eq!(
            *left,
            RspRegisterParent::CapturedInput {
                register: 8,
                value: 0xaa
            }
        );
        assert_eq!(left, right);
        assert_eq!((report.roots, report.definitions), (2, 2));
    }
    #[test]
    fn opaque_instruction_cuts_all_scalar_definition_candidates() {
        let mut state = ScalarRspProducers::new();
        let mut registers = [0; 32];
        state.root(1, 1, 0, registers).unwrap();
        state.begin(3, 2, 0, 0x340800aa, registers).unwrap();
        registers[8] = 0xaa;
        state.end(4, 4, registers).unwrap();
        state.begin(6, 5, 4, 0, registers).unwrap();
        state.end(7, 8, registers).unwrap();
        state.begin(9, 8, 8, 0x01084821, registers).unwrap();
        registers[9] = 0x154;
        state.end(10, 12, registers).unwrap();
        let report = state.finish().unwrap();
        assert_eq!(report.opaque_instructions, 1);
        let RspDefinitionExpression::Addu { left, .. } = &report.samples[1].definition.expression
        else {
            panic!()
        };
        assert!(matches!(left, RspRegisterParent::CapturedInput { .. }));
    }
    #[test]
    fn source_boundaries_and_all_register_effects_are_required() {
        let mut state = ScalarRspProducers::new();
        let mut registers = [0; 32];
        assert!(state.begin(2, 1, 0, 0x340800aa, registers).is_err());
        state.root(1, 1, 0, registers).unwrap();
        assert!(state.root(2, 1, 0, registers).is_err());
        assert!(state.begin(3, 2, 4, 0x340800aa, registers).is_err());
        state.begin(3, 2, 0, 0x340800aa, registers).unwrap();
        registers[8] = 0xaa;
        registers[7] = 1;
        assert!(state.end(4, 4, registers).is_err());
    }
}

#[cfg(test)]
mod reference_regression {
    use super::*;
    #[test]
    fn actual_pinned_scalar_snapshots_replay_through_shared_producer_state() {
        let source: serde_json::Value =
            serde_json::from_str(include_str!("../tests/fixtures/rsp_scalar_reference.json"))
                .unwrap();
        assert_eq!(
            source["revision"],
            "9408cb43d4948fc3ea6e152a307a34348df3fe04"
        );
        assert_eq!(
            source["parent_source_sha256"],
            "c3f2c2865fcbf788b0a54e404a785589435549bb7eafa3fac7845dd9b3fa8610"
        );
        let mut state = ScalarRspProducers::new();
        let mut reads = std::collections::BTreeMap::new();
        let mut active = None;
        for row in source["events"].as_array().unwrap() {
            let number = |key: &str| row[key].as_u64().unwrap();
            let registers =
                || serde_json::from_value::<[u32; 32]>(row["registers"].clone()).unwrap();
            match row["record"].as_str().unwrap() {
                "rsp_operand_root" => state
                    .root(
                        number("ordinal"),
                        number("epoch"),
                        number("rsp_pc") as u32,
                        registers(),
                    )
                    .unwrap(),
                "rsp_imem_read" => {
                    reads.insert(number("ordinal"), (number("offset"), number("word")));
                }
                "rsp_instruction" if row["begin"].as_bool().unwrap() => {
                    let read = number("read_ordinal");
                    let pc = number("rsp_pc") as u32;
                    let word = number("word") as u32;
                    assert_eq!(reads[&read], (u64::from(pc & 0xffc), u64::from(word)));
                    assert!(active.replace((read, pc, word)).is_none());
                    state
                        .begin(number("ordinal"), read, pc, word, registers())
                        .unwrap();
                }
                "rsp_instruction" => {
                    assert_eq!(
                        active.take(),
                        Some((
                            number("read_ordinal"),
                            number("rsp_pc") as u32,
                            number("word") as u32
                        ))
                    );
                    state
                        .end(number("ordinal"), number("next_pc") as u32, registers())
                        .unwrap();
                }
                _ => panic!("unexpected scalar regression row"),
            }
        }
        assert!(active.is_none());
        let report = state.finish().unwrap();
        assert_eq!(report.roots, source["roots"].as_u64().unwrap());
        assert_eq!(
            report.instructions,
            source["instructions"].as_u64().unwrap()
        );
        assert_eq!(report.definitions, source["definitions"].as_u64().unwrap());
        assert_eq!(
            report.opaque_instructions,
            source["opaque_instructions"].as_u64().unwrap()
        );
        assert_eq!(
            report.ordered_producers_sha256,
            source["ordered_producers_sha256"].as_str().unwrap()
        );
    }
}
