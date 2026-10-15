"""Lowers saved IMEM snapshots and writes the RSP text registry (ADR-0169).

    python runtime/rsp_texts.py <plaid> <snapshot dir> <out dir>

A runtime built with -DPLAID_RSP and run with --rsp-dump <dir> saves IMEM as
imem-<pc>-<hash>.bin whenever control reaches a word no lowered text holds.
Each snapshot is lowered whole (IMEM 0..0x1000) with `plaid lower-rsp`; the
lowered code runs only the words IMEM still holds, so leftover bytes in a
snapshot are harmless. Prints the C files to compile with the runtime, with
-DPLAID_RSP and -I crates/plaid-lower/src.
"""
import subprocess
import sys
from pathlib import Path


def main(plaid, snapshots, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    names, files = [], []
    for snapshot in sorted(Path(snapshots).glob('imem-*.bin')):
        assert snapshot.stat().st_size == 4096, snapshot
        name = snapshot.stem.replace('-', '_')
        c = out / f'{name}.c'
        subprocess.run([str(Path(plaid).resolve()), 'lower-rsp', str(snapshot), '0', '0x1000', '0', name, str(c), '--raw'],
                       check=True, stdout=subprocess.DEVNULL)
        names.append(name)
        files.append(c)
    registry = out / 'rsp_registry.c'
    registry.write_text('#include "rsp_state.h"\n'
                        + ''.join(f'extern const plaid_rsp_text plaid_rsp_text_{n};\n' for n in names)
                        + 'const plaid_rsp_text *const plaid_rsp_texts[] = {'
                        + ''.join(f'&plaid_rsp_text_{n}, ' for n in names) + '0};\n')
    print(' '.join(str(f) for f in files + [registry]))


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
