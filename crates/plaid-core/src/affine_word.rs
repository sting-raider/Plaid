//! Backward low-word relations for bounded compile-time analysis.
use crate::{GuestAddr, discovery::decode};
use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct AffineWord {
    coeff: BTreeMap<u8, u32>,
    constant: u32,
}

impl AffineWord {
    pub(crate) fn scaled_index(offset: u8, index: u8) -> Self {
        let mut result = Self {
            coeff: BTreeMap::new(),
            constant: 0,
        };
        result.add(offset, 1);
        result.add(index, 0u32.wrapping_sub(4));
        result
    }

    pub(crate) fn registers(&self) -> impl Iterator<Item = u8> + '_ {
        self.coeff.keys().copied()
    }

    pub(crate) fn is_zero(&self) -> bool {
        self.coeff.is_empty() && self.constant == 0
    }

    pub(crate) fn is_nonzero_constant(&self) -> bool {
        self.coeff.is_empty() && self.constant != 0
    }

    fn add(&mut self, register: u8, value: u32) {
        if register == 0 {
            return;
        }
        let coeff = self.coeff.entry(register).or_default();
        *coeff = coeff.wrapping_add(value);
        if *coeff == 0 {
            self.coeff.remove(&register);
        }
    }

    fn substitute(&mut self, dest: u8, sources: &[(u8, u32)], immediate: u32) {
        let coefficient = self.coeff.remove(&dest).unwrap_or(0);
        self.constant = self
            .constant
            .wrapping_add(coefficient.wrapping_mul(immediate));
        for &(source, scale) in sources {
            self.add(source, coefficient.wrapping_mul(scale));
        }
    }

    /// Substitute a supported instruction definition while walking backward.
    /// This is low-32-bit algebra only; callers own path, delay-slot, high-word,
    /// address-canonicality, and resource proofs.
    pub(crate) fn step(
        &mut self,
        pc: GuestAddr,
        word: u32,
        constants: &mut BTreeMap<u8, u32>,
    ) -> Option<()> {
        let instruction = decode(word, pc);
        if !instruction.is_valid()
            || instruction.is_trap()
            || instruction.has_delay_slot()
            || instruction.is_branch()
            || instruction.is_jump()
            || instruction.is_jump_with_address()
            || matches!(instruction.opcode_name(), "syscall" | "break" | "eret")
        {
            return None;
        }
        let Some(dest) = instruction
            .destination_gpr()
            .map(|r| r as u8)
            .filter(|r| *r != 0)
        else {
            return Some(());
        };
        if !self.coeff.contains_key(&dest) && !constants.contains_key(&dest) {
            return Some(());
        }

        // The consumer transfers constant requirements once; this helper only
        // adds a shift requirement and must not consume those definitions too.
        if constants.contains_key(&dest) {
            return (!self.coeff.contains_key(&dest)).then_some(());
        }

        let rs = ((word >> 21) & 31) as u8;
        let rt = ((word >> 16) & 31) as u8;
        let imm = word as u16 as u32;
        match word >> 26 {
            9 | 25 => self.substitute(dest, &[(rs, 1)], i32::from(word as i16) as u32),
            15 => self.substitute(dest, &[], (word & 0xffff) << 16),
            13 | 14 => {
                if rs == 0 {
                    self.substitute(dest, &[], imm);
                } else if imm == 0 {
                    self.substitute(dest, &[(rs, 1)], 0);
                } else {
                    return None;
                }
            }
            12 if imm == 0 => self.substitute(dest, &[], 0),
            0 => match word & 63 {
                0 => self.substitute(dest, &[(rt, 1u32.wrapping_shl((word >> 6) & 31))], 0),
                4 => {
                    if rs == 0 {
                        self.substitute(dest, &[(rt, 1)], 0);
                    } else {
                        if rs == dest || rs == rt || self.coeff.contains_key(&rs) {
                            return None;
                        }
                        match constants.get(&rs) {
                            Some(2) => {}
                            Some(_) => return None,
                            None => {
                                constants.insert(rs, 2);
                            }
                        }
                        self.substitute(dest, &[(rt, 4)], 0);
                    }
                }
                33 | 45 => self.substitute(dest, &[(rs, 1), (rt, 1)], 0),
                35 | 47 => self.substitute(dest, &[(rs, 1), (rt, u32::MAX)], 0),
                37 if rs == 0 || rt == 0 => {
                    self.substitute(dest, &[(if rs == 0 { rt } else { rs }, 1)], 0)
                }
                _ => return None,
            },
            _ => return None,
        }
        Some(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::indirect::transfer;

    const PC: GuestAddr = GuestAddr(0x8000_1000);
    fn i(op: u32, rs: u8, rt: u8, imm: u16) -> u32 {
        (op << 26) | (u32::from(rs) << 21) | (u32::from(rt) << 16) | u32::from(imm)
    }
    fn r(rs: u8, rt: u8, rd: u8, shamt: u8, funct: u8) -> u32 {
        (u32::from(rs) << 21)
            | (u32::from(rt) << 16)
            | (u32::from(rd) << 11)
            | (u32::from(shamt) << 6)
            | u32::from(funct)
    }
    fn eval(word: &AffineWord, state: &[u64; 32]) -> u32 {
        word.coeff
            .iter()
            .fold(word.constant, |sum, (&register, &coeff)| {
                sum.wrapping_add(coeff.wrapping_mul(state[register as usize] as u32))
            })
    }
    fn check(
        word: u32,
        mut goal: AffineWord,
        before: [u64; 32],
        constants: &mut BTreeMap<u8, u32>,
    ) {
        let original = goal.clone();
        let mut after = [Some(0); 32];
        after.copy_from_slice(&before.map(Some));
        transfer(word, PC, &mut after);
        let after: [u64; 32] = after.map(|v| v.unwrap());
        let dest = decode(word, PC)
            .destination_gpr()
            .unwrap_or_else(|| panic!("no decoded GPR destination for {word:08x}"))
            as u8;
        assert!(goal.coeff.contains_key(&dest));
        goal.step(PC, word, constants).unwrap();
        assert_eq!(eval(&original, &after), eval(&goal, &before));
    }

    fn goal(dest: u8) -> AffineWord {
        AffineWord {
            coeff: BTreeMap::from([(dest, 7), (9, 11)]),
            constant: 0xffff_fffb,
        }
    }

    fn states() -> [[u64; 32]; 5] {
        let mut states = [[0; 32]; 5];
        for (n, state) in states.iter_mut().enumerate() {
            for (register, value) in state.iter_mut().enumerate().skip(1) {
                *value = match (n, register) {
                    (0, _) => 0,
                    (1, _) => u64::MAX,
                    (2, _) => (1u64 << 32) | 0xffff_ffff,
                    (3, _) => (1u64 << 48) | (register as u64 * 0x1_0001),
                    _ => u64::from(register as u32).wrapping_mul(0x8000_0001),
                };
            }
        }
        states
    }

    #[test]
    fn affine_construction_and_normalization() {
        let goal = AffineWord::scaled_index(4, 9);
        assert_eq!(goal.registers().collect::<Vec<_>>(), [4, 9]);
        let mut cancel = AffineWord::scaled_index(3, 3);
        assert_eq!(cancel.coeff, BTreeMap::from([(3, 0xffff_fffd)]));
        cancel.coeff.clear();
        cancel.constant = 7;
        assert!(cancel.is_nonzero_constant());
        cancel.constant = 0;
        assert!(cancel.is_zero());
        assert!(!goal.is_zero());
    }

    #[test]
    fn supported_arithmetic_matches_forward_low_word_semantics() {
        let instructions = [
            i(9, 5, 6, 0x8001),
            i(25, 5, 6, 0x7fff),
            (15 << 26) | (6 << 16) | 0x8123,
            r(5, 7, 6, 0, 33),
            r(5, 7, 6, 0, 45),
            r(5, 7, 6, 0, 35),
            r(0, 5, 6, 31, 0),
            r(0, 5, 6, 0, 37),
            i(13, 0, 6, 0xa123),
            i(14, 0, 6, 0x8123),
            i(13, 5, 6, 0),
            i(14, 5, 6, 0),
            i(12, 5, 6, 0),
        ];
        for word in instructions {
            for before in states() {
                check(word, goal(6), before, &mut BTreeMap::new());
            }
        }
    }

    #[test]
    fn variable_shift_relation_matches_fixed_requirement_two() {
        let mut before = [0; 32];
        before[4] = 2;
        before[5] = (1u64 << 40) | 0xffff_ffff;
        before[9] = 0x8000_0001;
        let after = before[5].wrapping_shl(2);
        let original = goal(6);
        let original_value = original
            .constant
            .wrapping_add(7u32.wrapping_mul(after as u32))
            .wrapping_add(11u32.wrapping_mul(before[9] as u32));
        let mut transformed = original;
        let mut constants = BTreeMap::new();
        transformed
            .step(PC, r(4, 5, 6, 0, 4), &mut constants)
            .unwrap();
        assert_eq!(constants, BTreeMap::from([(4, 2)]));
        assert_eq!(original_value, eval(&transformed, &before));
    }

    #[test]
    fn dsubu_relation_matches_wrapping_64_bit_forward_result_low_word() {
        let mut before = [0; 32];
        before[5] = (1u64 << 48) | 0x8000_0001;
        before[7] = (1u64 << 40) | 2;
        before[9] = 0x7fff_ffff;
        let after_dest = before[5].wrapping_sub(before[7]);
        let original = goal(6);
        let after_value = original
            .constant
            .wrapping_add(7u32.wrapping_mul(after_dest as u32))
            .wrapping_add(11u32.wrapping_mul(before[9] as u32));
        let mut transformed = original;
        transformed
            .step(PC, r(5, 7, 6, 0, 47), &mut BTreeMap::new())
            .unwrap();
        assert_eq!(after_value, eval(&transformed, &before));
    }

    #[test]
    fn aliases_cancellation_zero_register_and_literal_discharge() {
        let mut before = [0; 32];
        before[4] = u64::MAX;
        let word = i(9, 6, 6, 1); // read old destination before replacing it
        check(word, goal(6), before, &mut BTreeMap::new());

        let mut cancel = AffineWord {
            coeff: BTreeMap::from([(6, 3), (4, 3u32.wrapping_neg())]),
            constant: 0,
        };
        // ADDU $6,$4,$0 substitutes $6 with $4 and cancels the old $4 term.
        cancel
            .step(PC, r(4, 0, 6, 0, 33), &mut BTreeMap::new())
            .unwrap();
        assert!(cancel.is_zero());

        let mut literal = AffineWord {
            coeff: BTreeMap::from([(6, 1)]),
            constant: u32::MAX,
        };
        literal
            .step(PC, r(0, 0, 6, 0, 33), &mut BTreeMap::new())
            .unwrap();
        assert!(literal.is_nonzero_constant());
        assert_eq!(literal.constant, u32::MAX);

        let mut zero_dest = AffineWord {
            coeff: BTreeMap::from([(6, 1)]),
            constant: 0,
        };
        zero_dest
            .step(PC, i(12, 4, 6, 0), &mut BTreeMap::new())
            .unwrap();
        assert!(zero_dest.is_zero());
    }

    #[test]
    fn zero_register_definitions_discharge_relation_terms() {
        let mut only_index = AffineWord::scaled_index(0, 9);
        only_index
            .step(PC, i(9, 0, 9, 0), &mut BTreeMap::new())
            .unwrap();
        assert!(only_index.is_zero());

        let mut only_offset = AffineWord::scaled_index(8, 0);
        only_offset
            .step(PC, (15 << 26) | (8 << 16), &mut BTreeMap::new())
            .unwrap();
        assert!(only_offset.is_zero());
    }

    #[test]
    fn rejects_unknown_required_writes_and_preserves_unrelated_writes() {
        let mut relation = goal(6);
        assert!(
            relation
                .step(PC, i(35, 4, 6, 0), &mut BTreeMap::new())
                .is_none()
        );
        assert!(
            relation
                .step(PC, r(5, 7, 6, 0, 36), &mut BTreeMap::new())
                .is_none()
        );
        let multiply = (28 << 26) | (5 << 21) | (7 << 16) | (6 << 11) | 2;
        assert!(relation.step(PC, multiply, &mut BTreeMap::new()).is_none());

        let original = goal(6);
        let mut preserved = original.clone();
        preserved
            .step(PC, i(43, 4, 6, 0), &mut BTreeMap::new())
            .unwrap();
        assert_eq!(preserved, original);
    }

    #[test]
    fn refuses_trapping_and_control_instructions() {
        for word in [
            0x0000_000d,      // BREAK
            i(4, 4, 5, 1),    // conditional branch
            r(0, 0, 0, 0, 8), // JR
        ] {
            assert!(goal(6).step(PC, word, &mut BTreeMap::new()).is_none());
        }
    }

    #[test]
    fn existing_constant_requirements_belong_to_the_consumer() {
        let mut constants = BTreeMap::from([(5, 2), (9, 7)]);
        goal(6).step(PC, i(9, 6, 5, 1), &mut constants).unwrap();
        assert_eq!(constants, BTreeMap::from([(5, 2), (9, 7)]));

        let mut conflict = BTreeMap::from([(5, 2), (4, 3)]);
        let before = conflict.clone();
        goal(6).step(PC, i(9, 4, 5, 1), &mut conflict).unwrap();
        assert_eq!(conflict, before);
    }

    #[test]
    fn variable_shift_needs_an_unaliased_exact_two_requirement() {
        let word = r(4, 5, 6, 0, 4);
        let mut relation = goal(6);
        let mut constants = BTreeMap::new();
        relation.step(PC, word, &mut constants).unwrap();
        assert_eq!(constants, BTreeMap::from([(4, 2)]));

        let mut same = BTreeMap::from([(4, 2)]);
        goal(6).step(PC, word, &mut same).unwrap();
        let mut conflict = BTreeMap::from([(4, 3)]);
        assert!(goal(6).step(PC, word, &mut conflict).is_none());
        assert!(
            goal(6)
                .step(PC, r(6, 5, 6, 0, 4), &mut BTreeMap::new())
                .is_none()
        );
        assert!(
            goal(6)
                .step(PC, r(4, 4, 6, 0, 4), &mut BTreeMap::new())
                .is_none()
        );
        let mut aliased = AffineWord {
            coeff: BTreeMap::from([(6, 1), (4, 2)]),
            constant: 0,
        };
        assert!(aliased.step(PC, word, &mut BTreeMap::new()).is_none());
        assert!(
            goal(6)
                .step(PC, r(0, 5, 6, 0, 4), &mut BTreeMap::new())
                .is_some()
        );
    }

    #[test]
    fn paired_index_and_offset_increments_preserve_the_same_relation() {
        let relation = AffineWord::scaled_index(8, 9);
        let mut paired = relation.clone();
        paired
            .step(PC, i(9, 8, 8, 4), &mut BTreeMap::new())
            .unwrap();
        paired
            .step(PC, i(9, 9, 9, 1), &mut BTreeMap::new())
            .unwrap();
        assert_eq!(paired, relation);

        let mut wrong_offset = relation.clone();
        wrong_offset
            .step(PC, i(9, 8, 8, 5), &mut BTreeMap::new())
            .unwrap();
        wrong_offset
            .step(PC, i(9, 9, 9, 1), &mut BTreeMap::new())
            .unwrap();
        assert_ne!(wrong_offset, relation);
        let mut wrong_index = relation.clone();
        wrong_index
            .step(PC, i(9, 8, 8, 4), &mut BTreeMap::new())
            .unwrap();
        wrong_index
            .step(PC, i(9, 9, 9, 2), &mut BTreeMap::new())
            .unwrap();
        assert_ne!(wrong_index, relation);
    }
}
