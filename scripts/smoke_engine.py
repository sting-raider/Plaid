"""Run a relocated engine with a sanitized PATH and fresh private outputs.

    python scripts/smoke_engine.py dist/engine [--rom <user-local ROM>]

The original synthetic CLI ROM exercises discover/solve/lower/C compile/run.
Production native.py deliberately rejects its unrecognized synthetic IPL3.
A supplied supported game additionally exercises the full native.py --rt64 flow.
No game inputs, generated code or paths are written into tracked files.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import time


def run(bundle, env, *arguments):
    result = subprocess.run(list(map(str, arguments)), cwd=bundle, env=env,
                            capture_output=True, text=True, errors='replace')
    if result.returncode:
        print(result.stdout[-8000:])
        print(result.stderr[-8000:])
        result.check_returncode()
    return result


def synthetic(bundle, work, env):
    # Original fixture from scripts/test_cli.py: two blocks and an indirect edge.
    data = bytearray(4096)
    data[:4] = bytes.fromhex('80371240')
    data[8:12] = struct.pack('>I', 0x80000000)
    words = [0x3c088000, 0x35080020, 0x01000008, 0, 0, 0, 0, 0, 0x08000008, 0]
    data[64:104] = struct.pack('>10I', *words)
    rom, mapping, source = [work / n for n in ('synthetic.z64', 'map.json', 'native.c')]
    rom.write_bytes(data)
    plaid = bundle / 'target/release/plaid.exe'
    run(bundle, env, plaid, 'discover', rom, '64', '0x80000000', '40', '0x80000000', mapping, '--address-taken')
    verdict = json.loads(run(bundle, env, plaid, 'solve', rom, mapping, '--address-taken').stdout)
    assert verdict['status'] == 'closed', verdict
    run(bundle, env, plaid, 'lower-map', rom, mapping, '0x80000000', '0x80000020', source)
    harness = work / 'harness.c'
    harness.write_text('#include "native.c"\n#include <stdio.h>\nstatic plaid_state s;\n'
        'int main(void) { int r=plaid_run(&s); printf("%d %08x %08x %u\\n",r,s.pc,(unsigned)s.r[8],s.fault);'
        'return r || s.pc!=0x80000020u || (unsigned)s.r[8]!=0x80000020u || s.fault; }\n')
    cc = bundle / 'toolchain/mingw/bin/gcc.exe'
    exe = work / 'synthetic.exe'
    run(bundle, env, bundle / 'python/python.exe', '-B', '-c',
        'import engine_paths,subprocess,sys; subprocess.run(sys.argv[1:],check=True)',
        cc, '-O0', '-std=gnu11', harness, '-o', exe)
    # GCC-generated programs must run without toolchain/bin on PATH too.
    for name in ('libgcc_s_seh-1.dll', 'libwinpthread-1.dll'):
        path = cc.parent / name
        if path.exists():
            shutil.copy2(path, work / name)
    result = run(bundle, env, exe)
    assert result.stdout.strip() == '0 80000020 80000020 0', result.stdout
    return dict(result='PASS', state=result.stdout.strip(), scope='synthetic CLI discover/solve/lower/compile/run; not IPL boot')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--rom', type=Path)
    parser.add_argument('--seconds', default='5')
    parser.add_argument('--checkout', type=Path, help='also build normally here and compare first-graphics-task stops')
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    original = args.bundle.resolve()
    # Unzip/copy outside the checkout, under a different root containing spaces.
    with tempfile.TemporaryDirectory(prefix='plaid relocated engine ') as temporary:
        base = Path(temporary)
        bundle, work = base / 'engine', base / 'writable work'
        shutil.copytree(original, bundle)
        work.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.startswith(('PLAID_', 'CARGO_', 'RUST', 'PYTHON', 'CC', 'CXX'))}
        env.update(PATH=str(Path(os.environ['SystemRoot']) / 'System32'),
                   PLAID_WORK_DIR=str(work), SDL_AUDIODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1')
        for name in ('cargo', 'rustc', 'python', 'clang', 'gcc', 'git'):
            assert shutil.which(name, path=env['PATH']) is None, name
        started = time.perf_counter()
        receipt = dict(format='plaid-engine-smoke-v1', synthetic=synthetic(bundle, work, env))
        if args.rom:
            result = run(bundle, env, bundle / 'python/python.exe', '-B', '-u', 'scripts/native.py', args.rom.resolve(),
                         '--name', 'smoke', '--rt64', '--seconds', args.seconds)
            assert (work / 'target/native/smoke/smoke.exe').is_file()
            program = work / 'target/rt64-shim/Release/smoke-rt64.exe'
            assert program.is_file()
            # native.py prints only a 400-character preview. Read a complete stop
            # directly from the produced executable for JSON/state comparisons.
            validation = run(bundle, env, program, '--rom', args.rom.resolve(), '--stop-at', 'none', '--seconds', args.seconds)
            stops = [json.loads(line) for line in validation.stdout.splitlines() if line.startswith('{"stop"')]
            assert stops and stops[-1]['fault'] == 0, validation.stdout[-4000:]
            receipt['game'] = dict(result='PASS', stop=stops[-1], rom_sha256=hashlib.sha256(args.rom.read_bytes()).hexdigest())
            if args.checkout:
                checkout = args.checkout.resolve()
                checkout_work = base / 'checkout work'
                checkout_env = {k: v for k, v in os.environ.items() if not k.startswith('PLAID_')}
                checkout_env.update(PLAID_WORK_DIR=str(checkout_work), SDL_AUDIODRIVER='dummy')
                assets = checkout_work / 'target/rt64-shim/Release'
                assets.mkdir(parents=True)
                # Same freshly built shim; baseline still uses the host tools.
                for dll in (bundle / 'target/rt64-shim/Release').glob('*.dll'):
                    shutil.copy2(dll, assets / dll.name)
                import sys
                baseline = run(checkout, checkout_env, sys.executable, '-u', 'scripts/native.py', args.rom.resolve(),
                               '--name', 'smoke', '--rt64', '--seconds', args.seconds)
                compared = []
                for cwd, run_env, program in [(bundle, env, work / 'target/rt64-shim/Release/smoke-rt64.exe'),
                        (checkout, checkout_env, assets / 'smoke-rt64.exe')]:
                    first = run(cwd, run_env, program, '--rom', args.rom.resolve(), '--stop-at', 'gfx', '--gfx-tasks', '1', '--seconds', '30')
                    compared.append(next(line for line in first.stdout.splitlines() if line.startswith('{"stop"')))
                assert compared[0] == compared[1], compared
                receipt['checkout_comparison'] = dict(result='PASS', stop_line=compared[0])
        assert not (bundle / 'target/native').exists(), 'bundle resource directory was written'
        receipt['seconds'] = round(time.perf_counter() - started, 3)
        if args.receipt:
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
