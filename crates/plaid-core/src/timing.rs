//! Opt-in analysis phase timings.
//!
//! `PLAID_PHASE_TIMINGS=1` makes the analysis stages report their own wall
//! times on stderr. It is a diagnostic only: the variable changes neither the
//! map bytes, the stdout report nor any decision, so a timed run and an
//! untimed run of the same inputs stay byte-identical.
use std::sync::OnceLock;
use std::time::{Duration, Instant};

/// Whether the process asked for phase timings.
pub fn enabled() -> bool {
    static ON: OnceLock<bool> = OnceLock::new();
    *ON.get_or_init(|| std::env::var_os("PLAID_PHASE_TIMINGS").is_some_and(|v| !v.is_empty()))
}

/// Report an already measured interval under `name`.
pub fn note(name: &str, elapsed: Duration) {
    if enabled() {
        eprintln!("plaid-timing: {name} {:.3} s", elapsed.as_secs_f64());
    }
}

/// Report how many times a repeated phase ran (rounds, items, candidates).
pub fn count(name: &str, n: usize) {
    if enabled() {
        eprintln!("plaid-timing: {name} count={n}");
    }
}

/// Run `f` and, when enabled, report how long it took under `name`.
pub fn phase<T>(name: &str, f: impl FnOnce() -> T) -> T {
    if !enabled() {
        return f();
    }
    let started = Instant::now();
    let value = f();
    note(name, started.elapsed());
    value
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_phase_returns_its_value() {
        // Timings are a diagnostic: the value never depends on the variable.
        assert_eq!(phase("synthetic", || 7), 7);
        note("synthetic", Duration::from_millis(1));
    }
}
