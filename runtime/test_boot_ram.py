"""The native startup RAM prefix preserves post-IPL boot data (ADR-0200)."""
import json
import subprocess


def run(exe, cc, T):
    A, out = T.A, T.OUT
    # The lowered fixture lives above the post-IPL prefix.  That lets the test
    # inspect all of [0, 0x400) after startup and also verify image-load order.
    base, exit_pc = A.BASE, A.EXIT
    A.BASE, A.EXIT = 0x80004000, 0x80004F00
    offsets = (0, 0x1D8, 0x2FC, 0x300, 0x3FC)
    # 0x3e0 is a distinct D-cache line from the sampled 0x3fc guard.
    changed = 0x3E0
    written = 0xD00DFEED
    values = []
    pattern = bytes((i * 73 + 0x5B) & 0xFF for i in range(0x400))
    (out / 'ram_boot.h').write_text(
        'static const u8 plaid_ram_boot[0x400] = {' + ','.join(map(str, pattern)) + '};\n')
    program = [*T.li(A.sp, 0x80007F00), *T.li(A.t8, T.INDEX), A.sw(A.zero, 0, A.t8)]
    try:
        for offset in offsets:
            for alias in (0x80000000, 0xA0000000):
                program += T.log_word(alias + offset)
        program += [*T.poke(0xA0000000 + changed, written)]
        program += T.log_word(0x80000000 + changed)
        program += T.log_word(0xA0000000 + changed)
        for offset in (changed - 4, changed + 4, 0x3FC):
            program += T.log_word(0x80000000 + offset)
        program += T.log_word(A.BASE)
        binary = T.build(exe, cc, 'boot_ram', program, [], ['-DPLAID_RAM_BOOT="ram_boot.h"'])
    finally:
        A.BASE, A.EXIT = base, exit_pc

    rom = out / 'boot_ram.z64'
    rom.write_bytes(bytes.fromhex('80371240') + bytes(0xFFC))
    run = subprocess.run([str(binary), '--rom', str(rom), '--dump', hex(T.LOG), '16'],
                         capture_output=True, text=True, timeout=30)
    lines = [json.loads(line) for line in run.stdout.splitlines() if line.startswith('{')]
    stop = next((row for row in lines if 'stop' in row), {})
    actual = next((row['words'] for row in lines if 'dump' in row), None)
    for offset in offsets:
        word = int.from_bytes(pattern[offset:offset + 4], 'big')
        values.extend((word, word))
    values.extend((written, written))
    values.extend(int.from_bytes(pattern[o:o + 4], 'big') for o in (changed - 4, changed + 4, 0x3FC))
    values.append(int.from_bytes((out / 'boot_ram.bin').read_bytes()[:4], 'big'))
    assert run.returncode == 0 and stop.get('stop') == 'exit' and stop.get('fault') == 0, (
        run.returncode, run.stdout, run.stderr)
    assert actual == values, ([hex(x) for x in actual or []], [hex(x) for x in values])
    print('boot RAM: declared post-IPL prefix samples read through KSEG0/KSEG1; alias write and guards hold; '
          'base image at 0x4000 loads after the prefix')
