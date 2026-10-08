"""CLI coverage for bounded raw fetch import; no emulator or firmware needed."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "target/debug/plaid.exe"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"


def main():
    cargo = os.environ.get("CARGO") or shutil.which("cargo") or str(Path.home() / ".cargo/bin/cargo.exe")
    subprocess.run([cargo, "build", "-p", "plaid"], cwd=ROOT, check=True)
    if not EXE.exists():
        exe = ROOT / "target/debug/plaid"
    else:
        exe = EXE
    with tempfile.TemporaryDirectory(prefix="fetch-cli-", dir=ROOT / "target") as temporary:
        directory = Path(temporary)
        data = bytearray(4096)
        data[:4] = bytes.fromhex("80371240")
        header = {"record":"header","format":"plaid-ares-fetch-research-v0","revision":REV,
            "rom_sha256":hashlib.sha256(data).hexdigest(),"budget":10,
            "initial_state":"declared_post_ipl2_sp_entry"}
        records = [header]
        for seq, (pc, word, slot) in enumerate(((0x9000000000001000,0,False),
            (0x9000000000001000,1,True),(0x9000000000001000,0,False))):
            records.append({"record":"fetch","seq":seq,"pc":pc,"word":word,"delay_slot":slot})
        records.append({"record":"end","fetch_count":3,"reason":"instruction_call_budget"})
        trace = directory / "fetch.ndjson"
        trace.write_bytes(b"".join((json.dumps(r)+"\n").encode() for r in records))
        outputs = []
        for order in ("z64","v64","n64"):
            encoded = bytes(data)
            if order == "v64": encoded = b"".join(encoded[n:n+2][::-1] for n in range(0,len(encoded),2))
            if order == "n64": encoded = b"".join(encoded[n:n+4][::-1] for n in range(0,len(encoded),4))
            rom = directory / f"original.{order}"
            rom.write_bytes(encoded)
            output = directory / f"{order}.json"
            subprocess.run([str(exe),"import-fetch",str(rom),str(trace),str(output)],check=True)
            subprocess.run([str(exe),"verify-fetch",str(rom),str(trace),str(output)],check=True)
            report = json.loads(subprocess.check_output([str(exe),"solve",str(rom),str(output)],text=True))
            assert report["status"] == "open" and not report["native_complete"]
            assert any(b["kind"] == "fetch_execution_identity_unknown" for b in report["blockers"])
            outputs.append(output.read_bytes())
        assert outputs[0] == outputs[1] == outputs[2]
        map_path = directory / "z64.json"
        altered = json.loads(map_path.read_text())
        assert len(altered["fetch_observations"]) == 2 and not altered["blocks"] and not altered["loads"]
        altered["fetch_observations"][0]["word"] ^= 2
        map_path.write_text(json.dumps(altered))
        assert subprocess.run([str(exe),"verify-fetch",str(rom),str(trace),str(map_path)],capture_output=True).returncode != 0
        physical_records = json.loads(json.dumps(records))
        physical_records[0].update(format="plaid-ares-fetch-research-v1",mapped_cartridge_size=4096)
        for event, (physical, cached) in zip(physical_records[1:-1], ((0x2000,False),(0x2000,True),(0x3000,False))):
            event.update(physical=physical,cached=cached)
        trace.write_bytes(b"".join((json.dumps(r)+"\n").encode() for r in physical_records))
        physical_outputs = []
        for order in ("z64","v64","n64"):
            output = directory / f"physical-{order}.json"
            source = directory / f"original.{order}"
            subprocess.run([str(exe),"import-fetch",str(source),str(trace),str(output)],check=True)
            subprocess.run([str(exe),"verify-fetch",str(source),str(trace),str(output)],check=True)
            physical_outputs.append(output.read_bytes())
        assert physical_outputs[0] == physical_outputs[1] == physical_outputs[2]
        physical_map = json.loads(physical_outputs[0])
        assert len(physical_map["fetch_observations"]) == 3
        assert all("access" in f for f in physical_map["fetch_observations"])
        assert not physical_map["regions"] and not physical_map["loads"]
        physical_map["fetch_observations"][0]["access"]["cached"] = True
        map_path.write_text(json.dumps(physical_map))
        assert subprocess.run([str(exe),"verify-fetch",str(rom),str(trace),str(map_path)],capture_output=True).returncode != 0
        source_records = json.loads(json.dumps(physical_records))
        source_records[0].update(format="plaid-ares-fetch-research-v2",source_policy="delegated_rom_halves_before_prologue")
        for event in source_records[1:-1]: event["source"] = {"kind":"unknown"}
        source_records[1].update(physical=0x10000044,cached=False,source={"kind":"cartridge_rom","offset":68})
        source_records[3].update(physical=0x10000044,cached=False)
        trace.write_bytes(b"".join((json.dumps(r)+"\n").encode() for r in source_records))
        source_outputs = []
        for order in ("z64","v64","n64"):
            output = directory / f"source-{order}.json"
            source = directory / f"original.{order}"
            subprocess.run([str(exe),"import-fetch",str(source),str(trace),str(output)],check=True)
            subprocess.run([str(exe),"verify-fetch",str(source),str(trace),str(output)],check=True)
            source_outputs.append(output.read_bytes())
        assert source_outputs[0] == source_outputs[1] == source_outputs[2]
        source_map = json.loads(source_outputs[0])
        assert len(source_map["fetch_observations"]) == 3
        assert sum(f["source"]["kind"] == "cartridge_rom" for f in source_map["fetch_observations"]) == 1
        source_records[1]["word"] = 1
        trace.write_bytes(b"".join((json.dumps(r)+"\n").encode() for r in source_records))
        rejected_source = directory / "rejected-source.json"
        assert subprocess.run([str(exe),"import-fetch",str(rom),str(trace),str(rejected_source)],capture_output=True).returncode != 0
        assert not rejected_source.exists()
        boot_records = json.loads(json.dumps(physical_records))
        boot_records[0].update(format="plaid-ares-fetch-research-v3",
            initial_state="cpu_power_pif_entry",source_policy="delegated_rom_halves_before_prologue",
            firmware_sha256="fa7b09795ef1e54461e59f6f2d902368133e3f1cd980e34383e6a780d74beffd",
            pif_processor="reference_hle",pif_checksum_enforced=True)
        for event in boot_records[1:-1]: event["source"] = {"kind":"unknown"}
        trace.write_bytes(b"".join((json.dumps(r)+"\n").encode() for r in boot_records))
        rejected_boot = directory / "rejected-boot.json"
        assert subprocess.run([str(exe),"import-fetch",str(rom),str(trace),str(rejected_boot)],capture_output=True).returncode != 0
        assert not rejected_boot.exists()
        trace.write_bytes(b"".join((json.dumps(r)+"\n").encode() for r in records[:-1]))
        rejected = directory / "rejected.json"
        assert subprocess.run([str(exe),"import-fetch",str(rom),str(trace),str(rejected)],capture_output=True).returncode != 0
        assert not rejected.exists()
    print("Raw fetch CLI: v0/v1/v2, all byte orders, wide PC/word/access/source variants, source rechecking and OPEN gate passed")


if __name__ == "__main__": main()
