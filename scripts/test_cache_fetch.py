"""Selected-cache CLI/source boundaries using original synthetic inputs."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    cargo = os.environ.get("CARGO") or shutil.which("cargo") or str(Path.home()/".cargo/bin/cargo.exe")
    subprocess.run([cargo,"build","-p","plaid"],cwd=ROOT,check=True)
    exe = ROOT / ("target/debug/plaid.exe" if os.name == "nt" else "target/debug/plaid")
    with tempfile.TemporaryDirectory(prefix="cache-fetch-",dir=ROOT/"target") as temporary:
        directory = Path(temporary)
        firmware = directory/"original.bin"; firmware.write_bytes(bytes(1984))
        data = bytes.fromhex("80371240")+bytes(4092)
        records = [{"record":"header","format":"plaid-ares-fetch-research-v5",
            "revision":"9408cb43d4948fc3ea6e152a307a34348df3fe04",
            "rom_sha256":hashlib.sha256(data).hexdigest(),"budget":10,
            "initial_state":"cpu_power_pif_entry","mapped_cartridge_size":4096,
            "source_policy":"delegated_rom_halves_before_prologue",
            "cache_policy":"selected_icache_line_at_prologue",
            "boot_inputs":{"firmware_sha256":hashlib.sha256(firmware.read_bytes()).hexdigest(),
                "firmware_size":1984,"region":"ntsc","cic":"CIC-NUS-6102",
                "rdram_size":8388608,"deterministic_entropy":True,
                "pif_processor":"reference_hle","pif_checksum_enforced":True}},
            {"record":"fetch","seq":0,"pc":0xffffffffbfc00000,"word":0,
                "delay_slot":False,"physical":0x1fc00000,"cached":False,"source":{"kind":"unknown"}},
            {"record":"fetch","seq":1,"pc":0xffffffff80001024,"word":7,
                "delay_slot":False,"physical":0x1024,"cached":True,"source":{"kind":"unknown"},
                "cache_line":{"slot":129,"tag_key":0x1001,"index":0x20,"words":[0,7,0,0,0,0,0,0]}},
            {"record":"end","fetch_count":2,"reason":"instruction_call_budget"}]
        trace = directory/"fetch.ndjson"
        trace.write_text("".join(json.dumps(r)+"\n" for r in records))
        maps = []
        for order in ("z64","v64","n64"):
            encoded = data
            if order == "v64": encoded = b"".join(data[n:n+2][::-1] for n in range(0,len(data),2))
            if order == "n64": encoded = b"".join(data[n:n+4][::-1] for n in range(0,len(data),4))
            rom = directory/f"original.{order}"; rom.write_bytes(encoded)
            output = directory/f"{order}.json"
            inputs = [str(rom),str(firmware),str(trace)]
            subprocess.run([str(exe),"import-boot-fetch",*inputs,str(output)],check=True,capture_output=True)
            subprocess.run([str(exe),"verify-boot-fetch",*inputs,str(output)],check=True,capture_output=True)
            report = json.loads(subprocess.check_output([str(exe),"solve",str(rom),str(output)],text=True))
            assert report["status"] == "open" and not report["native_complete"]
            assert any(b["kind"] == "fetch_execution_identity_unknown" for b in report["blockers"])
            maps.append(output.read_bytes())
        assert maps[0] == maps[1] == maps[2]
        altered = json.loads(output.read_text())
        next(f for f in altered["fetch_observations"] if "cache_line" in f)["cache_line"]["words"][7] = 9
        output.write_text(json.dumps(altered))
        assert subprocess.run([str(exe),"verify-boot-fetch",*inputs,str(output)],capture_output=True).returncode != 0
        rejected = directory/"rejected.json"
        records[2]["cache_line"]["words"][1] = 8
        trace.write_text("".join(json.dumps(r)+"\n" for r in records))
        assert subprocess.run([str(exe),"import-boot-fetch",*inputs,str(rejected)],capture_output=True).returncode != 0
        assert not rejected.exists()
    print("Cache fetch CLI: canonical orders, exact resident words, source rechecking and OPEN gating passed")


if __name__ == "__main__": main()
