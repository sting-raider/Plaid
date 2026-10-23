"""Compile and exercise generated relocated-byte verifiers on synthetic images."""
from pathlib import Path
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    out = ROOT / 'target/overlay-verifier'
    out.mkdir(parents=True, exist_ok=True)
    source = out / 'check.c'
    cargo = shutil.which('cargo') or str(Path.home() / '.cargo/bin/cargo.exe')
    with source.open('wb') as stream:
        subprocess.run([cargo, 'run', '--locked', '--quiet', '-p', 'plaid-lower',
                        '--example', 'overlay_verifier_fixture'], cwd=ROOT,
                       stdout=stream, check=True)
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    if not cc:
        raise RuntimeError('overlay verifier tests require a C compiler')
    exe = out / ('check.exe' if os.name == 'nt' else 'check')
    subprocess.run([cc, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                    str(source), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True, timeout=30)
    print('PASS native overlay verifier: five bases, shared/interleaved HI16, '
          'signed carry, segmented pointers, every-byte tampering, BSS and bounds')


if __name__ == '__main__':
    main()
