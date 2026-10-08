"""Recheck independent scalar/copy fixtures through the shared builder options."""
from pathlib import Path
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "target/ares-access-history-spike"


def load(name,path):
    spec = importlib.util.spec_from_file_location(name,path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def worker():
    builder = load("shared_builder",ROOT/"spikes/003-ares-oracle/run.py")
    for name,topic,old_output,options in (
        ("fetch","025-ares-rdram-uncached-fetch","ares-rdram-uncached-fetch-spike",{"fetch_boundary_access":True}),
        ("copy","020-ares-cpu-copy-transactions","ares-cpu-copy-transactions-spike",{"rdram_burst_access":True}),
    ):
        model = load(name,ROOT/f"spikes/{topic}/run.py")
        prior = json.loads((ROOT/f"target/{old_output}/results.json").read_text())["traced"]
        directory = OUTPUT/name
        model.OUTPUT = directory
        # Reuse the original independent fixture checks; only the build recipe changes.
        def build_instrumented():
            return builder.build(model.HERE/"driver.cpp",directory/"sensor",
                raw_fetch_access=True,physical_fetch_access=True,rdram_scalar_access=True,
                extra_sources=(model.HERE/"observer.hpp",),**options)
        model.build_instrumented = build_instrumented
        model.run()
        assert json.loads((directory/"results.json").read_text())["traced"] == prior
        print(f"PASS: shared {name} sensor retains the complete independently reproduced fixture JSON")


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(["wsl","-d","Ubuntu","--exec","python3",script],check=True)
    else: worker()


if __name__ == "__main__": main()
