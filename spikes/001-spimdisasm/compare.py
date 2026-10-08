"""Disposable pinned spimdisasm vs Plaid discovery comparison on original bytes.

Windows runs the Python reference worker under WSL Ubuntu; Plaid checks run on
the calling host. Linux needs GCC and Python development headers, which may be
provided by PLAID_PYTHON_DEPS (an extracted prefix). All outputs stay in target/.
No production dependency or function-boundary guarantee is introduced.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import sysconfig

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "target/spimdisasm-spike"
SPIM = "4b5d4c68eeb9f9eae14b3bb713971433ae2c3c43"
RABBIT = "724a49a5b4dbfb99f1a9e6992e63964fd29c90c8"
BASE = 0x80000000


def fixtures():
    calls = [0]*12
    calls[:6] = [0x0c000008, 0, 0x08000004, 0, 0x08000004, 0]
    calls[8:] = [0x24020001, 0x03e00008, 0, 0]
    indirect = [0]*20
    indirect[:6] = [0x3c088000, 0x35080040, 0x01000008, 0, 0x03e00008, 0]
    indirect[16:18] = [0x08000010, 0]
    table = [0]*67
    table[:10] = [0x2c890003, 0x11200016, 0, 0x3c088000, 0x25080100,
                  0x00045080, 0x010a4021, 0x8d080000, 0x01000008, 0]
    for offset in (0x40, 0x50, 0x60): table[offset//4] = 0x08000000 | offset//4
    table[64:] = [0x80000040, 0x80000050, 0x80000040]
    truncated = [0x03e00008]  # Missing return delay slot.
    return {"calls":(calls,len(calls)*4), "constant_and_unreachable":(indirect,len(indirect)*4),
            "guarded_table":(table,256), "truncated":(truncated,4)}


def worker():
    reference = ROOT / ".refs/rabbitizer"
    deps = Path(os.environ.get("PLAID_PYTHON_DEPS", ROOT / "target/reference-tools/python-root"))
    python_dir = f"python{sys.version_info.major}.{sys.version_info.minor}"
    extension = OUT / "rabbitizer.abi3.so"
    sources = sorted((reference / "rabbitizer").rglob("*.c")) + sorted((reference / "src").rglob("*.c"))
    command = ["gcc", "-shared", "-fPIC", "-std=c11", "-O1", "-DPy_LIMITED_API=0x03040000"]
    for directory in (reference / "include", reference / "rabbitizer", reference / "tables",
                      deps / "usr/include" / python_dir, deps / "usr/include",
                      Path("/usr/include") / python_dir):
        command += ["-I",str(directory)]
    manifest = OUT / "binding-build.json"
    inputs = {"pin":RABBIT,"abi":sysconfig.get_config_var("SOABI"),
        "compiler":subprocess.check_output(["gcc","--version"],text=True).splitlines()[0],
        "recipe":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    if not extension.exists() or not manifest.exists() or json.loads(manifest.read_text()) != inputs:
        with (OUT / "build.log").open("w") as log:
            built = subprocess.run([*command,*map(str,sources),"-o",str(extension)],stdout=log,stderr=subprocess.STDOUT,timeout=90)
        if built.returncode:
            raise RuntimeError("Rabbitizer binding build failed: " + "\n".join((OUT/"build.log").read_text().splitlines()[-20:]))
        manifest.write_text(json.dumps(inputs,indent=2)+"\n")
    sys.path[:0] = [str(OUT),str(ROOT / ".refs/spimdisasm")]
    import rabbitizer
    import spimdisasm
    from spimdisasm import common, mips
    result = {"spimdisasm_pin":SPIM,"rabbitizer_pin":RABBIT,"python":sys.version.split()[0],
              "spimdisasm_version":spimdisasm.__version__,"fixtures":{}}
    for name,(words,text_end) in fixtures().items():
        data = b"".join(w.to_bytes(4,"big") for w in words)
        context = common.Context()
        context.changeGlobalSegmentRanges(0,len(data),BASE,BASE+len(data))
        text = mips.sections.SectionText(context,0,text_end,BASE,name,data,0,None)
        text.analyze()
        rodata = None
        if text_end < len(data):
            rodata = mips.sections.SectionRodata(context,text_end,len(data),BASE+text_end,name,data,0,None)
            rodata.analyze()
        hints = [{"start":s.vram,"size":s.sizew*4,"name":s.getName(),"references":sorted(s.referencedVrams)} for s in text.symbolList]
        symbols = [{"address":address,"type":str(symbol.getTypeSpecial()),"jump_table":symbol.isJumpTable()}
                   for address,symbol in sorted(context.globalSegment.symbols.items())]
        result["fixtures"][name] = {"sha256":hashlib.sha256(data).hexdigest(),"text_end":text_end,
            "functions":hints,"symbols":symbols,"assembly":text.disassemble()}
    (OUT / "reference.json").write_text(json.dumps(result,indent=2)+"\n")


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for name,pin in (("spimdisasm",SPIM),("rabbitizer",RABBIT)):
        actual = subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT/".refs"/name,text=True).strip()
        if actual != pin: raise SystemExit(f"{name} differs from pin")
        if subprocess.run(["git","diff","--quiet","HEAD"],cwd=ROOT/".refs"/name,capture_output=True).returncode:
            raise SystemExit(f"{name} has tracked edits; refusing mixed source")
    if len(sys.argv)==2 and sys.argv[1]=="--worker": worker(); return
    if os.name=="nt":
        path = subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(["wsl","-d","Ubuntu","--exec","python3",path,"--worker"],check=True,timeout=120)
    else: worker()
    cargo = shutil.which("cargo") or str(Path.home()/".cargo/bin/cargo.exe")
    reference = json.loads((OUT/"reference.json").read_text())
    comparison = {}
    for name,(words,text_end) in fixtures().items():
        payload = b"".join(w.to_bytes(4,"big") for w in words)
        rom = bytearray(64)+payload
        rom[:4] = bytes.fromhex("80371240")
        source = OUT/f"{name}.z64"
        source.write_bytes(rom)
        mapped = OUT/f"{name}-map.json"
        subprocess.run([cargo,"run","--quiet","-p","plaid","--","discover",str(source),"64",hex(BASE),str(len(payload)),hex(BASE),str(mapped)],cwd=ROOT,check=True)
        program = json.loads(mapped.read_text())
        functions = [f["start"] for f in reference["fixtures"][name]["functions"]]
        blocks = sorted(b["start"]["pc"] for b in program["blocks"])
        candidates = sorted({pair[0]["pc"] for s in program["indirect_sites"] for pair in s["candidates"]})
        hinted_words = {pc for f in reference["fixtures"][name]["functions"] for pc in range(f["start"],f["start"]+f["size"],4)}
        reachable_words = {pc for b in program["blocks"] for pc in range(b["start"]["pc"],b["start"]["pc"]+b["size"],4)}
        comparison[name] = {"function_hints":functions,"reachable_blocks":blocks,"indirect_candidates":candidates,
                            "unresolved":sorted({u["kind"] for u in program["unresolved"]}),
                            "hinted_words_outside_reach":sorted(hinted_words-reachable_words)}
        if name=="calls": assert BASE+0x20 in functions and BASE+0x20 in blocks
        if name=="constant_and_unreachable":
            assert BASE+0x40 in candidates and BASE+0x10 not in reachable_words
            assert BASE+0x10 in comparison[name]["hinted_words_outside_reach"]
        if name=="guarded_table":
            assert candidates==[BASE+0x40,BASE+0x50]
            assert all(s["closed_proof"] is None for s in program["indirect_sites"])
            assert any(s["address"]==BASE+256 and s["jump_table"] for s in reference["fixtures"][name]["symbols"])
        if name=="truncated": assert "unsupported_delay_slot" in comparison[name]["unresolved"]
    (OUT/"comparison.json").write_text(json.dumps(comparison,indent=2)+"\n")
    print(json.dumps(comparison,indent=2))


if __name__=="__main__": main()
