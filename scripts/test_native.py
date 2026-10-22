"""Native object and analysis-stage caching: changed inputs and failures cannot reuse stale results."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import time

import native
from native import compile_source


def memo_contract():
    """Same binary, arguments, named files and ares sources: one run (ADR-0248)."""
    calls, saved = [], (native.ROOT, native.plaid)
    with tempfile.TemporaryDirectory(prefix='plaid memo ') as directory:
        root = Path(directory)
        exe = root / ('target/release/plaid.exe' if os.name == 'nt' else 'target/release/plaid')
        for path in [exe, *(root / p for p in native.ORACLE_SOURCES)]:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('v1')
        source, output = root / 'in.json', root / 'out.json'
        source.write_text('a')

        def fake(*args, **kw):
            calls.append(args)
            if args[0] == 'fail':
                raise subprocess.CalledProcessError(1, args, '', 'refused')
            output.write_text('map of ' + source.read_text())
            return subprocess.CompletedProcess(args, 0, f'run {len(calls)}', '')

        native.ROOT, native.plaid = root, fake
        try:
            run = lambda: native.memo_plaid('discover', source, 0x80000400, output, writes=(output,))
            assert run() == 'run 1' and len(calls) == 1
            output.unlink()
            assert run() == 'run 1' and output.read_text() == 'map of a' and len(calls) == 1
            source.write_text('b')
            assert run() == 'run 2' and output.read_text() == 'map of b'
            for changed in [exe, root / native.ORACLE_SOURCES[1]]:
                changed.write_text('v2' + changed.read_text())
                run()
            assert len(calls) == 4
            for _ in range(2):
                try:
                    native.memo_plaid('fail', source)
                    raise AssertionError('failed command reported success')
                except subprocess.CalledProcessError:
                    pass
            assert len(calls) == 6
        finally:
            native.ROOT, native.plaid = saved
    print('PASS analysis-stage memo: identical invocations reuse stdout and outputs; '
          'binary, argument file, ares source changes and failures rerun')


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
    memo_contract()
    main()
