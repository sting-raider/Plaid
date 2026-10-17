//! Bounded, analysis-only execution of a ROM's entry stub. This module is never
//! emitted by plaid-lower. Unknown power-on state stays unknown; device accesses
//! and system instructions stop capture instead of supplying invented inputs.
use crate::{GuestAddr, program::GuestRange, rom::CanonicalRom};
use serde::Serialize;
use std::collections::BTreeSet;

const RAM: usize = 8 << 20;
const BUDGET: u64 = 1_000_000;

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Capture {
    pub destination: GuestRange,
    pub bytes: Vec<u8>,
    /// Half-open canonical ROM ranges read by the executed transformation.
    pub consumed: Vec<(u32, u32)>,
    pub steps: u64,
    pub entry: GuestAddr,
    pub registers: [Option<u64>; 32],
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Stop {
    pub pc: GuestAddr,
    pub steps: u64,
    pub reason: String,
}

struct Machine<'a> {
    rom: &'a [u8],
    base: u32,
    size: u32,
    ram: Vec<Option<u8>>,
    written: Vec<bool>,
    flushed: Vec<bool>,
    data_lines: [Option<usize>; 512],
    fetched_lines: BTreeSet<usize>,
    r: [Option<u64>; 32],
    consumed: BTreeSet<u32>,
    pc: u32,
    pending: Option<u32>,
    steps: u64,
}

fn sx(v: u32) -> u64 {
    v as i32 as i64 as u64
}

