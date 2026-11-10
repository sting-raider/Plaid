//! Turns `scripts/native.py` output into a phase and an overall percentage.

use serde::Serialize;

/// (id, label, weight) in pipeline order; weights roughly follow wall time on a large ROM.
pub const PHASES: &[(&str, &str, u32)] = &[
    ("build", "Preparing the recompiler", 4),
    ("rom-info", "Reading the ROM header", 1),
    ("infer-loads", "Finding code in the ROM", 4),
    ("identify", "Identifying libultra functions", 3),
    ("discover", "Discovering code", 18),
    ("solve", "Proving control flow", 12),
    ("harvest", "Tracing the boot in a reference emulator", 8),
    ("lower", "Translating MIPS to C", 10),
    ("rsp", "Recompiling RSP microcode", 5),
    ("gcc", "Compiling native code", 33),
    ("validation", "Linking and first run", 10),
];

#[derive(Clone, Serialize, Debug, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct Progress {
    pub phase: usize,
    pub label: &'static str,
    pub percent: f32,
}

#[derive(Default)]
pub struct Tracker {
    phase: usize,
    compiled: u32,
    /// Units the gcc phase is expected to compile, learnt when it starts.
    pub expected: u32,
    built: u32,
    /// Crates the recompiler build may compile (packages in Cargo.lock).
    pub crates: u32,
    /// native.py hit an unknown jump target in its test run and rebuilds with the long trace.
    repair: bool,
}

fn phase_of(line: &str) -> Option<usize> {
    let cmd = line.strip_prefix("+ ")?;
    let cmd = cmd.strip_prefix("(cached) ").unwrap_or(cmd);
    let mut words = cmd.split_whitespace();
    let program = words.next()?;
    let tool = program.rsplit(['/', '\\']).next()?.trim_end_matches(".exe");
    let id = match tool {
        "cargo" => "build",
        "gcc" if cmd.contains("rt64.exe") => "validation",
        "gcc" | "clang" => "gcc",
        "plaid" => match words.next()? {
            "rom-info" => "rom-info",
            "infer-loads" | "infer-call-loads" => "infer-loads",
            "identify" => "identify",
            "discover" => "discover",
            "solve" => "solve",
            "lower-map" | "lower-c" => "lower",
            "rsp-from-rom" | "lower-rsp" => "rsp",
            _ => return None,
        },
        _ => return None,
    };
    PHASES.iter().position(|p| p.0 == id)
}

impl Tracker {
    pub fn new(crates: u32) -> Self {
        Tracker {
            crates,
            ..Default::default()
        }
    }

    /// Feeds one output line; returns the new progress when it changed.
    pub fn line(&mut self, line: &str) -> Option<Progress> {
        // cargo's own progress while the recompiler builds
        if self.phase == 0 && line.trim_start().starts_with("Compiling ") {
            self.built += 1;
            return Some(self.progress());
        }
        if line.contains("rebuilding with the full analysis-time replay") {
            // the one deliberate step back: the build restarts with a longer trace
            self.repair = true;
            self.phase = PHASES.iter().position(|p| p.0 == "harvest").unwrap();
            self.compiled = 0;
            return Some(self.progress());
        }
        // native.py then runs pinned ares for analysis, silently, for a minute or more
        let phase = if line.contains("boot harvest") || line.contains("refill harvest") {
            PHASES.iter().position(|p| p.0 == "harvest")?
        } else {
            phase_of(line)?
        };
        let gcc = PHASES.iter().position(|p| p.0 == "gcc").unwrap();
        if phase == gcc {
            self.compiled += 1;
        }
        // native.py re-solves after harvesting; progress never moves backwards
        self.phase = self.phase.max(phase);
        Some(self.progress())
    }

    pub fn progress(&self) -> Progress {
        let total: u32 = PHASES.iter().map(|p| p.2).sum();
        let done: u32 = PHASES[..self.phase].iter().map(|p| p.2).sum();
        let within = match PHASES[self.phase].0 {
            "gcc" if self.expected > 0 => (self.compiled as f32 / self.expected as f32).min(0.98),
            "build" if self.crates > 0 => (self.built as f32 / self.crates as f32).min(0.98),
            _ => 0.0,
        };
        let percent = (done as f32 + PHASES[self.phase].2 as f32 * within) / total as f32 * 100.0;
        Progress {
            phase: self.phase,
            label: if self.repair && self.phase < PHASES.len() - 1 {
                "Repairing: tracing the game longer"
            } else {
                PHASES[self.phase].1
            },
            percent,
        }
    }

    pub fn in_gcc(&self) -> bool {
        PHASES[self.phase].0 == "gcc"
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_fault_three_rebuild_shows_as_repair() {
        let mut t = Tracker::default();
        t.line("+ clang --target=x86_64-w64-windows-gnu -O0 -c a.part0.c").unwrap();
        assert!(t.in_gcc());
        let p = t
            .line("fault 3: rebuilding with the full analysis-time replay (--deep)")
            .unwrap();
        assert_eq!(p.label, "Repairing: tracing the game longer");
        assert!(!t.in_gcc());
    }

    #[test]
    fn follows_native_py_output() {
        let mut t = Tracker {
            crates: 4,
            ..Default::default()
        };
        let built = t
            .line("   Compiling plaid-core v0.0.1 (X:/P/crates/plaid-core)")
            .unwrap();
        assert!(built.percent > 0.0 && built.label == "Preparing the recompiler");
        assert_eq!(t.line("solve OPEN 3 blockers"), None);
        assert_eq!(
            t.line("+ cargo build -q --release -p plaid").unwrap().label,
            "Preparing the recompiler"
        );
        assert_eq!(
            t.line(r"+ X:\P\target\release\plaid discover rom.z64 0x1000")
                .unwrap()
                .label,
            "Discovering code"
        );
        assert_eq!(
            t.line(r"+ (cached) X:\P\target\release\plaid.exe solve rom map")
                .unwrap()
                .label,
            "Proving control flow"
        );
        assert_eq!(
            t.line(r"+ X:\P\target\release\plaid discover again")
                .unwrap()
                .label,
            "Proving control flow"
        );
        let harvest = t
            .line("solve open 1 blockers; analysis-time boot harvest")
            .unwrap();
        assert_eq!(harvest.label, "Tracing the boot in a reference emulator");
        // the re-solve after the harvest does not move progress backwards
        assert_eq!(
            t.line(r"+ X:\P\target\release\plaid solve rom map")
                .unwrap(),
            harvest
        );
        t.expected = 4;
        let a = t.line("+ gcc -O1 -c part0.c").unwrap();
        let b = t.line("+ gcc -O1 -c part1.c").unwrap();
        assert!(b.percent > a.percent && a.label == "Compiling native code");
        let end = t
            .line(r"+ gcc w.o p.o plaid_rt64.dll -o X:\P\game-rt64.exe")
            .unwrap();
        assert_eq!(end.label, "Linking and first run");
        assert!(end.percent < 100.0 && end.percent > b.percent);
    }
}
