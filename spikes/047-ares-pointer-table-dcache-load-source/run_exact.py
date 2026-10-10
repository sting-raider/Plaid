"""Execute run.py while shadowing cpu.cpp so its quoted dcache.cpp include is instrumented."""
from pathlib import Path
import importlib.util
import json
import re
import shutil

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("table_load_runner", HERE / "run.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)
_original_patch_dcache = runner.patch_dcache
_original_run_case = runner.run_case
_original_build_instrumented = runner.build_instrumented


def patch_dcache_and_cpu(output):
    _original_patch_dcache(output)
    source = (runner.REF / "ares/n64/cpu/cpu.cpp").read_text()
    cpu_dir = runner.REF / "ares/n64/cpu"
    generated_dcache = output / "include/n64/cpu/dcache.cpp"

    def route(match):
        name = match.group(1)
        target = generated_dcache if name == "dcache.cpp" else cpu_dir / name
        return f'#include "{target}"'

    routed, count = re.subn(r'#include "([^"]+\.cpp)"', route, source)
    assert count >= 10
    assert str(generated_dcache) in routed
    destination = output / "include/n64/cpu/cpu.cpp"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(routed)


def build_instrumented_with_provenance():
    exe, inputs = _original_build_instrumented()
    inputs = dict(inputs)
    inputs["wrapper"] = runner.sha(Path(__file__).resolve())
    inputs["upstream_cpu"] = runner.sha(runner.REF / "ares/n64/cpu/cpu.cpp")
    return exe, inputs


def diagnostic_run_case(exe, mode, scenario):
    raw, doc = _original_run_case(exe, mode, scenario)
    # driver.cpp stores the controlled code offset. Convert it to the actual
    # KSEG0 guest PC before any cross-build comparisons or source joins.
    doc["facts"]["dispatch_pc"] |= 0x80000000
    if mode == "traced":
        print("TRACE_DREADS=" + json.dumps({
            "scenario": scenario,
            "dispatch_pc": doc["facts"]["dispatch_pc"],
            "dreads": doc["events"]["dreads"],
            "dwrites": doc["events"]["dwrites"],
            "scalars": doc["events"]["scalars"],
        }, sort_keys=True), flush=True)
    return raw, doc


runner.patch_dcache = patch_dcache_and_cpu
runner.build_instrumented = build_instrumented_with_provenance
runner.run_case = diagnostic_run_case
# Refuse to reuse an older instrumented binary whose generated source recipe may
# have been different. Baseline caching remains safe because it is unmodified.
shutil.rmtree(runner.OUTPUT / "instrumented", ignore_errors=True)
runner.run()
