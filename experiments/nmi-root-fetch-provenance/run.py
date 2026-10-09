#!/usr/bin/env python3
"""Build exact pinned ares and compose NMI entry with actual PIF-ROM fetch provenance."""
from __future__ import annotations
import hashlib, importlib.util, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/nmi-root-fetch-provenance"
PIN = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
KNOWN_NTSC_SHA256 = "fa7b09795ef1e54461e59f6f2d902368133e3f1cd980e34383e6a780d74beffd"
ROOT_PC = 0xFFFFFFFFBFC00000
ENTRY_PC = 0xFFFFFFFFA0000104
MODES = (
    "transfer_only",
    "persistent_two",
    "clear_fetch",
    "clear_busy_equal",
    "clear_lockout",
    "foreign_read_then_persistent",
    "foreign_read_then_clear_fetch",
)

def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()

def source_guards(ref: Path):
    cpu = ref / "ares/n64/cpu/cpu.cpp"
    exc = ref / "ares/n64/cpu/exceptions.cpp"
    pif = ref / "ares/n64/pif/io.cpp"
    c, e, p = cpu.read_text(), exc.read_text(), pif.read_text()
    nmi = c.index("if (scc.nmiPending)")
    fetch = c.index("auto access = devirtualize<Read, Word>(ipu.pc);")
    assert nmi < fetch
    block = c[nmi:fetch]
    assert "exception.nmi();" in block and "return true;" in block
    assert "scc.nmiPending = 0" not in c
    assert "self.pipeline.setPc(0xffff'ffff'bfc0'0000);" in e
    assert "return rom.read<Word>(address);" in p
    return {"cpu":sha(cpu),"exceptions":sha(exc),"pif_io":sha(pif)}

def run_one(exe: Path, mode: str, firmware: Path):
    raw = subprocess.check_output([str(exe), mode, str(firmware)], text=True, timeout=30)
    rows = [line for line in raw.splitlines() if line.startswith("{")]
    assert len(rows)==1, (mode,raw)
    return json.loads(rows[0])

def event(state):
    assert len(state["fetches"])==1, state["fetches"]
    return state["fetches"][0]

def verify(rows, fw0):
    base, inst, repeat = rows["baseline"], rows["instrumented"], rows["repeat"]
    for mode in MODES:
        assert inst[mode] == repeat[mode], mode
        assert inst[mode]["machine"] == base[mode]["machine"], mode
        assert inst[mode]["first_pc"] == base[mode]["first_pc"] == ROOT_PC
        assert inst[mode]["first_errorepc"] == base[mode]["first_errorepc"] == ENTRY_PC
        assert inst[mode]["first_pending"] == base[mode]["first_pending"] == 1

    one = inst["transfer_only"]
    assert one["fetches"] == [] and one["backing_reads"] == 0
    assert one["machine"]["pc"] == ROOT_PC and one["machine"]["pending"] == 1

    two = inst["persistent_two"]
    assert two["fetches"] == [] and two["backing_reads"] == 0
    assert two["machine"]["pc"] == ROOT_PC and two["machine"]["pending"] == 1
    assert two["machine"]["errorepc"] == ROOT_PC

    real = inst["clear_fetch"]
    ev = event(real)
    assert ev["vaddr"] == ROOT_PC and ev["physical"] == 0x1FC00000 and not ev["cached"] and ev["ended"]
    assert ev["returned"] == fw0
    assert ev["witness"] == {"kind":"pif_rom","offset":0,"word":fw0}
    assert real["backing_reads"] == 1 and real["unattributed_backing_reads"] == 0

    latch = inst["clear_busy_equal"]
    ev = event(latch)
    assert ev["returned"] == fw0 and ev["witness"] is None
    assert latch["backing_reads"] == 0 and latch["machine"]["si_io_busy"] == 1

    lock = inst["clear_lockout"]
    ev = event(lock)
    assert ev["witness"] is None and lock["backing_reads"] == 0

    stale = inst["foreign_read_then_persistent"]
    assert stale["fetches"] == []
    assert stale["backing_reads"] == 1 and stale["unattributed_backing_reads"] == 1
    assert stale["machine"]["pc"] == ROOT_PC and stale["machine"]["errorepc"] == ROOT_PC

    mixed = inst["foreign_read_then_clear_fetch"]
    ev = event(mixed)
    assert ev["witness"] == {"kind":"pif_rom","offset":0,"word":fw0}
    assert mixed["backing_reads"] == 2 and mixed["unattributed_backing_reads"] == 1

def main():
    ref = ROOT / ".refs/ares"
    revision = subprocess.check_output(["git","rev-parse","HEAD"],cwd=ref,text=True).strip()
    assert revision == PIN, revision
    subprocess.run(["git","diff","--quiet","HEAD"],cwd=ref,check=True)
    guards = source_guards(ref)
    firmware = ref / "ares/System/Nintendo 64/pif.ntsc.rom"
    assert sha(firmware) == KNOWN_NTSC_SHA256
    fw0 = int.from_bytes(firmware.read_bytes()[:4],"big")

    base_builder = load("nmi_root_base_builder", ROOT/"spikes/003-ares-oracle/run.py")
    pif_builder = load("nmi_root_pif_builder", ROOT/"experiments/pif-rom-backing/run_ares.py")
    assert base_builder.REV == PIN and pif_builder.PIN == PIN
    OUTPUT.mkdir(parents=True,exist_ok=True)
    baseline = base_builder.build(HERE/"driver.cpp", OUTPUT/"baseline")
    patched = pif_builder.patched_builder(OUTPUT/"generated")
    instrumented = patched.build(HERE/"driver.cpp", OUTPUT/"instrumented", raw_fetch_access=True, physical_fetch_access=True, pif_rom_access=True)

    rows = {"baseline":{},"instrumented":{},"repeat":{}}
    for mode in MODES:
        rows["baseline"][mode]=run_one(baseline,mode,firmware)
        rows["instrumented"][mode]=run_one(instrumented,mode,firmware)
        rows["repeat"][mode]=run_one(instrumented,mode,firmware)
    verify(rows,fw0)
    body={"plaid_base":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),"ares_revision":PIN,"firmware_sha256":KNOWN_NTSC_SHA256,"source_sha256":guards,"firmware_word0":fw0,"modes":list(MODES),**rows}
    out=OUTPUT/"results.json";out.write_text(json.dumps(body,indent=2,sort_keys=True)+"\n")
    print("RESULT_SHA256="+sha(out))
    print("PASS exact-pin NMI root transfer/fetch/PIF backing composition across persistent, cleared, latch, lockout and foreign-read adversaries")

if __name__=="__main__": sys.exit(main())
