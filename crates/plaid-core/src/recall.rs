//! Discovery recall against a local reference symbol map (ADR-0144).
//! The reference is an oracle for measurement only: a decomp's GNU ld map or
//! a splat `symbol_addrs` file, read from an ignored local path.
use crate::program::{EdgeKind, ProgramMap};
use serde::Serialize;
use std::collections::{BTreeMap, BTreeSet};

/// Milestone 2's recall bar.
pub const TARGET: f64 = 0.99;

/// Code symbols, address -> first name. GNU ld map symbols count when listed
/// under a `.text` input section; `symbol_addrs` lines count with `type:func`.
pub fn parse_symbols(text: &str) -> BTreeMap<u32, String> {
    let mut out = BTreeMap::new();
    let mut in_text = false;
    for line in text.lines() {
        // splat: `name = 0x80246000; // type:func`
        if let Some((name, rest)) = line.split_once('=')
            && rest.contains("type:func")
            && let Some(value) = rest.trim().split(';').next().and_then(hex)
        {
            out.entry(value).or_insert_with(|| name.trim().to_string());
            continue;
        }
        let fields: Vec<_> = line.split_whitespace().collect();
        // An input section line (` .text  0x... size file`) starts with one
        // space and a dot; an output section starts in column 0.
        if line.starts_with(" .") {
            in_text = fields[0] == ".text" || fields[0].starts_with(".text.");
            continue;
        }
        if !line.starts_with(' ') && !line.is_empty() {
            in_text = false;
            continue;
        }
        if in_text
            && fields.len() == 2
            && let Some(value) = hex(fields[0])
            && is_identifier(fields[1])
        {
            out.entry(value).or_insert_with(|| fields[1].to_string());
        }
    }
    out
}

fn hex(s: &str) -> Option<u32> {
    let wide = u64::from_str_radix(s.trim().strip_prefix("0x")?, 16).ok()?;
    // ld prints KSEG0 addresses either zero- or sign-extended to 64 bits.
    u32::try_from(wide)
        .ok()
        .or_else(|| (wide >> 32 == 0xffff_ffff).then_some(wide as u32))
}

fn is_identifier(s: &str) -> bool {
    s.chars()
        .next()
        .is_some_and(|c| c.is_ascii_alphabetic() || c == '_')
        && s.chars().all(|c| c.is_ascii_alphanumeric() || c == '_')
}

/// Function entries a map knows: entries, call targets, candidates of
/// linking indirect sites and declared runtime functions. Guest PCs only; a
/// reference map has no image identity.
pub fn discovered_functions(map: &ProgramMap) -> BTreeSet<u32> {
    let mut out: BTreeSet<u32> = map.entries.keys().map(|a| a.pc.0).collect();
    out.extend(
        map.direct_edges
            .iter()
            .filter(|e| e.kind == EdgeKind::Call)
            .map(|e| e.target.pc.0),
    );
    for site in map
        .indirect_sites
        .iter()
        .filter(|s| s.link_register.is_some())
    {
        out.extend(site.candidates.keys().map(|a| a.pc.0));
    }
    out.extend(map.runtime_functions.keys().map(|a| a.pc.0));
    out
}

#[derive(Debug, Serialize)]
pub struct Missed {
    pub address: String,
    pub name: String,
}

#[derive(Debug, Serialize)]
pub struct RecallReport {
    pub format: &'static str,
    pub range: [String; 2],
    pub reference_functions: usize,
    pub discovered_functions: usize,
    pub matched: usize,
    pub recall: f64,
    pub target: f64,
    pub meets_target: bool,
    /// Discovered entries absent from the reference. Linker maps omit static
    /// functions, so these are not counted as errors.
    pub not_in_reference: usize,
    pub missed: Vec<Missed>,
}

pub fn score(
    map: &ProgramMap,
    reference: &BTreeMap<u32, String>,
    start: u32,
    end: u32,
) -> RecallReport {
    let inside = |a: u32| a >= start && a < end;
    let wanted: BTreeMap<_, _> = reference.iter().filter(|(a, _)| inside(**a)).collect();
    let found: BTreeSet<_> = discovered_functions(map)
        .into_iter()
        .filter(|a| inside(*a))
        .collect();
    let missed: Vec<_> = wanted
        .iter()
        .filter(|(a, _)| !found.contains(a))
        .map(|(a, name)| Missed {
            address: format!("0x{a:08x}"),
            name: (*name).clone(),
        })
        .collect();
    let matched = wanted.len() - missed.len();
    let recall = if wanted.is_empty() {
        0.0
    } else {
        matched as f64 / wanted.len() as f64
    };
    RecallReport {
        format: "plaid-recall-v0",
        range: [format!("0x{start:08x}"), format!("0x{end:08x}")],
        reference_functions: wanted.len(),
        discovered_functions: found.len(),
        matched,
        recall,
        target: TARGET,
        meets_target: !wanted.is_empty() && recall >= TARGET,
        not_in_reference: found.iter().filter(|a| !wanted.contains_key(a)).count(),
        missed,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const LD_MAP: &str = "\
.main           0x0000000080246000     0x2000
 build/us/src/game/main.o(.text)
 .text          0x0000000080246000      0x1d0 build/us/src/game/main.o
                0x0000000080246000                handle_debug_key_sequences
                0x0000000080246050                main_func
                0x0000000080246050                main_func_alias
                0x0000000080246100                _mainSegmentStart = .
 .data          0x0000000080246200       0x10 build/us/src/game/main.o
                0x0000000080246200                gGlobalTimer
 .text.unlikely 0x0000000080246300       0x20 build/us/src/game/sound.o
                0xffffffff80246300                sound_init
";

    #[test]
    fn ld_map_keeps_text_symbols_only() {
        let s = parse_symbols(LD_MAP);
        assert_eq!(
            s.iter().map(|(a, n)| (*a, n.as_str())).collect::<Vec<_>>(),
            [
                (0x80246000, "handle_debug_key_sequences"),
                (0x80246050, "main_func"),
                (0x80246300, "sound_init")
            ]
        );
    }

    #[test]
    fn splat_symbol_addrs_need_type_func() {
        let s = parse_symbols(
            "osInitialize = 0x80325070; // type:func size:0x1ac\nD_8033 = 0x80330000; // type:u32\n",
        );
        assert_eq!(s.len(), 1);
        assert_eq!(s[&0x80325070], "osInitialize");
    }
}
