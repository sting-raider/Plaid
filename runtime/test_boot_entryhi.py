"""EntryHi from the post-IPL replay survives runtime calls; other staging registers do not (ADR-0242)."""
import json
import subprocess


def run(exe, cc, T):
    A, out = T.A, T.OUT
    mfc0 = lambda rt, rd: 0x40000000 | rt << 16 | rd << 11
    mtc0 = lambda rt, rd: 0x40800000 | rt << 16 | rd << 11
    base, exit_pc = A.BASE, A.EXIT
    A.BASE, A.EXIT = 0x80004000, 0x80004F00  # above the post-IPL RAM prefix
    (out / 'entryhi_boot.h').write_text(
        '#define PLAID_BOOT_STATUS 0x34000000u\n#define PLAID_BOOT_ENTRYHI 0xffffffff123456abull\n'
        'static const u8 plaid_ram_boot[0x400] = {0};\n')
    program = [*T.li(A.sp, 0x80007F00), *T.li(A.t8, T.LOG),
               mtc0(A.zero, 0),                  # Index is known here
               *T.call('osInvalICache', 0, 0),   # any runtime call
               mfc0(A.t0, 10), A.sw(A.t0, 0, A.t8),
               mfc0(A.t1, 0), A.sw(A.t1, 4, A.t8),  # Index is no longer known: fault 12
               *A.DONE, 'osInvalICache', A.jr(A.ra), A.nop]
    try:
        binary = T.build(exe, cc, 'boot_entryhi', program, ['osInvalICache'],
                         ['-DPLAID_RAM_BOOT="entryhi_boot.h"'])
    finally:
        A.BASE, A.EXIT = base, exit_pc
    rom = out / 'boot_entryhi.z64'
    rom.write_bytes(bytes.fromhex('80371240') + bytes(0xFFC))
    actual = subprocess.run([str(binary), '--rom', str(rom), '--dump', hex(T.LOG), '2'],
                            capture_output=True, text=True, timeout=30)
    rows = [json.loads(line) for line in actual.stdout.splitlines() if line.startswith('{')]
    stop = next(row for row in rows if 'stop' in row)
    words = next(row['words'] for row in rows if 'dump' in row)
    assert actual.returncode == 1 and stop['fault'] == 12, (actual.stdout, actual.stderr)
    assert words == [0x123440ab, 0], [hex(w) for w in words]  # masked EntryHi; Index never stored
    print('boot EntryHi: the replayed value survives a runtime call and reads masked; Index written before the call is refused after it')
