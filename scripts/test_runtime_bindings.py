"""Public identification preserves separate, verified SDK scalar references."""
import json
import os
from pathlib import Path
import struct
import subprocess
import zlib

ROOT = Path(__file__).resolve().parents[1]


def main():
    out = ROOT / 'target/runtime-bindings-contract'
    out.mkdir(parents=True, exist_ok=True)
    exe = ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')
    bodies = [[0x3c088001, 0x25088000, 0x03e00008, 0],
              [0x3c088002, 0x25088000, 0x03e00008, 0]]
    rom = bytearray(0x1000)
    rom[:4] = bytes.fromhex('80371240')
    rom[8:12] = (0x80000400).to_bytes(4, 'big')
    rom.extend(b''.join(struct.pack('>4I', *body) for body in bodies))
    path, loads, sig = (out / name for name in ('input.z64', 'loads.json', 'scalar.sig'))
    path.write_bytes(rom)
    loads.write_text(json.dumps({'format': 'plaid-loads-v0', 'source': 'synthetic disjoint SDK copies',
        'loads': [{'destination': '0x80200400', 'size': '0x10', 'rom': '0x1010', 'encoding': 'raw'}]}))
    normalized = struct.pack('>4I', 0x3c080000, 0x25080000, 0x03e00008, 0)
    sig.write_text(f'osSetIntMask 0x10 0x{zlib.crc32(normalized[:8]):08X} 0x{zlib.crc32(normalized):08X}\n'
                   ' .hi16 __OSGlobalIntMask 0x0\n .lo16 __OSGlobalIntMask 0x4\n')
    result = subprocess.run([str(exe), 'identify', str(path), '0x1000', '0x80000400', '0x10',
                             str(sig), '--loads', str(loads)], check=True, capture_output=True, text=True)
    functions = json.loads(result.stdout)['functions']
    assert len(functions) == 2, functions
    assert [f['data_bindings']['__OSGlobalIntMask'] for f in functions] == ['0x80008000', '0x80018000'], functions
    # Consumers that only know the original declaration fields still parse it.
    declaration = out / 'runtime.json'
    declaration.write_text(result.stdout)
    mapped = out / 'map.json'
    subprocess.run([str(exe), 'discover', str(path), '0x1000', '0x80000400', '0x10',
                    '0x80000400', str(mapped), str(declaration), '--loads', str(loads)],
                   check=True, capture_output=True)
    # Explicit ABI declarations transport distinct bindings into the typed map.
    document = json.loads(result.stdout)
    for function in document['functions']:
        function['status_global'] = function['data_bindings']['__OSGlobalIntMask']
    declaration.write_text(json.dumps(document))
    command = [str(exe),'discover',str(path),'0x1000','0x80000400','0x10',
               '0x80000400',str(mapped),str(declaration),'--loads',str(loads)]
    subprocess.run(command,check=True,capture_output=True)
    assert [f['status_global'] for _,f in json.loads(mapped.read_bytes())['runtime_functions']] == [0x80008000,0x80018000]
    for value in ['0x80000001','0x80800000','0x00002000',123]:
        document['functions'][0]['status_global'] = value
        declaration.write_text(json.dumps(document))
        assert subprocess.run(command,capture_output=True).returncode != 0
    print('PASS runtime identification: separate scalar data bindings and original declaration consumer')


if __name__ == '__main__':
    main()
