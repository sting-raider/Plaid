"""Compose existing exact-source SP word hooks with scoped RSP instruction/DMEM hooks."""
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[2]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def generate(ref, out):
    ref, out = Path(ref), Path(out)
    sp = _load("plaid_sp_prepare", ROOT / "spikes/039-ares-cpu-sp-fetch/prepare.py")
    rsp = _load("plaid_rsp_prepare", ROOT / "spikes/042-ares-rsp-dmem-history/prepare.py")
    sp.generate(ref, out)
    rsp.generate(ref, out, sp_backing=True)
