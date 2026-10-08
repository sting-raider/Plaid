"""Optional queue/request/dispatch generation and reuse; no CPU claim."""
from pathlib import Path
import importlib.util
import subprocess
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]


def main():
    spec=importlib.util.spec_from_file_location("builder",ROOT/"spikes/003-ares-oracle/run.py")
    builder=importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    def output(command,**kwargs):
        return builder.REV+"\n" if command[0]=="git" else "recipe-only compiler stub\n"
    def run(command,**kwargs):
        if "-o" in command: Path(command[command.index("-o")+1]).touch()
        return subprocess.CompletedProcess(command,0)
    with tempfile.TemporaryDirectory(prefix="pi-queue-recipe-",dir=ROOT/"target") as temporary:
        destination=Path(temporary)
        with patch.object(builder.subprocess,"check_output",output),patch.object(builder.subprocess,"run",run):
            for enabled in (True,False,True):
                builder.build(ROOT/"spikes/035-ares-pi-queue-dispatch-context/baseline.cpp",destination,
                              raw_fetch_access=True,physical_fetch_access=True,pi_dma_access=True,queue_access=enabled)
                cpu=(destination/"cpu.cpp").read_text()
                header=(destination/"include/n64/cpu/cpu.hpp").read_text()
                pi=(destination/"pi.cpp").read_text()
                assert (destination/"include/nall/priority-queue.hpp").exists()==enabled
                assert ("PlaidQueueDispatchScope plaidDispatchScope(event)" in cpu)==enabled
                assert ("inline PlaidPiIoDmaObserver" in header)==enabled
                assert (str(destination/"pi_io.cpp") in pi)==enabled
                if enabled:
                    io=(destination/"pi_io.cpp").read_text()
                    assert io.count("plaidPiIoDmaObserver(true,")==2
                    assert io.count("plaidPiIoDmaObserver(false,")==2
                    for direction in ("Read","Write"):
                        assert io.count(f"cpu.queueInsert(Queue::PI_DMA_{direction},")==1
                        assert io.count(f"    dma{direction}();")==1
    print("PASS: opt-in queue/request/CPU dispatch generation preserves default source and reuse")


if __name__=="__main__": main()
