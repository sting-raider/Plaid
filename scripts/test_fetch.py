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
        trace.write_bytes(b"".join((json.dumps(r)+"\n").encode() for r in records[:-1]))
        rejected = directory / "rejected.json"
        assert subprocess.run([str(exe),"import-fetch",str(rom),str(trace),str(rejected)],capture_output=True).returncode != 0
        assert not rejected.exists()
    print("Raw fetch CLI: all byte orders, wide PC/word variants, source rechecking and OPEN gate passed")


if __name__ == "__main__": main()
