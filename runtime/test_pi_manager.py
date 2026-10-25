"""Host-owned PI manager: DMA bytes, completion queues and O32 state."""
import json
import os
import shutil
import subprocess


def run(exe, cc, T):
    A = T.A
    rom = T.OUT / 'pi-manager.z64'
    rom.write_bytes(bytes.fromhex('80371240') + bytes(range(256)) * 32)
    mb, destination = 0x80004800, 0x80004900
    runtime = ['osCreatePiManager', 'osPiStartDma', 'osCreateMesgQueue',
               'osCreateThread', 'osStartThread', 'osRecvMesg']
    for priority in (0, 1):
        program = [*T.li(A.sp, 0x80007f00),
                   *T.call('osCreateThread', T.T1, 1, 'worker', 0, 0x8000ff00, 10),
                   *T.call('osStartThread', T.T1), *A.DONE, 'worker',
                   *T.poke(0x80000308, 0xb0000000),
                   *T.call('osCreateMesgQueue', T.Q, T.BUF, 4),
                   *T.call('osCreatePiManager', 150, T.Q2, T.BUF2, 4),
                   *T.li(A.s6, 0x81234560), *T.poke(destination - 4, 0x12345678),
                   *T.poke(destination + 16, 0x87654321),
                   *T.call('osPiStartDma', mb, priority, 0, 0x40, destination, 16, T.Q),
                   *T.li(A.t0, destination + 20), A.sw(A.v0, 0, A.t0),
                   *T.call('osRecvMesg', T.Q, T.SLOT, 1), *T.li(A.t0, destination + 24), A.sw(A.v0, 0, A.t0),
                   *T.li(A.t0, T.SLOT), A.lw(A.t1, 0, A.t0),
                   *T.li(A.t0, destination + 28), A.sw(A.t1, 0, A.t0), A.sw(A.s6, 4, A.t0),
                   *A.DONE]
        for name in runtime:
            program += [name, A.jr(A.ra), A.nop]
        binary = T.build(exe, cc, f'pi-manager-{priority}', program, runtime)
        result = subprocess.run([str(binary), '--rom', str(rom), '--dump', hex(destination - 4), '10'],
                                capture_output=True, text=True, timeout=30)
        rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
        stop = next(row for row in rows if 'stop' in row)
        memory = [row['words'] for row in rows if 'dump' in row]
        expected = [int.from_bytes(rom.read_bytes()[i:i+4], 'big') for i in range(0x40, 0x50, 4)]
        assert result.returncode == 0 and stop['stop'] == 'exit' and stop['fault'] == 0, rows
        assert stop['pi_dma'] == 1, stop
        assert memory == [[0x12345678, *expected, 0x87654321, 0, 0, mb, 0x81234560]], memory
    for label, direction, offset, reason in [
            ('write', 1, 0x40, 'PI write to cartridge'),
            ('bounds', 0, 0x100000, 'PI DMA outside the ROM')]:
        program = [*T.li(A.sp, 0x80007f00), *T.poke(0x80000308, 0xb0000000),
                   *T.poke(destination, 0x12345678),
                   *T.call('osPiStartDma', mb, 0, direction, offset, destination, 16, 0),
                   *A.DONE, 'osPiStartDma', A.jr(A.ra), A.nop]
        binary = T.build(exe, cc, 'pi-manager-' + label, program, ['osPiStartDma'])
        result = subprocess.run([str(binary), '--rom', str(rom), '--dump', hex(destination), '1'],
                                capture_output=True, text=True, timeout=30)
        rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
        stop = next(row for row in rows if 'stop' in row)
        assert result.returncode == 1 and stop['stop'] == reason and stop['pi_dma'] == 0, rows
        assert next(row['words'] for row in rows if 'dump' in row) == [0x12345678], rows
    print('PI manager: normal/high priority ROM DMA, return, completion message, saved s6 and RAM canaries')


if __name__ == '__main__':
    import test_runtime as T
    T.OUT.mkdir(parents=True, exist_ok=True)
    run(T.ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid'),
        os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang'), T)
