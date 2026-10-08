"""Build a separately licensed pinned core and check original CPU fixtures."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import shutil
import re

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / ".refs/ares"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
OUTPUT = ROOT / "target/ares-oracle-spike"


def build(driver, directory, raw_fetch_access=False, physical_fetch_access=False, extra_sources=()):
    output = Path(directory)
    assert subprocess.check_output(["git","rev-parse","HEAD"],cwd=REF,text=True).strip() == REV
    subprocess.run(["git","-c","core.autocrlf=true","diff","--quiet","HEAD"],cwd=REF,check=True)
    output.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(REF / "LICENSE", output / "LICENSE")
    driver = Path(driver)
    compiler = subprocess.check_output(["g++","--version"],text=True).splitlines()[0]
    inputs = {"revision":REV,"compiler":compiler,"driver":hashlib.sha256(driver.read_bytes()).hexdigest(),
        "raw_fetch_access":raw_fetch_access,
        "physical_fetch_access":physical_fetch_access,
        "extra_sources":{str(Path(p).relative_to(ROOT)):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in extra_sources},
        "fixture_driver":hashlib.sha256(Path(__file__).with_name("driver.cpp").read_bytes()).hexdigest(),
        "recipe":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    exe = output / "oracle"
    manifest = output / "build.json"
    if not manifest.exists() or json.loads(manifest.read_text()) != inputs or not exe.exists():
        flags = ["-O1","-std=c++20","-msse4.1","-DSLJIT_HAVE_CONFIG_PRE=1","-DSLJIT_HAVE_CONFIG_POST=1"]
        includes = [REF / p for p in ("ares","nall",".","thirdparty","thirdparty/xxhash","ares/n64/system")]
        if raw_fetch_access:
            # Expose existing debugger input through an accessor in a generated
            # header. No CPU fields, instruction code or object layout changes.
            header = (REF / "ares/n64/cpu/cpu.hpp").read_text()
            signature = "    auto disassemble(u32 address, u32 instruction) -> string;"
            assert header.count(signature) == 1
            header = header.replace(signature, signature + "\n    auto fetchedWord() const -> u32 { return instruction; }")
            if physical_fetch_access:
                header = "// Project-owned observer metadata; no CPU object-layout change.\nstruct PlaidFetchAccess { u32 physical; bool cached; };\ninline PlaidFetchAccess plaidFetchAccess;\n" + header
            destination = output / "include/n64/cpu/cpu.hpp"
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_text(header)
            includes.insert(0, output / "include")
        include_flags = [part for path in includes for part in ("-I",str(path))]
        core = (REF / "ares/ares/ares.cpp.in").read_text().replace("#include <ares/resource/resource.cpp>", "// UI-only resources omitted in headless build.")
        for key, value in {"ARES_NAME":"Plaid pinned ares oracle", "ARES_VERSION":REV,
                "ARES_LEGAL_COPYRIGHT_SHORT":"See upstream LICENSE", "ARES_WEBSITE":"ares-emu.net"}.items():
            core = core.replace(f"@{key}@", value)
        (output / "core.cpp").write_text(core)
        # The pin leaves one Vulkan load call unguarded in System::run. Guard
        # only that renderer call in a generated TU; CPU/RSP sources stay exact.
        system = (REF / "ares/n64/system/system.cpp").read_text()
        assert system.count("    vulkan.load(node);") == 1
        system = system.replace("    vulkan.load(node);", "#if defined(VULKAN)\n    vulkan.load(node);\n#endif")
        (output / "system.cpp").write_text(system)
        unity = (REF / "ares/n64/n64.cpp").read_text()
        assert unity.count("#include <n64/system/system.cpp>") == 1
        unity = unity.replace("#include <n64/system/system.cpp>", f'#include "{output / "system.cpp"}"')
        if physical_fetch_access:
            assert raw_fetch_access
            memory = (REF / "ares/n64/cpu/memory.cpp").read_text()
            marker = "  if(context.littleEndian()) paddr = reverseEndianPaddr<Word>(paddr);\n  if(access.cache) return icache.fetch(access.vaddr, paddr, cpu);"
            assert memory.count(marker) == 1
            memory = memory.replace(marker, marker.split("\n")[0] + "\n  plaidFetchAccess = {paddr, access.cache};\n" + marker.split("\n")[1])
            (output / "cpu_memory.cpp").write_text(memory)
            cpu = (REF / "ares/n64/cpu/cpu.cpp").read_text()
            assert cpu.count('#include "memory.cpp"') == 1
            # Relocating this TU changes quoted-include lookup. Resolve every
            # CPU include explicitly; system/serialization.cpp shares a name.
            cpu = re.sub(r'#include "([^"]+)"', lambda match:
                f'#include "{output / "cpu_memory.cpp" if match[1] == "memory.cpp" else REF / "ares/n64/cpu" / match[1]}"', cpu)
            (output / "cpu.cpp").write_text(cpu)
            assert unity.count("#include <n64/cpu/cpu.cpp>") == 1
            unity = unity.replace("#include <n64/cpu/cpu.cpp>", f'#include "{output / "cpu.cpp"}"')
        (output / "n64.cpp").write_text(unity)
        objects = []
        with (output / "build.log").open("w") as log:
            for name, source in [("sljit",REF / "thirdparty/sljit/sljit_src/sljitLir.c"),("libco",REF / "libco/libco.c")]:
                obj = output / f"{name}.o"
                subprocess.run(["gcc","-O1",*include_flags,"-DSLJIT_HAVE_CONFIG_PRE=1","-DSLJIT_HAVE_CONFIG_POST=1","-c",str(source),"-o",str(obj)],check=True,stdout=log,stderr=subprocess.STDOUT)
                objects.append(obj)
            sources = [driver,output / "core.cpp",output / "n64.cpp",REF / "ares/component/processor/sm5k/sm5k.cpp",
                REF / "ares/ares/memory/fixed-allocator.cpp",REF / "nall/nall/nall.cpp",REF / "thirdparty/sljitAllocator.cpp"]
            try:
                subprocess.run(["g++",*flags,*include_flags,*map(str,sources),*map(str,objects),"-pthread","-ldl","-o",str(exe)],check=True,stdout=log,stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError:
                print("\n".join((output / "build.log").read_text().splitlines()[-30:]))
                raise
        manifest.write_text(json.dumps(inputs,indent=2)+"\n")
    return exe


def worker():
    exe = build(Path(__file__).with_name("driver.cpp"), OUTPUT)
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
