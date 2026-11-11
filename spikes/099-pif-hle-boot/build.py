"""Build the state-dump tool with the stock pinned-ares reference (no observers)."""
from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('ares_oracle_builder', ROOT / 'spikes/003-ares-oracle/run.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
out = ROOT / 'target/pif-hle-boot'
print(builder.build(ROOT / "spikes/099-pif-hle-boot/dump.cpp", out, extra_sources=[ROOT / "scripts/ares_hle_boot.hpp", ROOT / "scripts/ares_hle_boot_tables.hpp"]))
