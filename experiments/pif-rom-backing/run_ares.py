#!/usr/bin/env python3
"""Compile/run a causal PIF-ROM fetch-backing sensor against pinned ares."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PIN = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
MODES = (
    "natural",
    "mirror",
    "high_mirror",
    "busy_latch",
    "lockout_zero",
    "pif_ram_same_value",
    "cached_pif",
    "stale_decoy",
    "nonfetch_rom",
)
SYNTHETIC_FW0 = 0x3C1ABFC0
KNOWN_NTSC_SHA256 = "fa7b09795ef1e54461e59f6f2d902368133e3f1cd980e34383e6a780d74beffd"


def import_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def patched_builder(output: Path):
    original = ROOT / "spikes/003-ares-oracle/run.py"
    text = original.read_text()
    sig = next(line for line in text.splitlines() if line.startswith("def build("))
    assert text.count(sig) == 1
    text = text.replace(sig, sig[:-2] + ", pif_rom_access=False):")

    marker = "    if pi_dma_access: assert raw_fetch_access and physical_fetch_access\n"
    assert text.count(marker) == 1
    text = text.replace(marker, marker + "    if pif_rom_access: assert raw_fetch_access and physical_fetch_access\n")

    marker = '        "pi_dma_access":pi_dma_access,\n'
    assert text.count(marker) == 1
    text = text.replace(marker, marker + '        "pif_rom_access":pif_rom_access,\n')

    marker = '            (output / "cpu_memory.cpp").write_text(memory)\n'
    assert text.count(marker) == 1
    inject = r'''            if pif_rom_access:
                memory = "extern void plaidPifFetchBoundary(bool, u64, u32, u32, bool, u32);\n" + memory
                fetch_marker = "  if(access.cache) return icache.fetch(access.vaddr, paddr, cpu);\n  return busRead<Word>(paddr);"
                assert memory.count(fetch_marker) == 1
                memory = memory.replace(fetch_marker, """  plaidPifFetchBoundary(true, access.vaddr, access.paddr, paddr, access.cache, 0);
  u32 plaidPifValue = access.cache ? icache.fetch(access.vaddr, paddr, cpu) : busRead<Word>(paddr);
  plaidPifFetchBoundary(false, access.vaddr, access.paddr, paddr, access.cache, plaidPifValue);
  return plaidPifValue;""")
'''
    text = text.replace(marker, inject + marker)

    marker = '        (output / "n64.cpp").write_text(unity)\n'
    assert text.count(marker) == 1
    inject = r'''        if pif_rom_access:
            pif_io = (REF / "ares/n64/pif/io.cpp").read_text()
            branch = "    return rom.read<Word>(address);"
            assert pif_io.count(branch) == 1
            pif_io = pif_io.replace(branch, """    u32 plaidPifRomValue = rom.read<Word>(address);
    plaidPifRomBackingRead(address, plaidPifRomValue);
    return plaidPifRomValue;""")
            pif_io = "extern void plaidPifRomBackingRead(u32, u32);\n" + pif_io
            (output / "pif_io.cpp").write_text(pif_io)
            pif_source = (REF / "ares/n64/pif/pif.cpp").read_text()
            assert pif_source.count('#include "io.cpp"') == 1
            pif_source = re.sub(r'#include "([^"]+)"', lambda match:
                f'#include "{output / "pif_io.cpp" if match[1] == "io.cpp" else REF / "ares/n64/pif" / match[1]}"', pif_source)
            (output / "pif.cpp").write_text(pif_source)
            assert unity.count("#include <n64/pif/pif.cpp>") == 1
            unity = unity.replace("#include <n64/pif/pif.cpp>", f'#include "{output / "pif.cpp"}"')
'''
    text = text.replace(marker, inject + marker)

    generated = output / "builder_pif.py"
    generated.parent.mkdir(parents=True, exist_ok=True)
    generated.write_text(text)
    generated.with_name("driver.cpp").write_bytes(original.with_name("driver.cpp").read_bytes())
    module = import_module(generated, "plaid_pif_builder")
    module.ROOT = ROOT
    module.REF = ROOT / ".refs/ares"
    module.REV = PIN
    return module


def run_one(exe: Path, mode: str, firmware: Path | None):
    cmd = [str(exe), mode]
    if firmware is not None:
        cmd.append(str(firmware))
    for attempt in range(2):
        raw = subprocess.check_output(cmd, text=True, timeout=30)
        json_lines = [line for line in raw.splitlines() if line.startswith("{")]
        if json_lines:
            return json.loads(json_lines[-1])
        assert attempt == 0, (mode, "successful process produced no JSON twice")
    raise AssertionError((mode, "unreachable"))


def witness(event):
    return event["witness"] if event else None


def verify(results: dict, *, firmware: Path | None):
    base = results["baseline"]
    inst = results["instrumented"]
    repeat = results["repeat"]
    for mode in MODES:
        assert inst[mode] == repeat[mode], mode
        assert inst[mode]["machine"] == base[mode]["machine"], mode
        assert inst[mode]["returned"] == base[mode]["returned"], mode

    fw0 = SYNTHETIC_FW0 if firmware is None else int.from_bytes(firmware.read_bytes()[:4], "big")

    for mode, offset in (("natural", 0), ("mirror", 0), ("high_mirror", 0)):
        event = inst[mode]["fetches"]
        assert len(event) == 1, (mode, event)
        event = event[0]
        assert event["ended"] and not event["cached"]
        assert event["returned"] == fw0
        assert witness(event) == {"kind": "pif_rom", "offset": offset, "word": fw0}
        assert inst[mode]["backing_reads"] == 1
        assert inst[mode]["unattributed_backing_reads"] == 0

    for mode in ("busy_latch", "lockout_zero", "pif_ram_same_value", "cached_pif"):
        events = inst[mode]["fetches"]
        assert len(events) == 1 and witness(events[0]) is None, (mode, events)
        assert inst[mode]["backing_reads"] == 0, mode
        assert inst[mode]["unattributed_backing_reads"] == 0, mode

    assert inst["busy_latch"]["returned"] == fw0
    assert inst["pif_ram_same_value"]["returned"] == fw0
    if firmware is None:
        assert inst["lockout_zero"]["returned"] == 0

    stale = inst["stale_decoy"]
    assert stale["returned"] == fw0
    assert stale["backing_reads"] == 1 and stale["unattributed_backing_reads"] == 1
    assert len(stale["fetches"]) == 1 and witness(stale["fetches"][0]) is None

    nonfetch = inst["nonfetch_rom"]
    assert nonfetch["returned"] == fw0
    assert nonfetch["backing_reads"] == 1 and nonfetch["unattributed_backing_reads"] == 1
    assert nonfetch["fetches"] == []

    assert inst["mirror"]["fetches"][0]["physical"] == 0x1FC00800
    assert inst["high_mirror"]["fetches"][0]["physical"] == 0x1FCFF800
    assert inst["mirror"]["fetches"][0]["witness"]["offset"] == 0
    assert inst["high_mirror"]["fetches"][0]["witness"]["offset"] == 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--firmware", type=Path, help="Optional local 1,984-byte NTSC PIF ROM; bytes are never copied to output")
    ap.add_argument("--output", type=Path, default=ROOT / "target/pif-rom-backing-ares")
    args = ap.parse_args()
    if args.firmware:
        blob = args.firmware.read_bytes()
        assert len(blob) == 0x7C0
        digest = hashlib.sha256(blob).hexdigest()
        assert digest == KNOWN_NTSC_SHA256, digest
    else:
        digest = "synthetic-original-fixture"

    base_builder = import_module(ROOT / "spikes/003-ares-oracle/run.py", "plaid_base_builder")
    assert base_builder.REV == PIN
    args.output.mkdir(parents=True, exist_ok=True)
    driver = Path(__file__).with_name("ares_driver.cpp")
    baseline = base_builder.build(driver, args.output / "baseline")
    probe_builder = patched_builder(args.output / "generated")
    instrumented = probe_builder.build(
        driver,
        args.output / "instrumented",
        raw_fetch_access=True,
        physical_fetch_access=True,
        pif_rom_access=True,
    )

    results = {"ares_revision": PIN, "firmware": digest, "baseline": {}, "instrumented": {}, "repeat": {}}
    for mode in MODES:
        results["baseline"][mode] = run_one(baseline, mode, args.firmware)
        results["instrumented"][mode] = run_one(instrumented, mode, args.firmware)
        results["repeat"][mode] = run_one(instrumented, mode, args.firmware)
    verify(results, firmware=args.firmware)
    out = args.output / "results.json"
    out.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "result": "VALIDATED",
        "ares_revision": PIN,
        "firmware": digest,
        "modes": list(MODES),
        "results_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        "instrumentation_machine_state_equal": True,
        "instrumented_repeat_equal": True,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    import os, sys
    if os.name == "nt":
        def linux_path(path):
            return subprocess.check_output(["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(path).resolve().as_posix()], text=True).strip()
        forwarded = sys.argv[1:]
        for option in ("--firmware", "--output"):
            if option in forwarded:
                index = forwarded.index(option) + 1
                forwarded[index] = linux_path(forwarded[index])
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", linux_path(__file__), *forwarded], check=True)
    else:
        main()
