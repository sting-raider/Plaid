"""PI inspection CLI: source/canonical/version gates and report/input protection."""
from pathlib import Path
import argparse
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    sys.path.insert(0, str(ROOT/"spikes/030-ares-boot-pi-history"))
    spec = importlib.util.spec_from_file_location("pi_fixture", ROOT/"spikes/030-ares-boot-pi-history/test_verifier.py")
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    source, raw = helper.fixture()
    firmware_bytes = bytes(1984)
    firmware_hash = hashlib.sha256(firmware_bytes).hexdigest()
    header = dict(raw[0], budget=2, firmware_sha256=firmware_hash)
    rows = [header]
    fetches = [dict(record="header", format="plaid-ares-fetch-research-v5", revision=header["revision"],
        rom_sha256=header["rom_sha256"], budget=2, initial_state="cpu_power_pif_entry",
        mapped_cartridge_size=len(source), source_policy="delegated_rom_halves_before_prologue",
        cache_policy="selected_icache_line_at_prologue", boot_inputs=dict(firmware_sha256=firmware_hash,
            firmware_size=1984, region="ntsc", cic="CIC-NUS-6102", rdram_size=8388608,
            deterministic_entropy=True, pif_processor="reference_hle", pif_checksum_enforced=True))]
    def append(payload):
        rows.append(dict(payload, ordinal=len(rows)))
    def fetch(seq, pc, physical, word):
        context = len(rows)
        common = dict(context=context, pc=pc, vaddr=pc, translated=physical, bus=physical, cached=False)
        append(dict(common, record="fetch_begin", value=0))
        if seq:
            append(dict(record="scalar", context=context, pc=pc, write=False, address=physical,
                        aligned_address=physical, bytes=4, device=3, value=word))
        append(dict(common, record="fetch_end", value=word))
        append(dict(record="fetch", context=0, pc=pc, fetch_context=context, fetch_seq=seq,
                    word=word, physical=physical, cached=False))
        fetches.append(dict(record="fetch", seq=seq, pc=pc, physical=physical, word=word,
                            cached=False, delay_slot=False, source=dict(kind="unknown")))
    fetch(0, 0xffffffffbfc00000, 0x1fc00000, 0)
    for event in raw[1:-1]:
        append(event)
    fetch(1, 0xffffffffa0004000, 0x4000, 0x34081111)
    rows.append(dict(record="end", record_count=len(rows)-1, fetch_count=2, reason="instruction_call_budget"))
    fetches.append(dict(record="end", fetch_count=2, reason="instruction_call_budget"))
    return source, firmware_bytes, rows, fetches


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-build", action="store_true")
    options = parser.parse_args()
    cargo = os.environ.get("CARGO") or shutil.which("cargo") or str(Path.home()/".cargo/bin/cargo.exe")
    if not options.no_build:
        subprocess.run([cargo, "build", "-p", "plaid"], cwd=ROOT, check=True)
    exe = ROOT/("target/debug/plaid.exe" if os.name == "nt" else "target/debug/plaid")
    source, firmware_bytes, rows, fetches = fixture()
    with tempfile.TemporaryDirectory(prefix="pi-history-cli-", dir=ROOT/"target") as temporary:
        directory = Path(temporary)
        firmware = directory/"firmware.bin"; firmware.write_bytes(firmware_bytes)
        trace = directory/"fetch.ndjson"; history = directory/"history.ndjson"
        def write(path, values):
            path.write_text(''.join(json.dumps(value)+"\n" for value in values), encoding="utf-8")
        write(trace, fetches); write(history, rows)
        def command(name, *args):
            return subprocess.run([str(exe), name, *map(str, args)], capture_output=True, text=True)
        reports = []
        for order in ("z64", "v64", "n64"):
            width = 2 if order == "v64" else 4
            encoded = source if order == "z64" else b''.join(source[i:i+width][::-1] for i in range(0, len(source), width))
            rom = directory/f"toy.{order}"; rom.write_bytes(encoded)
            output = directory/f"{order}-report.json"; inputs = (rom, firmware, trace, history)
            result = command("inspect-pi-boot-history", *inputs, output)
            assert result.returncode == 0, result.stderr
            assert command("verify-pi-boot-history", *inputs, output).returncode == 0
            report = json.loads(output.read_text())
            assert report["canonical_rom_byte_origins"] == 4 and report["unknown_pi_byte_origins"] == 2
            assert report["failed_destination_witnesses"] == 2 and report["successful_pi_writes"] == 6
            assert not report["transfer_completion_certified"] and report["writes_without_observer_status"] == [3]
            reports.append(output.read_bytes())
            before = rom.read_bytes()
            assert command("inspect-pi-boot-history", *inputs, rom).returncode != 0
            assert rom.read_bytes() == before
        assert reports[0] == reports[1] == reports[2]
        original_report = output.read_bytes()
        report["transfer_completion_certified"] = True
        output.write_text(json.dumps(report), encoding="utf-8")
        assert command("verify-pi-boot-history", *inputs, output).returncode != 0
        output.write_bytes(original_report)
        changed = copy.deepcopy(rows)
        next(e for e in changed if e["record"] == "pi_dma" and e["event"] == 6)["dram"] += 1
        write(history, changed)
        assert command("verify-pi-boot-history", *inputs, output).returncode != 0
        rejected = directory/"rejected.json"
        write(history, rows[:-1])
        assert command("inspect-pi-boot-history", *inputs, rejected).returncode != 0 and not rejected.exists()
        changed = copy.deepcopy(rows); changed[0].update(format="plaid-ares-access-history-v0",
            policy="identity_ram_successful_access_and_fetch_boundaries")
        write(history, changed)
        assert command("inspect-pi-boot-history", *inputs, rejected).returncode != 0 and not rejected.exists()
        write(history, rows)
        assert command("inspect-boot-history", *inputs, rejected).returncode != 0 and not rejected.exists()
        firmware.write_bytes(bytes([1])+firmware_bytes[1:])
        assert command("inspect-pi-boot-history", *inputs, rejected).returncode != 0 and not rejected.exists()
    print("PI history CLI: canonical byte orders, finite origins/unknowns, source/report rechecking, version/input/truncation gates and overwrite protection passed")


if __name__ == "__main__":
    main()
