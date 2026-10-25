"""Native Joybus packets, SI DMA through PIF RAM and the EEPROM busy state shared with __osEepStatus."""
import os
import shutil
import subprocess


def run(exe, cc, T):
    A, out = T.A, T.OUT
    T.build(exe, cc, 'joybus-fixture', list(A.DONE), [])
    native = out / ('joybus-contract.exe' if os.name == 'nt' else 'joybus-contract')
    subprocess.run([cc, '-O2', '-std=gnu11', '-Wall', '-Werror', '-Wno-unused-label', '-Wno-unused-function',
                    '-DPLAID_SAFEPOINTS', '-DPLAID_LOWERED="joybus-fixture.c"', '-I', str(out),
                    str(T.ROOT / 'runtime/test_joybus.c'), '-pthread', '-o', str(native)], check=True)
    result = subprocess.run([str(native)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0 and '"joybus":"ok"' in result.stdout, (result.stdout, result.stderr)
    print('joybus: gamepad/absent-channel status, controller read and repeat, skipped headers, '
          'absent-Pak reads/write CRC, EEPROM write/busy/read with block masking, refused packets, SI DMA through PIF RAM and '
          'the busy state shared with __osEepStatus')


if __name__ == '__main__':
    import test_runtime as T
    run(T.ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid'),
        os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang'), T)
