"""Counterfactual-PC source exploration; never a production source certificate.

An explicit caller-supplied root replaces PC once during a pinned reset replay.
All exception, TLB, DMA and instruction behavior remains in the reference core.
Outputs stay in ignored target/. No result is installed in a ProgramMap/loads file.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from ares_boot import capture_many


def probe_driver():
    source = (ROOT / 'scripts/ares_boot.cpp').read_text()
    include = '#include "../spikes/003-ares-oracle/driver.cpp"'
    assert source.count(include) == 1
    source = source.replace(include, f'#include "{(ROOT / "spikes/003-ares-oracle/driver.cpp").as_posix()}"')
    marker = '  u32 vis = 0;'
    assert source.count(marker) == 1
    source = source.replace(marker, '''  bool probeApplied = false;
  u32 probeAnchor = std::strtoul(std::getenv("PLAID_EXPERIMENT_ANCHOR"), nullptr, 0);
  u32 probeTarget = std::strtoul(std::getenv("PLAID_EXPERIMENT_TARGET"), nullptr, 0);
''' + marker)
    marker = '    if(cpu.instruction()) cpu.synchronize();'
    assert source.count(marker) == 1
    return source.replace(marker, '''    if(!probeApplied && entered && (u32)cpu.ipu.pc == probeAnchor) {
      probeApplied = true;
      std::fprintf(stderr, "EXPERIMENT forced PC %08x -> %08x at step %llu status %08x\\n", probeAnchor, probeTarget, (unsigned long long)steps, (u32)cpu.getControlRegister(12));
      cpu.pipeline.setPc((u64)(s64)(s32)probeTarget);
    }
''' + marker)


def brief(rows):
    return [{k: v for k, v in row.items() if k not in ('bytes', 'sp', 'ram_prefix')}
            for row in rows]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=Path)
    parser.add_argument('anchor', type=lambda v: int(v, 0))
    parser.add_argument('targets', nargs='+', type=lambda v: int(v, 0))
    args = parser.parse_args()
    if any(v < 0 or v > 0xffffffff or v & 3 for v in [args.anchor, *args.targets]):
        parser.error('roots must be aligned 32-bit guest addresses')
    os.environ['SDL_AUDIODRIVER'] = 'dummy'
    rom = args.rom.resolve()
    data = rom.read_bytes()
    if data[:4] != bytes.fromhex('80371240'):
        parser.error('this experiment requires canonical .z64 input')
    anchor_rows = capture_many(rom, [args.anchor], exact=True)
    anchor = next((v for v in anchor_rows if 'bytes' in v), None)
    if anchor is None:
        raise RuntimeError('the unmodified reset replay did not authenticate the anchor')
    if anchor['rom_sha256'] != hashlib.sha256(data).hexdigest():
        raise RuntimeError('the anchor belongs to a different ROM')
    out = ROOT / 'target/mapped-refill-probe' / anchor['rom_sha256']
    out.mkdir(parents=True, exist_ok=True)
    neutral = capture_many(rom, args.targets, exact=True)
    (out / 'neutral.json').write_text(json.dumps(brief(neutral), indent=2))
    cpp = out / 'driver.cpp'
    cpp.write_text(probe_driver())
    spec = importlib.util.spec_from_file_location('probe_builder', ROOT / 'spikes/003-ares-oracle/run.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    exe = builder.build(cpp, out / 'oracle', raw_fetch_access=True, physical_fetch_access=True,
        rdram_burst_access=True, rdram_scalar_access=True, pi_dma_access=True, cpu_instruction_access=True)
    firmware = ROOT / '.refs/ares/ares/System/Nintendo 64/pif.ntsc.rom'
    records = []
    for target in args.targets:
        repeats = []
        at = time.monotonic()
        for repeat in range(2):
            path = out / f'{target:08x}-{repeat}.jsonl'
            command = [str(exe), str(rom), str(firmware), hex(anchor_rows[-1]['boot_entry']), hex(target),
                '100000000', 'CIC-NUS-' + anchor['cic'], str(path), 'exact-many']
            result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=300,
                env={**os.environ, 'PLAID_EXPERIMENT_ANCHOR': hex(args.anchor),
                     'PLAID_EXPERIMENT_TARGET': hex(target)})
            (out / f'{target:08x}-{repeat}.stderr').write_text(result.stderr)
            if 'EXPERIMENT forced PC ' not in result.stderr:
                raise RuntimeError('the requested counterfactual root was not applied')
            repeats.append([json.loads(line) for line in path.read_text().splitlines()])
        assert repeats[0] == repeats[1], 'fresh reset probes disagree'
        capture = next((row for row in repeats[0] if 'bytes' in row), None)
        record = dict(target=f'{target:08x}', repeated_equal=True,
            seconds=round(time.monotonic() - at, 3), summary=brief(repeats[0]))
        if capture is not None and 'physical_start' in capture:
            payload = bytes(capture['bytes'])
            physical = capture['physical_start']
            offsets = {cart - 0x10000000 + physical - dram
                for dram, cart, size in capture['pi_dma']
                if dram <= physical and physical + len(payload) <= dram + size
                and 0x10000000 <= cart
                and cart - 0x10000000 + physical - dram + len(payload) <= len(data)}
            matches = sorted(source for source in offsets if data[source:source + len(payload)] == payload)
            record.update(size=len(payload), sha256=hashlib.sha256(payload).hexdigest(),
                raw_rom_proposals=[hex(source) for source in matches])
        records.append(record)
        print(json.dumps({k: v for k, v in record.items() if k != 'summary'}), flush=True)
    (out / 'receipt.json').write_text(json.dumps(dict(
        scope='counterfactual source proposals, not reachability/provenance/closure',
        ares=builder.REV, anchor=f'{args.anchor:08x}', records=records), indent=2))


if __name__ == '__main__':
    main()
