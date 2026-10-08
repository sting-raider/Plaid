"""Build pinned ares and test ordinary RDRAM backing witnesses for uncached CPU fetches."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / ".refs/ares"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
OUTPUT = ROOT / "target/ares-rdram-uncached-fetch-spike"
HERE = Path(__file__).resolve().parent


def build_instrumented():
    output = OUTPUT / "instrumented"
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip() == REV
    subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=REF, check=True)
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REF / "LICENSE", output / "LICENSE")
    driver = HERE / "driver.cpp"
    observer = HERE / "observer.hpp"
    compiler = subprocess.check_output(["g++", "--version"], text=True).splitlines()[0]
    inputs = {
        "revision": REV,
        "compiler": compiler,
        "driver": hashlib.sha256(driver.read_bytes()).hexdigest(),
        "observer": hashlib.sha256(observer.read_bytes()).hexdigest(),
        "recipe": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    exe = output / "oracle"
    manifest = output / "build.json"
    if manifest.exists() and exe.exists() and json.loads(manifest.read_text()) == inputs:
        return exe

    ram = (REF / "ares/n64/rdram/rdram.hpp").read_text()
    scalar_read = "      return Memory::Writable::read<Size>(address);"
    assert ram.count(scalar_read) == 1
    ram = ram.replace(scalar_read, """      u64 plaidValue = Memory::Writable::read<Size>(address);
      if(plaidRdramScalarObserver) plaidRdramScalarObserver(false, address, Size, (u32)device, plaidValue);
      return plaidValue;""")
    ram = """// Project-owned callbacks. Scalar callback is emitted only after a completed
