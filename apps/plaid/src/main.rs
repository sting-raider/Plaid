use plaid_core::{program::ProgramMap, trace::DiscoveryTrace};
use std::{env, fs, process::ExitCode};

fn run() -> Result<(), String> {
    let args: Vec<_> = env::args().skip(1).collect();
    match args.as_slice() {
        [command, path] if command == "check-trace" => {
            let t =
                DiscoveryTrace::from_ndjson(&fs::read_to_string(path).map_err(|e| e.to_string())?)?;
            println!(
                "trace v{}: {} events; engine {} @ {}; canonical ROM {}",
                t.header.schema_version,
                t.events.len(),
                t.header.engine,
                t.header.revision,
                t.header.rom.sha256
            );
        }
        [command, path] if command == "check-map" => {
            let p = ProgramMap::from_json(&fs::read_to_string(path).map_err(|e| e.to_string())?)?;
            println!(
                "ProgramMap v{}: {} blocks, {} indirect sites, {} unresolved items",
                p.schema_version,
                p.blocks.len(),
                p.indirect_sites.len(),
                p.unresolved.len()
            );
        }
        _ => return Err("usage: plaid check-trace <trace.ndjson> | check-map <map.json>".into()),
    }
    Ok(())
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("plaid: {e}");
            ExitCode::FAILURE
        }
    }
}
