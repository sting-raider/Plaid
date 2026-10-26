//! Status.FR facts from native guest data flow (ADR-0276).
//! Unknown entry/call state is never a constant: native accesses select the
//! live layout in that case. Status writes can prove either guarded mode.
use super::*;
use std::collections::VecDeque;

const FR: u32 = 1 << 26;

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
struct Bits {
    mask: u32,
    value: u32,
}
impl Bits {
    fn constant(value: u32) -> Self {
        Self { mask: !0, value }
    }
    fn meet(self, other: Self) -> Self {
        let mask = self.mask & other.mask & !(self.value ^ other.value);
        Self {
            mask,
            value: self.value & mask,
        }
    }
    fn and(self, other: Self) -> Self {
        let zero = (self.mask & !self.value) | (other.mask & !other.value);
        let one = self.mask & self.value & other.mask & other.value;
        Self {
            mask: zero | one,
            value: one,
        }
    }
    fn not(self) -> Self {
        Self {
            mask: self.mask,
            value: !self.value & self.mask,
        }
    }
    fn or(self, other: Self) -> Self {
        self.not().and(other.not()).not()
    }
    fn xor(self, other: Self) -> Self {
        let mask = self.mask & other.mask;
        Self {
            mask,
            value: (self.value ^ other.value) & mask,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct State {
    regs: [Bits; 32],
    status: Bits,
}
impl Default for State {
    fn default() -> Self {
        let mut regs = [Bits::default(); 32];
        regs[0] = Bits::constant(0);
        Self {
            regs,
            status: Bits::default(),
        }
    }
}
impl State {
    fn meet(&self, other: &Self) -> Self {
        Self {
            regs: std::array::from_fn(|i| self.regs[i].meet(other.regs[i])),
            status: self.status.meet(other.status),
        }
    }
    fn step(&mut self, w: u32, pc: u32, relocated: bool) {
        let (op, rs, rt, rd, f) = (
            w >> 26,
            (w >> 21 & 31) as usize,
            (w >> 16 & 31) as usize,
            (w >> 11 & 31) as usize,
            w & 63,
        );
        let (a, b) = (self.regs[rs], self.regs[rt]);
        let ins = plaid_core::discovery::decode(w, GuestAddr(pc));
        for (modified, reg) in [
            (ins.modifies_rs(), rs),
            (ins.modifies_rt(), rt),
            (ins.modifies_rd(), rd),
        ] {
            if modified {
                self.regs[reg] = Bits::default();
            }
        }
        // Links are implicit GPR writes too; the bound address may relocate.
        if ins.does_link() {
            self.regs[if op == 0 { rd } else { 31 }] = Bits::default();
        }
        let imm = Bits::constant(w & 0xffff);
        if !relocated {
            match (op, f) {
                (15, _) => self.regs[rt] = Bits::constant(w << 16),
                (12, _) => self.regs[rt] = a.and(imm),
                (13, _) => self.regs[rt] = a.or(imm),
                (14, _) => self.regs[rt] = a.xor(imm),
                (0, 36) => self.regs[rd] = a.and(b),
                (0, 37) => self.regs[rd] = a.or(b),
                (0, 38) => self.regs[rd] = a.xor(b),
                (0, 39) => self.regs[rd] = a.or(b).not(),
                (0, 0) => {
                    let shift = w >> 6 & 31;
                    self.regs[rd] = Bits {
                        mask: (b.mask << shift) | !(!0u32 << shift),
                        value: b.value << shift,
                    };
                }
                (0, 2) => {
                    let shift = w >> 6 & 31;
                    self.regs[rd] = Bits {
                        mask: (b.mask >> shift) | !(!0u32 >> shift),
                        value: b.value >> shift,
                    };
                }
                (0, 33 | 45) if rs == 0 => self.regs[rd] = b,
                (0, 33 | 45) if rt == 0 => self.regs[rd] = a,
                (9, _) if w & 0xffff == 0 => self.regs[rt] = a,
                (16, _) if matches!(rs, 0 | 1) && rd == 12 => self.regs[rt] = self.status,
                _ => {}
            }
        }
        if op == 16 && matches!(rs, 4 | 5) && rd == 12 {
            self.status = Bits {
                mask: b.mask & FR,
                value: b.value & FR,
            };
        }
        self.regs[0] = Bits::constant(0);
    }
}

/// Analyze the actual emitted CFG, including annulled delay slots. Calls kill
/// facts rather than assuming an ABI preserves FR or a saved Status value.
pub(super) fn modes(
    entry: u32,
    blocks: &[&BasicBlock],
    image: &CodeImage,
    targets: &BTreeMap<u32, BTreeSet<u32>>,
    relocated: &BTreeSet<u32>,
    word: &dyn Fn(u32) -> Result<u32, String>,
) -> Result<BTreeMap<u32, bool>, String> {
    let pcs = || {
        blocks
            .iter()
            .flat_map(|b| (b.start.pc.0..b.start.pc.0 + b.size).step_by(4))
    };
    // Almost every function has no Status writer; use live-layout accesses.
    let mut writes_status = false;
    for pc in pcs() {
        let w = word(pc)?;
        if w >> 26 == 16 && matches!(w >> 21 & 31, 4 | 5) && w >> 11 & 31 == 12 {
            writes_status = true;
            break;
        }
    }
    if !writes_status {
        return Ok(BTreeMap::new());
    }
    let words: BTreeMap<u32, u32> = pcs()
        .map(|pc| Ok((pc, word(pc)?)))
        .collect::<Result<_, String>>()?;
    let mut incoming = BTreeMap::from([(entry, State::default())]);
    let mut observed: BTreeMap<u32, State> = BTreeMap::new();
    let mut work = VecDeque::from([entry]);
    while let Some(pc) = work.pop_front() {
        let Some(&w) = words.get(&pc) else { continue };
        let mut state = incoming[&pc].clone();
        observe(&mut observed, pc, &state);
        let ins = plaid_core::discovery::decode(w, GuestAddr(pc));
        let mut successors = Vec::new();
        if is_control(w) {
            let never = plaid_core::discovery::branch_never_taken(w);
            let likely = ins.is_branch_likely();
            let before_slot = state.clone();
            // A linking instruction writes the link before executing its slot.
            state.step(w, pc, relocated.contains(&pc));
            if !(never && likely) {
                if let Some(&slot) = words.get(&(pc + 4)) {
                    observe(&mut observed, pc + 4, &state);
                    state.step(slot, pc + 4, relocated.contains(&(pc + 4)));
                } else {
                    continue;
                }
            }
            if ins.does_link() && !(w >> 26 == 0 && w >> 11 & 31 == 0) && !never {
                successors.push((pc + 8, State::default()));
            } else if never {
                successors.push((pc + 8, state));
            } else {
                match w >> 26 {
                    2 => successors.push((image.jump_target(GuestAddr(pc), w).0, state)),
                    0 => successors.extend(
                        targets
                            .get(&pc)
                            .into_iter()
                            .flatten()
                            .map(|&t| (t, state.clone())),
                    ),
                    _ => {
                        let branch = pc
                            .wrapping_add(4)
                            .wrapping_add_signed(i32::from(w as u16 as i16) * 4);
                        successors.push((branch, state.clone()));
                        successors.push((pc + 8, if likely { before_slot } else { state }));
                    }
                }
            }
        } else if !plaid_core::solver::is_eret(w) {
            state.step(w, pc, relocated.contains(&pc));
            successors.push((pc + 4, state));
        }
        for (next, state) in successors {
            if !words.contains_key(&next) {
                continue;
            }
            let merged = incoming
                .get(&next)
                .map_or_else(|| state.clone(), |old| old.meet(&state));
            if incoming.get(&next) != Some(&merged) {
                incoming.insert(next, merged);
                work.push_back(next);
            }
        }
    }
    Ok(observed
        .into_iter()
        .filter_map(|(pc, state)| {
            (state.status.mask & FR != 0).then_some((pc, state.status.value & FR == 0))
        })
        .collect())
}

fn observe(states: &mut BTreeMap<u32, State>, pc: u32, state: &State) {
    states
        .entry(pc)
        .and_modify(|old| *old = old.meet(state))
        .or_insert_with(|| state.clone());
}

#[cfg(test)]
mod tests {
    use super::*;
    use plaid_core::program::CodeAddress;

    const BASE: u32 = 0x8000_0000;
    const ON: u32 = 0x3c08_0400; // lui t0,FR
    const WRITE: u32 = 0x4088_6000; // mtc0 t0,Status

    fn facts(words: &[u32], relocated: &[u32]) -> BTreeMap<u32, bool> {
        let start = CodeAddress {
            pc: GuestAddr(BASE),
            image: "fr".into(),
            generation: 0,
        };
        let block = BasicBlock {
            start: start.clone(),
            size: words.len() as u32 * 4,
            delay_slot_entry: false,
            evidence: BTreeSet::new(),
        };
        let image = CodeImage {
            base: start,
            words: words.to_vec(),
            rom_offset: None,
            physical_start: None,
            holes: Vec::new(),
            slots: Vec::new(),
        };
        modes(
            BASE,
            &[&block],
            &image,
            &BTreeMap::new(),
            &relocated.iter().map(|n| BASE + n * 4).collect(),
            &|pc| Ok(words[((pc - BASE) / 4) as usize]),
        )
        .unwrap()
    }

    #[test]
    fn writes_and_register_clobbers() {
        let f = facts(
            &[
                ON,
                WRITE,
                0,
                0x4009_6000, // mfc0 t1,Status
                0x3c08_fbff,
                0x3508_ffff,
                0x0128_4024,
                WRITE,
                0,
            ],
            &[],
        );
        assert_eq!(f.get(&(BASE + 8)), Some(&false));
        assert_eq!(f.get(&(BASE + 32)), Some(&true));
        let f = facts(&[ON, 0x8c08_1000, WRITE, 0], &[]);
        assert!(
            !f.contains_key(&(BASE + 12)),
            "load must kill its destination"
        );
        let f = facts(&[ON, WRITE, 0], &[0]);
        assert!(
            !f.contains_key(&(BASE + 8)),
            "relocated immediates are unknown"
        );
        let f = facts(&[ON, 0x0100_f825, 0x0c00_0008, 0x409f_6000, 0], &[]);
        assert!(!f.contains_key(&(BASE + 16)), "call kills all facts");
        let mut state = State::default();
        state.regs[31] = Bits::constant(FR);
        state.step(0x0c00_0008, BASE, false);
        assert_eq!(state.regs[31], Bits::default(), "link precedes slot");
    }

    #[test]
    fn branch_slots_joins_and_loops() {
        // Both paths to the final NOP disagree about FR.
        let f = facts(&[ON, 0x1080_0003, WRITE, 0x4080_6000, 0, 0], &[]);
        assert_eq!(f.get(&(BASE + 12)), Some(&false));
        assert!(!f.contains_key(&(BASE + 20)));
        // Likely untaken path annuls Status write; ordinary branch does not.
        let f = facts(&[ON, 0x5080_0003, WRITE, 0, 0x03e0_0008, 0], &[]);
        assert!(!f.contains_key(&(BASE + 12)));
        let f = facts(&[ON, 0x5400_0001, WRITE, 0], &[]); // bnel zero,zero
        assert!(!f.contains_key(&(BASE + 8)));
        assert!(!f.contains_key(&(BASE + 12)));
        // Backedge removes the first iteration's FR=1 fact at a join.
        let f = facts(&[ON, WRITE, 0, 0x4080_6000, 0x1000_fffd, 0], &[]);
        assert!(!f.contains_key(&(BASE + 8)));
        // Status write in a jump slot reaches its actual destination.
        let f = facts(&[ON, 0x0800_0004, WRITE, 0, 0], &[]);
        assert_eq!(f.get(&(BASE + 16)), Some(&false));
    }
}
