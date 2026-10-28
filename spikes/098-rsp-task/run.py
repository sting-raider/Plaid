"""spike098: one real RSP task, native against the pinned ares RSP (ADR-0169).

    python spikes/098-rsp-task/run.py <capture dir> [--rebuild]

The capture comes from a native runtime built with -DPLAID_RSP and run with
--rsp-capture <task> <dir>: RDRAM, IMEM, DMEM and the RSP state before the
task, and the same after the lowered microcode ran it. ares runs the task
from the "before" state; all of RDRAM, IMEM and DMEM and the register, vector
and status state must match the native "after". Captures hold game data, so
they stay local; the receipt records hashes only.
"""
import hashlib
import importlib.util
import json
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'target/rsp-task'


def builder():
    s = importlib.util.spec_from_file_location('builder', ROOT / 'scripts/ares_oracle.py')
    module = importlib.util.module_from_spec(s)
    s.loader.exec_module(module)
    return module


def state_bin(state):
    vu = bytes.fromhex(state['vu'])
    words = [state['pc'], *state['regs'], *(int.from_bytes(vu[i:i + 2], 'big') for i in range(0, len(vu), 2)),
             *state['vflags'], *state['signals'], state['semaphore'], state['interrupt_on_break']]
    assert len(words) == 1 + 32 + 280 + 6 + 8 + 2
    return struct.pack(f'<{len(words)}I', *words)


def oracle(capture):
    exe = builder().build(HERE / 'driver.cpp', OUT / 'oracle')
    run = subprocess.run([str(exe), *(str(capture / f) for f in ('before-rdram.bin', 'before-imem.bin',
                                                                  'before-dmem.bin', 'state.bin')), str(capture)],
                         capture_output=True, text=True, timeout=3600)
    assert run.returncode == 0, (run.returncode, run.stderr)
    (capture / 'oracle-state.json').write_text(run.stdout)


def windows(capture):
    before = json.loads((capture / 'before-state.json').read_text())
    (capture / 'state.bin').write_bytes(state_bin(before))
    oracle(capture)
    mine = json.loads((capture / 'after-state.json').read_text())
    theirs = json.loads((capture / 'oracle-state.json').read_text())
    for key in ('regs', 'vu', 'vflags', 'signals', 'semaphore', 'halted', 'broken'):
        assert mine[key] == theirs[key], (key, mine[key], theirs[key])
    digests = {}
    for part in ('rdram', 'imem', 'dmem'):
        a, b = (capture / f'after-{part}.bin').read_bytes(), (capture / f'oracle-{part}.bin').read_bytes()
        if a != b:
            diff = [i for i in range(len(a)) if a[i] != b[i]]
            raise AssertionError((part, len(diff), hex(diff[0]), a[diff[0]:diff[0] + 16].hex(),
                                  b[diff[0]:diff[0] + 16].hex()))
        digests[part] = hashlib.sha256(a).hexdigest()
    changed = sum(x != y for x, y in zip((capture / 'before-rdram.bin').read_bytes(),
                                         (capture / 'after-rdram.bin').read_bytes()))
    receipt = dict(format='plaid-rsp-task-receipt-v0', ares_revision=builder().REV, ares_instructions=theirs['instructions'],
                   rdram_bytes_written=changed, after_sha256=digests,
                   before_sha256={p: hashlib.sha256((capture / f'before-{p}.bin').read_bytes()).hexdigest()
                                  for p in ('rdram', 'imem', 'dmem')})
    print('PASS the native RSP task matches pinned ares in all of RDRAM, IMEM, DMEM and the RSP state;',
          theirs['instructions'], 'ares instructions,', changed, 'RDRAM bytes written')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    capture = Path(sys.argv[1])
    oracle(capture) if '--oracle' in sys.argv else windows(capture)
