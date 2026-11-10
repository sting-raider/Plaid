"""Build, sign and publish the launcher as a GitHub release the in-app updater finds.

usage: python release.py "what changed"
Bump "version" in src-tauri/tauri.conf.json first. Needs gh (logged in) and the
signing key at ~/.tauri/plaid-launcher.key (TAURI_SIGNING_PRIVATE_KEY_PATH overrides).
"""
import datetime, json, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = 'sting-raider/Plaid'

notes = sys.argv[1] if len(sys.argv) > 1 else 'Launcher update'
version = json.loads((HERE / 'src-tauri/tauri.conf.json').read_text(encoding='utf-8'))['version']
tag = f'launcher-v{version}'
key = Path(os.environ.get('TAURI_SIGNING_PRIVATE_KEY_PATH', Path.home() / '.tauri/plaid-launcher.key'))
env = {**os.environ, 'TAURI_SIGNING_PRIVATE_KEY': key.read_text().strip(), 'TAURI_SIGNING_PRIVATE_KEY_PASSWORD': ''}
env['PATH'] = str(Path.home() / '.cargo/bin') + os.pathsep + env['PATH']
subprocess.run('npx tauri build --bundles nsis', shell=True, cwd=HERE, env=env, check=True)

setup = HERE / f'src-tauri/target/release/bundle/nsis/Plaid_{version}_x64-setup.exe'
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
subprocess.run(['gh', 'release', 'create', tag, str(setup), str(latest), '-R', REPO, '--target', commit,
                '--title', f'Plaid launcher {version}', '--notes', notes, '--latest'], check=True)
print('published', tag)
