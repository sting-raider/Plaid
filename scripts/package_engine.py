"""Assemble the Windows x64 offline engine (maintainer build tools required).

    python scripts/package_engine.py

Output: dist/engine/ and dist/engine-windows-x64.zip. Licenses and the
redistribution decision are in ADR-0316 and THIRD_PARTY_NOTICES/INDEX.txt.
No ROM, game build, save, replay cache, console firmware or entire checkout is
copied; the analysis oracle boots without the PIF ROM (ADR-0316) and the final
audit refuses any file that is a known PIF boot ROM.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS = ROOT / 'target/engine-downloads'
PYTHON_URL = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip'
PYTHON_SHA = '4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3'
PSUTIL_URL = 'https://files.pythonhosted.org/packages/50/1b/6921afe68c74868b4c9fa424dad3be35b095e16687989ebbb50ce4fceb7c/psutil-7.0.0-cp37-abi3-win_amd64.whl'
PSUTIL_SHA = '4cf3d4eb1aa9b348dec30105c55cd9b7d4629285735a102beb4441e38db90553'
LLVM_REV = '4434dabb69916856b824f68a64b029c67175e532'
MINGW_BUILD_REV = '076c9de644c2f373858d2c4e34ba95a0887423cb'
SCRIPTS = ('native.py', 'engine_paths.py', 'ares_boot.py', 'ares_oracle.py',
           'harvest_boot.py', 'native_audio.py', 'fragment_mapped.py', 'repair_record.py')
# Console firmware must never ship (AGENTS.md invariant 4): the pinned ares NTSC and PAL PIF ROMs.
FIRMWARE_SHA256 = {
    'fa7b09795ef1e54461e59f6f2d902368133e3f1cd980e34383e6a780d74beffd': 'PIF NTSC boot ROM',
    '79c81fffae934b6df251da6c3a394f52c6a0eaa07115a3b9677743e3c1335f4a': 'PIF PAL boot ROM',
}
# RT64 vendors these two headers without a license file; upstream is MIT (ADR-0316).
UTF8CONV_SHA256 = {
    'utf8conv.h': '15e9bfa5d7361c38715e11bc334aca97098ca2eb91458419d0e4da5b71ca449f',
    'utf8except.h': 'bd0ea604b7356725fff93c94cda260893dff0657f21b2b84757899fd337b1b19',
}
UTF8CONV_COMMIT = '6a7d4612cf18c62456504b2bf60b3802a1b95552'
UTF8CONV_LICENSE_SHA256 = '76e8b35698653c646cac547272b6c1b2173e3bc92c6f19d1ad1e9825d18427f2'
# (component, shipped license, where its text is in THIRD_PARTY_NOTICES). Mirrors the ADR-0316 table.
LICENSES = [
    ('Plaid (plaid.exe, scripts, runtime C, headers)', 'MIT OR Apache-2.0', 'plaid/'),
    ('Rust crates linked into plaid.exe', 'per crate (engine.json rust_components)', 'rust/'),
    ('ares reference core (analysis oracle)', 'ISC', 'ares/LICENSE'),
    ('sljit (inside the oracle)', 'BSD-2-Clause', 'ares/sljit-LICENSE'),
    ('xxHash (inside the oracle)', 'BSD-2-Clause', 'ares/xxhash-LICENSE.txt'),
    ('PIF boot ROM', 'not distributed (HLE IPL2 state table instead)', '-'),
    ('RT64 renderer', 'MIT', 'rt64/'),
    ('RT64 utf8conv headers', 'MIT (upstream Giovanni Dicanio)', 'rt64/utf8conv/LICENSE.MIT'),
    ('RT64 miniz, nlohmann/json, plainargs', 'MIT, MIT, Unlicense', 'rt64/'),
    ('SDL2', 'zlib', 'rt64/'),
    ('DirectX-Headers (compiled in)', 'MIT', 'directx-headers/'),
    ('DirectXShaderCompiler dxcompiler.dll', 'LLVM/UIUC + MIT', 'dxc/'),
    ('DXIL validator dxil.dll', 'Microsoft redistribution terms', 'dxc/LICENSE-MS.txt'),
    ('Visual C++ runtime DLLs', 'Microsoft redistributable terms', 'msvc/'),
    ('Python 3.12.10 (embeddable) and its libraries', 'PSF-2.0 and bundled-library licenses', 'python-dependencies/'),
    ('psutil 7.0.0', 'BSD-3-Clause', 'python/site-packages/psutil-7.0.0.dist-info'),
    ('MinGW-Builds GCC 15.2.0, binutils 2.45', 'GPL-3.0-or-later with GCC Runtime Library Exception', 'mingw/, mingw-sources/'),
    ('mingw-w64 v13 runtime, headers, winpthreads', 'ZPL-2.1 / MIT-style / public domain', 'mingw/'),
    ('LLVM/Clang (tested commit) and builtin headers', 'Apache-2.0 WITH LLVM-exception', 'llvm/LICENSE.txt'),
]
# The VC++ 2015-2022 runtime comes from Visual Studio's redistributable CRT folder, never
# System32, and is recorded by hash in engine.json (ADR-0316).
VC_RUNTIME = re.compile(r'^(msvcp140(_\d)?|vcruntime140(_1)?|concrt140|vcomp140)\.dll$', re.I)
SYSTEM_DLL = re.compile(r'^(api-ms-|ext-ms-)|^(kernel32|ntdll|user32|gdi32|gdi32full|advapi32|'
    r'shell32|shlwapi|ole32|oleaut32|comdlg32|comctl32|ws2_32|winmm|imm32|version|'
    r'setupapi|cfgmgr32|secur32|bcrypt|bcryptprimitives|crypt32|cryptbase|rpcrt4|'
    r'ucrtbase|msvcrt|dwmapi|uxtheme|hid|wintrust|normaliz|psapi|powrprof|d3dcompiler_47|'
    r'iphlpapi|userenv|dbghelp|pdh|cabinet|msi|d3d12|dxgi|d3d11|opengl32|winhttp|msimg32|'
    r'wldap32|dinput8|xinput1_4|xinput9_1_0|mfplat|avrt|propsys|mfreadwrite)\.dll$', re.I)


def run(*args, **kwargs):
    print('+', *args, flush=True)
    return subprocess.run(list(map(str, args)), cwd=ROOT, check=True, **kwargs)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download(url, name, expected=None):
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    path = DOWNLOADS / name
    if not path.is_file():
        temporary = path.with_suffix(path.suffix + '.tmp')
        with urllib.request.urlopen(url, timeout=120) as response, temporary.open('wb') as output:
            shutil.copyfileobj(response, output)
        temporary.replace(path)
    if expected and sha(path) != expected:
        raise ValueError(f'download digest mismatch: {name}')
    return path


def copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def tree(source, destination):
    shutil.copytree(source, destination, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('.git', '__pycache__'))


def imported_dlls(path, objdump):
    result = subprocess.check_output([str(objdump), '-p', str(path)], text=True, errors='replace')
    return re.findall(r'DLL Name:\s+(\S+)', result)


def dll_closure(seeds, search, destination, objdump):
    """Resolve PE imports recursively; never silently use an installed VC runtime."""
    found, pending = {}, list(seeds)
    while pending:
        path = pending.pop()
        for name in imported_dlls(path, objdump):
            key = name.lower()
            if SYSTEM_DLL.search(name) or key in found:
                continue
            source = next((folder / name for folder in search if (folder / name).is_file()), None)
            if source is None:
                raise FileNotFoundError(f'unbundled PE dependency {name} imported by {path.name}')
            target = destination / name
            if source.resolve() != target.resolve():
                copy(source, target)
            found[key] = target
            pending.append(target)
    return sorted(found.values())


def notices_under(source, destination):
    """Retain nested upstream notices, including header-only and static dependencies."""
    for path in source.rglob('*'):
        if path.is_file() and not any(p in ('.git', 'node_modules') for p in path.parts):
            name = path.name.lower()
            if (name.startswith(('license', 'licence', 'copying', 'copyright', 'notice'))
                    and path.suffix.lower() not in ('.cpp', '.h', '.c', '.rs')):
                copy(path, destination / path.relative_to(source))


def cargo_notices(destination):
    metadata = json.loads(subprocess.check_output(['cargo', 'metadata', '--locked', '--format-version', '1'], cwd=ROOT))
    components = []
    for package in metadata['packages']:
        if package['source'] is None:
            continue
        name = f"{package['name']}-{package['version']}"
        notices_under(Path(package['manifest_path']).parent, destination / 'rust' / name)
        components.append(dict(name=name, license=package['license'] or ('MIT' if package['name'] == 'rabbitizer' else None), source=package['repository']))
    return components


def python_notices(destination):
    dependencies = [('openssl-3.0.16', 'LICENSE.txt'), ('bzip2-1.0.8', 'LICENSE'),
        ('libffi-3.4.4', 'LICENSE'), ('xz-5.2.5', 'COPYING'), ('zlib-1.3.1', 'README')]
    for tag, name in dependencies:
        copy(download(f'https://raw.githubusercontent.com/python/cpython-source-deps/{tag}/{name}',
            'python-' + tag + '-' + name), destination / tag / name)
    for name, url in [('expat-2.7.1', 'https://raw.githubusercontent.com/libexpat/libexpat/R_2_7_1/expat/COPYING'),
        ('cpython-additional', 'https://raw.githubusercontent.com/python/cpython/v3.12.10/Doc/license.rst')]:
        copy(download(url, 'python-' + name + '-LICENSE.txt'), destination / name / 'LICENSE.txt')
    # SQLite is public domain; preserve the dedication from its shipped header.
    header = download('https://raw.githubusercontent.com/python/cpython-source-deps/sqlite-3.49.1.0/sqlite3.h',
                      'python-sqlite3.h').read_text()
    path = destination / 'sqlite-3.49.1/LICENSE.txt'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header[:header.index('*/') + 2] + '\n')
    decimal = download('https://raw.githubusercontent.com/python/cpython/v3.12.10/Modules/_decimal/libmpdec/mpdecimal.c',
                       'python-mpdecimal.c').read_text()
    path = destination / 'libmpdec-2.5.1/LICENSE.txt'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(decimal[:decimal.index('*/') + 2] + '\n')


def toolchain_sources(mingw, destination):
    """Ship sources, patches and configure recipes alongside GPL compiler binaries.

    Restricted to the tested MinGW-Builds release, not arbitrary host GCC installs.
    The build-info file supplies exact static prerequisite versions and patches.
    """
    info = (mingw / 'build-info.txt').read_text()
    if 'gcc-15.2.0' not in info or 'binutils-2.45' not in info:
        raise ValueError('engine supports MinGW-Builds GCC 15.2.0 / binutils 2.45')
    copy(mingw / 'build-info.txt', destination / 'build-info.txt')
    sources = {}
    for section in info.split('# **************************************************************************'):
        match = re.search(r'^name\s+: (.+)$', section, re.M)
        url = re.search(r'^url\s+: (.+)$', section, re.M)
        if match and url and any(n in match[1] for n in ('libiconv', 'zlib-', 'gmp-', 'mpfr-', 'mpc-', 'isl-', 'binutils-', 'gcc-')):
            sources[url[1].strip()] = url[1].strip().rsplit('/', 1)[-1]
    # The vendor's build-info accidentally repeats the ISL URL for MinGW.
    sources['https://codeload.github.com/mingw-w64/mingw-w64/tar.gz/refs/tags/v13.0.0'] = 'mingw-w64-v13.0.0.tar.gz'
    sources[f'https://codeload.github.com/niXman/mingw-builds/tar.gz/{MINGW_BUILD_REV}'] = 'mingw-builds-scripts.tar.gz'
    records = []
    for url, name in sources.items():
        # ftp.gnu.org avoids geo-mirror redirects; cached archives are reused.
        url = url.replace('https://ftpmirror.gnu.org/', 'https://ftp.gnu.org/')
        if '/gmp/gmp-' in url and '/gnu/gmp/' not in url:
            url = url.replace('/gmp/', '/gnu/gmp/')
        path = download(url, name)
        copy(path, destination / name)
        records.append(dict(file=name, url=url, sha256=sha(path)))
    (destination / 'sources.json').write_text(json.dumps(records, indent=2) + '\n')


def audit_no_firmware(files):
    """files: {relative path: sha256}. Refuse console firmware by content or name."""
    bad = [f'{name} ({FIRMWARE_SHA256[digest]})' for name, digest in files.items() if digest in FIRMWARE_SHA256]
    bad += [name for name in files if re.search(r'(^|/)pif[^/]*[.](rom|bin)$', name, re.I)]
    if bad:
        raise ValueError('console firmware must not be bundled: ' + ', '.join(sorted(set(bad))))


def build(args):
    if os.name != 'nt':
        raise RuntimeError('first engine target is Windows x64; build on Windows')
    destination = ROOT / 'dist/engine'
    if destination.exists():
        raise FileExistsError('dist/engine already exists; move it aside before packaging')
    mingw = (args.mingw or Path(shutil.which('gcc')).parent.parent).resolve()
    llvm = (args.llvm or Path(shutil.which('clang')).parent.parent).resolve()
    if LLVM_REV not in subprocess.check_output([str(llvm / 'bin/clang.exe'), '--version'], text=True):
        raise ValueError('packaging requires tested LLVM commit ' + LLVM_REV)
    env = os.environ.copy()
    encoded = env.get('CARGO_ENCODED_RUSTFLAGS', '')
    env['CARGO_ENCODED_RUSTFLAGS'] = (encoded + '\x1f' if encoded else '') + f'--remap-path-prefix={ROOT}=.'
    run('cargo', 'build', '--locked', '--release', '-p', 'plaid', env=env)
    sys.path.insert(0, str(ROOT / 'scripts'))
    import ares_boot
    oracle = ares_boot.build_oracle()
    rt64_build = args.rt64_build or ROOT / 'target/engine-rt64'
    headers_zip = download('https://codeload.github.com/microsoft/DirectX-Headers/zip/refs/tags/v1.614.1',
        'DirectX-Headers-v1.614.1.zip', 'ffdf333bfd867bdf32f69898ab822c53922744cc7797729090a7c2b2e63e4982')
    with zipfile.ZipFile(headers_zip) as archive:
        archive.extractall(DOWNLOADS)
    directx_headers = DOWNLOADS / 'DirectX-Headers-1.614.1'
    if args.rt64_build is None:
        includes = ';'.join(str(directx_headers / p) for p in ('include/directx', 'include'))
        run('cmake', '-S', 'runtime/rt64', '-B', rt64_build, '-A', 'x64',
            '-DCMAKE_CXX_STANDARD_INCLUDE_DIRECTORIES=' + includes)
        run('cmake', '--build', rt64_build, '--config', 'Release', '--target', 'plaid_rt64', '--parallel')
    rt64 = rt64_build / 'Release'
    refs = {p['name']: p for p in __import__('tomllib').loads((ROOT / 'refs.lock.toml').read_text())['repo']}
    for name in ('ares', 'rt64', 'n64sym'):
        actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT / '.refs' / name, text=True).strip()
        if actual != refs[name]['rev']:
            raise ValueError(f'{name} reference differs from refs.lock.toml')
        run('git', '-C', ROOT / '.refs' / name, 'diff', '--quiet', 'HEAD', '--ignore-submodules=none')
    for name in SCRIPTS:
        copy(ROOT / 'scripts' / name, destination / 'scripts' / name)
    for name in ares_boot.ORACLE_SOURCES:
        copy(ROOT / name, destination / name)
    for path in (ROOT / 'runtime').glob('*.h'):
        copy(path, destination / 'runtime' / path.name)
    copy(ROOT / 'runtime/plaid_rt.c', destination / 'runtime/plaid_rt.c')
    for path in (ROOT / 'crates/plaid-lower/src').glob('*.h'):
        copy(path, destination / 'crates/plaid-lower/src' / path.name)
    for name in ('icon.rc', 'icon.ico', 'icon.bmp'):
        copy(ROOT / 'runtime/rt64' / name, destination / 'runtime/rt64' / name)
    copy(ROOT / 'target/release/plaid.exe', destination / 'target/release/plaid.exe')
    for name in ('oracle.exe', 'build.json'):
        copy(oracle.parent / name, destination / 'target/ares-boot/oracle' / name)
    for name in ('plaid_rt64.dll', 'plaid_rt64.lib', 'SDL2.dll', 'dxcompiler.dll', 'dxil.dll'):
        copy(rt64 / name, destination / 'target/rt64-shim/Release' / name)
    for relative in ('.refs/n64sym/src/builtin_signatures.sig', 'refs.lock.toml'):
        copy(ROOT / relative, destination / relative)
    with zipfile.ZipFile(download(PYTHON_URL, 'python.zip', PYTHON_SHA)) as archive:
        archive.extractall(destination / 'python')
    (destination / 'python/python312._pth').write_text('python312.zip\n.\n../scripts\nsite-packages\n', encoding='ascii')
    with zipfile.ZipFile(download(PSUTIL_URL, 'psutil.whl', PSUTIL_SHA)) as archive:
        archive.extractall(destination / 'python/site-packages')
    # Copy only the C/C++ toolchain, not unrelated bundled GDB/Python/Fortran tools.
    for name in ('gcc', 'as', 'ld', 'windres', 'objdump', 'ar'):
        copy(mingw / 'bin' / f'{name}.exe', destination / 'toolchain/mingw/bin' / f'{name}.exe')
    game_runtime = ('libgcc_s_seh-1.dll', 'libstdc++-6.dll', 'libwinpthread-1.dll')
    for name in game_runtime:
        copy(mingw / 'bin' / name, destination / 'toolchain/mingw/bin' / name)
    for folder in ('lib/gcc', 'libexec/gcc', 'x86_64-w64-mingw32'):
        shutil.copytree(mingw / folder, destination / 'toolchain/mingw' / folder,
            ignore=shutil.ignore_patterns('f951.exe', 'finclude', '*gfortran*', '*quadmath*', 'install-tools',
                                         'cc1plus.exe', 'g++-mapper-server.exe', '*stdc++*', 'c++'), dirs_exist_ok=True)
    copy(llvm / 'bin/clang.exe', destination / 'toolchain/llvm/bin/clang.exe')
    for version in (llvm / 'lib/clang').iterdir():
        if version.is_dir():
            tree(version / 'include', destination / 'toolchain/llvm/lib/clang' / version.name / 'include')
    notices = destination / 'THIRD_PARTY_NOTICES'
    python_notices(notices / 'python-dependencies')
    tree(mingw / 'licenses', notices / 'mingw')
    notices_under(ROOT / '.refs/rt64', notices / 'rt64')
    contrib = ROOT / '.refs/rt64/src/contrib'
    # These vendored headers carry their notices inline, not in LICENSE files.
    for relative in ('miniz/miniz.c', 'plainargs/plainargs.h', 'utf8conv/utf8conv.h', 'utf8conv/utf8except.h'):
        content = (contrib / relative).read_text()
        if relative.endswith('.c'):
            start = content.index('/*')
            notice = content[start:content.index('*/', start) + 2]
        else:
            notice = content[:content.index('namespace' if relative.startswith('plainargs') else '#ifndef')]
        path = notices / 'rt64/inline' / (relative.replace('/', '-') + '.txt')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(notice + '\n')
    copy(download('https://raw.githubusercontent.com/nlohmann/json/v3.12.0/LICENSE.MIT',
        'nlohmann-json-v3.12.0-LICENSE.MIT'), notices / 'rt64/json/LICENSE.MIT')
    copy(ROOT / '.refs/ares/LICENSE', notices / 'ares/LICENSE')
    copy(ROOT / '.refs/ares/thirdparty/sljit/LICENSE', notices / 'ares/sljit-LICENSE')
    xxhash = (ROOT / '.refs/ares/thirdparty/xxhash.h').read_text(errors='replace')
    (notices / 'ares/xxhash-LICENSE.txt').write_text(xxhash[:xxhash.index('*/') + 2] + '\n')
    copy(ROOT / 'LICENSE-MIT', notices / 'plaid/LICENSE-MIT')
    copy(ROOT / 'LICENSE-APACHE', notices / 'plaid/LICENSE-APACHE')
    for name, digest in UTF8CONV_SHA256.items():
        if sha(contrib / 'utf8conv' / name) != digest:
            raise ValueError(f'RT64 {name} differs from the upstream release whose MIT license ADR-0316 records')
    copy(download(f'https://raw.githubusercontent.com/GiovanniDicanio/UnicodeConversions/{UTF8CONV_COMMIT}/LICENSE',
                  'utf8conv-LICENSE.MIT', UTF8CONV_LICENSE_SHA256), notices / 'rt64/utf8conv/LICENSE.MIT')
    copy(ROOT / '.refs/n64sym/LICENSE.md', notices / 'n64sym/LICENSE.md')
    notices_under(directx_headers, notices / 'directx-headers')
    copy(download(f'https://raw.githubusercontent.com/llvm/llvm-project/{LLVM_REV}/llvm/LICENSE.TXT', 'LLVM-LICENSE.txt'), notices / 'llvm/LICENSE.txt')
    rust_components = cargo_notices(notices)
    toolchain_sources(mingw, notices / 'mingw-sources')
    # DXC's binary package in the RT64 pin lacks notices. Preserve Microsoft's
    # upstream notices as well; the DXIL validator has separate binary terms.
    dxc_zip = download('https://github.com/microsoft/DirectXShaderCompiler/releases/download/v1.7.2212/dxc_2022_12_16.zip',
        'dxc_2022_12_16.zip', 'ed77c7775fcf1e117bec8b5bb4de6735af101b733d3920dda083496dceef130f')
    with zipfile.ZipFile(dxc_zip) as archive:
        if archive.read('bin/x64/dxil.dll') != (rt64 / 'dxil.dll').read_bytes():
            raise ValueError('DXIL validator differs from licensed redistribution package')
        for name in ('LICENSE-LLVM.txt', 'LICENSE-MIT.txt', 'LICENSE-MS.txt'):
            path = notices / 'dxc' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(name))
    copy(download('https://raw.githubusercontent.com/microsoft/DirectXShaderCompiler/0dc8d9060/ThirdPartyNotices.txt',
        'dxc-0dc8d9060-ThirdPartyNotices.txt'), notices / 'dxc/ThirdPartyNotices.txt')
    copy(download('https://visualstudio.microsoft.com/wp-content/uploads/2021/09/Visual-C-Runtime-2015-2022-License-1.docx',
                  'Visual-C-Runtime-License.docx'), notices / 'msvc/Visual-C-Runtime-License.docx')
    objdump = mingw / 'bin/objdump.exe'
    vswhere = Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')) / 'Microsoft Visual Studio/Installer/vswhere.exe'
    vc = []
    if vswhere.is_file():
        # -products * includes Build Tools installs, which hold the redistributable CRT folder.
        installs = subprocess.check_output([str(vswhere), '-all', '-products', '*', '-property', 'installationPath'], text=True).splitlines()
        vc = sorted((c for vs in installs for c in Path(vs).glob('VC/Redist/MSVC/*/x64/Microsoft.VC*.CRT')),
                    key=lambda c: tuple(map(int, c.parts[-3].split('.'))), reverse=True)
    if not vc:
        raise FileNotFoundError('no Visual Studio redistributable CRT folder (VC/Redist/MSVC/*/x64/Microsoft.VC*.CRT)')
    search = [*vc, destination / 'python', rt64, mingw / 'bin', llvm / 'bin']
    # Each application gets its own PE dependency closure, not every other
    # application's DLLs. No reliance on a globally installed VC runtime.
    for folder in ('python', 'target/release', 'target/ares-boot/oracle',
                   'toolchain/mingw', 'toolchain/llvm/bin', 'target/rt64-shim/Release'):
        directory = destination / folder
        seeds = [p for p in directory.rglob('*') if p.suffix.lower() in ('.exe', '.dll', '.pyd')]
        output = directory / 'bin' if folder == 'toolchain/mingw' else directory
        dll_closure(seeds, [directory, *search], output, objdump)
    runtime_dlls = [p.relative_to(destination).as_posix() for p in (destination / 'target/rt64-shim/Release').glob('*.dll')]
    runtime_dlls += ['toolchain/mingw/bin/' + name for name in game_runtime]
    manifest = dict(format='plaid-engine-v1', platform='windows-x86_64',
        source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        redistributable=True, firmware_included=False, pif_boot='hle-ipl2-v1',
        python='3.12.10', psutil='7.0.0', gcc='15.2.0', llvm_revision=LLVM_REV,
        references={name: refs[name] for name in ('ares', 'rt64', 'n64sym')},
        vc_runtime={path.relative_to(destination).as_posix(): sha(path) for path in sorted(destination.rglob('*.dll'))
                    if VC_RUNTIME.match(path.name)},
        rust_components=rust_components, runtime_dlls=sorted(runtime_dlls))
    (destination / 'engine.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (notices / 'INDEX.txt').write_text('Plaid engine third-party notices (see docs/DECISIONS.md ADR-0316)\n\n'
        + ''.join(f'{name}\n    license: {kind}\n    text: THIRD_PARTY_NOTICES/{where}\n' for name, kind, where in LICENSES)
        + '\nNo console firmware is included. MinGW sources, vendor patches and configure recipes are in mingw-sources/.\n'
        'RT64 nested notices include components not linked on Windows; preserved conservatively.\n'
        'Python licenses are in python/LICENSE.txt.\n')
    (destination / 'engine.cmd').write_text('@echo off\r\nsetlocal DisableDelayedExpansion\r\n'
        '"%~dp0python\\python.exe" -B -u "%~dp0scripts\\native.py" %*\r\nexit /b %errorlevel%\r\n')
    (destination / 'README.txt').write_text('Plaid offline Windows x64 engine\n'
        'cwd: this directory\npython\\python.exe -B -u scripts\\native.py <user ROM> --rt64 --seconds 60\n'
        'Set PLAID_WORK_DIR to an absolute writable directory. Default: engine directory.\n'
        'Outputs: %PLAID_WORK_DIR%/target/native/<id> and target/rt64-shim/Release/<id>-rt64.exe\n'
        'No system Python, Rust, git, C compiler or checkout required at runtime.\n'
        'Requires Windows 10+ x64 and a working DirectX12/Vulkan graphics driver.\n'
        'Licenses: THIRD_PARTY_NOTICES/INDEX.txt. No console firmware is included or needed.\n')
    files = {p.relative_to(destination).as_posix(): sha(p) for p in sorted(destination.rglob('*')) if p.is_file()}
    audit_no_firmware(files)
    (destination / 'files.sha256.json').write_text(json.dumps(files, indent=2) + '\n')
    uncompressed = sum(p.stat().st_size for p in destination.rglob('*') if p.is_file())
    archive = ROOT / 'dist/engine-windows-x64.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6, strict_timestamps=False) as output:
        for path in sorted(destination.rglob('*')):
            if path.is_file():
                output.write(path, 'engine/' + path.relative_to(destination).as_posix())
    sizes = dict(uncompressed_bytes=uncompressed, zip_bytes=archive.stat().st_size, files=len(files) + 1)
    (ROOT / 'dist/engine-sizes.json').write_text(json.dumps(sizes, indent=2) + '\n')
    print(json.dumps(sizes), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mingw', type=Path, help='MinGW-Builds GCC 15.2 root (default: from PATH)')
    parser.add_argument('--llvm', type=Path, help='tested LLVM root (default: from PATH)')
    parser.add_argument('--rt64-build', type=Path, help='existing validated RT64 shim build, including Release/')
    build(parser.parse_args())
