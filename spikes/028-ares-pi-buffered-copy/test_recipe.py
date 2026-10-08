"""Check PI optional generation/reuse; compiler stubs are not CPU evidence."""
from pathlib import Path
import importlib.util
import subprocess
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def main():
    spec = importlib.util.spec_from_file_location("builder",ROOT/"spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    def command_output(command,**kwargs):
        return builder.REV+"\n" if command[0] == "git" else "recipe-only compiler stub\n"
    def command_run(command,**kwargs):
        if "-o" in command: Path(command[command.index("-o")+1]).touch()
        return subprocess.CompletedProcess(command,0)
    with tempfile.TemporaryDirectory(prefix="pi-copy-recipe-",dir=ROOT/"target") as temporary:
        output = Path(temporary)
        assert output.resolve().is_relative_to((ROOT/"target").resolve())
        with patch.object(builder.subprocess,"check_output",command_output),patch.object(builder.subprocess,"run",command_run):
            for enabled in (True,False,True):
                builder.build(ROOT/"spikes/028-ares-pi-buffered-copy/baseline.cpp",output,
                    raw_fetch_access=True,physical_fetch_access=True,pi_dma_access=enabled)
                unity = (output/"n64.cpp").read_text()
                header = (output/"include/n64/cpu/cpu.hpp").read_text()
                assert ('#include <n64/pi/pi.cpp>' in unity) == (not enabled)
                assert ("inline PlaidPiDmaObserver plaidPiDmaObserver" in header) == enabled
                if enabled:
                    dma = (output/"pi_dma.cpp").read_text()
                    assert dma.count("plaidPiDmaObserver(3,") == 1
                    assert dma.count("plaidPiDmaObserver(4,") == dma.count("plaidPiDmaObserver(5,") == 3
                    assert dma.count("plaidPiDmaObserver(8,") == 1
    print("PASS: optional PI sensor generation/reuse preserves default PI source and all three byte-write sites")


if __name__ == "__main__": main()
