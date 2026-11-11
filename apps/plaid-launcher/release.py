"""Build, sign and publish the launcher as a GitHub release the in-app updater finds.

usage: python release.py NOTES.md
NOTES.md is the GitHub release body (Markdown: "## What's new", "## Known limitations",
one "- **Name.** sentence" bullet per item). The app's update panel shows the same bullets.
List only what works in this build. Bump "version" in src-tauri/tauri.conf.json first. Needs gh (logged in) and the
signing key at ~/.tauri/plaid-launcher.key (TAURI_SIGNING_PRIVATE_KEY_PATH overrides).
"""
import datetime, hashlib, json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = 'sting-raider/Plaid'

notes_md = Path(sys.argv[1]).read_text(encoding='utf-8')
# the in-app panel: the bullets, whose leading **Name.** it renders in bold; a limitation is labelled
lines, section = [], ''
for line in notes_md.splitlines():
    if line.startswith('## '):
        section = line[3:].strip()
    elif line.lstrip().startswith('- '):
        text = line.lstrip()[2:].strip()
        lines.append(f"**Known limitation.** {text.replace('**', '')}" if 'limitation' in section.lower() else text)
notes = '\n'.join(lines)
version = json.loads((HERE / 'src-tauri/tauri.conf.json').read_text(encoding='utf-8'))['version']
tag = f'launcher-v{version}'
key = Path(os.environ.get('TAURI_SIGNING_PRIVATE_KEY_PATH', Path.home() / '.tauri/plaid-launcher.key'))
env = {**os.environ, 'TAURI_SIGNING_PRIVATE_KEY': key.read_text().strip(), 'TAURI_SIGNING_PRIVATE_KEY_PASSWORD': ''}
env['PATH'] = str(Path.home() / '.cargo/bin') + os.pathsep + env['PATH']
# The app downloads the engine (ADR-0316) on first run from its own release, engine-<sha12>,
# pinned into the build by URL and SHA-256; app updates stay small. Build it from this checkout.
# PLAID_ENGINE_READY=1 reuses a dist/engine-windows-x64.zip already built from this same commit.
repo = HERE.parents[1]
# PLAID_BUILT=1 publishes the installer already built (and tested) in target/, building nothing.
built = os.environ.get('PLAID_BUILT') == '1'
engine_zip = repo / 'dist/engine-windows-x64.zip'
if not built and os.environ.get('PLAID_ENGINE_READY') != '1':
    shutil.rmtree(repo / 'dist/engine', ignore_errors=True)  # build output; the packager refuses to overwrite it
    engine_zip.unlink(missing_ok=True)
    subprocess.run([sys.executable, 'scripts/package_engine.py'], cwd=repo, env=env, check=True)
if not engine_zip.exists():
    sys.exit(f'{engine_zip} is missing; the app would have no engine to download')
engine_sha = hashlib.sha256(engine_zip.read_bytes()).hexdigest()
engine_tag = f'engine-{engine_sha[:12]}'
engine_asset = f'plaid-engine-{engine_sha[:12]}.zip'
env['PLAID_ENGINE_SHA256'] = engine_sha
env['PLAID_ENGINE_URL'] = f'https://github.com/{REPO}/releases/download/{engine_tag}/{engine_asset}'
# a dev build may have left its icon in the exe's resources; build the app crate from clean
if not built:
    subprocess.run('cargo clean -p plaid-launcher --release --manifest-path src-tauri/Cargo.toml', shell=True, cwd=HERE, env=env, check=True)
    subprocess.run('npx tauri build --bundles nsis', shell=True, cwd=HERE, env=env, check=True)

setup = HERE / f'src-tauri/target/release/bundle/nsis/Plaid_{version}_x64-setup.exe'
# Defender's ML model flagged one unsigned build (Trojan:Win32/Bearfoos.A!ml) while a rebuild
# scanned clean; never publish a file Defender flags. shortcut: until the installer is code-signed.
if os.name == 'nt':
    mp = Path(os.environ['ProgramFiles']) / 'Windows Defender/MpCmdRun.exe'
    scan = subprocess.run([str(mp), '-Scan', '-ScanType', '3', '-File', str(setup), '-DisableRemediation'], capture_output=True, text=True)
    if 'found no threats' not in scan.stdout:
        sys.exit(f'Defender flags {setup.name}; not publishing. Rebuild and rerun. ' + scan.stdout[-600:])
latest = setup.with_name('latest.json')
latest.write_text(json.dumps({
    'version': version,
    'notes': notes,
    'pub_date': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    'platforms': {'windows-x86_64': {
        'signature': Path(f'{setup}.sig').read_text().strip(),
        'url': f'https://github.com/{REPO}/releases/download/{tag}/{setup.name}',
    }},
}, indent=2))
commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=HERE, text=True).strip()
# the engine release first, so the new app finds its engine; an unchanged engine is reused.
# Never --latest: the updater reads latest.json from the latest release.
if subprocess.run(['gh', 'release', 'view', engine_tag, '-R', REPO], capture_output=True).returncode:
    upload = engine_zip.with_name(engine_asset)
    shutil.copyfile(engine_zip, upload)
    subprocess.run(['gh', 'release', 'create', engine_tag, f'{upload}', '-R', REPO, '--target', commit,
                    '--title', f'Plaid engine {engine_sha[:12]}', '--latest=false', '--prerelease',
                    '--notes', f'Recompiler engine the launcher downloads on first run. SHA-256 `{engine_sha}`.'], check=True)
    upload.unlink()
# PLAID_CANDIDATE=1 stops here: the engine is up, the installer is for testing; publish
# that same file after testing with PLAID_BUILT=1 PLAID_ENGINE_READY=1.
if os.environ.get('PLAID_CANDIDATE') == '1':
    sys.exit(f'release candidate ready to test: {setup}')
subprocess.run(['gh', 'release', 'create', tag, str(setup), str(latest), '-R', REPO, '--target', commit,
                '--title', f'Plaid launcher {version}', '--notes', notes_md, '--latest'], check=True)
print('published', tag)
