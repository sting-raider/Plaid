"""Shared native pinned-ares oracle builds for analysis and differential tests.

The original builder owns instrumentation, license notices and the content cache.
All callers use the host compiler; no guest OS or path conversion is involved.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('plaid_ares_builder', ROOT / 'spikes/003-ares-oracle/run.py')
_builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_builder)
REV = _builder.REV
ORACLE = _builder.ORACLE
build = _builder.build


def default():
    """Authenticate/build the common CPU fixture oracle, using its shared cache."""
    return build(ROOT / 'spikes/096-native-slice/driver.cpp', ROOT / 'target/native-slice/oracle')


def execute(oracle, *arguments, **kwargs):
    """Run a native oracle, retaining subprocess byte/text and failure semantics."""
    oracle = Path(oracle)
    metadata = oracle.parent / 'build.json'
    if not oracle.is_file() or not metadata.is_file():
        raise RuntimeError('pinned ares oracle or build manifest is missing')
    if json.loads(metadata.read_text())['revision'] != REV:
        raise AssertionError(f'ares oracle is not pinned revision {REV}')
    return subprocess.run([str(oracle), *map(str, arguments)], **kwargs)


def run(image, exit_pc, *arguments, **kwargs):
    oracle = Path(os.environ['PLAID_ARES_ORACLE']) if 'PLAID_ARES_ORACLE' in os.environ else default()
    return execute(oracle, image, hex(exit_pc), *arguments, **kwargs)
