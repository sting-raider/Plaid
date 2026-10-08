"""Regression: a disabled RAM observer must not reuse a shadowing header.

Compiler invocations are stubbed; actual compilation/CPU behavior is checked by
run.py. This tests recipe output and reuse, never a fabricated CPU oracle.
"""
from pathlib import Path
import importlib.util
import subprocess
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def main():
    spec = importlib.util.spec_from_file_location("builder",ROOT/"spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    def command_output(command, **kwargs):
        return builder.REV+"\n" if command[0] == "git" else "stub compiler for recipe-only test\n"
    def command_run(command, **kwargs):
        if "-o" in command: Path(command[command.index("-o")+1]).touch()
        return subprocess.CompletedProcess(command,0)
    with tempfile.TemporaryDirectory(prefix="ram-recipe-",dir=ROOT/"target") as temporary:
        output = Path(temporary)
        assert output.resolve().is_relative_to((ROOT/"target").resolve())
        with patch.object(builder.subprocess,"check_output",command_output), patch.object(builder.subprocess,"run",command_run):
            for enabled in (True,False,True):
                builder.build(ROOT/"spikes/013-ares-cache-tag/baseline.cpp",output,
                    raw_fetch_access=True,physical_fetch_access=True,rdram_burst_access=enabled)
                header = output/"include/n64/rdram/rdram.hpp"
                assert header.exists() == enabled
                if enabled:
                    source = header.read_text()
                    assert source.count("plaidRdramBurstObserver(true,") == 1
                    assert source.count("plaidRdramBurstObserver(false,") == 1
    print("PASS: recipe-only enabled/disabled/enabled reuse selects the correct RAM header; no CPU execution claimed")


if __name__ == "__main__": main()
