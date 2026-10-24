"""Visible, silent GPU contract for the built RT64 shim; no ROM or assets.

    python runtime/rt64/test_scissor.py [path/to/plaid_rt64.dll]
"""
import ctypes as C
import os
from pathlib import Path
import struct
import subprocess
import sys
import traceback


def worker(path):
    os.environ['SDL_AUDIODRIVER'] = 'dummy'
    directory = os.add_dll_directory(str(path.parent))
    lib = C.CDLL(str(path))
    ram = (C.c_ubyte * 0x800000)()
    header = (C.c_ubyte * 64)()
    lib.plaid_gfx_open.argtypes = [C.c_void_p]
    assert lib.plaid_gfx_open(header) == 0, 'renderer setup'
    writeback = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_uint32, C.c_uint32, C.c_void_p)

    @writeback
    def copy(_context, address, size, data):
        if address > len(ram) or size > len(ram) - address:
            return 1
        C.memmove(C.addressof(ram) + address, data, size)
        return 0

    lib.plaid_gfx_rdp.argtypes = [C.c_void_p, C.c_void_p, C.c_uint32, C.c_void_p, writeback, C.c_void_p]
    width, height = 64, 48
    scissor = (8, 8, 56, 40)

    def clip(rect, bounds):
        return (max(rect[0], bounds[0]), max(rect[1], bounds[1]),
                min(rect[2], bounds[2]), min(rect[3], bounds[3]))

    def commands(rect, color):
        left, top, right, bottom = rect
        return [(0xf7000000, color),
                (0xf6000000 | ((right - 1) * 4) << 12 | (bottom - 1) * 4,
                 (left * 4) << 12 | top * 4)]

    def draw(address, siz, bounds, rectangles):
        left, top, right, bottom = bounds
        words = [(0xef300000, 0),
                 (0xff000000 | siz << 19 | (width - 1), address),
                 (0xed000000 | (left * 4) << 12 | top * 4, (right * 4) << 12 | bottom * 4)]
        for rect, color in rectangles:
            words += commands(rect, color)
        # Force readback of the whole image, including pixels outside the inset.
        words += [(0xed000000, (width * 4) << 12 | height * 4)]
        black = 0x00010001 if siz == 2 else 0x000000ff
        words += commands((0, 0, 1, 1), black)
        words += commands((width - 1, height - 1, width, height), black)
        words += [(0xe9000000, 0)]
        raw = b''.join(struct.pack('>II', *word) for word in words)
        data = (C.c_ubyte * len(raw)).from_buffer_copy(raw)
        assert lib.plaid_gfx_rdp(ram, data, len(data), None, copy, None) == 0

    cases = [
        ('inside', (12, 12, 16, 16)),
        ('left', (1, 12, 2, 13)), ('right', (62, 12, 63, 13)),
        ('top', (12, 1, 13, 2)), ('bottom', (12, 46, 13, 47)),
        ('cross-left', (4, 12, 12, 16)), ('cross-right', (52, 12, 60, 16)),
        ('cross-top', (12, 4, 16, 12)), ('cross-bottom', (12, 36, 16, 44)),
        ('cover', (4, 4, 60, 44)),
        ('touch-left', (4, 12, 8, 16)), ('touch-top', (12, 4, 16, 8)),
        ('touch-right', (56, 12, 60, 16)), ('touch-bottom', (12, 40, 16, 44)),
    ]
    for siz in (2, 3):
        address = 0x10000 + siz * 0x10000
        pixel_bytes = 2 if siz == 2 else 4
        black = 0x00010001 if siz == 2 else 0x000000ff
        for name, rect in cases:
            draw(address, siz, (0, 0, width, height), [((0, 0, width, height), black)])
            draw(address, siz, scissor, [(rect, 0xffffffff)])
            expected = clip(rect, scissor)
            for y in range(height):
                for x in range(width):
                    offset = address + (y * width + x) * pixel_bytes
                    value = int.from_bytes(bytes(ram[offset:offset + pixel_bytes]), 'big')
                    inside = expected[0] <= x < expected[2] and expected[1] <= y < expected[3]
                    want = (0xffff if siz == 2 else 0xffffffff) if inside else (1 if siz == 2 else black)
                    assert value == want, (siz, name, x, y, hex(value), hex(want))
        for bounds in [(8, 8, 8, 40), (8, 8, 56, 8)]:
            draw(address, siz, (0, 0, width, height), [((0, 0, width, height), black)])
            draw(address, siz, bounds, [((0, 0, width, height), 0xffffffff)])
            raw = bytes(ram[address:address + width * height * pixel_bytes])
            assert raw == (1 if siz == 2 else black).to_bytes(pixel_bytes, 'big') * (width * height), bounds
    print('PASS RT64 fill scissor: RGBA16/RGBA32, four edges, partial overlaps, touching and empty bounds; all framebuffer pixels checked', flush=True)
    # The renderer owns a detached window thread, as in the native runtime.
    # Exit the test process after readback instead of unloading a live DLL.
    os._exit(0)


def main():
    default = Path(__file__).resolve().parents[2] / 'target/rt64-shim/Release/plaid_rt64.dll'
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        try:
            worker(Path(sys.argv[2]).resolve())
        except Exception:
            traceback.print_exc()
            sys.stderr.flush()
            os._exit(1)
    else:
        path = Path(sys.argv[1] if len(sys.argv) > 1 else default).resolve()
        env = dict(os.environ, SDL_AUDIODRIVER='dummy')
        return subprocess.run([sys.executable, __file__, '--worker', str(path)], env=env, timeout=60).returncode


if __name__ == '__main__':
    sys.exit(main())
