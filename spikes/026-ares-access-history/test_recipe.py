"""Test sensor option combinations/reuse without claiming reference execution."""
from pathlib import Path
import importlib.util
import subprocess
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def main():
    spec = importlib.util.spec_from_file_location("builder",ROOT/"spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    def command_output(command,**kwargs):
        return builder.REV+"\n" if command[0] == "git" else "recipe-only compiler stub\n"
    def command_run(command,**kwargs):
        if "-o" in command: Path(command[command.index("-o")+1]).touch()
        return subprocess.CompletedProcess(command,0)
    with tempfile.TemporaryDirectory(prefix="access-recipe-",dir=ROOT/"target") as temporary:
        directory = Path(temporary)
        assert directory.resolve().is_relative_to((ROOT/"target").resolve())
        with patch.object(builder.subprocess,"check_output",command_output),patch.object(builder.subprocess,"run",command_run):
            for burst,scalar,boundary in ((True,True,True),(False,True,False),(True,False,True),
                                          (False,False,False),(False,False,True),(True,True,False)):
                builder.build(ROOT/"spikes/013-ares-cache-tag/baseline.cpp",directory,
                    raw_fetch_access=True,physical_fetch_access=True,rdram_burst_access=burst,
                    rdram_scalar_access=scalar,fetch_boundary_access=boundary)
                ram = directory/"include/n64/rdram/rdram.hpp"
                assert ram.exists() == (burst or scalar)
                source = ram.read_text() if ram.exists() else ""
                for direction in ("true","false"):
                    assert source.count(f"plaidRdramBurstObserver({direction},") == int(burst)
                    assert source.count(f"plaidRdramScalarObserver({direction},") == int(scalar)
                memory = (directory/"cpu_memory.cpp").read_text()
                for direction in ("true","false"):
                    assert memory.count(f"plaidCpuFetchObserver({direction},") == int(boundary)
                assert memory.count("plaidFetchAccess = {paddr, access.cache};") == 1
    print("PASS: six shared sensor recipe/reuse combinations; compiler stub makes no CPU claim")


if __name__ == "__main__": main()
