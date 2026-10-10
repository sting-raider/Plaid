"""Execute run.py while shadowing cpu.cpp so its quoted dcache.cpp include is instrumented."""
from pathlib import Path
import importlib.util
import re
import shutil

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("table_load_runner", HERE / "run.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)
_original_patch_dcache = runner.patch_dcache


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


runner.patch_dcache = patch_dcache_and_cpu
# Refuse to reuse an older instrumented binary whose generated source recipe may
# have been different. Baseline caching remains safe because it is unmodified.
shutil.rmtree(runner.OUTPUT / "instrumented", ignore_errors=True)
runner.run()
