"""Deterministic packaging boundaries; no external downloads or game inputs."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import engine_paths
import package_engine


class EngineContracts(unittest.TestCase):
    def test_checkout_defaults(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(engine_paths, 'BUNDLED', False):
            self.assertEqual(engine_paths.work_root(Path('checkout')), Path('checkout'))
            self.assertEqual(engine_paths.tool('gcc'), 'gcc')

    def test_bundle_relocation_and_work_separation(self):
        with tempfile.TemporaryDirectory(prefix='engine contracts ') as directory:
            base = Path(directory)
            root, work = base / 'moved engine', base / 'user work'
            root.mkdir()
            (root / 'engine.json').write_text(json.dumps(dict(format='plaid-engine-v1', runtime_dlls=['assets/test.dll'])))
            (root / 'assets').mkdir()
            (root / 'assets/test.dll').write_bytes(b'synthetic DLL payload')
            cc = root / 'toolchain/mingw/bin/gcc.exe'
            cc.parent.mkdir(parents=True)
            cc.write_bytes(b'synthetic compiler')
            with patch.object(engine_paths, 'ROOT', root), patch.object(engine_paths, 'BUNDLED', True), \
                    patch.dict(os.environ, {'PLAID_WORK_DIR': str(work), 'PATH': ''}, clear=True), \
                    patch.object(sys, 'dont_write_bytecode', False):
                engine_paths.configure()
                self.assertEqual(engine_paths.work_root(), work)
                self.assertEqual(Path(engine_paths.tool('gcc')), cc)
                self.assertTrue(os.environ['PLAID_REPLAY_CACHE'].startswith(str(work)))
                self.assertEqual(os.environ['PLAID_ENGINE_ROOT'], str(root))
                engine_paths.prepare_runtime(work / 'target/rt64-shim/Release')
                self.assertEqual((work / 'target/rt64-shim/Release/test.dll').read_bytes(), b'synthetic DLL payload')
                self.assertFalse((root / 'target').exists())
                with self.assertRaises(FileNotFoundError):
                    engine_paths.tool('clang')

    def test_unknown_dll_refused_and_recursive_closure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seeds = root / 'app.exe'
            seeds.write_bytes(b'app')
            imports = {'app.exe': ['KERNEL32.dll', 'first.dll'], 'first.dll': ['second.dll'], 'second.dll': ['first.dll']}
            with patch.object(package_engine, 'imported_dlls', lambda p, _: imports[p.name]):
                with self.assertRaises(FileNotFoundError):
                    package_engine.dll_closure([seeds], [root], root / 'out', 'unused')
                for name in ('first.dll', 'second.dll'):
                    (root / name).write_bytes(name.encode())
                result = package_engine.dll_closure([seeds], [root], root / 'out', 'unused')
                self.assertEqual([p.name for p in result], ['first.dll', 'second.dll'])

    def test_download_digest_refusal(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(package_engine, 'DOWNLOADS', Path(directory)):
            payload = Path(directory) / 'archive.zip'
            payload.write_bytes(b'cached test')
            self.assertEqual(package_engine.download('unused', payload.name, hashlib.sha256(payload.read_bytes()).hexdigest()), payload)
            with self.assertRaises(ValueError):
                package_engine.download('unused', payload.name, '0' * 64)

    def test_packager_does_not_copy_game_outputs(self):
        # Retain the resource boundary as data rather than copying target/ or .refs/.
        self.assertNotIn('test_engine.py', package_engine.SCRIPTS)
        self.assertIn('native.py', package_engine.SCRIPTS)
        self.assertTrue(package_engine.SYSTEM_DLL.search('api-ms-win-crt-runtime-l1-1-0.dll'))
        self.assertFalse(package_engine.SYSTEM_DLL.search('VCRUNTIME140.dll'))
        self.assertFalse(package_engine.SYSTEM_DLL.search('libwinpthread-1.dll'))


def run_contract():
    result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(EngineContracts))
    assert result.wasSuccessful(), 'engine packaging boundary regression'


if __name__ == '__main__':
    unittest.main()
