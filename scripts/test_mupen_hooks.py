"""Build and exercise the actual pinned x64 recompiler's discovery hooks.

Requires the reference checkout, GCC (MinGW on Windows), and Rust. No game ROM,
SDL, emulator frontend or guest/native execution is required.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / ".refs/mupen64plus-core"

def main():
    subprocess.run([shutil.which("python") or "python", str(ROOT / "scripts/prepare_mupen.py")], check=True)
    cc = os.environ.get("CC", "gcc")
    machine = subprocess.check_output([cc, "-dumpmachine"], text=True)
    if "x86_64" not in machine:
        raise SystemExit("This synthetic hook driver requires an x64 GCC toolchain")
    cargo = shutil.which("cargo") or str(Path.home() / ".cargo/bin/cargo.exe")
    (ROOT / "target").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mupen-hooks-", dir=ROOT / "target") as directory:
        directory = Path(directory)
        exe = directory / ("sensor.exe" if os.name == "nt" else "sensor")
        trace = directory / "hooks.ndjson"
        rom = directory / "synthetic.z64"
        output = directory / "map.json"
        data = bytearray(4096)
        data[:4] = bytes.fromhex("80371240")
        data[64:72] = bytes.fromhex("0800000000000000")
        rom.write_bytes(data)
        flags = ["-std=gnu99", "-O1", "-ffunction-sections", "-fdata-sections", "-DNEW_DYNAREC=NEW_DYNAREC_X64", "-DDYNAREC"]
        if os.name == "nt": flags += ["-DWIN32"]
        subprocess.run([cc, *flags, "-I", str(REF / "src"), "-I", str(REF / "subprojects/md5"),
            str(ROOT / "instruments/mupen/compile_driver.c"), str(ROOT / "instruments/mupen/compile_traps.c"),
            str(REF / "src/device/r4300/new_dynarec/new_dynarec.c"), str(REF / "src/device/cart/cart_rom.c"), "-Wl,--gc-sections", "-lm", "-o", str(exe)], check=True)
        env = dict(os.environ, PLAID_TRACE_PATH=str(trace), PLAID_ROM_SHA256=hashlib.sha256(data).hexdigest(), PLAID_ROM_SIZE=str(len(data)))
        subprocess.run([str(exe)], env=env, check=True)
        first = trace.read_bytes()
        subprocess.run([str(exe)], env=env, check=True)
        assert trace.read_bytes() == first, "actual hook facts must be repeatable"
        events = [json.loads(line) for line in first.splitlines()][1:-1]
        compiled = [e["data"] for e in events if e["data"]["event"] == "unit_compiled"]
        assert len(compiled) == 4
        assert compiled[0]["words"] == [0x08000000, 0]
        assert compiled[1]["words"] == [0x3c088000, 0x35080000, 0x01000008, 0]
        assert compiled[2]["words"] == [0, 0x08000401, 0]
        assert compiled[3]["words"] == [0x08000000, 0]
        assert any(e["data"]["event"] == "runtime_link" and e["data"]["target"] == 0x80000000 for e in events)
        assert any(e["data"] == {"event":"rom_dma_observed","rom_offset":64,"physical_destination":0,"size":8} for e in events)
        assert any(e["data"]["event"] == "compile_begin" and e["data"]["delay_slot_entry"] and e["data"]["start"] == 0x80001000 for e in events)
        assert sum(e["data"]["event"] == "entry_installed" for e in events) >= 2
        assert sum(e["data"]["event"] == "target_lookup" for e in events) >= 2
        assert any(e["data"]["event"] == "invalidate" and e["data"]["range"] is None for e in events)
        def run(*args):
            return subprocess.run([cargo, "run", "--quiet", "-p", "plaid", "--", *map(str, args)], cwd=ROOT, check=True, capture_output=True, text=True).stdout
        run("check-trace", trace)
        run("import-trace", rom, trace, output)
        imported = json.loads(output.read_text())
        assert len(imported["blocks"]) >= 2
        assert len({r["generation"] for r in imported["regions"]}) >= 2
        assert len(imported["dma_observations"]) == 3
        dma = [e["data"] for e in events if e["data"]["event"] == "rom_dma_observed"]
        assert dma[1] == {"event":"rom_dma_observed","rom_offset":4092,"physical_destination":0x2000,"size":4}
        assert dma[2] == {"event":"rom_dma_observed","rom_offset":64,"physical_destination":0x7ffffc,"size":4}
        assert any(l["rom_offset"] == 64 and l["destination"]["start"] == 0x80000000 for l in imported["loads"])
        report = json.loads(run("solve", output))
        assert report["status"] == "open" and report["native_complete"] is False
        assert any(b["kind"] == "unresolved_executable_write" for b in report["blockers"])
        assert b"host_pointer" not in first
        print(f"Actual Mupen hooks: {len(events)} events, four guest units including pagespan entry, links, clipped DMA, generation separation, Rust import and OPEN solver verified")

if __name__ == "__main__":
    main()
