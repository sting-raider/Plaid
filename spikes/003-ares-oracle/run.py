"""Build a separately licensed pinned core and check original CPU fixtures."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import shutil

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / ".refs/ares"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
OUTPUT = ROOT / "target/ares-oracle-spike"


def worker():
    assert subprocess.check_output(["git","rev-parse","HEAD"],cwd=REF,text=True).strip() == REV
    subprocess.run(["git","-c","core.autocrlf=true","diff","--quiet","HEAD"],cwd=REF,check=True)
    OUTPUT.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(REF / "LICENSE", OUTPUT / "LICENSE")
    driver = Path(__file__).with_name("driver.cpp")
    compiler = subprocess.check_output(["g++","--version"],text=True).splitlines()[0]
    inputs = {"revision":REV,"compiler":compiler,"driver":hashlib.sha256(driver.read_bytes()).hexdigest(),
        "recipe":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    exe = OUTPUT / "oracle"
    manifest = OUTPUT / "build.json"
    if not manifest.exists() or json.loads(manifest.read_text()) != inputs or not exe.exists():
        flags = ["-O1","-std=c++20","-msse4.1","-DSLJIT_HAVE_CONFIG_PRE=1","-DSLJIT_HAVE_CONFIG_POST=1"]
        includes = [REF / p for p in ("ares","nall",".","thirdparty","thirdparty/xxhash","ares/n64/system")]
        include_flags = [part for path in includes for part in ("-I",str(path))]
        core = (REF / "ares/ares/ares.cpp.in").read_text().replace("#include <ares/resource/resource.cpp>", "// UI-only resources omitted in headless build.")
        for key, value in {"ARES_NAME":"Plaid pinned ares oracle", "ARES_VERSION":REV,
                "ARES_LEGAL_COPYRIGHT_SHORT":"See upstream LICENSE", "ARES_WEBSITE":"ares-emu.net"}.items():
            core = core.replace(f"@{key}@", value)
        (OUTPUT / "core.cpp").write_text(core)
        # The pin leaves one Vulkan load call unguarded in System::run. Guard
        # only that renderer call in a generated TU; CPU/RSP sources stay exact.
        system = (REF / "ares/n64/system/system.cpp").read_text()
        assert system.count("    vulkan.load(node);") == 1
        system = system.replace("    vulkan.load(node);", "#if defined(VULKAN)\n    vulkan.load(node);\n#endif")
        (OUTPUT / "system.cpp").write_text(system)
        unity = (REF / "ares/n64/n64.cpp").read_text()
        assert unity.count("#include <n64/system/system.cpp>") == 1
        unity = unity.replace("#include <n64/system/system.cpp>", f'#include "{OUTPUT / "system.cpp"}"')
        (OUTPUT / "n64.cpp").write_text(unity)
        objects = []
        with (OUTPUT / "build.log").open("w") as log:
            for name, source in [("sljit",REF / "thirdparty/sljit/sljit_src/sljitLir.c"),("libco",REF / "libco/libco.c")]:
                obj = OUTPUT / f"{name}.o"
                subprocess.run(["gcc","-O1",*include_flags,"-DSLJIT_HAVE_CONFIG_PRE=1","-DSLJIT_HAVE_CONFIG_POST=1","-c",str(source),"-o",str(obj)],check=True,stdout=log,stderr=subprocess.STDOUT)
                objects.append(obj)
            sources = [driver,OUTPUT / "core.cpp",OUTPUT / "n64.cpp",REF / "ares/component/processor/sm5k/sm5k.cpp",
                REF / "ares/ares/memory/fixed-allocator.cpp",REF / "nall/nall/nall.cpp",REF / "thirdparty/sljitAllocator.cpp"]
            try:
                subprocess.run(["g++",*flags,*include_flags,*map(str,sources),*map(str,objects),"-pthread","-ldl","-o",str(exe)],check=True,stdout=log,stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError:
                print("\n".join((OUTPUT / "build.log").read_text().splitlines()[-30:]))
                raise
        manifest.write_text(json.dumps(inputs,indent=2)+"\n")
    results = {}
    for case in ("cartridge","linked","unaligned","slot_exception"):
        first = subprocess.check_output([str(exe),case],text=True,timeout=10)
        assert first == subprocess.check_output([str(exe),case],text=True,timeout=10)
        results[case] = json.loads(first)
    cartridge = results["cartridge"]
    assert cartridge["pc"] == 0xb0001014 and cartridge["exception"] == 0
    assert [cartridge["regs"][r] for r in (8,16,17,18,19,31)] == [-1342173152,5,3,7,2,-1342173168]
    linked = results["linked"]
    assert linked["pc"] == 0xa000000c and linked["regs"][4] == 1 and linked["exception"] == 0
    assert linked["memory"] == 0x123456789abcdef1 and linked["lladdr"] == 0x200
    for case, bd in (("unaligned",0),("slot_exception",1)):
        state = results[case]
        assert (state["exception"],state["bd"],state["epc"],state["badva"],state["pc"]) == (
            4, bd, 0xffffffffa0000000, 0xffffffffa0002001, 0xbfc00380), state
    for case, state in results.items():
        expected = [0] * 32
        if case == "cartridge":
            for register, value in zip((8,16,17,18,19,31),(-1342173152,5,3,7,2,-1342173168)):
                expected[register] = value
            assert state["memory"] == 0
        else:
            expected[3] = -1610604544
            if case == "linked": expected[4] = 1
            else: assert state["memory"] == 0x123456789abcdef0
        assert state["regs"] == expected and state["hi"] == state["lo"] == 0, (case,state)
    sys.path.insert(0, str(ROOT / "scripts"))
    import test_mupen_execution as mupen
    subprocess.run([sys.executable,str(ROOT / "scripts/prepare_mupen.py")],check=True)
    comparison = OUTPUT / "mupen"
    comparison.mkdir(exist_ok=True)
    for scenario in mupen.SCENARIOS:
        data = bytearray(8192)
        data[:4] = bytes.fromhex("80371240")
        for offset, word in mupen.program(scenario).items():
            data[64+offset:68+offset] = word.to_bytes(4, "big")
        (comparison / f"{scenario}.z64").write_bytes(data)
    mupen.worker(comparison)
    for scenario in mupen.SCENARIOS:
        raw = subprocess.check_output([str(exe),"fixture",str(comparison / f"{scenario}.z64")],text=True,timeout=10)
        assert raw == subprocess.check_output([str(exe),"fixture",str(comparison / f"{scenario}.z64")],text=True,timeout=10)
        state = json.loads(raw)
        shared = {key:state[key] for key in ("pc","regs","hi","lo")}
        for mode, other in json.loads((comparison / f"{scenario}-states.json").read_text()).items():
            assert shared == other, (scenario,mode,shared,other)
        assert state["exception"] == 0, (scenario,state)
        results[scenario] = state
    (OUTPUT / "results.json").write_text(json.dumps(results,indent=2)+"\n")
    print(f"PASS: four ares capability fixtures and {len(mupen.SCENARIOS)} independent CPU comparisons; repeated states match")


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(["wsl","-d","Ubuntu","--exec","python3",script],check=True)
    else: worker()


if __name__ == "__main__": main()