// in-range identity-mapped ordinary RDRAM read; fetch callback brackets CPU::fetch.
using PlaidRdramScalarObserver = void (*)(bool, u32, u32, u32, u64);
inline PlaidRdramScalarObserver plaidRdramScalarObserver = nullptr;
using PlaidCpuFetchObserver = void (*)(bool, u64, u32, u32, bool, u32);
inline PlaidCpuFetchObserver plaidCpuFetchObserver = nullptr;
""" + ram
    destination = output / "include/n64/rdram/rdram.hpp"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(ram)

    memory = (REF / "ares/n64/cpu/memory.cpp").read_text()
    original_fetch = """auto CPU::fetch(PhysAccess access) -> maybe<u32> {
  step(1 * 2);
  if(!access) return nothing;
  u32 paddr = access.paddr;
  if(context.littleEndian()) paddr = reverseEndianPaddr<Word>(paddr);
  if(access.cache) return icache.fetch(access.vaddr, paddr, cpu);
  return busRead<Word>(paddr);
}"""
    instrumented_fetch = """auto CPU::fetch(PhysAccess access) -> maybe<u32> {
  step(1 * 2);
  if(!access) return nothing;
  u32 translatedPaddr = access.paddr;
  u32 paddr = translatedPaddr;
  if(context.littleEndian()) paddr = reverseEndianPaddr<Word>(paddr);
  if(plaidCpuFetchObserver) plaidCpuFetchObserver(true, access.vaddr, translatedPaddr, paddr, access.cache, 0);
  u32 value = access.cache ? icache.fetch(access.vaddr, paddr, cpu) : busRead<Word>(paddr);
  if(plaidCpuFetchObserver) plaidCpuFetchObserver(false, access.vaddr, translatedPaddr, paddr, access.cache, value);
  return value;
}"""
    assert memory.count(original_fetch) == 1
    memory = memory.replace(original_fetch, instrumented_fetch)
    (output / "cpu_memory.cpp").write_text(memory)

    includes = [output / "include"] + [REF / p for p in
        ("ares", "nall", ".", "thirdparty", "thirdparty/xxhash", "ares/n64/system")]
    include_flags = [part for path in includes for part in ("-I", str(path))]
    flags = ["-O1", "-std=c++20", "-msse4.1", "-DSLJIT_HAVE_CONFIG_PRE=1", "-DSLJIT_HAVE_CONFIG_POST=1"]

    core = (REF / "ares/ares/ares.cpp.in").read_text().replace(
        "#include <ares/resource/resource.cpp>", "// UI-only resources omitted in headless build.")
    for key, value in {
        "ARES_NAME": "Plaid pinned ares uncached-fetch oracle",
        "ARES_VERSION": REV,
        "ARES_LEGAL_COPYRIGHT_SHORT": "See upstream LICENSE",
        "ARES_WEBSITE": "ares-emu.net",
    }.items():
        core = core.replace(f"@{key}@", value)
    (output / "core.cpp").write_text(core)

    system = (REF / "ares/n64/system/system.cpp").read_text()
    assert system.count("    vulkan.load(node);") == 1
    system = system.replace("    vulkan.load(node);", "#if defined(VULKAN)\n    vulkan.load(node);\n#endif")
    (output / "system.cpp").write_text(system)

    cpu_source = (REF / "ares/n64/cpu/cpu.cpp").read_text()
    replacements = {"memory.cpp": output / "cpu_memory.cpp"}
    cpu_source = re.sub(r'#include "([^"]+)"', lambda match:
        f'#include "{replacements.get(match[1], REF / "ares/n64/cpu" / match[1])}"', cpu_source)
    (output / "cpu.cpp").write_text(cpu_source)

    unity = (REF / "ares/n64/n64.cpp").read_text()
    assert unity.count("#include <n64/system/system.cpp>") == 1
    unity = unity.replace("#include <n64/system/system.cpp>", f'#include "{output / "system.cpp"}"')
    assert unity.count("#include <n64/cpu/cpu.cpp>") == 1
    unity = unity.replace("#include <n64/cpu/cpu.cpp>", f'#include "{output / "cpu.cpp"}"')
    (output / "n64.cpp").write_text(unity)

    objects = []
    with (output / "build.log").open("w") as log:
        for name, source in [
            ("sljit", REF / "thirdparty/sljit/sljit_src/sljitLir.c"),
            ("libco", REF / "libco/libco.c"),
        ]:
            obj = output / f"{name}.o"
            subprocess.run(["gcc", "-O1", *include_flags,
                "-DSLJIT_HAVE_CONFIG_PRE=1", "-DSLJIT_HAVE_CONFIG_POST=1",
                "-c", str(source), "-o", str(obj)], check=True, stdout=log, stderr=subprocess.STDOUT)
            objects.append(obj)
        sources = [driver, output / "core.cpp", output / "n64.cpp",
            REF / "ares/component/processor/sm5k/sm5k.cpp",
            REF / "ares/ares/memory/fixed-allocator.cpp", REF / "nall/nall/nall.cpp",
            REF / "thirdparty/sljitAllocator.cpp"]
        try:
            subprocess.run(["g++", *flags, *include_flags, *map(str, sources), *map(str, objects),
                "-pthread", "-ldl", "-o", str(exe)], check=True, stdout=log, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            print("\n".join((output / "build.log").read_text().splitlines()[-60:]))
            raise
    manifest.write_text(json.dumps(inputs, indent=2) + "\n")
    return exe


def build_baseline():
    spec = importlib.util.spec_from_file_location("ares_builder", ROOT / "spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    return builder.build(HERE / "baseline.cpp", OUTPUT / "baseline",
                         extra_sources=(HERE / "driver.cpp", HERE / "observer.hpp"))


def pair_fetches(payload):
    scalars = payload["scalar_events"]
    fetches = payload["fetch_events"]
    assert len(fetches) % 2 == 0
    pairs = []
    for i in range(0, len(fetches), 2):
        begin, end = fetches[i], fetches[i + 1]
        assert begin["begin"] and not end["begin"]
        for key in ("phase", "vaddr", "translated_paddr", "bus_paddr", "cache"):
            assert begin[key] == end[key], (begin, end)
        exact = [e for e in scalars
                 if begin["ordinal"] < e["ordinal"] < end["ordinal"]
                 and not e["write"] and e["bytes"] == 4 and e["uncached_cpu"]
                 and e["address"] == begin["bus_paddr"] and e["value"] == end["value"]]
        witness = exact[0]["ordinal"] if not begin["cache"] and len(exact) == 1 else None
        pairs.append({
            "phase": begin["phase"], "vaddr": begin["vaddr"],
            "translated_paddr": begin["translated_paddr"], "bus_paddr": begin["bus_paddr"],
            "cache": begin["cache"], "value": end["value"], "witness_ordinal": witness,
            "between_scalars": [e["ordinal"] for e in scalars if begin["ordinal"] < e["ordinal"] < end["ordinal"]],
        })
    return pairs


def run():
    baseline_exe = build_baseline()
    instrumented_exe = build_instrumented()
    baseline_raw = subprocess.check_output([str(baseline_exe), "plain"], text=True, timeout=30)
    plain_raw = subprocess.check_output([str(instrumented_exe), "plain"], text=True, timeout=30)
    traced_raw = subprocess.check_output([str(instrumented_exe), "traced"], text=True, timeout=30)
    repeat_raw = subprocess.check_output([str(instrumented_exe), "traced"], text=True, timeout=30)
    assert traced_raw == repeat_raw
    baseline, plain, traced = map(json.loads, (baseline_raw, plain_raw, traced_raw))
    assert not baseline["scalar_events"] and not baseline["fetch_events"]
    assert not plain["scalar_events"] and not plain["fetch_events"]
    assert baseline["facts"] == plain["facts"] == traced["facts"]
    assert baseline["state"] == plain["state"] == traced["state"]
    assert traced["facts"]["cached_ori"] == 0x1357
    assert traced["facts"]["little_ori"] == 0x5678
    assert traced["facts"]["translated_ori"] == 0x1234
    assert traced["state"]["exception"] == 0

    pairs = pair_fetches(traced)
    p1 = [p for p in pairs if p["phase"] == 1]
    assert len(p1) == 2 and all(p["witness_ordinal"] is not None for p in p1), p1
    assert [(p["bus_paddr"], p["value"]) for p in p1] == [(0x6000, 0x8e080000), (0x6004, 0)], p1
    scalar1 = [e for e in traced["scalar_events"] if e["phase"] == 1]
    assert [(e["address"], e["value"]) for e in scalar1] == [(0x6000, 0x8e080000), (0x1000, 0), (0x6004, 0)], scalar1
    assert scalar1[1]["ordinal"] < next(e["ordinal"] for e in traced["fetch_events"] if e["phase"] == 1 and e["begin"] and e["vaddr"] == 0xffffffffa0006004)

    p2 = [p for p in pairs if p["phase"] == 2]
    assert len(p2) == 1 and p2[0]["cache"] and p2[0]["witness_ordinal"] is None, p2
    assert not [e for e in traced["scalar_events"] if e["phase"] == 2]

    p3 = [p for p in pairs if p["phase"] == 3]
    assert len(p3) == 1 and p3[0]["witness_ordinal"] is not None, p3
    assert (p3[0]["translated_paddr"], p3[0]["bus_paddr"], p3[0]["value"]) == (0x7000, 0x7004, 0x340a5678), p3
    scalar3 = [e for e in traced["scalar_events"] if e["phase"] == 3]
    assert [(e["address"], e["value"]) for e in scalar3] == [(0x7004, 0x340a5678)], scalar3

    for phase in (4, 5, 6):
        selected = [p for p in pairs if p["phase"] == phase]
        assert len(selected) == 1 and selected[0]["witness_ordinal"] is None, selected
        assert not [e for e in traced["scalar_events"] if e["phase"] == phase]
    p4 = next(p for p in pairs if p["phase"] == 4)
    assert p4["value"] == 0x34091234 and not p4["cache"]
    assert next(p for p in pairs if p["phase"] == 5)["value"] == 0
    assert next(p for p in pairs if p["phase"] == 6)["value"] == 0

    evidence = {
        "fetch_pairs": pairs,
        "scalar_events": traced["scalar_events"],
        "facts": traced["facts"],
        "state": traced["state"],
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results = {"baseline": baseline, "plain": plain, "traced": traced, "evidence": evidence}
    result_path = OUTPUT / "results.json"
    result_path.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    print("EVIDENCE_JSON=" + json.dumps(evidence, sort_keys=True, separators=(",", ":")))
    print("RESULT_SHA256=" + hashlib.sha256(result_path.read_bytes()).hexdigest())
    print("PASS: direct uncached identity-RDRAM fetches join to exact scalar reads; cached, translated, OOB, and failed mappings fail closed")


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", script], check=True)
    else:
        run()


if __name__ == "__main__":
    main()
