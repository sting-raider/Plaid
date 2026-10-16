"""Native object caching: dependency changes and failed rebuilds cannot reuse stale objects."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import time

from native import compile_source


def main():
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    compiler = subprocess.check_output([cc, '--version'])
    with tempfile.TemporaryDirectory(prefix='plaid native ') as directory:
        source = Path(directory) / 'fixture.c'
        header = source.with_suffix('.h')
        source.write_text('#include "fixture.h"\nint value(void) { return VALUE; }\n')
        header.write_text('#define VALUE 7\n')
        flags = [cc, '-O1']

        def build(options=flags):
            return compile_source(source, options, header.read_bytes(), compiler)

        start = time.perf_counter()
        obj = build()
        cold = time.perf_counter() - start
        original, modified = obj.read_bytes(), obj.stat().st_mtime_ns
        start = time.perf_counter()
        build()
        warm = time.perf_counter() - start
        assert obj.stat().st_mtime_ns == modified
        header.write_text('#define VALUE 11\n')
        build()
        assert obj.read_bytes() != original
        stamp = Path(f'{obj}.sha256')
        before = stamp.read_text()
        build([cc, '-O0'])
        assert stamp.read_text() != before
        source.write_text('this is not C;\n')
        try:
            build()
        except subprocess.CalledProcessError:
            pass
        else:
            raise AssertionError('invalid C unexpectedly compiled')
        assert not stamp.exists() and not Path(f'{obj}.tmp').exists()
        source.write_text('int value(void) { return 19; }\n')
        build()
        assert stamp.exists() and obj.read_bytes() != original
        print(f'PASS native object cache: cold {cold:.4f}s, warm {warm:.4f}s; '
              'headers, flags, source changes and failed compilation invalidate it')


if __name__ == '__main__':
    main()
