use plaid_core::{
    GuestAddr,
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
    pipeline::discover_image,
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
    Ok(images)
}

fn run() -> Result<(), String> {
    let args: Vec<_> = env::args().skip(1).collect();
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
                _ => return Err("solve accepts only --guarded-ram".into()),
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
        [command, rom_path, offset, start, size, entry, output] if command == "discover" => {
            let rom = CanonicalRom::from_bytes(&fs::read(rom_path).map_err(|e| e.to_string())?)?;
            let image = CodeImage::from_rom(
                &rom,
                RomOffset(number(offset)?),
                GuestRange {
                    start: GuestAddr(number32(start)?),
                    size: number32(size)?,
                },
            )?;
            let d = discover_image(
                rom.identity,
                &image,
                &[GuestAddr(number32(entry)?)],
                1_000_000,
            )?;
            fs::write(output, d.map.to_json()?).map_err(|e| e.to_string())?;
            println!(
                "discovered {} blocks, {} indirect sites, {} unresolved items",
                d.map.blocks.len(),
                d.map.indirect_sites.len(),
                d.map.unresolved.len()
            );
        }
        [command, image_path, base, entry, exit, output] if command == "lower-c" => {
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
            };
            let rom = plaid_core::program::RomIdentity {
                sha256: image.base.image.clone(),
                size: bytes.len() as u64,
            };
            let d = discover_image(rom, &image, &[GuestAddr(number32(entry)?)], 1_000_000)?;
            let c = plaid_lower::lower_c(
                &d.map,
                &[image],
                GuestAddr(number32(entry)?),
                &[GuestAddr(number32(exit)?)],
            )?;
            fs::write(output, c).map_err(|e| e.to_string())?;
            println!("lowered {} blocks", d.map.blocks.len());
        }
        [command, path] if command == "rom-info" => {
            let rom = CanonicalRom::from_bytes(&fs::read(path).map_err(|e| e.to_string())?)?;
            println!(
                "{}",
                serde_json::to_string_pretty(&serde_json::json!({
                    "source_order": rom.source_order, "identity": rom.identity, "header": rom.header
                }))
                .map_err(|e| e.to_string())?
            );
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
                "usage: plaid inspect-sp-pi-fetch-lineage <rom> <firmware> <fetch.ndjson> <history-v3.ndjson> <expected-history-sha256> <expected-fetch-sha256> <report.json> | verify-sp-pi-fetch-lineage <same-inputs> | inspect-dcache-store64 <history-v2.json> <expected-source-sha256> <report.json> | verify-dcache-store64 <same-inputs> | compose-cop1-mutations <history.json> <expected-source-sha256> <contexts.json> <expected-contexts-sha256> <report.json> | verify-cop1-mutations <same-inputs> | inspect-dcache-resident-reads <history-v1.json> <expected-source-sha256> <report.json> | verify-dcache-resident-reads <same-inputs> | inspect-rsp-cpu-imem <history.json> <expected-source-sha256> <report.json> | verify-rsp-cpu-imem <same-inputs> | inspect-sp-writer-fetch <rom> <firmware> <fetch.ndjson> <history-v3.ndjson> <expected-history-sha256> <expected-fetch-sha256> <report.json> | verify-sp-writer-fetch <same-inputs> | create-trace-expectations <new-expected.json> <trace.ndjson>... | solve-traces <rom> <map.json> <expected.json> <trace.ndjson>... | inspect-cpu-definitions <history.json> <external-source-sha256> <report.json> | verify-cpu-definitions <history.json> <external-source-sha256> <report.json> | inspect-cpu-copy-history <history.json> <external-source-sha256> <report.json> | verify-cpu-copy-history <history.json> <external-source-sha256> <report.json> | rom-info <rom> | check-trace <trace.ndjson> | check-map <map.json> | solve [rom] <map.json> [--guarded-ram] | discover <rom> <rom-offset> <guest-start> <size> <entry> <output.json> | import-trace <rom> <trace.ndjson> <output.json> | import-fetch <rom> <fetch.ndjson> <output.json> | verify-fetch <rom> <fetch.ndjson> <map.json> | import-boot-fetch <rom> <firmware> <fetch.ndjson> <output.json> | verify-boot-fetch <rom> <firmware> <fetch.ndjson> <map.json> | inspect-boot-history <rom> <firmware> <fetch.ndjson> <history.ndjson> <report.json> | verify-boot-history <rom> <firmware> <fetch.ndjson> <history.ndjson> <report.json> | inspect-pi-boot-history <rom> <firmware> <fetch.ndjson> <history-v1.ndjson> <report.json> | verify-pi-boot-history <rom> <firmware> <fetch.ndjson> <history-v1.ndjson> <report.json> | inspect-pi-queue-boot-history <rom> <firmware> <fetch.ndjson> <history-v2.ndjson> <report.json> | verify-pi-queue-boot-history <rom> <firmware> <fetch.ndjson> <history-v2.ndjson> <report.json> | inspect-pi-fetch-lineage <rom> <firmware> <fetch.ndjson> <history-v2.ndjson> <report.json> | verify-pi-fetch-lineage <rom> <firmware> <fetch.ndjson> <history-v2.ndjson> <report.json> | inspect-sp-boot-history <rom> <firmware> <fetch.ndjson> <history-v3.ndjson> <report.json> | verify-sp-boot-history <rom> <firmware> <fetch.ndjson> <history-v3.ndjson> <report.json> | inspect-pif-boot-history <rom> <firmware> <fetch.ndjson> <history-v4.ndjson> <report.json> | verify-pif-boot-history <rom> <firmware> <fetch.ndjson> <history-v4.ndjson> <report.json> | merge <left.json> <right.json> <output.json> | lower-c <words.bin> <base> <entry> <exit> <out.c>"
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
