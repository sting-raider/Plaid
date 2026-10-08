"""Boot-input CLI boundaries using original synthetic bytes, without firmware assets."""
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
    with tempfile.TemporaryDirectory(prefix="boot-fetch-",dir=ROOT/"target") as temporary:
        directory = Path(temporary)
        firmware = directory/"synthetic.bin"; firmware.write_bytes(bytes(1984))
        data = bytes.fromhex("80371240")+bytes(4092)
        header = {"record":"header","format":"plaid-ares-fetch-research-v4",
            "revision":"9408cb43d4948fc3ea6e152a307a34348df3fe04",
            "rom_sha256":hashlib.sha256(data).hexdigest(),"budget":10,
            "initial_state":"cpu_power_pif_entry","mapped_cartridge_size":4096,
            "source_policy":"delegated_rom_halves_before_prologue",
            "boot_inputs":{"firmware_sha256":hashlib.sha256(firmware.read_bytes()).hexdigest(),
                "firmware_size":1984,"region":"ntsc","cic":"CIC-NUS-6102",
                "rdram_size":8388608,"deterministic_entropy":True,
                "pif_processor":"reference_hle","pif_checksum_enforced":True}}
        records = [header,{"record":"fetch","seq":0,"pc":0xffffffffbfc00000,
            "word":0,"delay_slot":False,"physical":0x1fc00000,"cached":False,
            "source":{"kind":"unknown"}},
            {"record":"end","fetch_count":1,"reason":"instruction_call_budget"}]
        trace = directory/"fetch.ndjson"
        trace.write_text("".join(json.dumps(event)+"\n" for event in records))
        maps = []
        for order in ("z64","v64","n64"):
            encoded = data
            if order == "v64": encoded = b"".join(data[n:n+2][::-1] for n in range(0,len(data),2))
            if order == "n64": encoded = b"".join(data[n:n+4][::-1] for n in range(0,len(data),4))
            rom = directory/f"original.{order}"; rom.write_bytes(encoded)
            output = directory/f"{order}.json"
            subprocess.run([str(exe),"import-boot-fetch",str(rom),str(firmware),str(trace),str(output)],check=True,capture_output=True)
            subprocess.run([str(exe),"verify-boot-fetch",str(rom),str(firmware),str(trace),str(output)],check=True,capture_output=True)
            report = json.loads(subprocess.check_output([str(exe),"solve",str(rom),str(output)],text=True))
            assert report["status"] == "open" and not report["native_complete"]
            assert any(b["kind"] == "fetch_execution_identity_unknown" for b in report["blockers"])
            maps.append(output.read_bytes())
        assert maps[0] == maps[1] == maps[2]
        bad_output = directory/"rejected.json"
        assert subprocess.run([str(exe),"import-fetch",str(rom),str(trace),str(bad_output)],capture_output=True).returncode != 0
        assert not bad_output.exists()
        firmware.write_bytes(bytes(1983)+b"\x01")
        for command in ("import-boot-fetch","verify-boot-fetch"):
            target = bad_output if command.startswith("import") else output
            assert subprocess.run([str(exe),command,str(rom),str(firmware),str(trace),str(target)],capture_output=True).returncode != 0
        assert not bad_output.exists()
        firmware.write_bytes(bytes(1984))
        altered = json.loads(output.read_text()); altered["fetch_observations"][0]["word"] = 1
        output.write_text(json.dumps(altered))
        assert subprocess.run([str(exe),"verify-boot-fetch",str(rom),str(firmware),str(trace),str(output)],capture_output=True).returncode != 0
        header["boot_inputs"]["pif_checksum_enforced"] = False
        trace.write_text("".join(json.dumps(event)+"\n" for event in records))
        assert subprocess.run([str(exe),"import-boot-fetch",str(rom),str(firmware),str(trace),str(bad_output)],capture_output=True).returncode != 0
        assert not bad_output.exists()
    print("Boot fetch CLI: canonical orders, firmware identity, profile/source rechecking and OPEN gating passed")


if __name__ == "__main__": main()
