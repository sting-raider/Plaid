mod infer_calls;
mod rsp_rom;
use plaid_core::{
    EvidenceKind, GuestAddr,
    cop1_lineage::{
        Cop1MutationContext, Cop1MutationLineageReport, compose_cop1_mutation_history,
        verify_cop1_mutation_lineage_report,
    },
    cpu_copy::{
        CpuCopyReport, inspect_cpu_copy_history, inspect_cpu_definition_history,
        verify_cpu_copy_report, verify_cpu_definition_report,
    },
    dcache_writeback::{
        DcacheResidentReadReport, inspect_dcache_resident_read_history,
        inspect_dcache_store64_history, verify_dcache_resident_read_report,
        verify_dcache_store64_report,
    },
    discovery::CodeImage,
    evidence_manifest::DiscoveryTraceManifestSet,
    fetch::{import_boot_fetch, import_fetch, verify_boot_fetch_capture, verify_fetch_capture},
    history::{AccessHistoryReport, inspect_boot_history, verify_boot_history_report},
    merge::{import_trace_with_rom, merge_maps},
    pi_fetch_lineage::{
        PiFetchLineageReport, SpPiFetchLineageReport, inspect_pi_fetch_lineage,
        inspect_sp_pi_fetch_lineage, verify_pi_fetch_lineage_report,
        verify_sp_pi_fetch_lineage_report,
    },
    pi_history::{PiHistoryReport, inspect_pi_boot_history, verify_pi_boot_history_report},
    pi_queue_history::{
        PiQueueHistoryReport, inspect_pi_queue_boot_history, verify_pi_queue_boot_history_report,
    },
    pif_history::{PifHistoryReport, inspect_pif_boot_history, verify_pif_boot_history_report},
    pipeline::discover_image_with_loads,
    program::Evidence,
    program::{GuestRange, ProgramMap, RomOffset},
    rom::CanonicalRom,
    rsp_cpu_imem::{RspCpuImemReport, inspect_rsp_cpu_imem_history, verify_rsp_cpu_imem_report},
    solver::{DiscoverySourceInputs, Scope, solve, solve_with_discovery_sources},
    sp_history::{
        SpHistoryReport, SpWriterFetchReport, inspect_sp_boot_history,
        inspect_sp_writer_fetch_history, verify_sp_boot_history_report,
        verify_sp_writer_fetch_report,
    },
    trace::DiscoveryTrace,
};
use std::{
    collections::{BTreeMap, BTreeSet},
    env, fs,
    io::{BufReader, Write},
    process::ExitCode,
};

fn trace_sources(paths: &[String]) -> Result<Vec<DiscoveryTrace>, String> {
    paths
        .iter()
        .map(|path| {
            DiscoveryTrace::from_ndjson(&fs::read_to_string(path).map_err(|e| e.to_string())?)
        })
        .collect()
}

fn rom_images(rom: &CanonicalRom, map: &ProgramMap) -> Result<Vec<CodeImage>, String> {
    let mut images: Vec<CodeImage> = Vec::new();
    for region in &map.regions {
        if let Some(offset) = region.rom_offset {
            let mut image = CodeImage::from_rom(rom, offset, region.range.clone())?;
            // Partial regions may reference a larger image's identity.
            // Only complete hash-matching source witnesses enter here.
            if image.base.image == region.image {
                image.base.generation = region.generation;
                if !images
                    .iter()
                    .any(|old| old.base == image.base && old.words == image.words)
                {
                    images.push(image);
                }
            }
        }
    }
    for (id, spec) in &map.load_images {
        let (_, composite) = plaid_core::declared_loads::compose(rom.bytes(), spec)?;
        if &composite.base.image != id {
            return Err(format!("declared loads do not rebuild image {id}"));
        }
        images.push(composite);
    }
    Ok(images)
}