impl Machine<'_> {
    fn physical(address: u32) -> Result<usize, String> {
        // Only the normal cached boot RAM view is accepted. KSEG1/RCP,
        // aliases, cache discard and device events require a broader model.
        if (0x8000_0000..0x8080_0000).contains(&address) {
            Ok((address - 0x8000_0000) as usize)
        } else {
            Err(format!(
                "external or unsupported memory input at {address:08x}"
            ))
        }
    }

    fn value(&self, r: usize) -> Result<u64, String> {
        self.r[r].ok_or_else(|| format!("unknown power-on register r{r}"))
    }

    fn address(&self, register: usize, displacement: u64) -> Result<u32, String> {
        let address = self.value(register)?.wrapping_add(displacement);
        if address != sx(address as u32) {
            return Err("noncanonical memory address".into());
        }
        Ok(address as u32)
    }

    fn flush(&mut self, line: usize) {
        self.flushed[line..line + 16].fill(true);
    }

    fn touch(&mut self, offset: usize) {
        let index = (offset >> 4) & 511;
        let line = offset & !15;
        if self.data_lines[index] != Some(line) {
            if let Some(old) = self.data_lines[index] {
                self.flush(old);
            }
            self.data_lines[index] = Some(line);
        }
    }

    fn read(&mut self, address: u32, size: usize, data: bool) -> Result<Option<u64>, String> {
        if !(address as usize).is_multiple_of(size) {
            return Err("unaligned memory access".into());
        }
        let (source, offset) = if (0xb000_0000..0xbfc0_0000).contains(&address) {
            (true, (address - 0xb000_0000) as usize)
        } else {
            (false, Self::physical(address)?)
        };
        let mut value = Some(0u64);
        if !source && data {
            self.touch(offset);
        }
        if !source && !data {
            self.fetched_lines.insert(offset & !31);
        }
        for n in offset..offset.checked_add(size).ok_or("read overflow")? {
            let byte = if source {
                self.consumed.insert(n as u32);
                Some(*self.rom.get(n).ok_or("read outside ROM")?)
            } else {
                // Original IPL3-copy reads also consume their source bytes.
                let boot = self.base as usize;
                if n >= boot
                    && n - boot < self.rom.len().saturating_sub(0x1000).min(0x10_0000)
                    && !self.written.get(n).copied().unwrap_or(false)
                {
                    self.consumed.insert((0x1000 + n - boot) as u32);
                }
                *self.ram.get(n).ok_or("read outside RAM")?
            };
            value = value.zip(byte).map(|(v, b)| (v << 8) | u64::from(b));
        }
        Ok(value)
    }

    fn store(&mut self, address: u32, size: usize, value: Option<u64>) -> Result<(), String> {
        if !(address as usize).is_multiple_of(size) {
            return Err("unaligned memory access".into());
        }
        let start = Self::physical(address)?;
        if start + size > RAM {
            return Err("write outside RAM".into());
        }
        if start < self.base as usize + self.size as usize && (self.base as usize) < start + size {
            return Err("write into executing boot image needs cache/lifetime proof".into());
        }
        self.touch(start);
        for i in 0..size {
            self.ram[start + i] = value.map(|v| (v >> (8 * (size - i - 1))) as u8);
            self.written[start + i] = true;
            self.flushed[start + i] = false;
        }
        Ok(())
    }

    fn step(&mut self) -> Result<(), String> {
        let word = self
            .read(self.pc, 4, false)?
            .ok_or("unknown instruction bytes")? as u32;
        if !crate::discovery::decode(word, GuestAddr(self.pc)).is_valid() {
            return Err(format!("invalid instruction encoding {word:08x}"));
        }
        let (op, rs, rt, rd, sh, fun) = (
            word >> 26,
            ((word >> 21) & 31) as usize,
            ((word >> 16) & 31) as usize,
            ((word >> 11) & 31) as usize,
            (word >> 6) & 31,
            word & 63,
        );
        let imm = word as i16 as i64 as u64;
        let (a, b) = (self.r[rs], self.r[rt]);
        let pair = a.zip(b);
        let old_pending = self.pending.take();
        let mut branch = None;
        let mut transfer = false;
        match op {
            0 => match fun {
                0 => self.r[rd] = b.map(|b| sx((b as u32) << sh)),
                2 => self.r[rd] = b.map(|b| sx((b as u32) >> sh)),
                3 => self.r[rd] = b.map(|b| sx(((b as i32) >> sh) as u32)),
                8 | 9 => {
                    transfer = true;
                    let target = self.value(rs)?;
                    if target != sx(target as u32) {
                        return Err("noncanonical jump address".into());
                    }
                    branch = Some(target as u32);
                    if fun == 9 {
                        self.r[rd] = Some(sx(self.pc.wrapping_add(8)));
                    }
                }
                0x21 => self.r[rd] = pair.map(|(a, b)| sx((a as u32).wrapping_add(b as u32))),
                0x23 => self.r[rd] = pair.map(|(a, b)| sx((a as u32).wrapping_sub(b as u32))),
                0x24 => self.r[rd] = pair.map(|(a, b)| a & b),
                0x25 => self.r[rd] = pair.map(|(a, b)| a | b),
                0x26 => self.r[rd] = pair.map(|(a, b)| a ^ b),
                0x27 => self.r[rd] = pair.map(|(a, b)| !(a | b)),
                0x2a => self.r[rd] = pair.map(|(a, b)| u64::from((a as i64) < (b as i64))),
                0x2b => self.r[rd] = pair.map(|(a, b)| u64::from(a < b)),
                _ => return Err(format!("unsupported SPECIAL instruction {word:08x}")),
            },
            2 | 3 => {
                transfer = true;
                branch =
                    Some((self.pc.wrapping_add(4) & 0xf000_0000) | ((word & 0x03ff_ffff) << 2));
                if op == 3 {
                    self.r[31] = Some(sx(self.pc.wrapping_add(8)));
                }
            }
            4..=7 => {
                transfer = true;
                let taken = match op {
                    4 => self.value(rs)? == self.value(rt)?,
                    5 => self.value(rs)? != self.value(rt)?,
                    6 => (self.value(rs)? as i64) <= 0,
                    _ => (self.value(rs)? as i64) > 0,
                };
                branch = Some(if taken {
                    self.pc.wrapping_add(4).wrapping_add((imm as u32) << 2)
                } else {
                    self.pc.wrapping_add(8)
                });
            }
            8 => {
                self.r[rt] = match a {
                    Some(a) => Some(sx((a as i32)
                        .checked_add(imm as i32)
                        .ok_or("integer overflow exception")?
                        as u32)),
                    None => return Err("unknown operand of overflow-trapping ADDI".into()),
                }
            }
            9 => self.r[rt] = a.map(|a| sx((a as u32).wrapping_add(imm as u32))),
            10 => self.r[rt] = a.map(|a| u64::from((a as i64) < (imm as i64))),
            11 => self.r[rt] = a.map(|a| u64::from(a < imm)),
            12 => self.r[rt] = a.map(|a| a & u64::from(word & 0xffff)),
            13 => self.r[rt] = a.map(|a| a | u64::from(word & 0xffff)),
            14 => self.r[rt] = a.map(|a| a ^ u64::from(word & 0xffff)),
            15 => self.r[rt] = Some(sx(word << 16)),
            16..=19 => {
                return Err(format!(
                    "unmodeled coprocessor state/instruction {word:08x}; verified boot/device state is required"
                ));
            }
            32 | 33 | 35 | 36 | 37 | 39 => {
                let address = self.address(rs, imm)?;
                let size = match op {
                    32 | 36 => 1,
                    33 | 37 => 2,
                    _ => 4,
                };
                self.r[rt] = self.read(address, size, true)?.map(|v| match op {
                    32 => v as i8 as i64 as u64,
                    33 => v as i16 as i64 as u64,
                    35 => sx(v as u32),
                    _ => v,
                });
            }
            40 | 41 | 43 => {
                let address = self.address(rs, imm)?;
                self.store(
                    address,
                    match op {
                        40 => 1,
                        41 => 2,
                        _ => 4,
                    },
                    b,
                )?;
            }
            47 => {
                let address = self.address(rs, imm)?;
                let physical = Self::physical(address)?;
                let index = (physical >> 4) & 511;
                match rt {
                    1 => {
                        if let Some(line) = self.data_lines[index].take() {
                            self.flush(line);
                        }
                    }
                    0x15 | 0x19 => {
                        if self.data_lines[index] == Some(physical & !15) {
                            self.flush(physical & !15);
                            if rt == 0x15 {
                                self.data_lines[index] = None;
                            }
                        }
                    }
                    _ => return Err("unsupported cache operation".into()),
                }
            }
            _ => return Err(format!("unsupported instruction {word:08x}")),
        }
        if transfer && old_pending.is_some() {
            return Err("control transfer in delay slot".into());
        }
        self.r[0] = Some(0);
        self.pending = branch;
        self.pc = old_pending.unwrap_or_else(|| self.pc.wrapping_add(4));
        self.steps += 1;
        Ok(())
    }

    fn capture(&self) -> Result<Capture, String> {
        let at = Self::physical(self.pc)?;
        if self.pc & 3 != 0 || !self.written[at] {
            return Err("boot exited without CPU-produced target bytes".into());
        }
        let mut lo = at;
        let mut hi = at;
        while lo > 0 && self.written[lo - 1] {
            lo -= 1;
        }
        while hi < RAM && self.written[hi] {
            hi += 1;
        }
        if lo % 4 != 0 || hi % 4 != 0 {
            return Err("produced image is not word aligned".into());
        }
        let bytes = self.ram[lo..hi]
            .iter()
            .copied()
            .collect::<Option<Vec<_>>>()
            .ok_or("produced image depends on unknown power-on state")?;
        if self.flushed[lo..hi].contains(&false) {
            return Err("produced text has cached stores without writeback".into());
        }
        if (lo..hi)
            .step_by(4)
            .any(|p| self.fetched_lines.contains(&(p & !31)))
        {
            return Err(
                "produced text overlaps a previously fetched instruction-cache line".into(),
            );
        }
        let mut consumed: Vec<(u32, u32)> = Vec::new();
        for &offset in &self.consumed {
            if let Some(last) = consumed.last_mut()
                && last.1 == offset
            {
                last.1 += 1;
            } else {
                consumed.push((offset, offset + 1));
            }
        }
        Ok(Capture {
            destination: GuestRange {
                start: GuestAddr(0x8000_0000 + lo as u32),
                size: bytes.len() as u32,
            },
            bytes,
            consumed,
            steps: self.steps,
            entry: GuestAddr(self.pc),
            registers: self.r,
        })
    }
}

