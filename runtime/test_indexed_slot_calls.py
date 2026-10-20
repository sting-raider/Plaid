"""Synthetic affine indexed loop in a loaded slot, checked against pinned ares."""
from pathlib import Path
import importlib.util
import json
import os
import shutil
import subprocess

from test_tlb_execution import _ares_run

ROOT = Path(__file__).resolve().parents[1]
SLICE = ROOT / 'spikes/096-native-slice'
OUT = ROOT / 'target/indexed-slot-call-contract'
BASE, EXIT, SLOT, BRIDGE = 0x80000000, 0x80000F00, 0x80004000, 0x80006000


def _slot_words(A, leaf, stride=4):
    items = [A.addu(A.s4, A.zero, A.zero), A.addu(A.s5, A.zero, A.zero),
             'header', A.sltiu(A.v0, A.s4, 3), A.beq(A.v0, A.zero, 'done'), A.nop,
             A.lui(A.v0, 0x8000), A.addu(A.v0, A.v0, A.s5),
             lambda pc, labels: A.lw(A.v0, labels['table'] & 0xFFFF, A.v0),
             A.jr(A.v0), A.nop]
    for i, value in enumerate((1, 10, 100)):
        items += [f'case{i}', A.addiu(A.s1, A.s1, value),
                  lambda pc, labels: (3 << 26) | ((leaf >> 2) & 0x03FFFFFF), A.nop,
                  A.j('step'), A.nop]
    items += ['step', A.addiu(A.s5, A.s5, stride),
              A.addiu(A.s4, A.s4, 1), A.j('header'), A.nop,
              'done', A.lui(A.gp, 0x8000), A.sw(A.s1, 0x1000, A.gp),
              A.j('exit'), A.nop,
              'table', *[lambda pc, labels, i=i: labels[f'case{i}'] for i in range(3)]]
    original_base = A.BASE
    try:
        A.BASE = SLOT
        labels = A.label_pcs(items)
        pc, words = SLOT, []
        for item in items:
            if isinstance(item, str):
                continue
            words.append(item(pc, labels) & 0xFFFFFFFF if callable(item) else item)
            pc += 4
        encoded = b''.join(word.to_bytes(4, 'big') for word in words)
    finally:
        A.BASE = original_base
    return encoded


def _fixture(A, stride=4, clobber=False, bridge=False, bad_target=False):
    provisional = _slot_words(A, 0, stride)
    words = len(provisional) // 4
    def copy(label, destination, count):
        loop = f'copy_{label}'
        return [A.lui(A.s0, 0xA000), A.LO(A.s0, A.s0, label),
                A.lui(A.s1, 0xA000), A.ori(A.s1, A.s1, destination & 0xFFFF),
                A.addiu(A.s2, A.zero, count),
                loop, A.lw(A.t1, 0, A.s0), A.sw(A.t1, 0, A.s1),
                A.addiu(A.s0, A.s0, 4), A.addiu(A.s1, A.s1, 4),
                A.addiu(A.s2, A.s2, -1), A.bgtz(A.s2, loop), A.nop,
                A.lui(A.a0, 0x8000), A.ori(A.a0, A.a0, destination & 0xFFFF),
                A.jal('icache'), A.nop]
    items = [*copy('payload', SLOT, words),
             *(copy('bridge_payload', BRIDGE, 5) if bridge else []),
             A.addu(A.s1, A.zero, A.zero),
             A.jal('slot'), A.nop, *A.DONE,
             'icache', A.jr(A.ra), A.nop,
             'slot', 3 << 26 | ((SLOT >> 2) & 0x03FFFFFF), A.nop,
             'leaf', A.addiu(A.a0, A.zero, 99), A.addiu(A.v1, A.zero, 85),
             *([A.addiu(A.s5, A.zero, 77)] if clobber else []), A.jr(A.ra), A.nop,
             'payload', *([0] * words),
             *(['bridge_payload', *([0] * 5)] if bridge else [])]
    labels = A.label_pcs(items)
    payload = _slot_words(A, BRIDGE if bridge else labels['leaf'], stride)
    raw = bytearray(A.assemble(items))
    payload_offset = labels['payload'] - BASE
    raw[payload_offset:payload_offset + len(payload)] = payload
    declarations = [{'destination': hex(SLOT), 'size': hex(len(payload)),
                     'rom': hex(0x1000 + payload_offset), 'encoding': 'raw', 'slot': True}]
    if bridge:
        bridge_words = [0x3c018000, 0x8c216010, 0x00200008, 0,
                        BASE + 0x7000 if bad_target else labels['leaf']]
        encoded_bridge = b''.join(word.to_bytes(4, 'big') for word in bridge_words)
        offset = labels['bridge_payload'] - BASE
        raw[offset:offset + len(encoded_bridge)] = encoded_bridge
        declarations.append({'destination': hex(BRIDGE), 'size': hex(len(encoded_bridge)),
                             'text_size': '0x10', 'rom': hex(0x1000 + offset),
                             'encoding': 'raw', 'slot': True})
    rom = bytearray(0x1000)
    rom[:4] = bytes.fromhex('80371240')
    rom.extend(raw)
    return bytes(rom), bytes(raw), labels, declarations


