"""Retain the Linux oracle's full vector state across native compiler ABIs."""
import hashlib
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import ares_oracle


def main():
    spec = importlib.util.spec_from_file_location('rsp_fixture', ROOT / 'spikes/097-rsp-slice/run.py')
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    out = ROOT / 'target/rsp-oracle-contract'
    out.mkdir(parents=True, exist_ok=True)
    imem, _ = fixture.assemble(fixture.PROGRAMS['vec0'])
    (out / 'imem.bin').write_bytes(imem)
    (out / 'dmem.bin').write_bytes(fixture.dmem_image())
    oracle = ares_oracle.build(ROOT / 'spikes/097-rsp-slice/driver.cpp', out / 'oracle')
    result = ares_oracle.execute(oracle, out / 'imem.bin', out / 'dmem.bin', hex(fixture.IMEM),
                                 capture_output=True, check=True, timeout=120)
    # Independently retained pinned Linux output: PC, scalar/vector registers,
    # accumulator, flags, IMEM, DMEM and RDRAM. No text normalization is allowed.
    expected = '304ef265a806278b986b58947887e43c9ffc0e57baffe5c6e9a52534cb3fc0c2'
    assert hashlib.sha256(result.stdout).hexdigest() == expected, 'RSP oracle byte/state mismatch'
    assert not result.stderr
    print('PASS native RSP oracle: full vector state and raw bytes match pinned Linux receipt')


if __name__ == '__main__':
    main()
