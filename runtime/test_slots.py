"""Two ROM files loaded into one executable slot, through the public CLI."""
from pathlib import Path
import importlib.util
import json
import os
import shutil
import subprocess
import zlib

ROOT = Path(__file__).resolve().parents[1]
SLICE = ROOT / 'spikes/096-native-slice'
OUT = ROOT / 'target/slot-contract'


def main():
    spec = importlib.util.spec_from_file_location('slot_asm', SLICE / 'run.py')
    a = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(a)
    OUT.mkdir(parents=True, exist_ok=True)
    exe = ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    slot = 0x80004000

    def copy(label, loop):
        return [a.lui(a.s0, 0xa000), a.LO(a.s0, a.s0, label),
                a.lui(a.s1, 0xa000), a.ori(a.s1, a.s1, slot & 0xffff), a.addiu(a.s2, 0, 4),
                loop, a.lw(a.t1, 0, a.s0), a.sw(a.t1, 0, a.s1),
                a.addiu(a.s0, a.s0, 4), a.addiu(a.s1, a.s1, 4),
                a.addiu(a.s2, a.s2, -1), a.bgtz(a.s2, loop), a.nop,
                a.lui(a.a0, 0x8000), a.ori(a.a0, a.a0, slot & 0xffff), a.jal('icache'), a.nop]

    call = [3 << 26 | (slot >> 2 & 0x3ffffff), a.nop]
    def snapshot(offset):
        # Retain each generation's actual slot writes in the oracle RAM slice.
        return [a.lui(a.t0, 0xa000), a.ori(a.t0, a.t0, slot & 0xffff),
                a.lui(a.t2, 0xa000), a.ori(a.t2, a.t2, offset),
                *[word for at in range(0, 16, 4)
                  for word in (a.lw(a.t1, at, a.t0), a.sw(a.t1, at, a.t2))]]
    for mode in ('switch', 'tamper', 'ambiguous', 'paired-switch', 'paired-tamper', 'paired-ambiguous'):
        case = mode.removeprefix('paired-')
        items = [*copy('one', 'copy1')]
        if case == 'tamper':
            items += [a.sw(0, -16, a.s1)]
        items += [*call, a.addu(a.s3, a.v0, 0), *snapshot(0x1000)]
        if case == 'switch':
            items += [*copy('two', 'copy2'), *call, a.addu(a.s4, a.v0, 0), *snapshot(0x1010),
                      *copy('one', 'copy3'), a.lui(a.t9, 0x8000), a.ori(a.t9, a.t9, 0x4000),
                      a.jalr(a.ra, a.t9), a.nop, a.addu(a.s5, a.v0, 0), *snapshot(0x1020)]
        items += [*a.DONE,
                  'icache', a.I(47, 16, a.a0, 0), a.jr(a.ra), a.nop,
                  'one', a.addiu(a.v0, 0, 7), a.jr(a.ra), a.nop, slot,
                  'two', a.addiu(a.v0, 0, 7 if case == 'ambiguous' else 11), a.jr(a.ra), a.nop, slot]
        raw = a.assemble(items)
        labels = a.label_pcs(items)
        rom = bytearray(0x1000)
        rom[:4] = bytes.fromhex('80371240')
        rom.extend(raw)
        source, loads, m, c, runtime = (OUT / f'{mode}{ext}' for ext in ('.z64', '.loads.json', '.map.json', '.c', '.runtime.json'))
        declarations = []
        for label in ('one', 'two'):
            offset = 0x1000 + labels[label] - a.BASE
            entry = {'destination': hex(slot), 'size': '0x10', 'rom': hex(offset),
                     'encoding': 'raw', 'slot': True}
            if mode.startswith('paired-'):
                def stream(data):
                    compressor = zlib.compressobj(wbits=-15)
                    return b'\x11\x72' + len(data).to_bytes(4, 'big') + compressor.compress(data) + compressor.flush()
                encoded = stream(rom[offset:offset + 16]) + stream(bytes(16))
                entry.update(rom=hex(len(rom)), rom_end=hex(len(rom) + len(encoded)),
                             size='0x20', text_size='0x10', encoding='rare_pair')
                rom.extend(encoded)
            declarations.append(entry)
        rom.extend(bytes((-len(rom)) % 4))
        source.write_bytes(rom)
        loads.write_text(json.dumps({'format': 'plaid-loads-v0', 'source': 'synthetic shared-slot contract',
                                    'loads': declarations}))
        runtime.write_text(json.dumps({'format': 'plaid-runtime-functions-v0', 'source': 'synthetic cache boundary',
                                      'functions': [{'entry': hex(labels['icache']), 'name': 'icache', 'callbacks': []}]}))
        cmd = [str(exe), 'discover', str(source), '0x1000', hex(a.BASE), hex(len(raw)), hex(a.BASE), str(m), str(runtime),
               '--loads', str(loads), '--address-taken']
        subprocess.run(cmd, check=True, capture_output=True)
        solve = subprocess.run([str(exe), 'solve', str(source), str(m), '--address-taken'],
                               check=True, capture_output=True, text=True)
        verdict = json.loads(solve.stdout)
        assert verdict['status'] == 'closed', (mode, verdict['blockers'])
        subprocess.run([str(exe), 'lower-map', str(source), str(m), hex(a.BASE), hex(a.EXIT), str(c)], check=True, capture_output=True)
        with c.open('a') as f:
            f.write('\nint plaid_rt_icache(plaid_state *s) { (void)s; return 0; }\n')
        native = OUT / (mode + ('.exe' if os.name == 'nt' else ''))
        subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
                        f'-DPLAID_LOWERED="{c.name}"', f'-DPLAID_EXIT={hex(a.EXIT)}u', '-I', str(OUT),
                        str(SLICE / 'harness.c'), '-lm', '-o', str(native)], check=True)
        run = subprocess.run([str(native)], capture_output=True, text=True, timeout=30)
        state = json.loads(run.stdout)
        if case == 'switch':
            assert run.returncode == 0 and state['regs'][19:22] == [7, 11, 7], (mode, state)
            raw_path = OUT / 'switch.bin'
            raw_path.write_bytes(raw)
            oracle = ROOT / 'target/native-slice/oracle/oracle'
            if os.name == 'nt':
                def linux(path):
                    return subprocess.check_output(['wsl', '-d', 'Ubuntu', '--exec', 'wslpath', '-a', str(path)], text=True).strip()
                if not oracle.exists():
                    subprocess.run(['wsl', '-d', 'Ubuntu', '--exec', 'python3', linux(SLICE / 'run.py'), '--oracle', '--build-only'], check=True)
                reference = ['wsl', '-d', 'Ubuntu', '--exec', linux(oracle), linux(raw_path), hex(a.EXIT)]
            else:
                if not oracle.exists():
                    a.builder().build(SLICE / 'driver.cpp', oracle.parent)
                reference = [str(oracle), str(raw_path), hex(a.EXIT)]
            built = json.loads((oracle.parent / 'build.json').read_text())
            assert built['revision'] == a.builder().REV
            ref = subprocess.run(reference, capture_output=True, text=True, timeout=120)
            assert ref.returncode == 0 and state == json.loads(ref.stdout), (state, ref.stdout, ref.stderr)
        else:
            assert run.returncode == 6 and state['fault'] == 3, (mode, state)
    print('PASS raw and paired-stream slots match pinned ares (7/11/7); tampered and ambiguous text fail closed')


if __name__ == '__main__':
    main()