def _run_case(A, exe, cc, name, stride=4, clobber=False, bridge=False, bad_target=False):
    rom, raw, labels, declarations = _fixture(A, stride, clobber, bridge, bad_target)
    source, loads, runtime, program_map = (OUT / f'{name}{suffix}' for suffix in
                                           ('.z64', '.loads.json', '.runtime.json', '.map.json'))
    source.write_bytes(rom)
    oracle_input = OUT / f'{name}.bin'
    oracle_input.write_bytes(raw)
    loads.write_text(json.dumps({'format': 'plaid-loads-v0', 'source': 'synthetic indexed slot contract',
                                 'loads': declarations}))
    runtime.write_text(json.dumps({'format': 'plaid-runtime-functions-v0', 'source': 'synthetic cache boundary',
                                   'functions': [{'entry': hex(labels['icache']), 'name': 'icache',
                                                  'callbacks': []}]}))
    discover = subprocess.run([str(exe), 'discover', str(source), '0x1000', hex(BASE), hex(len(rom) - 0x1000),
                               hex(BASE), str(program_map), str(runtime), '--loads', str(loads), '--address-taken'],
                              capture_output=True, text=True)
    assert discover.returncode == 0, (discover.stdout, discover.stderr)
    solved = subprocess.run([str(exe), 'solve', str(source), str(program_map), '--address-taken'],
                            capture_output=True, text=True)
    assert solved.returncode == 0, (solved.stdout, solved.stderr)
    verdict = json.loads(solved.stdout)
    if name not in ('affine', 'bound-tail'):
        if verdict['status'] == 'closed':
            native_c = OUT / f'{name}.c'
            native_c.unlink(missing_ok=True)
            lowered = subprocess.run([str(exe), 'lower-map', str(source), str(program_map),
                                      hex(BASE), hex(EXIT), str(native_c)], capture_output=True, text=True)
            assert lowered.returncode != 0 and not native_c.exists(), (verdict, lowered.stdout, lowered.stderr)
        else:
            assert verdict['status'] != 'closed', verdict
        return

    assert verdict['status'] == 'closed', verdict
    native_c = OUT / f'{name}.c'
    subprocess.run([str(exe), 'lower-map', str(source), str(program_map), hex(BASE), hex(EXIT), str(native_c)],
                   check=True, capture_output=True, text=True)
    with native_c.open('a') as output:
        output.write('\nint plaid_rt_icache(plaid_state *s) { (void)s; return 0; }\n')
    native = OUT / (name + ('.exe' if os.name == 'nt' else ''))
    subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
                    f'-DPLAID_LOWERED="{native_c.name}"', f'-DPLAID_EXIT=0x{EXIT:x}u',
                    '-I', str(OUT), str(SLICE / 'harness.c'), '-o', str(native)], check=True)
    actual = subprocess.run([str(native)], capture_output=True, text=True, timeout=30)
    expected = _ares_run(oracle_input)
    assert actual.returncode == expected.returncode == 0, (actual.stdout, actual.stderr, expected.stderr)
    state, reference = json.loads(actual.stdout), json.loads(expected.stdout)
    assert state == reference, (actual.stdout, expected.stdout)
    assert state['pc'] == EXIT and state['regs'][17] == 111 and state['regs'][20:22] == [3, 12], state
    assert state['ram'][0] == 111 and state['regs'][4] == 99 and state['regs'][3] == 85, state


def main():
    spec = importlib.util.spec_from_file_location('indexed_slot_asm', SLICE / 'run.py')
    A = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(A)
    OUT.mkdir(parents=True, exist_ok=True)
    exe = Path(os.environ.get('PLAID_EXE', ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')))
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    if not exe.exists() or not cc:
        raise RuntimeError('indexed slot contract requires the supplied plaid CLI and a C compiler')
    _run_case(A, exe, cc, 'affine')
    _run_case(A, exe, cc, 'clobbering-callee', clobber=True)
    _run_case(A, exe, cc, 'wrong-stride', stride=8)
    _run_case(A, exe, cc, 'bound-tail', bridge=True)
    _run_case(A, exe, cc, 'bound-tail-clobber', clobber=True, bridge=True)
    _run_case(A, exe, cc, 'bound-tail-unknown', bridge=True, bad_target=True)
    print('PASS loaded affine slot loop matches pinned ares; clobbering callee and wrong stride refuse closure/lowering')


if __name__ == '__main__':
    main()
