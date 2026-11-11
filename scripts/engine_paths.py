"""Resource/tool resolution for an installed engine; checkout defaults stay intact."""
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
BUNDLED = (ROOT / 'engine.json').is_file()


def work_root(root=ROOT):
    return Path(os.environ['PLAID_WORK_DIR']).resolve() if os.environ.get('PLAID_WORK_DIR') else root


def configure():
    if not BUNDLED and not os.environ.get('PLAID_WORK_DIR'):
        return
    work = work_root()
    work.mkdir(parents=True, exist_ok=True)
    # Child Python and Rust analysis processes inherit these same destinations.
    for key, folder in [('PLAID_OBJECT_CACHE', 'objects'), ('PLAID_REPLAY_CACHE', 'ares-replay'),
                        ('PLAID_ORACLE_CACHE', 'ares-oracle')]:
        os.environ.setdefault(key, str(work / 'target/cache' / folder))
    temporary = work / 'target/tmp'
    temporary.mkdir(parents=True, exist_ok=True)
    os.environ['TMP'] = os.environ['TEMP'] = os.environ['TMPDIR'] = str(temporary)
    if BUNDLED:
        if json.loads((ROOT / 'engine.json').read_text())['format'] != 'plaid-engine-v1':
            raise RuntimeError('unsupported engine bundle format')
        os.environ['PLAID_ENGINE_ROOT'] = str(ROOT)
        os.environ['PLAID_PYTHON'] = str(ROOT / 'python/python.exe')
        os.environ['PATH'] = os.pathsep.join(map(str, [ROOT / 'toolchain/mingw/bin',
            ROOT / 'toolchain/llvm/bin', ROOT / 'python'])) + os.pathsep + os.environ.get('PATH', '')
        os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
        sys.dont_write_bytecode = True


def tool(name):
    if not BUNDLED:
        return name
    folder = 'llvm' if name == 'clang' else 'mingw'
    path = ROOT / 'toolchain' / folder / 'bin' / f'{name}.exe'
    if not path.is_file():
        raise FileNotFoundError(f'missing bundled tool: {path}')
    return str(path)


def prepare_runtime(destination):
    """Keep generated games runnable without the compiler directory on PATH."""
    if not BUNDLED:
        return
    destination.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / 'engine.json').read_text())
    for relative in manifest['runtime_dlls']:
        source = ROOT / relative
        target = destination / source.name
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)


configure()
