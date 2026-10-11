"""Exercise normalized ROM -> CFG/indirect targets -> map -> fail-closed report."""
from pathlib import Path
import json
import hashlib
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
        registers=[0]*32
        registers[16]=0xffffffffa0001000; registers[17]=0xffffffffa0002000
        loaded=registers.copy(); loaded[8]=0xffffffff89abcdef
        def instruction(begin,ordinal,context,pc,word,gpr):
            return dict(begin=begin,ordinal=ordinal,context=context,phase=1,pc=pc,word=word,gpr=gpr)
        pc=0xffffffffa0006000
        copy_history=dict(format='plaid-cpu-copy-history-v0',instruction_events=[
            instruction(True,1,1,pc,0x8e080000,registers),
            instruction(False,3,1,pc,0x8e080000,loaded),
            instruction(True,4,4,pc+4,0xae280000,loaded),
            instruction(False,6,4,pc+4,0xae280000,loaded)],scalar_events=[
                dict(ordinal=2,context=1,phase=1,pc=pc,write=False,address=0x1000,
                    bytes=4,uncached_cpu=True,value=0x89abcdef),
                dict(ordinal=5,context=4,phase=1,pc=pc+4,write=True,address=0x2000,
                    bytes=4,uncached_cpu=True,value=0x89abcdef)])
        source=directory/'copy-history.json'; source.write_bytes(json.dumps(copy_history).encode())
        source_bytes=source.read_bytes(); receipt=hashlib.sha256(source_bytes).hexdigest()
        copy_report=directory/'copy-report.json'
        run('inspect-cpu-copy-history',source,receipt,copy_report)
        run('verify-cpu-copy-history',source,receipt,copy_report)
        report=json.loads(copy_report.read_bytes())
        assert len(report['witnesses'])==1 and report['witnesses'][0]['read_ordinal']==2
        assert report['native_complete'] is False
        run('inspect-cpu-copy-history',source,'f'*64,copy_report,ok=False)
        run('inspect-cpu-copy-history',source,receipt,source,ok=False)
        assert source.read_bytes()==source_bytes
        report['witnesses']=[]; copy_report.write_bytes(json.dumps(report).encode())
        run('verify-cpu-copy-history',source,receipt,copy_report,ok=False)
        source.write_bytes(b'{"format":"plaid-cpu-copy-history-v0","instruction_events":[],"scalar_events":[]}')
        run('inspect-cpu-copy-history',source,receipt,copy_report,ok=False)
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