fn run() -> Result<(), String> {
    let mut args: Vec<_> = env::args().skip(1).collect();
    // `--loads <loads.json>` applies declared loads to discover, lower-c and
    // identify (ADR-0136); rsp-from-rom reads RSP-only sources (ADR-0225).
    let loads_path = match args.iter().position(|a| a == "--loads") {
        Some(i)
            if i + 1 < args.len()
                && matches!(
                    args[0].as_str(),
                    "discover" | "lower-c" | "identify" | "rsp-from-rom"
                ) =>
        {
            let path = args.remove(i + 1);
            args.remove(i);
            Some(path)
        }
        Some(_) => {
            return Err(
                "--loads <file> applies only to discover, lower-c, identify and rsp-from-rom"
                    .into(),
            );
        }
        None => None,
    };
    // `identify --symbols` reads a reference symbol map instead of n64sym
    // signatures (ADR-0148).
    let symbols = args.first().is_some_and(|c| c == "identify")
        && args
            .iter()
            .position(|a| a == "--symbols")
            .map(|i| args.remove(i))
            .is_some();
    // `identify --reference-map <map>` completes signature identification from
    // a reference symbol map where the ROM leaves a name open (ADR-0171).
    let reference_map = match args.iter().position(|a| a == "--reference-map") {
        Some(i) if i + 1 < args.len() && args[0] == "identify" && !symbols => {
            let path = args.remove(i + 1);
            args.remove(i);
            Some(path)
        }
        Some(_) => {
            return Err("--reference-map <map> applies only to identify with signatures".into());
        }
        None => None,
    };
    // `discover --data-roots` adds roots from function pointers in ROM data
    // (ADR-0152).
    let data_roots = args.first().is_some_and(|c| c == "discover")
        && args
            .iter()
            .position(|a| a == "--data-roots")
            .map(|i| args.remove(i))
            .is_some();
    // `discover --address-taken` adds only the address-taken roots: data
    // words and code constants, without the layout pass (ADR-0153).
    let address_taken = args
        .first()
        .is_some_and(|c| c == "discover" || c == "lower-c")
        && args
            .iter()
            .position(|a| a == "--address-taken")
            .map(|i| args.remove(i))
            .is_some();
    // `lower-c`/`lower-map --residual-dispatch`: VALIDATION ONLY (ADR-0218).
    let residual_dispatch = args
        .first()
        .is_some_and(|c| c == "lower-c" || c == "lower-map")
        && args
            .iter()
            .position(|a| a == "--residual-dispatch")
            .map(|i| args.remove(i))
            .is_some();
    // `discover --overlays` adds the ROM's own relocatable overlays at their
    // link addresses (ADR-0172, ADR-0179).
    let overlays = args.first().is_some_and(|c| c == "discover")
        && args
            .iter()
            .position(|a| a == "--overlays")
            .map(|i| args.remove(i))
            .is_some();
    // `--fr0` declares that guest code runs with Status.FR = 0 (ADR-0160).
    let fr0 = args
        .first()
        .is_some_and(|c| c == "discover" || c == "lower-c")
        && args
            .iter()
            .position(|a| a == "--fr0")
            .map(|i| args.remove(i))
            .is_some();
    match args.as_slice() {
        [
            command,
            source_path,
            expected_sha256,
            contexts_path,
            expected_contexts_sha256,
            output,
        ] if command == "compose-cop1-mutations" || command == "verify-cop1-mutations" => {
            let source = fs::read(source_path).map_err(|e| e.to_string())?;
            let contexts = fs::read(contexts_path).map_err(|e| e.to_string())?;
            if plaid_core::rom::sha256(&contexts) != *expected_contexts_sha256 {
                return Err("COP1 normalization side-input receipt mismatch".into());
            }
            let contexts: Vec<Cop1MutationContext> =
                serde_json::from_slice(&contexts).map_err(|e| e.to_string())?;
            if command.starts_with("verify-") {
                let report: Cop1MutationLineageReport =
                    serde_json::from_slice(&fs::read(output).map_err(|e| e.to_string())?)
                        .map_err(|e| e.to_string())?;
                verify_cop1_mutation_lineage_report(&report, &source, expected_sha256, &contexts)?;
                println!(
                    "COP1 FPR lineage/normalized mutations match both independently preserved inputs"
                );
            } else {
                if let Ok(destination) = fs::canonicalize(output) {
                    for input in [source_path, contexts_path] {
                        if destination == fs::canonicalize(input).map_err(|e| e.to_string())? {
                            return Err("composition output would overwrite an input".into());
                        }
                    }
                }
                let report = compose_cop1_mutation_history(&source, expected_sha256, &contexts)?;
                fs::write(
                    output,
                    serde_json::to_string_pretty(&report).map_err(|e| e.to_string())? + "\n",
                )
                .map_err(|e| e.to_string())?;
                println!(
                    "composed {} COP1 backing mutations; executable ancestry remains uncertified",
                    report.mutations.len()
                );
            }
        }
        [command, source_path, expected_sha256, output]
            if command == "inspect-dcache-resident-reads"
                || command == "verify-dcache-resident-reads"
                || command == "inspect-dcache-store64"
                || command == "verify-dcache-store64" =>
        {
            let source = fs::read(source_path).map_err(|e| e.to_string())?;
            if command.starts_with("verify-") {
                let report: DcacheResidentReadReport =
                    serde_json::from_slice(&fs::read(output).map_err(|e| e.to_string())?)
                        .map_err(|e| e.to_string())?;
                if command.ends_with("store64") {
                    verify_dcache_store64_report(&report, &source, expected_sha256)?;
                } else {
                    verify_dcache_resident_read_report(&report, &source, expected_sha256)?;
                }
                println!("D-cache reads/writebacks match complete source and independent receipt");
            } else {
                if let Ok(destination) = fs::canonicalize(output)
                    && destination == fs::canonicalize(source_path).map_err(|e| e.to_string())?
                {
                    return Err("inspection output would overwrite an input".into());
                }
                let report = if command.ends_with("store64") {
                    inspect_dcache_store64_history(&source, expected_sha256)?
                } else {
                    inspect_dcache_resident_read_history(&source, expected_sha256)?
                };
                fs::write(
                    output,
                    serde_json::to_string_pretty(&report).map_err(|e| e.to_string())? + "\n",
                )
                .map_err(|e| e.to_string())?;
                if command.ends_with("store64") {
                    println!(
                        "inspected {} decoded store64 attempts and {} backing exports; executable lifetime remains uncertified",
                        report.store64_operations.as_ref().map_or(0, Vec::len),
                        report.writeback.successful_backing_writebacks
                    );
                } else {
                    println!(
                        "inspected {} resident Word reads; table/target closure remains uncertified",
                        report.reads.len()
                    );
                }
            }
        }
        [command, source_path, expected_sha256, output]
            if command == "inspect-rsp-cpu-imem" || command == "verify-rsp-cpu-imem" =>
        {
            let source = fs::read(source_path).map_err(|e| e.to_string())?;
            if command.starts_with("verify-") {
                let report: RspCpuImemReport =
                    serde_json::from_slice(&fs::read(output).map_err(|e| e.to_string())?)
                        .map_err(|e| e.to_string())?;
                verify_rsp_cpu_imem_report(&report, &source, expected_sha256)?;
                println!(
                    "RSP/CPU IMEM composition matches complete source and independent receipt"
                );
            } else {
                if let Ok(destination) = fs::canonicalize(output)
                    && destination == fs::canonicalize(source_path).map_err(|e| e.to_string())?
                {
                    return Err("inspection output would overwrite an input".into());
                }
                let report = inspect_rsp_cpu_imem_history(&source, expected_sha256)?;
                fs::write(
                    output,
                    serde_json::to_string_pretty(&report).map_err(|e| e.to_string())? + "\n",
                )
                .map_err(|e| e.to_string())?;
                println!(
                    "inspected {} decoded RSP/CPU IMEM chains; executable consumption remains uncertified",
                    report.copies.len()
                );
            }
        }
        [
            command,
            rom_path,
            firmware_path,
            fetch_path,
            history_path,
            expected_history,
            expected_fetch,
            output,
        ] if command == "inspect-sp-writer-fetch" || command == "verify-sp-writer-fetch" => {
            let rom = CanonicalRom::from_bytes(&fs::read(rom_path).map_err(|e| e.to_string())?)?;
            let firmware = fs::read(firmware_path).map_err(|e| e.to_string())?;
            let fetched = BufReader::new(fs::File::open(fetch_path).map_err(|e| e.to_string())?);
            let history = BufReader::new(fs::File::open(history_path).map_err(|e| e.to_string())?);
            if command.starts_with("verify-") {
                let report: SpWriterFetchReport =
                    serde_json::from_slice(&fs::read(output).map_err(|e| e.to_string())?)
                        .map_err(|e| e.to_string())?;
                verify_sp_writer_fetch_report(
                    &report,
                    history,
                    fetched,
                    &rom,
                    &firmware,
                    expected_history,
                    expected_fetch,
                )?;
                println!(
                    "SP captured-writer/fetch report matches complete sources and independent receipts"
                );
            } else {
                if let Ok(destination) = fs::canonicalize(output) {
                    for source in [rom_path, firmware_path, fetch_path, history_path] {
                        if destination == fs::canonicalize(source).map_err(|e| e.to_string())? {
                            return Err("inspection output would overwrite an input".into());
                        }
                    }
                }
                let report = inspect_sp_writer_fetch_history(
                    history,
                    fetched,
                    &rom,
                    &firmware,
                    expected_history,
                    expected_fetch,
                )?;
                fs::write(
                    output,
                    serde_json::to_string_pretty(&report).map_err(|e| e.to_string())? + "\n",
                )
                .map_err(|e| e.to_string())?;
                println!(
                    "inspected {} SP executable backing reads; captured writers are candidates, ultimate ancestry remains uncertified",
                    report.projection.sp_backed_fetches
                );
            }
        }
        [command, output, sources @ ..]
            if command == "create-trace-expectations" && !sources.is_empty() =>
        {
            let traces = trace_sources(sources)?;
            let expected = DiscoveryTraceManifestSet::from_traces(&traces)?;
            let encoded =
                serde_json::to_string_pretty(&expected).map_err(|e| e.to_string())? + "\n";
            // Expectations are created once at a trusted boundary, never silently
            // replaced from subsequently edited sources or maps.
            let mut file = fs::OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(output)
                .map_err(|e| e.to_string())?;
            file.write_all(encoded.as_bytes())
                .map_err(|e| e.to_string())?;
            println!(
                "preserved {} discovery source expectations; retain this file independently of editable maps and sources",
                expected.sessions.len()
            );
        }
        [command, rom_path, map_path, expectations_path, sources @ ..]
            if command == "solve-traces" && !sources.is_empty() =>
        {
            let rom = CanonicalRom::from_bytes(&fs::read(rom_path).map_err(|e| e.to_string())?)?;
            let map =
                ProgramMap::from_json(&fs::read_to_string(map_path).map_err(|e| e.to_string())?)?;
            let expected: DiscoveryTraceManifestSet =
                serde_json::from_slice(&fs::read(expectations_path).map_err(|e| e.to_string())?)
                    .map_err(|e| e.to_string())?;
            let traces = trace_sources(sources)?;
            let images = rom_images(&rom, &map)?;
            let report = solve_with_discovery_sources(
                &map,
                &images,
                Scope::WholeRom,
                &DiscoverySourceInputs {
                    expected: &expected,
                    traces: &traces,
                    rom: &rom,
                    known_images: &[],
                    import_budget: 1_000_000,
                },
            )?;
            println!(
                "{}",
                serde_json::to_string_pretty(&report).map_err(|e| e.to_string())?
            );
        }
        [command, source_path, expected_sha256, output]
            if matches!(
                command.as_str(),
                "inspect-cpu-copy-history"
                    | "verify-cpu-copy-history"
                    | "inspect-cpu-definitions"
                    | "verify-cpu-definitions"
            ) =>
        {
            let source = fs::read(source_path).map_err(|e| e.to_string())?;
            let definitions = command.ends_with("cpu-definitions");
            if command.starts_with("verify-") {
                let report: CpuCopyReport =
                    serde_json::from_slice(&fs::read(output).map_err(|e| e.to_string())?)
                        .map_err(|e| e.to_string())?;
                if definitions {
                    verify_cpu_definition_report(&report, &source, expected_sha256)?;
                } else {
                    verify_cpu_copy_report(&report, &source, expected_sha256)?;
                }
                println!("CPU producer report matches complete source and external receipt");
            } else {
                if let Ok(destination) = fs::canonicalize(output)
                    && destination == fs::canonicalize(source_path).map_err(|e| e.to_string())?
                {
                    return Err("inspection output would overwrite an input".into());
                }
                let report = if definitions {
                    inspect_cpu_definition_history(&source, expected_sha256)?
                } else {
                    inspect_cpu_copy_history(&source, expected_sha256)?
                };
                fs::write(
                    output,
                    serde_json::to_string_pretty(&report).map_err(|e| e.to_string())? + "\n",
                )
                .map_err(|e| e.to_string())?;
                println!(
                    "inspected {} instruction contexts and {} bounded copy/transform witnesses; executable lifetime remains uncertified",
                    report.instruction_contexts,
                    report.witnesses.len()
                );
            }
        }
        [
            command,
            rom_path,
            firmware_path,
            fetch_path,
            history_path,
            output,
        ] if command == "inspect-pif-boot-history" || command == "verify-pif-boot-history" => {
            let rom = CanonicalRom::from_bytes(&fs::read(rom_path).map_err(|e| e.to_string())?)?;
            let firmware = fs::read(firmware_path).map_err(|e| e.to_string())?;
            let fetched = BufReader::new(fs::File::open(fetch_path).map_err(|e| e.to_string())?);
            let history = BufReader::new(fs::File::open(history_path).map_err(|e| e.to_string())?);
            if command == "verify-pif-boot-history" {
                let report: PifHistoryReport =
                    serde_json::from_str(&fs::read_to_string(output).map_err(|e| e.to_string())?)
                        .map_err(|e| e.to_string())?;
                verify_pif_boot_history_report(&report, history, fetched, &rom, &firmware)?;
                println!(
                    "Observed PIF backing report matches both complete sources and supplied inputs"
                );
            } else {
                if let Ok(destination) = fs::canonicalize(output) {
                    for source in [rom_path, firmware_path, fetch_path, history_path] {
                        if destination == fs::canonicalize(source).map_err(|e| e.to_string())? {
                            return Err("inspection output would overwrite an input".into());
                        }
                    }
                }
                let report = inspect_pif_boot_history(history, fetched, &rom, &firmware)?;
                fs::write(
                    output,
                    serde_json::to_string_pretty(&report).map_err(|e| e.to_string())? + "\n",
                )
                .map_err(|e| e.to_string())?;
                println!(
                    "inspected {} fetches and {} actual PIF backing reads; mutation coverage and executable lifetime remain uncertified",
                    report.fetches, report.pif_backed_fetches
                );
            }
        }
        [
            command,
            rom_path,
            firmware_path,
            fetch_path,
            history_path,
            output,
        ] if command == "inspect-sp-boot-history" || command == "verify-sp-boot-history" => {
            let rom = CanonicalRom::from_bytes(&fs::read(rom_path).map_err(|e| e.to_string())?)?;
            let firmware = fs::read(firmware_path).map_err(|e| e.to_string())?;
            let fetched = BufReader::new(fs::File::open(fetch_path).map_err(|e| e.to_string())?);
            let history = BufReader::new(fs::File::open(history_path).map_err(|e| e.to_string())?);
            if command == "verify-sp-boot-history" {
                let report: SpHistoryReport =
                    serde_json::from_str(&fs::read_to_string(output).map_err(|e| e.to_string())?)
                        .map_err(|e| e.to_string())?;
                verify_sp_boot_history_report(&report, history, fetched, &rom, &firmware)?;
                println!(
                    "Observed SP backing report matches both complete sources and supplied inputs"
                );
            } else {
                if let Ok(destination) = fs::canonicalize(output) {
                    for source in [rom_path, firmware_path, fetch_path, history_path] {
                        if destination == fs::canonicalize(source).map_err(|e| e.to_string())? {
                            return Err("inspection output would overwrite an input".into());
                        }
                    }
                }
                let report = inspect_sp_boot_history(history, fetched, &rom, &firmware)?;
                fs::write(
                    output,
                    serde_json::to_string_pretty(&report).map_err(|e| e.to_string())? + "\n",
                )
                .map_err(|e| e.to_string())?;
                println!(
                    "inspected {} fetches and {} actual SP backing reads; mutation coverage and executable lifetime remain uncertified",
                    report.fetches, report.sp_backed_fetches
                );
            }
        }
        [
            command,
            rom_path,
            firmware_path,
            fetch_path,
            history_path,
            output,
        ] if command == "inspect-pi-fetch-lineage" || command == "verify-pi-fetch-lineage" => {
            let rom = CanonicalRom::from_bytes(&fs::read(rom_path).map_err(|e| e.to_string())?)?;
            let firmware = fs::read(firmware_path).map_err(|e| e.to_string())?;
            let fetched = BufReader::new(fs::File::open(fetch_path).map_err(|e| e.to_string())?);
            let history = BufReader::new(fs::File::open(history_path).map_err(|e| e.to_string())?);
            if command == "verify-pi-fetch-lineage" {
                let report: PiFetchLineageReport =
                    serde_json::from_str(&fs::read_to_string(output).map_err(|e| e.to_string())?)
                        .map_err(|e| e.to_string())?;
                verify_pi_fetch_lineage_report(&report, history, fetched, &rom, &firmware)?;
                println!(
                    "Observed PI fetch lineage matches both complete sources and supplied inputs"
                );
            } else {
                if let Ok(destination) = fs::canonicalize(output) {
                    for source in [rom_path, firmware_path, fetch_path, history_path] {
                        if destination == fs::canonicalize(source).map_err(|e| e.to_string())? {
                            return Err("inspection output would overwrite an input".into());
                        }
                    }
                }
                let report = inspect_pi_fetch_lineage(history, fetched, &rom, &firmware)?;
                let encoded =
                    serde_json::to_string_pretty(&report).map_err(|e| e.to_string())? + "\n";
                fs::write(output, encoded).map_err(|e| e.to_string())?;
                println!(
                    "inspected {} fetches and {} observed PI-byte fetch chains; mutation coverage and executable lifetime remain uncertified",
                    report.fetches,
                    report.fully_attributed_fetches + report.partially_attributed_fetches
                );
            }
        }
        [
            command,
            rom_path,
            firmware_path,
            fetch_path,
            history_path,
            expected_history,
            expected_fetch,
            output,
        ] if command == "inspect-sp-pi-fetch-lineage"
            || command == "verify-sp-pi-fetch-lineage" =>
        {
            let rom = CanonicalRom::from_bytes(&fs::read(rom_path).map_err(|e| e.to_string())?)?;
            let firmware = fs::read(firmware_path).map_err(|e| e.to_string())?;
            let fetched = BufReader::new(fs::File::open(fetch_path).map_err(|e| e.to_string())?);
            let history = BufReader::new(fs::File::open(history_path).map_err(|e| e.to_string())?);
            if command == "verify-sp-pi-fetch-lineage" {
                let report: SpPiFetchLineageReport =
                    serde_json::from_str(&fs::read_to_string(output).map_err(|e| e.to_string())?)
                        .map_err(|e| e.to_string())?;
                verify_sp_pi_fetch_lineage_report(
                    &report,
                    history,
                    fetched,
                    &rom,
                    &firmware,
                    expected_history,
                    expected_fetch,
                )?;
                println!(
                    "SP/PI byte-chain report matches complete sources and independent receipts"
                );
            } else {
                if let Ok(destination) = fs::canonicalize(output) {
                    for source in [rom_path, firmware_path, fetch_path, history_path] {
                        if destination == fs::canonicalize(source).map_err(|e| e.to_string())? {
                            return Err("inspection output would overwrite an input".into());
                        }
                    }
                }
                let report = inspect_sp_pi_fetch_lineage(
                    history,
                    fetched,
                    &rom,
                    &firmware,
                    expected_history,
                    expected_fetch,
                )?;
                fs::write(
                    output,
                    serde_json::to_string_pretty(&report).map_err(|e| e.to_string())? + "\n",
                )
                .map_err(|e| e.to_string())?;
                println!(
                    "inspected {} fetches and {} compatible PI-byte fetch chains on the raw SP clock; mutation coverage and executable lifetime remain uncertified",
                    report.fetches,
                    report.fully_attributed_fetches + report.partially_attributed_fetches,
                );
            }
        }
        [
            command,
            rom_path,
            firmware_path,
            fetch_path,
            history_path,
            output,
        ] if command == "inspect-pi-queue-boot-history"
            || command == "verify-pi-queue-boot-history" =>
        {
            let rom = CanonicalRom::from_bytes(&fs::read(rom_path).map_err(|e| e.to_string())?)?;
            let firmware = fs::read(firmware_path).map_err(|e| e.to_string())?;
            let fetched = BufReader::new(fs::File::open(fetch_path).map_err(|e| e.to_string())?);
            let history = BufReader::new(fs::File::open(history_path).map_err(|e| e.to_string())?);
            if command == "verify-pi-queue-boot-history" {
                let report: PiQueueHistoryReport =
                    serde_json::from_str(&fs::read_to_string(output).map_err(|e| e.to_string())?)
                        .map_err(|e| e.to_string())?;
                verify_pi_queue_boot_history_report(&report, history, fetched, &rom, &firmware)?;
                println!(
                    "PI request/queue inspection matches both complete sources and supplied inputs"
                );
            } else {
                if let Ok(destination) = fs::canonicalize(output) {
                    for source in [rom_path, firmware_path, fetch_path, history_path] {
                        if destination == fs::canonicalize(source).map_err(|e| e.to_string())? {
                            return Err("inspection output would overwrite an input".into());
                        }
                    }
                }
                let report = inspect_pi_queue_boot_history(history, fetched, &rom, &firmware)?;
                let encoded =
                    serde_json::to_string_pretty(&report).map_err(|e| e.to_string())? + "\n";
                fs::write(output, encoded).map_err(|e| e.to_string())?;
                println!(
                    "inspected {} PI queue history records and {} actual request/status links; native completion remains open",
                    report.records,
                    report.request_status_links.len()
                );
            }
        }
        [
            command,
            rom_path,
            firmware_path,
            fetch_path,
            history_path,
            output,
        ] if command == "inspect-pi-boot-history" || command == "verify-pi-boot-history" => {
            let rom = CanonicalRom::from_bytes(&fs::read(rom_path).map_err(|e| e.to_string())?)?;
            let firmware = fs::read(firmware_path).map_err(|e| e.to_string())?;
            let fetched = BufReader::new(fs::File::open(fetch_path).map_err(|e| e.to_string())?);
            let history = BufReader::new(fs::File::open(history_path).map_err(|e| e.to_string())?);
            if command == "verify-pi-boot-history" {
                let report: PiHistoryReport =
                    serde_json::from_str(&fs::read_to_string(output).map_err(|e| e.to_string())?)
                        .map_err(|e| e.to_string())?;
                verify_pi_boot_history_report(&report, history, fetched, &rom, &firmware)?;
                println!("PI effect inspection matches both complete sources and supplied inputs");
            } else {
                if let Ok(destination) = fs::canonicalize(output) {
                    for source in [rom_path, firmware_path, fetch_path, history_path] {
                        if destination == fs::canonicalize(source).map_err(|e| e.to_string())? {
                            return Err("inspection output would overwrite an input".into());
                        }
                    }
                }
                let report = inspect_pi_boot_history(history, fetched, &rom, &firmware)?;
                let encoded =
                    serde_json::to_string_pretty(&report).map_err(|e| e.to_string())? + "\n";
                fs::write(output, encoded).map_err(|e| e.to_string())?;
                println!(
                    "inspected {} PI history records and {} successful byte effects; transfer completion remains uncertified",
                    report.records, report.successful_pi_writes
                );
            }
        }
        [
            command,
            rom_path,
            firmware_path,
            fetch_path,
            history_path,
            output,
        ] if command == "inspect-boot-history" || command == "verify-boot-history" => {
            let rom = CanonicalRom::from_bytes(&fs::read(rom_path).map_err(|e| e.to_string())?)?;
            let firmware = fs::read(firmware_path).map_err(|e| e.to_string())?;
            let fetched = BufReader::new(fs::File::open(fetch_path).map_err(|e| e.to_string())?);
            let history = BufReader::new(fs::File::open(history_path).map_err(|e| e.to_string())?);
            if command == "verify-boot-history" {
                let report: AccessHistoryReport =
                    serde_json::from_str(&fs::read_to_string(output).map_err(|e| e.to_string())?)
                        .map_err(|e| e.to_string())?;
                verify_boot_history_report(&report, history, fetched, &rom, &firmware)?;
                println!("history inspection matches both complete sources and supplied inputs");
            } else {
                if let Ok(destination) = fs::canonicalize(output) {
                    for source in [rom_path, firmware_path, fetch_path, history_path] {
                        if destination == fs::canonicalize(source).map_err(|e| e.to_string())? {
                            return Err("inspection output would overwrite an input".into());
                        }
                    }
                }
                let report = inspect_boot_history(history, fetched, &rom, &firmware)?;
                let encoded =
                    serde_json::to_string_pretty(&report).map_err(|e| e.to_string())? + "\n";
                fs::write(output, encoded).map_err(|e| e.to_string())?;
                println!(
                    "inspected {} ordered records and {} fetched words",
                    report.records, report.fetches
                );
            }
        }
        [command, rom_path, firmware_path, fetch_path, output]
            if command == "import-boot-fetch" =>
        {
            let rom = CanonicalRom::from_bytes(&fs::read(rom_path).map_err(|e| e.to_string())?)?;
            let firmware = fs::read(firmware_path).map_err(|e| e.to_string())?;
            let reader = BufReader::new(fs::File::open(fetch_path).map_err(|e| e.to_string())?);
            let map = import_boot_fetch(reader, &rom, &firmware)?;
            fs::write(output, map.to_json()?).map_err(|e| e.to_string())?;
            println!(
                "imported {} boot fetch summaries; executable identities remain unknown",
                map.fetch_observations.len()
            );
        }
        [command, rom_path, firmware_path, fetch_path, map_path]
            if command == "verify-boot-fetch" =>
        {
            let rom = CanonicalRom::from_bytes(&fs::read(rom_path).map_err(|e| e.to_string())?)?;
            let firmware = fs::read(firmware_path).map_err(|e| e.to_string())?;
            let map =
                ProgramMap::from_json(&fs::read_to_string(map_path).map_err(|e| e.to_string())?)?;
            let reader = BufReader::new(fs::File::open(fetch_path).map_err(|e| e.to_string())?);
            verify_boot_fetch_capture(&map, reader, &rom, &firmware)?;
            println!("boot fetch summaries and firmware inputs match their complete sources");
        }
        [command, rom_path, fetch_path, output] if command == "import-fetch" => {
            let rom = CanonicalRom::from_bytes(&fs::read(rom_path).map_err(|e| e.to_string())?)?;
            let reader = BufReader::new(fs::File::open(fetch_path).map_err(|e| e.to_string())?);
            let map = import_fetch(reader, &rom)?;
            fs::write(output, map.to_json()?).map_err(|e| e.to_string())?;
            println!(
                "imported {} raw fetch summaries; executable identities remain unknown",
                map.fetch_observations.len()
            );
        }
        [command, rom_path, fetch_path, map_path] if command == "verify-fetch" => {
            let rom = CanonicalRom::from_bytes(&fs::read(rom_path).map_err(|e| e.to_string())?)?;
            let map =
                ProgramMap::from_json(&fs::read_to_string(map_path).map_err(|e| e.to_string())?)?;
            let reader = BufReader::new(fs::File::open(fetch_path).map_err(|e| e.to_string())?);
            verify_fetch_capture(&map, reader, &rom)?;
            println!("fetch summaries and provenance match their complete raw source");
        }
        [command, rom_path, map_path, flag @ ..] if command == "solve" && flag.len() <= 1 => {
            let scope = match flag {
                [] => Scope::WholeRom,
                [f] if f == "--guarded-ram" => Scope::DeclaredStaticImagesGuardedRam,
                [f] if f == "--address-taken" => Scope::DeclaredStaticImagesGuardedRamAddressTaken,
                [f] if f == "--residual-dispatch" => {
                    Scope::DeclaredStaticImagesGuardedRamResidualDispatch
                }
                _ => {
                    return Err(
                        "solve accepts only --guarded-ram, --address-taken or --residual-dispatch"
                            .into(),
                    );
                }
            };
            let rom = CanonicalRom::from_bytes(&fs::read(rom_path).map_err(|e| e.to_string())?)?;
            let map =
                ProgramMap::from_json(&fs::read_to_string(map_path).map_err(|e| e.to_string())?)?;
            if map.rom != rom.identity {
                return Err("map does not match canonical ROM".into());
            }
            let images = rom_images(&rom, &map)?;
            let report = solve(&map, &images, scope)?;
            println!(
                "{}",
                serde_json::to_string_pretty(&report).map_err(|e| e.to_string())?
            );
        }
        [command, path] if command == "solve" => {
            let map = ProgramMap::from_json(&fs::read_to_string(path).map_err(|e| e.to_string())?)?;
            let report = solve(&map, &[], Scope::WholeRom)?;
            println!(
                "{}",
                serde_json::to_string_pretty(&report).map_err(|e| e.to_string())?
            );
        }
        [command, rom_path, trace_path, output] if command == "import-trace" => {
            let rom = CanonicalRom::from_bytes(&fs::read(rom_path).map_err(|e| e.to_string())?)?;
            let trace = DiscoveryTrace::from_ndjson(
                &fs::read_to_string(trace_path).map_err(|e| e.to_string())?,
            )?;
            if trace.header.rom != rom.identity {
                return Err("trace does not match normalized ROM identity".into());
            }
            let map = import_trace_with_rom(&trace, &[], &rom, 1_000_000)?;
            fs::write(output, map.to_json()?).map_err(|e| e.to_string())?;
            println!(
                "imported {} blocks; {} unresolved facts",
                map.blocks.len(),
                map.unresolved.len()
            );
        }
        [command, left, right, output] if command == "merge" => {
            let a = ProgramMap::from_json(&fs::read_to_string(left).map_err(|e| e.to_string())?)?;
            let b = ProgramMap::from_json(&fs::read_to_string(right).map_err(|e| e.to_string())?)?;
            fs::write(output, merge_maps(&a, &b)?.to_json()?).map_err(|e| e.to_string())?;
        }
        [
            command,
            rom_path,
            offset,
            start,
            size,
            entry,
            output,
            runtime @ ..,
        ] if command == "discover" && runtime.len() <= 1 => {
            let (runtime, evidence, reference_named, status_globals, eeprom_timers, source_sizes) =
                runtime_declarations(runtime.first())?;
            let rom = CanonicalRom::from_bytes(&fs::read(rom_path).map_err(|e| e.to_string())?)?;
            let range = GuestRange {
                start: GuestAddr(number32(start)?),
                size: number32(size)?,
            };
            let mut image = CodeImage::from_rom(&rom, RomOffset(number(offset)?), range.clone())?;
            let mut declared = load_declarations(
                loads_path.as_ref(),
                RomOffset(number(offset)?),
                range.clone(),
            )?;
            if let Some((spec, _)) = &declared {
                image = plaid_core::declared_loads::compose(rom.bytes(), spec)?.1;
            }
            // overlay tables are found in the image as composed so far
            let mut overlay_evidence = None;
            if overlays {
                let table: Vec<u8> = image.words.iter().flat_map(|w| w.to_be_bytes()).collect();
                let catalog = plaid_core::overlays::discover(rom.bytes(), &table)?;
                let detail = serde_json::to_vec(&catalog).map_err(|e| e.to_string())?;
                let id = format!("overlays:{}", plaid_core::rom::sha256(&detail));
                // a validated catalog file supersedes an inferred raw slot view
                // of part of its bytes, which names the wrong link (ADR-0258);
                // a slot in a validated format of its own stays (ADR-0262)
                if let Some((spec, _)) = &mut declared {
                    spec.loads.retain(|l| {
                        l.linked.is_none()
                            || l.encoding != plaid_core::declared_loads::LoadEncoding::Raw
                            || !catalog.iter().any(|o| {
                                (u64::from(o.file.rom_start)..u64::from(o.file.rom_end))
                                    .contains(&l.source.0)
                            })
                    });
                }
                // catalog slots go above RAM and every load declared so far
                let slot_base = declared
                    .iter()
                    .flat_map(|(spec, _)| &spec.loads)
                    .map(|l| l.destination.end())
                    .chain([0x8080_0000])
                    .max()
                    .map_or(Ok(0x8080_0000), u32::try_from)
                    .map_err(|e| e.to_string())?;
                // a file already declared is not declared again (ADR-0262)
                let declared_sources: BTreeSet<u64> = declared
                    .iter()
                    .flat_map(|(spec, _)| &spec.loads)
                    .map(|l| l.source.0)
                    .collect();
                let loads: Vec<_> =
                    plaid_core::overlays::loads(&catalog, &[id.clone()].into(), slot_base)
                        .into_iter()
                        .filter(|l| !declared_sources.contains(&l.source.0))
                        .collect();
                println!(
                    "{} of {} overlay candidates placed at their link addresses",
                    loads.len(),
                    catalog.len()
                );
                let spec = match &mut declared {
                    Some((spec, _)) => spec,
                    None => {
                        &mut declared
                            .insert((
                                plaid_core::declared_loads::LoadImage {
                                    base_offset: RomOffset(number(offset)?),
                                    base: range,
                                    loads: Vec::new(),
                                },
                                (id.clone(), overlay_evidence_of(&catalog)),
                            ))
                            .0
                    }
                };
                spec.loads.extend(loads);
                plaid_core::declared_loads::exclude_replayed_catalog_text(spec);
                spec.loads.sort();
                image = plaid_core::declared_loads::compose(rom.bytes(), spec)?.1;
                overlay_evidence = Some((id, overlay_evidence_of(&catalog)));
            }
            let source_context =
                discovery_load_context(declared.as_ref(), overlay_evidence.as_ref());
            let observed = observed_roots(loads_path.as_ref())?;
            let mut entries = vec![GuestAddr(number32(entry)?)];
            // Replayed RAM vectors are explicit guest entry sources. Seed them
            // before discovery so a vector reached only by hardware exceptions
            // retains its handler CFG and exact executable source identity.
            let vector_roots: BTreeSet<_> = declared
                .iter()
                .flat_map(|(spec, _)| &spec.loads)
                .filter_map(|load| match load.encoding {
                    plaid_core::declared_loads::LoadEncoding::AresBoot { entry }
                        if matches!(entry.0, 0x8000_0000 | 0x8000_0180)
                            && load.destination.contains(entry) =>
                    {
                        Some(entry)
                    }
                    _ => None,
                })
                .collect();
            entries.extend(vector_roots.iter().copied());
            let roots = if data_roots {
                plaid_core::data_roots::scan(rom.bytes(), &image)
            } else {
                Default::default()
            };
            entries.extend(roots.iter().copied());
            let mut d = if address_taken {
                plaid_core::data_roots::discover_address_taken_with_loads(
                    rom.identity.clone(),
                    rom.bytes(),
                    &image,
                    &entries,
                    &runtime,
                    evidence.clone(),
                    &load_starts(declared.as_ref()),
                    source_context.as_ref(),
                    &observed,
                    1_000_000,
                )?
            } else {
                discover_image_with_loads(
                    rom.identity.clone(),
                    &image,
                    &entries,
                    &runtime,
                    evidence.clone(),
                    source_context.as_ref(),
                    1_000_000,
                )?
            };
            // calls into a slot root each alternate's code there (ADR-0185)
            if declared.is_some() {
                loop {
                    let starts: BTreeSet<u32> = d.map.blocks.iter().map(|b| b.start.pc.0).collect();
                    let more: BTreeSet<GuestAddr> = d
                        .map
                        .direct_edges
                        .iter()
                        .filter(|e| {
                            e.kind == plaid_core::program::EdgeKind::Call
                                && !starts.contains(&e.target.pc.0)
                        })
                        .flat_map(|e| {
                            let t = e.target.pc.0;
                            image.slot_copies(t).into_iter().filter(move |&c| c != t)
                        })
                        .filter(|&t| {
                            !starts.contains(&t)
                                && !runtime.iter().any(|(entry, _, _)| entry.0 == t)
                                && plaid_core::data_roots::plausible_at(
                                    &image,
                                    GuestAddr(t),
                                    &starts,
                                )
                        })
                        .map(GuestAddr)
                        .collect();
                    if more.is_empty() {
                        break;
                    }
                    entries.extend(more);
                    d = if address_taken {
                        plaid_core::data_roots::discover_address_taken_with_loads(
                            rom.identity.clone(),
                            rom.bytes(),
                            &image,
                            &entries,
                            &runtime,
                            evidence.clone(),
                            &load_starts(declared.as_ref()),
                            source_context.as_ref(),
                            &observed,
                            1_000_000,
                        )?
                    } else {
                        discover_image_with_loads(
                            rom.identity.clone(),
                            &image,
                            &entries,
                            &runtime,
                            evidence.clone(),
                            source_context.as_ref(),
                            1_000_000,
                        )?
                    };
                }
            }
            // a second pass adds functions found only by layout (ADR-0152)
            let mut roots = roots;
            if data_roots {
                let layout = plaid_core::data_roots::layout(&image, &d.map);
                if !layout.is_empty() {
                    roots.extend(layout.iter().copied());
                    entries.extend(layout);
                    d = discover_image_with_loads(
                        rom.identity.clone(),
                        &image,
                        &entries,
                        &runtime,
                        evidence.clone(),
                        source_context.as_ref(),
                        1_000_000,
                    )?;
                }
            }
            if let Some((id, evidence)) = overlay_evidence {
                d.map.evidence.insert(id, evidence);
            }
            if let Some((spec, (id, evidence))) = declared {
                d.map.evidence.insert(id, evidence);
                d.map.load_images.insert(image.base.image.clone(), spec);
            }
            bind_status_globals(&mut d.map, &status_globals)?;
            bind_eeprom_timers(&mut d.map, &eeprom_timers);
            for (entry, function) in &mut d.map.runtime_functions {
                function.source_size = source_sizes.get(&entry.pc).copied();
            }
            // names only a reference map gives carry their own evidence, so the
            // solver can list them (ADR-0171)
            if let Some((id, evidence)) = &evidence
                && !reference_named.is_empty()
            {
                let map_id = format!("{id}:reference-map");
                d.map.evidence.insert(
                    map_id.clone(),
                    Evidence {
                        producer: plaid_core::signatures::REFERENCE_MAP_PRODUCER.into(),
                        detail: format!(
                            "named by a reference symbol map, not by ROM bytes; {}",
                            evidence.detail
                        ),
                        ..evidence.clone()
                    },
                );
                for f in d.map.runtime_functions.values_mut() {
                    if reference_named.contains(&f.name) {
                        f.evidence = [map_id.clone()].into();
                    }
                }
            }
            if !roots.is_empty() {
                let id = format!("data-roots:{}", rom.identity.sha256);
                d.map.evidence.insert(
                    id.clone(),
                    Evidence {
                        kind: EvidenceKind::Static,
                        producer: "plaid-data-pointer-roots/v0".into(),
                        revision: "0".into(),
                        detail: "aligned ROM words equal to a function start by layout (after jr ra); heuristic discovery roots (ADR-0152)".into(),
                    },
                );
                for root in &roots {
                    if let Some(refs) = d.map.entries.get_mut(&image.address(*root)) {
                        refs.insert(id.clone());
                    }
                }
            }
            d.map.cop1_fr0 = fr0;
            d.map.tlb_exception_vectors =
                vector_roots.iter().map(|pc| image.address(*pc)).collect();
            fs::write(output, d.map.to_json()?).map_err(|e| e.to_string())?;
            println!(
                "discovered {} blocks, {} indirect sites, {} unresolved items",
                d.map.blocks.len(),
                d.map.indirect_sites.len(),
                d.map.unresolved.len()
            );
        }
        [command, rom_path, map_path, output] if command == "rsp-from-rom" => {
            let rom = CanonicalRom::from_bytes(&fs::read(rom_path).map_err(|e| e.to_string())?)?;
            let map =
                ProgramMap::from_json(&fs::read_to_string(map_path).map_err(|e| e.to_string())?)?;
            if map.rom != rom.identity {
                return Err("map does not match canonical ROM".into());
            }
            let sources = rsp_sources(&rom, loads_path.as_ref())?;
            rsp_rom::generate(&rom, &map, rom_images(&rom, &map)?, sources, output)?;
        }
        [command, path, offset, size, imem, name, output, raw @ ..]
            if command == "lower-rsp" && (raw.is_empty() || raw == ["--raw"]) =>
        {
            // RSP microcode (ADR-0167): text bytes from a ROM (any byte order)
            // or, with --raw, from a big-endian file.
            let bytes = fs::read(path).map_err(|e| e.to_string())?;
            let bytes = if raw.is_empty() {
                CanonicalRom::from_bytes(&bytes)?.bytes().to_vec()
            } else {
                bytes
            };
            let (offset, size) = (number32(offset)? as usize, number32(size)? as usize);
            let text = bytes
                .get(offset..offset + size)
                .ok_or("microcode text is outside the file")?;
            let lowered = plaid_lower::rsp::lower_rsp(text, number32(imem)?, name)?;
            fs::write(output, lowered.c).map_err(|e| e.to_string())?;
            println!(
                "lowered {} RSP words, {} as fault stubs",
                size / 4,
                lowered.stubs.len()
            );
            for why in lowered.stubs.iter().take(8) {
                println!("  stub {why}");
            }
        }
        [command, rom_path, map_path, output] if command == "inspect-overlays" => {
            if let Ok(destination) = fs::canonicalize(output) {
                for input in [rom_path, map_path] {
                    if destination == fs::canonicalize(input).map_err(|e| e.to_string())? {
                        return Err("overlay output would overwrite an input".into());
                    }
                }
            }
            let rom = CanonicalRom::from_bytes(&fs::read(rom_path).map_err(|e| e.to_string())?)?;
            let map =
                ProgramMap::from_json(&fs::read_to_string(map_path).map_err(|e| e.to_string())?)?;
            if map.rom != rom.identity {
                return Err("map does not match canonical ROM".into());
            }
            let mut catalogs = Vec::new();
            for image in rom_images(&rom, &map)? {
                let bytes: Vec<_> = image.words.iter().flat_map(|w| w.to_be_bytes()).collect();
                let overlays = plaid_core::overlays::discover(rom.bytes(), &bytes)?;
                println!(
                    "{} overlay candidates in {}",
                    overlays.len(),
                    image.base.image
                );
                catalogs.push(serde_json::json!({"table_image":image.base,"overlays":overlays}));
            }
            let report = serde_json::json!({"format":"plaid-overlay-candidates-v0","rom":rom.identity,"images":catalogs});
            fs::write(
                output,
                serde_json::to_vec_pretty(&report).map_err(|e| e.to_string())?,
            )
            .map_err(|e| e.to_string())?;
        }
        [command, rom_path, map_path, entry, exit, output, rest @ ..]
            if command == "lower-map" && matches!(rest, [] | [_, _]) =>
        {
            // `--parts N` writes N translation units: `output` and, for N > 1,
            // `<stem>.part<k>.c` beside it (ADR-0174).
            let parts = match rest {
                [] => 1,
                [flag, n] if flag == "--parts" => n
                    .parse::<usize>()
                    .ok()
                    .filter(|n| (1..=256).contains(n))
                    .ok_or("--parts takes 1..=256")?,
                _ => return Err("lower-map takes only --parts N".into()),
            };
            // A discovered ROM map (ADR-0157): its images are rebuilt from the
            // ROM as `solve` does, and the host preloads the base window.
            let rom = CanonicalRom::from_bytes(&fs::read(rom_path).map_err(|e| e.to_string())?)?;
            let map =
                ProgramMap::from_json(&fs::read_to_string(map_path).map_err(|e| e.to_string())?)?;
            if map.rom != rom.identity {
                return Err("map does not match canonical ROM".into());
            }
            let images = rom_images(&rom, &map)?;
            let [image] = images.as_slice() else {
                return Err("lower-map lowers exactly one code image".into());
            };
            let preload = match map.load_images.get(&image.base.image) {
                Some(spec) => CodeImage::from_rom(&rom, spec.base_offset, spec.base.clone())?,
                None => image.clone(),
            };
            let units = plaid_lower::lower_c_parts(
                &map,
                &images,
                &preload,
                GuestAddr(number32(entry)?),
                &[GuestAddr(number32(exit)?)],
                parts,
                residual_dispatch,
            )?;
            let stem = output.strip_suffix(".c").unwrap_or(output);
            for (k, c) in units.iter().enumerate() {
                let path = if k == 0 {
                    output.clone()
                } else {
                    format!("{stem}.part{k}.c")
                };
                fs::write(path, c).map_err(|e| e.to_string())?;
            }
            println!("lowered {} blocks", map.blocks.len());
        }
        [command, image_path, base, entry, exit, output, runtime @ ..]
            if command == "lower-c" && runtime.len() <= 1 =>
        {
            let (runtime, evidence, _, status_globals, eeprom_timers, source_sizes) =
                runtime_declarations(runtime.first())?;
            // Synthetic-only native slice (ADR-0126): raw big-endian words at `base`.
            let bytes = fs::read(image_path).map_err(|e| e.to_string())?;
            let image = CodeImage {
                base: plaid_core::program::CodeAddress {
                    pc: GuestAddr(number32(base)?),
                    image: plaid_core::rom::sha256(&bytes),
                    generation: 0,
                },
                words: bytes
                    .as_chunks::<4>()
                    .0
                    .iter()
                    .map(|w| u32::from_be_bytes(*w))
                    .collect(),
                rom_offset: None,
                physical_start: None,
                holes: Vec::new(),
                slots: Vec::new(),
            };
            let rom = plaid_core::program::RomIdentity {
                sha256: image.base.image.clone(),
                size: bytes.len() as u64,
            };
            let range = GuestRange {
                start: image.base.pc,
                size: image.size()?,
            };
            let declared = load_declarations(loads_path.as_ref(), RomOffset(0), range)?;
            let code = match &declared {
                Some((spec, _)) => plaid_core::declared_loads::compose(&bytes, spec)?.1,
                None => image.clone(),
            };
            let source_context = discovery_load_context(declared.as_ref(), None);
            let observed = observed_roots(loads_path.as_ref())?;
            let mut d = if address_taken {
                plaid_core::data_roots::discover_address_taken_with_loads(
                    rom,
                    &bytes,
                    &code,
                    &[GuestAddr(number32(entry)?)],
                    &runtime,
                    evidence,
                    &load_starts(declared.as_ref()),
                    source_context.as_ref(),
                    &observed,
                    1_000_000,
                )?
            } else {
                discover_image_with_loads(
                    rom,
                    &code,
                    &[GuestAddr(number32(entry)?)],
                    &runtime,
                    evidence,
                    source_context.as_ref(),
                    1_000_000,
                )?
            };
            if let Some((spec, (id, evidence))) = declared {
                d.map.evidence.insert(id, evidence);
                d.map.load_images.insert(code.base.image.clone(), spec);
            }
            bind_status_globals(&mut d.map, &status_globals)?;
            bind_eeprom_timers(&mut d.map, &eeprom_timers);
            for (entry, function) in &mut d.map.runtime_functions {
                function.source_size = source_sizes.get(&entry.pc).copied();
            }
            d.map.cop1_fr0 = fr0;
            let c = plaid_lower::lower_c_with_preload(
                &d.map,
                std::slice::from_ref(&code),
                &image,
                GuestAddr(number32(entry)?),
                &[GuestAddr(number32(exit)?)],
                residual_dispatch,
            )?;
            fs::write(output, c).map_err(|e| e.to_string())?;
            println!("lowered {} blocks", d.map.blocks.len());
        }
        [command, rom_path, offset, start, size, signatures] if command == "identify" => {
            let rom = CanonicalRom::from_bytes(&fs::read(rom_path).map_err(|e| e.to_string())?)?;
            let range = GuestRange {
                start: GuestAddr(number32(start)?),
                size: number32(size)?,
            };
            let mut image = CodeImage::from_rom(&rom, RomOffset(number(offset)?), range.clone())?;
            if let Some((spec, _)) =
                load_declarations(loads_path.as_ref(), RomOffset(number(offset)?), range)?
            {
                image = plaid_core::declared_loads::compose(rom.bytes(), &spec)?.1;
            }
            let text = fs::read(signatures).map_err(|e| e.to_string())?;
            let wanted = plaid_core::signatures::RUNTIME_FUNCTIONS;
            let (mut found, mut source, mut map_only) = if symbols {
                let symbols = plaid_core::recall::parse_symbols(&String::from_utf8_lossy(&text));
                let found = plaid_core::signatures::from_symbols(&image, &symbols, wanted);
                let names = found.matches.iter().map(|m| m.name.clone()).collect();
                (
                    found,
                    format!(
                        "reference symbol map (ADR-0148), symbols sha256 {}",
                        plaid_core::rom::sha256(&text)
                    ),
                    names,
                )
            } else {
                let sigs = plaid_core::signatures::parse(&String::from_utf8_lossy(&text))?;
                (
                    plaid_core::signatures::identify(&image, &sigs, wanted),
                    format!(
                        "n64sym signatures and exact SDK-body profiles (ADR-0133, ADR-0171, ADR-0202), signatures sha256 {}",
                        plaid_core::rom::sha256(&text)
                    ),
                    BTreeSet::new(),
                )
            };
            if let Some(path) = &reference_map {
                let map = fs::read(path).map_err(|e| e.to_string())?;
                let symbols = plaid_core::recall::parse_symbols(&String::from_utf8_lossy(&map));
                (found, map_only) = plaid_core::signatures::with_reference_map(
                    found,
                    plaid_core::signatures::from_symbols(&image, &symbols, wanted),
                );
                source += &format!(
                    ", completed from a reference symbol map sha256 {}",
                    plaid_core::rom::sha256(&map)
                );
            }
            let functions: Vec<_> = found
                .matches
                .iter()
                .map(|m| {
                    let callbacks: Vec<_> = plaid_core::signatures::callback_registers(&m.name)
                        .iter()
                        .map(|r| format!("a{}", r - 4))
                        .collect();
                    let mut function = serde_json::json!({
                        "entry": format!("{:#010x}", m.entry.0),
                        "name": m.name,
                        "size": (m.size > 0).then_some(m.size),
                        "callbacks": callbacks,
                        "evidence": if map_only.contains(&m.name) { "reference map" } else { "signature" },
                    });
                    if let Some(data) = found.data_bindings.get(&m.entry) {
                        function["data_bindings"] = serde_json::json!(data.iter()
                            .map(|(name, address)| (name, format!("{:#010x}", address.0)))
                            .collect::<std::collections::BTreeMap<_, _>>());
                    }
                    if let Some(global) = found.status_globals.get(&m.entry) {
                        function["status_global"] = serde_json::json!(format!("{:#010x}", global.0));
                    }
                    function
                })
                .collect();
            println!(
                "{}",
                serde_json::to_string_pretty(&serde_json::json!({
                    "format": "plaid-runtime-functions-v0",
                    "source": format!("{source}, rom sha256 {}", rom.identity.sha256),
                    "functions": functions,
                    "ambiguous": found.ambiguous,
                }))
                .map_err(|e| e.to_string())?
            );
        }
        [command] if command == "isa-coverage" => {
            let coverage = plaid_lower::coverage::isa_coverage();
            let lowered = coverage.values().filter(|l| **l).count();
            println!(
                "{}",
                serde_json::to_string_pretty(&serde_json::json!({
                    "format": "plaid-isa-coverage-v0",
                    "lowered": lowered,
                    "decoded": coverage.len(),
                    "mnemonics": coverage,
                }))
                .map_err(|e| e.to_string())?
            );
        }
        [command] if command == "rsp-coverage" => {
            let coverage = plaid_lower::coverage::rsp_coverage();
            let lowered = coverage.values().filter(|(_, l)| *l).count();
            println!(
                "{}",
                serde_json::to_string_pretty(&serde_json::json!({
                    "format": "plaid-rsp-coverage-v0",
                    "lowered": lowered,
                    "documented": coverage.len(),
                    "mnemonics": coverage
                        .iter()
                        .map(|(name, (group, l))| (name.clone(), serde_json::json!({"group": group, "lowered": l})))
                        .collect::<serde_json::Map<_, _>>(),
                }))
                .map_err(|e| e.to_string())?
            );
        }
        [command, path] if command == "rom-info" => {
            let rom = CanonicalRom::from_bytes(&fs::read(path).map_err(|e| e.to_string())?)?;
            println!(
                "{}",
                serde_json::to_string_pretty(&serde_json::json!({
                    "source_order": rom.source_order, "identity": rom.identity, "header": rom.header,
                    "boot_image_size": rom.boot_image_size()
                }))
                .map_err(|e| e.to_string())?
            );
        }
        [command, rom, map, loads] if command == "infer-call-loads" => {
            infer_calls::refine(rom, map, loads)?;
        }
        // Fixed loads inferred from the IPL3 window (ADR-0183), written as
        // ordinary declarations so the evidence stays inspectable.
        [command, path, output] if command == "infer-loads" => {
            let rom = CanonicalRom::from_bytes(&fs::read(path).map_err(|e| e.to_string())?)?;
            let bytes = rom.bytes();
            // the main image when the entry stub bounds it, else IPL3's 1 MiB
            let size = rom.boot_image_size().unwrap_or(0x10_0000) as usize;
            let end = bytes.len().min(0x1000 + size);
            let base = bytes
                .get(0x1000..end)
                .ok_or("ROM ends before its boot window")?;
            let mut found =
                plaid_core::overlays::static_loads(bytes, base, rom.header.boot_address.0)?;
            // a fixed load of bytes inside a bounded main image would overwrite
            // that image with itself elsewhere; slots and in-place copies stay
            // (ADR-0258)
            if rom.boot_image_size().is_some() {
                let boot = rom.header.boot_address.0;
                found.retain(|l| {
                    l.alternate
                        || l.file.rom_start as usize >= end
                        || l.destination.wrapping_sub(boot) == l.file.rom_start.wrapping_sub(0x1000)
                });
            }
            let paired = plaid_core::paired_streams::infer(bytes, base);
            let segments = plaid_core::segments::infer(
                bytes,
                base,
                rom.header.boot_address,
                RomOffset(0x1000),
            );
            let stub = plaid_core::overlays::reset_stub(bytes, base.len() as u32);
            let mut loads: Vec<_> = stub
                .map(|size| {
                    serde_json::json!({
                        "destination": format!("{:#x}", rom.header.boot_address.0),
                        "size": format!("{size:#x}"),
                        "rom": "0x1000",
                        "encoding": "raw",
                    })
                })
                .into_iter()
                .chain(found.iter().map(|l| {
                    let mut load = serde_json::json!({
                        "destination": format!("{:#x}", l.destination),
                        "size": format!("{:#x}", l.size),
                        "rom": format!("{:#x}", l.file.rom_start),
                        "encoding": if l.file.rom_end == 0 { "raw" } else { "yaz0" },
                    });
                    // one of a slot's files: placed apart and bound by content (ADR-0185)
                    if l.alternate {
                        load["slot"] = true.into();
                    }
                    load
                }))
                .collect();
            for file in &paired {
                loads.push(serde_json::json!({
                    "destination": format!("{:#x}", file.destination),
                    "size": format!("{:#x}", file.text + file.data),
                    "rom": format!("{:#x}", file.source),
                    "rom_end": format!("{:#x}", file.end),
                    "text_size": format!("{:#x}", file.text),
                    "encoding": "rare_pair", "slot": true,
                }));
            }
            for file in &segments {
                loads.push(serde_json::json!({
                    "destination": format!("{:#x}", file.linked.0),
                    "size": format!("{:#x}", file.end - file.source),
                    "rom": format!("{:#x}", file.source),
                    "descriptor": format!("{:#x}", file.descriptor.0),
                    "text_size": format!("{:#x}", file.text),
                    "encoding": "segment", "slot": true,
                }));
            }
            let descriptors = plaid_core::descriptor_loads::infer(bytes, base);
            for d in &descriptors {
                loads.push(serde_json::json!({
                    "destination": format!("{:#x}", d.destination),
                    "size": format!("{:#x}", d.size),
                    "rom": format!("{:#x}", d.source),
                    "encoding": "raw", "slot": true,
                }));
            }
            let mut evidence: Vec<_> = stub
                .map(|size| format!("reset stub of {size:#x} bytes before the first file in the boot window"))
                .into_iter()
                .chain(found
                .iter()
                .map(|l| {
                    format!(
                        "file {:#x} named at {:#x}, placed at {:#x} built at {:#x}, {}/{} calls begin functions",
                        l.file.virtual_start,
                        l.file_constant_at,
                        l.destination,
                        l.destination_constant_at,
                        l.calls.1,
                        l.calls.0
                    )
                }))
                .collect();
            for file in &paired {
                evidence.push(format!("1172 paired-stream catalog {:#x} index {}; metadata container {:#x}+{:#x}; text/data {:#x}/{:#x}, BSS {:#x}; decoded SHA256 {}",
                    file.source_table, file.index, file.metadata_source, file.metadata_offset,
                    file.text, file.data, file.bss, file.sha256));
            }
            for file in &segments {
                evidence.push(format!(
                    "named section descriptor {:#x}: ROM {:#x}..{:#x}, linked {:#x}, text {:#x}, BSS {:#x}",
                    file.descriptor.0, file.source, file.end, file.linked.0, file.text, file.bss
                ));
            }
            for d in &descriptors {
                evidence.push(format!(
                    "code-built PI descriptor at image offset {:#x}: ROM {:#x}+{:#x}, RAM {:#x}, checked end {:#x}",
                    d.built_at, d.source, d.size, d.destination, d.destination + d.size
                ));
            }
            match plaid_core::boot_execution::execute(&rom) {
                Ok(capture) => {
                    let lo = u64::from(capture.destination.start.0);
                    let hi = capture.destination.end();
                    let overlaps = loads.iter().any(|l| {
                        let start = l["destination"].as_str().and_then(|v| number(v).ok());
                        let size = l["size"].as_str().and_then(|v| number(v).ok());
                        start.zip(size).is_some_and(|(s, n)| s < hi && lo < s + n)
                    });
                    if !overlaps {
                        loads.push(serde_json::json!({
                            "destination": format!("{lo:#x}"),
                            "size": format!("{:#x}", capture.destination.size),
                            "rom": "0x0", "encoding": "boot",
                        }));
                        evidence.push(format!(
                            "ROM-only boot execution/v1: ROM sha256 {}; entry {:08x}; {} instructions; consumed ROM ranges {:?}; output sha256 {}; replayed during composition, content-guarded at native entry",
                            rom.identity.sha256, capture.entry.0, capture.steps,
                            capture.consumed, plaid_core::rom::sha256(&capture.bytes)
                        ));
                    }
                }
                Err(stop) => println!(
                    "boot execution stopped at {:08x} after {} instructions: {}",
                    stop.pc.0, stop.steps, stop.reason
                ),
            }
            let doc = serde_json::json!({
                "format": "plaid-loads-v0",
                "source": format!("inferred from the boot window (ADR-0183): {}", evidence.join("; ")),
                "loads": loads,
            });
            fs::write(
                output,
                serde_json::to_string_pretty(&doc).map_err(|e| e.to_string())? + "\n",
            )
            .map_err(|e| e.to_string())?;
            println!("{} inferred loads -> {output}", loads.len());
            for e in evidence {
                println!("  {e}");
            }
        }
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
        // Discovery recall against a local reference symbol map (ADR-0144).
        [command, path, symbols, range @ ..]
            if command == "recall" && matches!(range.len(), 0 | 2) =>
        {
            let map = ProgramMap::from_json(&fs::read_to_string(path).map_err(|e| e.to_string())?)?;
            let text = fs::read(symbols).map_err(|e| e.to_string())?;
            let reference = plaid_core::recall::parse_symbols(&String::from_utf8_lossy(&text));
            if reference.is_empty() {
                return Err("reference map has no code symbols".into());
            }
            let (start, end) = match range {
                [start, end] => (number32(start)?, number32(end)?),
                _ => (0, u32::MAX),
            };
            let report = plaid_core::recall::score(&map, &reference, start, end);
            println!(
                "{}",
                serde_json::to_string_pretty(&report).map_err(|e| e.to_string())?
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
        _ => {
            return Err(
                "usage: plaid inspect-sp-pi-fetch-lineage <rom> <firmware> <fetch.ndjson> <history-v3.ndjson> <expected-history-sha256> <expected-fetch-sha256> <report.json> | verify-sp-pi-fetch-lineage <same-inputs> | inspect-dcache-store64 <history-v2.json> <expected-source-sha256> <report.json> | verify-dcache-store64 <same-inputs> | compose-cop1-mutations <history.json> <expected-source-sha256> <contexts.json> <expected-contexts-sha256> <report.json> | verify-cop1-mutations <same-inputs> | inspect-dcache-resident-reads <history-v1.json> <expected-source-sha256> <report.json> | verify-dcache-resident-reads <same-inputs> | inspect-rsp-cpu-imem <history.json> <expected-source-sha256> <report.json> | verify-rsp-cpu-imem <same-inputs> | inspect-sp-writer-fetch <rom> <firmware> <fetch.ndjson> <history-v3.ndjson> <expected-history-sha256> <expected-fetch-sha256> <report.json> | verify-sp-writer-fetch <same-inputs> | create-trace-expectations <new-expected.json> <trace.ndjson>... | solve-traces <rom> <map.json> <expected.json> <trace.ndjson>... | inspect-cpu-definitions <history.json> <external-source-sha256> <report.json> | verify-cpu-definitions <history.json> <external-source-sha256> <report.json> | inspect-cpu-copy-history <history.json> <external-source-sha256> <report.json> | verify-cpu-copy-history <history.json> <external-source-sha256> <report.json> | isa-coverage | rsp-coverage | identify <rom> <rom-offset> <guest-start> <size> <signatures.sig | reference.map --symbols> | rom-info <rom> | infer-loads <rom> <loads.json> | infer-call-loads <rom> <map.json> <loads.json> | recall <map.json> <reference.map> [start end] | check-trace <trace.ndjson> | check-map <map.json> | solve [rom] <map.json> [--guarded-ram | --address-taken] | discover <rom> <rom-offset> <guest-start> <size> <entry> <output.json> [runtime.json] [--data-roots | --address-taken] [--fr0] | import-trace <rom> <trace.ndjson> <output.json> | import-fetch <rom> <fetch.ndjson> <output.json> | verify-fetch <rom> <fetch.ndjson> <map.json> | import-boot-fetch <rom> <firmware> <fetch.ndjson> <output.json> | verify-boot-fetch <rom> <firmware> <fetch.ndjson> <map.json> | inspect-boot-history <rom> <firmware> <fetch.ndjson> <history.ndjson> <report.json> | verify-boot-history <rom> <firmware> <fetch.ndjson> <history.ndjson> <report.json> | inspect-pi-boot-history <rom> <firmware> <fetch.ndjson> <history-v1.ndjson> <report.json> | verify-pi-boot-history <rom> <firmware> <fetch.ndjson> <history-v1.ndjson> <report.json> | inspect-pi-queue-boot-history <rom> <firmware> <fetch.ndjson> <history-v2.ndjson> <report.json> | verify-pi-queue-boot-history <rom> <firmware> <fetch.ndjson> <history-v2.ndjson> <report.json> | inspect-pi-fetch-lineage <rom> <firmware> <fetch.ndjson> <history-v2.ndjson> <report.json> | verify-pi-fetch-lineage <rom> <firmware> <fetch.ndjson> <history-v2.ndjson> <report.json> | inspect-sp-boot-history <rom> <firmware> <fetch.ndjson> <history-v3.ndjson> <report.json> | verify-sp-boot-history <rom> <firmware> <fetch.ndjson> <history-v3.ndjson> <report.json> | inspect-pif-boot-history <rom> <firmware> <fetch.ndjson> <history-v4.ndjson> <report.json> | verify-pif-boot-history <rom> <firmware> <fetch.ndjson> <history-v4.ndjson> <report.json> | merge <left.json> <right.json> <output.json> | lower-c <words.bin> <base> <entry> <exit> <out.c> [runtime.json] [--address-taken] [--fr0] | lower-map <rom> <map.json> <entry> <exit> <out.c> | rsp-from-rom <rom> <map.json> <output-dir> | lower-rsp <rom> <offset> <size> <imem> <name> <out.c> [--raw] (discover, lower-c and identify also take --loads <loads.json>)"
                    .into(),
            );
        }
    }
    Ok(())
}

fn number(value: &str) -> Result<u64, String> {
    if let Some(hex) = value.strip_prefix("0x") {
        u64::from_str_radix(hex, 16)
    } else {
        value.parse()
    }
    .map_err(|e| e.to_string())
}
fn number32(value: &str) -> Result<u32, String> {
    u32::try_from(number(value)?).map_err(|e| e.to_string())
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

/// Declared functions, their evidence, and the names a reference symbol map
/// alone gives (ADR-0171).
type RuntimeDeclarations = (
    Vec<(GuestAddr, String, Vec<u8>)>,
    Option<(String, Evidence)>,
    BTreeSet<String>,
    BTreeMap<GuestAddr, GuestAddr>,
    BTreeMap<GuestAddr, (GuestAddr, GuestAddr)>,
    BTreeMap<GuestAddr, u32>,
);

/// Read a `plaid-runtime-functions-v0` declaration (ADR-0129): host-provided
/// guest functions that discovery records as call targets but never decodes.
type LoadDeclarations = Option<(plaid_core::declared_loads::LoadImage, (String, Evidence))>;

/// Parse `plaid-loads-v0`: loads applied over the base window (ADR-0136).
fn discovery_load_context(
    declared: Option<&(plaid_core::declared_loads::LoadImage, (String, Evidence))>,
    extra: Option<&(String, Evidence)>,
) -> Option<plaid_core::pipeline::LoadContext> {
    let (spec, (id, evidence)) = declared?;
    let mut sources = BTreeMap::from([(id.clone(), evidence.clone())]);
    if let Some((id, evidence)) = extra {
        sources.insert(id.clone(), evidence.clone());
    }
    Some((spec.clone(), sources))
}

fn load_declarations(
    path: Option<&String>,
    base_offset: RomOffset,
    base: GuestRange,
) -> Result<LoadDeclarations, String> {
    use plaid_core::declared_loads::{DeclaredLoad, LoadEncoding, LoadImage, OverlayCompression};
    let Some(path) = path else {
        return Ok(None);
    };
    let bytes = fs::read(path).map_err(|e| e.to_string())?;
    let doc: serde_json::Value = serde_json::from_slice(&bytes).map_err(|e| e.to_string())?;
    if doc["format"] != "plaid-loads-v0" {
        return Err("load declarations need format plaid-loads-v0".into());
    }
    let source = doc["source"]
        .as_str()
        .ok_or("load declarations need a source string")?;
    let id = format!("loads:{}", plaid_core::rom::sha256(&bytes));
    let mut loads = Vec::new();
    for l in doc["loads"]
        .as_array()
        .ok_or("load declarations need a loads array")?
    {
        let field = |name: &str| -> Result<u64, String> {
            number(
                l[name]
                    .as_str()
                    .ok_or(format!("each load needs a {name} string"))?,
            )
        };
        let encoding = match l["encoding"].as_str() {
            Some("raw") => LoadEncoding::Raw,
            Some("tlb_raw") => LoadEncoding::TlbRaw {
                text_size: u32::try_from(field("text_size")?).map_err(|e| e.to_string())?,
            },
            Some("ares_tlb") => LoadEncoding::AresTlb {
                entry: GuestAddr(u32::try_from(field("entry")?).map_err(|e| e.to_string())?),
                physical: u32::try_from(field("physical")?).map_err(|e| e.to_string())?,
                text_size: u32::try_from(field("text_size")?).map_err(|e| e.to_string())?,
            },
            Some("yaz0") => LoadEncoding::Yaz0,
            Some("catalog_overlay") => LoadEncoding::CatalogOverlay {
                encoding: match l["compression"].as_str() {
                    Some("raw") => OverlayCompression::Raw,
                    Some("mio0") => OverlayCompression::Mio0,
                    _ => return Err("catalog overlay compression is raw or mio0".into()),
                },
                encoded_size: u32::try_from(field("encoded_size")?).map_err(|e| e.to_string())?,
                text_size: u32::try_from(field("text_size")?).map_err(|e| e.to_string())?,
                bss_size: u32::try_from(field("bss_size")?).map_err(|e| e.to_string())?,
            },
            Some("rare_pair") => LoadEncoding::RarePair {
                end: RomOffset(field("rom_end")?),
                text_size: u32::try_from(field("text_size")?).map_err(|e| e.to_string())?,
            },
            Some("segment") => LoadEncoding::Segment {
                descriptor: RomOffset(field("descriptor")?),
                text_size: u32::try_from(field("text_size")?).map_err(|e| e.to_string())?,
            },
            Some("boot") => LoadEncoding::Boot,
            Some("ares_boot") => LoadEncoding::AresBoot {
                entry: GuestAddr(u32::try_from(field("entry")?).map_err(|e| e.to_string())?),
            },
            Some("ares_data") => LoadEncoding::AresData {
                entry: GuestAddr(u32::try_from(field("entry")?).map_err(|e| e.to_string())?),
                physical: u32::try_from(field("physical")?).map_err(|e| e.to_string())?,
            },
            _ => {
                return Err(
                    "load encoding is raw, tlb_raw, ares_tlb, yaz0, catalog_overlay, rare_pair, segment, boot, ares_boot or ares_data"
                        .into(),
                );
            }
        };
        loads.push(DeclaredLoad {
            destination: GuestRange {
                start: GuestAddr(u32::try_from(field("destination")?).map_err(|e| e.to_string())?),
                size: u32::try_from(field("size")?).map_err(|e| e.to_string())?,
            },
            source: RomOffset(field("rom")?),
            encoding,
            evidence: [id.clone()].into(),
            // placed at its link address; runs only through a binding (ADR-0181)
            relocatable: l["relocatable"].as_bool().unwrap_or(false),
            linked: None,
        });
        // a slot's file is placed apart, above RAM, after the loads before it
        if l["slot"].as_bool() == Some(true)
            && let Some(load) = loads.last_mut()
        {
            load.linked = Some(load.destination.start);
            load.relocatable = true;
        }
    }
    // slot files go above every other load and RAM, each at its link address
    // modulo 64 KiB, so moving it changes only the high half of a HI16/LO16 pair
    let mut next = loads
        .iter()
        .filter(|l| l.linked.is_none())
        .map(|l| l.destination.end())
        .chain([0x8080_0000])
        .max()
        .unwrap_or(0x8080_0000);
    for load in loads.iter_mut().filter(|l| l.linked.is_some()) {
        let link = u64::from(load.linked.map_or(0, |a| a.0));
        next += (link.wrapping_sub(next)) & 0xffff;
        load.destination.start = GuestAddr(u32::try_from(next).map_err(|e| e.to_string())?);
        next += u64::from(load.destination.size);
    }
    loads.sort();
    let evidence = Evidence {
        kind: EvidenceKind::Static,
        producer: "plaid-load-declaration/v0".into(),
        revision: "0".into(),
        detail: format!("{source}; declaration sha256 {}", &id[6..]),
    };
    Ok(Some((
        LoadImage {
            base_offset,
            base,
            loads,
        },
        (id, evidence),
    )))
}

/// Targets that unproven indirect transfers took in the analysis-time pinned
/// ares replay, from a loads file's `observed_roots` (ADR-0222). They root
/// address-taken discovery and never certify a transfer.
fn observed_roots(path: Option<&String>) -> Result<BTreeSet<GuestAddr>, String> {
    let Some(path) = path else {
        return Ok(BTreeSet::new());
    };
    let doc: serde_json::Value =
        serde_json::from_slice(&fs::read(path).map_err(|e| e.to_string())?)
            .map_err(|e| e.to_string())?;
    let Some(rows) = doc.get("observed_roots") else {
        return Ok(BTreeSet::new());
    };
    rows.as_array()
        .ok_or("observed_roots must be an array")?
        .iter()
        .map(|row| {
            let field = |name: &str| {
                row[name]
                    .as_str()
                    .ok_or(format!("each observed root needs a {name} string"))
                    .and_then(number32)
            };
            field("site")?;
            Ok(GuestAddr(field("target")?))
        })
        .collect()
}

/// RAM ranges filled by PI DMA from the ROM in the analysis-time replay, from a
/// loads file's `rsp_sources` (ADR-0225): RSP search inputs only.
fn rsp_sources(rom: &CanonicalRom, path: Option<&String>) -> Result<Vec<CodeImage>, String> {
    let Some(path) = path else {
        return Ok(Vec::new());
    };
    let doc: serde_json::Value =
        serde_json::from_slice(&fs::read(path).map_err(|e| e.to_string())?)
            .map_err(|e| e.to_string())?;
    let Some(rows) = doc.get("rsp_sources") else {
        return Ok(Vec::new());
    };
    let mut out = Vec::new();
    for row in rows.as_array().ok_or("rsp_sources must be an array")? {
        let field = |name: &str| -> Result<u32, String> {
            row[name]
                .as_str()
                .ok_or(format!("each RSP source needs a {name} string"))
                .and_then(number32)
        };
        let (destination, size, source) = (field("destination")?, field("size")?, field("rom")?);
        if !(0x8000_0000..0x8080_0000).contains(&destination)
            || destination % 8 != 0
            || size == 0
            || size % 4 != 0
            || size > 0x8080_0000 - destination
        {
            return Err("an RSP source must be a nonempty aligned RDRAM range in KSEG0".into());
        }
        let range = GuestRange {
            start: GuestAddr(destination),
            size,
        };
        out.push(CodeImage::from_rom(
            rom,
            RomOffset(u64::from(source)),
            range,
        )?);
    }
    Ok(out)
}

/// Evidence for loads placed from the ROM's own overlay catalog.
/// Where each declared load begins (ADR-0182).
fn load_starts<E>(declared: Option<&(plaid_core::declared_loads::LoadImage, E)>) -> BTreeSet<u32> {
    declared
        .into_iter()
        .flat_map(|(spec, _)| spec.loads.iter().map(|l| l.destination.start.0))
        .collect()
}

fn overlay_evidence_of(catalog: &[plaid_core::overlays::Overlay]) -> Evidence {
    Evidence {
        kind: EvidenceKind::Static,
        producer: "plaid-overlay-catalog/v0".into(),
        revision: "0".into(),
        detail: format!(
            "{} relocatable overlays from the ROM's file table and overlay tuples (ADR-0172), placed at link addresses (ADR-0179)",
            catalog.len()
        ),
    }
}

fn runtime_declarations(path: Option<&String>) -> Result<RuntimeDeclarations, String> {
    let Some(path) = path else {
        return Ok((
            Vec::new(),
            None,
            BTreeSet::new(),
            BTreeMap::new(),
            BTreeMap::new(),
            BTreeMap::new(),
        ));
    };
    let bytes = fs::read(path).map_err(|e| e.to_string())?;
    let doc: serde_json::Value = serde_json::from_slice(&bytes).map_err(|e| e.to_string())?;
    if doc["format"] != "plaid-runtime-functions-v0" {
        return Err("runtime declarations need format plaid-runtime-functions-v0".into());
    }
    let source = doc["source"]
        .as_str()
        .ok_or("runtime declarations need a source string")?;
    let mut functions = Vec::new();
    let mut reference_named = BTreeSet::new();
    let mut status_globals = BTreeMap::new();
    let mut eeprom_timers = BTreeMap::new();
    let mut source_sizes = BTreeMap::new();
    for f in doc["functions"]
        .as_array()
        .ok_or("runtime declarations need a functions array")?
    {
        let (Some(entry), Some(name)) = (f["entry"].as_str(), f["name"].as_str()) else {
            return Err("each runtime function needs entry and name strings".into());
        };
        let mut callbacks = Vec::new();
        if let Some(size) = f.get("size").filter(|size| !size.is_null()) {
            let size = size
                .as_u64()
                .and_then(|n| u32::try_from(n).ok())
                .ok_or("runtime size must be a u32 integer")?;
            let entry = GuestAddr(number32(entry)?);
            if size == 0 || size % 4 != 0 || entry.0.checked_add(size).is_none() {
                return Err("invalid runtime source extent".into());
            }
            source_sizes.insert(entry, size);
        }
        if let Some(global) = f.get("status_global") {
            if !matches!(name, "osCreateThread" | "osSetIntMask" | "osInitialize") {
                return Err("Status global binding on an unsupported runtime ABI".into());
            }
            let global = number32(
                global
                    .as_str()
                    .ok_or("Status global must be an address string")?,
            )?;
            if global & 3 != 0 || global & 0x1fff_ffff >= 0x800000 || !matches!(global >> 29, 4 | 5)
            {
                return Err("Status global must be aligned direct-mapped guest RAM".into());
            }
            let entry = GuestAddr(number32(entry)?);
            if status_globals.insert(entry, GuestAddr(global)).is_some() {
                return Err("duplicate Status global declaration".into());
            }
        }
        if name == "osContInit"
            && let (Some(queue), Some(message)) = (
                f["data_bindings"]["__osEepromTimerQ"].as_str(),
                f["data_bindings"]["__osEepromTimerMsg"].as_str(),
            )
        {
            eeprom_timers.insert(
                GuestAddr(number32(entry)?),
                (GuestAddr(number32(queue)?), GuestAddr(number32(message)?)),
            );
        }
        for r in f["callbacks"].as_array().into_iter().flatten() {
            let register = match r.as_str() {
                Some("a0") => 4,
                Some("a1") => 5,
                Some("a2") => 6,
                Some("a3") => 7,
                _ => return Err("runtime callbacks are argument registers a0-a3".into()),
            };
            callbacks.push(register);
        }
        // files from `identify --symbols` predate the per-function field
        match f["evidence"].as_str() {
            Some("reference map") => {
                reference_named.insert(name.to_string());
            }
            None if source.starts_with("reference symbol map") => {
                reference_named.insert(name.to_string());
            }
            Some("signature") | None => {}
            Some(_) => return Err("runtime evidence is signature or reference map".into()),
        }
        functions.push((GuestAddr(number32(entry)?), name.to_string(), callbacks));
    }
    let hash = plaid_core::rom::sha256(&bytes);
    let evidence = Evidence {
        kind: EvidenceKind::Signature,
        producer: "plaid-runtime-declaration/v0".into(),
        revision: "0".into(),
        detail: format!("{source}; declaration sha256 {hash}"),
    };
    Ok((
        functions,
        Some((format!("runtime:{hash}"), evidence)),
        reference_named,
        status_globals,
        eeprom_timers,
        source_sizes,
    ))
}

/// The queue libultra's osContInit creates (ADR-0196).
fn bind_eeprom_timers(map: &mut ProgramMap, timers: &BTreeMap<GuestAddr, (GuestAddr, GuestAddr)>) {
    for (address, function) in &mut map.runtime_functions {
        function.eeprom_timer = timers.get(&address.pc).copied();
    }
}

fn bind_status_globals(
    map: &mut ProgramMap,
    globals: &BTreeMap<GuestAddr, GuestAddr>,
) -> Result<(), String> {
    for (address, function) in &mut map.runtime_functions {
        if let Some(global) = globals.get(&address.pc) {
            function.status_global = Some(*global);
        }
    }
    Ok(())
}
