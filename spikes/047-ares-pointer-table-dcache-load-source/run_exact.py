"""Execute run.py while shadowing cpu.cpp so its quoted dcache.cpp include is instrumented."""
from pathlib import Path
import importlib.util
import shutil

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("table_load_runner", HERE / "run.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)
_original_patch_dcache = runner.patch_dcache


def patch_dcache_and_cpu(output):
    _original_patch_dcache(output)
    source = (runner.REF / "ares/n64/cpu/cpu.cpp").read_text()
    marker = '#include "dcache.cpp"'
    assert source.count(marker) == 1
    generated_dcache = output / "include/n64/cpu/dcache.cpp"
    source = source.replace(marker, f'#include "{generated_dcache}"')
    destination = output / "include/n64/cpu/cpu.cpp"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(source)


runner.patch_dcache = patch_dcache_and_cpu
# This experiment is cheap compared with ambiguity.  Refuse to reuse an older
# instrumented binary whose manifest predates this generated cpu.cpp shadow.
shutil.rmtree(runner.OUTPUT / "instrumented", ignore_errors=True)
runner.run()
