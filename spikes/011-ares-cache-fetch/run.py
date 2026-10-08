"""Check selected cache context while preserving earlier boot-stream goldens."""
from pathlib import Path
import argparse
import importlib.util
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "target/ares-cache-fetch-spike"


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--budget",type=int,default=1000000)
    budget = parser.parse_args().budget
    assert 0 < budget <= 10000000
    if os.name == "nt":
        script = subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(["wsl","-d","Ubuntu","--exec","python3",script,*sys.argv[1:]],check=True)
    else:
        spec = importlib.util.spec_from_file_location("boot",ROOT/"spikes/008-ares-pif-boot/run.py")
        boot = importlib.util.module_from_spec(spec); spec.loader.exec_module(boot)
        profile = {"firmware_sha256":boot.FIRMWARE_SHA,"firmware_size":1984,
            "region":"ntsc","cic":"CIC-NUS-6102","rdram_size":8388608,
            "deterministic_entropy":True,"pif_processor":"reference_hle","pif_checksum_enforced":True}
        results = boot.worker(budget,driver=Path(__file__).with_name("driver.cpp"),output_root=OUTPUT,
            boot_inputs=profile,cache_policy="selected_icache_line_at_prologue")
        if budget == 1000000:
            assert results["v4_projection_sha256"] == "38a0781c763a110ca419af65bf9f1a19ed96cd9282e01b2545486d9d865bd937"
            assert results["trace_sha256"] == "c0dcae4870aaec1b30097d7fd95f2b6214f043e2ac1dea6366b1814655ce4ce9"
            assert results["cached_fetches"] == 400954 and results["unique_resident_snapshots"] == 32
        if budget == 10000000:
            assert results["v4_projection_sha256"] == "d46c9c99245c65cb2b671b182da0a247006b077026000ac2b29d5df786644027"


if __name__ == "__main__": main()
