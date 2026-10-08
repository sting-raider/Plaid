"""Exercise normalized ROM -> CFG/indirect targets -> map -> fail-closed report."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def main():
    cargo = shutil.which("cargo") or str(Path.home() / ".cargo/bin/cargo.exe")
    subprocess.run([cargo,"build","--quiet","-p","plaid"],cwd=ROOT,check=True)
    exe = ROOT / "target/debug" / ("plaid.exe" if os.name == "nt" else "plaid")
    with tempfile.TemporaryDirectory(prefix="cli-",dir=ROOT / "target") as directory:
        directory = Path(directory)
        canonical = bytearray(4096)
        canonical[:4] = bytes.fromhex("80371240")
        canonical[8:12] = (0x80000000).to_bytes(4,"big")
        words = [0x3c088000,0x35080020,0x01000008,0,0,0,0,0,0x08000008,0]
        canonical[64:104] = b"".join(w.to_bytes(4,"big") for w in words)
        v = b"".join(canonical[i:i+2][::-1] for i in range(0,len(canonical),2))
        n = b"".join(canonical[i:i+4][::-1] for i in range(0,len(canonical),4))
        def run(*args,ok=True):
            result = subprocess.run([str(exe),*map(str,args)],capture_output=True,text=True)
            assert (result.returncode == 0) == ok,(args,result.stdout,result.stderr)
            return result.stdout
        identities=[]; maps=[]
        for suffix,data in [("z64",canonical),("v64",v),("n64",n)]:
            rom = directory / ("synthetic." + suffix); rom.write_bytes(data)
            identities.append(json.loads(run("rom-info",rom))["identity"])
            output = directory / (suffix + ".json")
            run("discover",rom,"64","0x80000000","40","0x80000000",output)
            run("check-map",output)
            maps.append(output.read_bytes())
            report=json.loads(run("solve",rom,output))
            assert report["status"] == "open" and report["native_complete"] is False
            assert not any(b["kind"] in {"missing_instruction_source","unresolved_indirect_target","unresolved_indirect_site"} for b in report["blockers"])
            assert any(b["kind"] == "unproven_executable_universe" for b in report["blockers"])
        assert identities[0] == identities[1] == identities[2]
        assert maps[0] == maps[1] == maps[2]
        merged=directory / "merged.json"
        run("merge",directory/"z64.json",directory/"v64.json",merged)
        assert merged.read_bytes() == maps[0]
        m=json.loads(maps[0]); assert len(m["blocks"]) == 2
        assert m["indirect_sites"][0]["closed_proof"] is not None
        bad=directory/"malformed.z64"; bad.write_bytes(b"bad")
        run("rom-info",bad,ok=False)
        run("unknown-command",ok=False)
        changed=bytearray(canonical); changed[64] ^= 1
        bad.write_bytes(changed)
        run("solve",bad,directory/"z64.json",ok=False)
    print("CLI pipeline: all byte orders, deterministic maps, target traversal, identity gates and OPEN whole-ROM reports passed")

if __name__ == "__main__":
    main()