/// No firmware, controller, timer or guessed register values are supplied. Only
/// r0 and IPL3's declared ROM copy are known. A refusal leaves static inference
/// unchanged. This is a candidate generator, never a closed-world proof.
/// Its declared analysis profile starts with empty caches, not a PIF/IPL3 trace.
pub fn execute(rom: &CanonicalRom) -> Result<Capture, Stop> {
    let start = rom.header.boot_address.0;
    let mut m = Machine {
        rom: rom.bytes(),
        base: start.wrapping_sub(0x8000_0000),
        size: rom.boot_image_size().unwrap_or(0x10_0000),
        ram: vec![None; RAM],
        written: vec![false; RAM],
        flushed: vec![false; RAM],
        data_lines: [None; 512],
        fetched_lines: BTreeSet::new(),
        r: [None; 32],
        consumed: BTreeSet::new(),
        pc: start,
        pending: None,
        steps: 0,
    };
    let run = |m: &mut Machine<'_>| -> Result<Capture, String> {
        let base = Machine::physical(start)?;
        let copied = rom.bytes().len().saturating_sub(0x1000).min(0x10_0000);
        if copied == 0 || base + copied > RAM || m.size as usize > copied {
            return Err("boot copy outside ROM/RAM".into());
        }
        for (to, &byte) in m.ram[base..base + copied]
            .iter_mut()
            .zip(&rom.bytes()[0x1000..0x1000 + copied])
        {
            *to = Some(byte);
        }
        m.r[0] = Some(0);
        while m.steps < BUDGET {
            if m.pc.wrapping_sub(start) >= m.size {
                return m.capture();
            }
            m.step()?;
        }
        Err("analysis instruction budget exhausted".into())
    };
    run(&mut m).map_err(|reason| Stop {
        pc: GuestAddr(m.pc),
        steps: m.steps,
        reason,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture() -> Vec<u8> {
        let mut bytes = vec![0; 0x3000];
        bytes[..4].copy_from_slice(&[0x80, 0x37, 0x12, 0x40]);
        bytes[8..12].copy_from_slice(&0x8000_0400u32.to_be_bytes());
        // Bound the stub with its BSS clear, then XOR-decode 12 ROM bytes
        // into RAM. Both loop and final jump execute their delay slots.
        let words: [u32; 21] = [
            0x3c08_8000,
            0x3508_0500,
            0xad00_0000,
            0x3c09_b000,
            0x3529_2000,
            0x3c0a_8000,
            0x354a_2000,
            0x240b_000c,
            0x912c_0000,
            0x398c_0055,
            0xa14c_0000,
            0x2529_0001,
            0x254a_0001,
            0x256b_ffff,
            0x1560_fff9,
            0,
            0x3c19_8000,
            0x3739_2000,
            0xbf39_0000,
            0x0320_0008,
            0x2410_0007,
        ];
        for (n, word) in words.iter().enumerate() {
            bytes[0x1000 + 4 * n..0x1004 + 4 * n].copy_from_slice(&word.to_be_bytes());
        }
        let text: Vec<_> = [0x2402_002au32, 0x03e0_0008, 0]
            .into_iter()
            .flat_map(u32::to_be_bytes)
            .collect();
        for (out, byte) in bytes[0x2000..0x200c].iter_mut().zip(text) {
            *out = byte ^ 0x55;
        }
        bytes
    }

    #[test]
    fn cpu_transformation_replays_with_register_memory_control_and_source_evidence() {
        let bytes = fixture();
        let rom = CanonicalRom::from_bytes(&bytes).unwrap();
        let capture = execute(&rom).unwrap();
        assert_eq!(capture, execute(&rom).unwrap());
        assert_eq!(
            capture.destination,
            GuestRange {
                start: GuestAddr(0x8000_2000),
                size: 12
            }
        );
        assert_eq!(capture.entry, GuestAddr(0x8000_2000));
        assert_eq!(capture.steps, 109);
        assert_eq!(capture.registers[11], Some(0));
        assert_eq!(capture.registers[16], Some(7));
        assert_eq!(capture.registers[31], None);
        assert_eq!(capture.consumed, vec![(0x1000, 0x1054), (0x2000, 0x200c)]);
        assert_eq!(
            capture.bytes,
            [0x2402_002au32, 0x03e0_0008, 0]
                .into_iter()
                .flat_map(u32::to_be_bytes)
                .collect::<Vec<_>>()
        );
        use crate::{
            declared_loads::{DeclaredLoad, LoadEncoding, LoadImage, compose},
            program::RomOffset,
        };
        let mut spec = LoadImage {
            base_offset: RomOffset(0x1000),
            base: GuestRange {
                start: GuestAddr(0x8000_0400),
                size: 0x100,
            },
            loads: vec![DeclaredLoad {
                destination: capture.destination,
                source: RomOffset(0),
                encoding: LoadEncoding::Boot,
                evidence: Default::default(),
                relocatable: false,
                linked: None,
            }],
        };
        let (_, image) = compose(&bytes, &spec).unwrap();
        assert_eq!(image.word(GuestAddr(0x8000_2000)), Some(0x2402_002a));
        spec.loads[0].destination.size += 4;
        assert!(
            compose(&bytes, &spec)
                .unwrap_err()
                .contains("replayed destination")
        );
    }

    #[test]
    fn external_input_exceptions_unknown_text_and_budget_never_produce_images() {
        for (word, reason) in [
            (0x4002_4800u32, "unmodeled coprocessor"), // Count is not guessed.
            (0x8c02_0000, "external or unsupported memory"),
            (0x2042_0001, "unknown operand"),
            (0x1821_0000, "invalid instruction encoding"),
            (0, "unknown power-on register"),
        ] {
            let mut bytes = fixture();
            bytes[0x100c..0x1010].copy_from_slice(&word.to_be_bytes());
            if word == 0 {
                bytes[0x1010..0x1014].copy_from_slice(&0x0040_0008u32.to_be_bytes());
            }
            let stop = execute(&CanonicalRom::from_bytes(&bytes).unwrap()).unwrap_err();
            assert!(stop.reason.contains(reason), "{stop:?}");
        }
        let mut bytes = fixture();
        // Unknown initial register bytes may be stored but never certify text.
        bytes[0x1020..0x1024].copy_from_slice(&0x0000_0000u32.to_be_bytes());
        assert!(
            execute(&CanonicalRom::from_bytes(&bytes).unwrap())
                .unwrap_err()
                .reason
                .contains("unknown power-on state")
        );
        // ADDI overflow is an exception, not wrapping arithmetic.
        bytes[0x100c..0x1018].copy_from_slice(
            &[0x3c02_7fffu32, 0x3442_ffff, 0x2042_0001]
                .into_iter()
                .flat_map(u32::to_be_bytes)
                .collect::<Vec<_>>(),
        );
        assert!(
            execute(&CanonicalRom::from_bytes(&bytes).unwrap())
                .unwrap_err()
                .reason
                .contains("overflow exception")
        );
        let mut bytes = fixture();
        bytes[0x100c..0x1010].copy_from_slice(&0x1000_ffffu32.to_be_bytes());
        bytes[0x1010..0x1014].copy_from_slice(&0u32.to_be_bytes());
        assert_eq!(
            execute(&CanonicalRom::from_bytes(&bytes).unwrap())
                .unwrap_err()
                .steps,
            BUDGET
        );
    }

    #[test]
    fn text_requires_writeback_and_delay_slot_transfers_are_refused() {
        let mut bytes = fixture();
        bytes[0x1048..0x104c].copy_from_slice(&0u32.to_be_bytes());
        assert!(
            execute(&CanonicalRom::from_bytes(&bytes).unwrap())
                .unwrap_err()
                .reason
                .contains("without writeback")
        );
        for word in [0xbf35_0000u32, 0xbf21_0000] {
            bytes[0x1048..0x104c].copy_from_slice(&word.to_be_bytes());
            assert!(execute(&CanonicalRom::from_bytes(&bytes).unwrap()).is_ok());
        }
        bytes[0x1050..0x1054].copy_from_slice(&0x0320_0008u32.to_be_bytes());
        assert!(
            execute(&CanonicalRom::from_bytes(&bytes).unwrap())
                .unwrap_err()
                .reason
                .contains("control transfer in delay slot")
        );
    }
}
