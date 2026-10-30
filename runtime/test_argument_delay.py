"""Scalar JAL-slot bindings equal arguments actually delivered on pinned ares."""
import json
import struct
import subprocess
import sys
import zlib


def run(exe, cc, T):
    del cc
    A, out = T.A, T.OUT
    sys.path.insert(0, str(T.ROOT / 'scripts'))
    import ares_oracle
    oracle = ares_oracle.default()
    path, raw, signature = (out / name for name in ('argument-delay.z64', 'argument-delay.bin', 'argument-delay.sig'))
    cases = []
    for argument in range(4, 8):
        for opcode in (9, 13):
            for low in (0, 0x7fff, 0x8000, 0xffff):
                high = A.lui(argument, 0x8001)
                slot = opcode << 26 | argument << 21 | argument << 16 | low
                program = [high, A.jal('callee'), slot, *A.DONE,
                           'callee', *T.li(A.t0, 0x80001000), A.sw(argument, 0, A.t0), A.jr(A.ra), A.nop]
                assembled = A.assemble(program); raw.write_bytes(assembled)
                rom = bytearray(0x1000); rom[:4] = bytes.fromhex('80371240'); rom[8:12] = A.BASE.to_bytes(4, 'big')
                path.write_bytes(rom + assembled)
                words = list(struct.unpack('>5I', assembled[:20]))
                # Normalize precisely the declared high/low/call relocations.
                words[0] &= 0xffff0000; words[1] &= 0xfc000000; words[2] &= 0xffff0000
                normalized = struct.pack('>5I', *words)
                signature.write_text(f'osYieldThread 0x14 0x{zlib.crc32(normalized[:8]):08x} 0x{zlib.crc32(normalized):08x}\n'
                                     ' .hi16 __osRunQueue 0x0\n .lo16 __osRunQueue 0x8\n .targ26 callee 0x4\n')
                identified = subprocess.run([str(exe), 'identify', str(path), '0x1000', hex(A.BASE), hex(len(assembled)), str(signature)],
                                            capture_output=True, text=True, check=True, timeout=30)
                functions = json.loads(identified.stdout)['functions']
                assert len(functions) == 1, functions
                binding = int(functions[0]['data_bindings']['__osRunQueue'], 0)
                reference = subprocess.run([str(oracle), str(raw), hex(A.EXIT)], capture_output=True, text=True, check=True, timeout=60)
                state = json.loads(reference.stdout)
                assert state['pc'] == A.EXIT and state['ram'] == [binding] + [0] * 63, state
                canonical = binding | (0xffffffff00000000 if binding & 0x80000000 else 0)
                assert state['regs'][argument] == canonical, state
                cases.append(dict(register=argument, opcode=opcode, low=low, binding=binding))
    (out / 'argument-delay-reference.json').write_text(json.dumps(cases, indent=2))
    print('PASS 32 JAL delay-slot scalar bindings match pinned-ares callee GPR, PC and RAM; ADDIU/ORI, signed-low boundaries and a0-a3')


if __name__ == '__main__':
    import os
    import shutil
    import test_runtime as T
    os.environ['SDL_AUDIODRIVER'] = 'dummy'
    T.OUT.mkdir(parents=True, exist_ok=True)
    run(T.ROOT / 'target/debug/plaid.exe', shutil.which('gcc'), T)
