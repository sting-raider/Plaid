"""Capture actual PI queue scopes, recheck exact complete prior boot projections."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from verify import inspect

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / 'target/ares-boot-pi-queue-history-spike'

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def capture(budget, variant):
    boot = load('queue_boot_capture', ROOT / 'spikes/008-ares-pif-boot/run.py')
    history = load('queue_base_history', ROOT / 'spikes/027-ares-boot-history/run.py')
    options = dict(cache_fill_access=True, cache_operation_access=True, rdram_burst_access=True,
                   rdram_scalar_access=True, fetch_boundary_access=True, pi_dma_access=True)
    observers = (ROOT / 'spikes/030-ares-boot-pi-history/observer.hpp',
                 ROOT / 'spikes/027-ares-boot-history/observer.hpp',
                 ROOT / 'spikes/011-ares-cache-fetch/driver.cpp')
    driver = ROOT / 'spikes/030-ares-boot-pi-history/driver.cpp'
    directory = 'pi'
    if variant == 'queue':
        options['queue_access'] = True
        driver, directory = HERE / 'driver.cpp', 'queue'
        observers = (HERE / 'observer.hpp', *observers[:2],
                     ROOT / 'spikes/032-ares-queue-identity/observer.hpp', observers[2])
    return boot.worker(budget, driver=driver, output_root=OUTPUT / directory,
                       boot_inputs=history.PROFILE, cache_policy='selected_icache_line_at_prologue',
                       build_options=options, observer_sources=observers, run_timeout=600)

def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as file:
        while chunk := file.read(1024 * 1024):
            result.update(chunk)
    return result.hexdigest()

def verify(budget):
    boot = load('queue_boot_verify', ROOT / 'spikes/008-ares-pif-boot/run.py')
    history = load('queue_history_verify', ROOT / 'spikes/027-ares-boot-history/run.py')
    old = load('queue_pi_verify', ROOT / 'spikes/030-ares-boot-pi-history/verify.py')
    baseline, current = OUTPUT / 'pi' / str(budget), OUTPUT / 'queue' / str(budget)
    if not baseline.exists():
        # A retained fully checked v1 capture avoids recapturing gigabytes.
        # Complete byte/state/source equality below still checks every input.
        baseline = ROOT / 'target/ares-boot-pi-history-spike/pi' / str(budget)
    states = []
    for directory in (baseline, current):
        checkpoints = [json.loads((directory / f'{mode}.json').read_text()) for mode in ('plain', 'traced', 'repeat')]
        assert checkpoints[0] == checkpoints[1] == checkpoints[2]
        states.append(checkpoints[0])
        for suffix in ('ndjson', 'ndjson.history.ndjson', 'messages'):
            boot.equal_files(directory / f'traced.{suffix}', directory / f'repeat.{suffix}')
        assert not (directory / 'plain.ndjson.history.ndjson').exists()
    assert states[0] == states[1]
    for suffix in ('ndjson', 'messages'):
        boot.equal_files(baseline / f'traced.{suffix}', current / f'traced.{suffix}')
    raw = current / 'traced.ndjson.history.ndjson'
    projection = current / 'v1-projection.ndjson'
    with projection.open('wb') as file:
        report = inspect(history.records(raw), file)
    boot.equal_files(projection, baseline / 'traced.ndjson.history.ndjson')
    v0 = current / 'v0-projection.ndjson'
    with v0.open('wb') as file:
        report['pi_effects'] = old.inspect(history.records(projection), boot.ROM.read_bytes(), file)
    report['prior'] = history.verify(v0, current / 'traced.ndjson', budget)
    report.update(history_sha256=digest(raw), v1_projection_sha256=digest(projection),
                  v0_projection_sha256=digest(v0), paired_fetch_sha256=digest(current / 'traced.ndjson'),
                  checkpoint_unchanged=True)
    (current / 'queue-history-results.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps(report, sort_keys=True))
    print('PASS: actual PI request/queue/dispatch scopes retain exact complete v1/v0/v5 and reported checkpoints')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--budget', type=int, default=10000)
    parser.add_argument('--capture', choices=('v1', 'queue'))
    parser.add_argument('--verify-existing', action='store_true')
    args = parser.parse_args()
    assert 0 < args.budget <= 1000000 and not (args.capture and args.verify_existing)
    if os.name == 'nt':
        script = subprocess.check_output(['wsl', '-d', 'Ubuntu', '--exec', 'wslpath', '-a', Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(['wsl', '-d', 'Ubuntu', '--exec', 'python3', script, *sys.argv[1:]], check=True)
    elif args.capture:
        capture(args.budget, args.capture)
    else:
        if not args.verify_existing:
            capture(args.budget, 'v1')
            capture(args.budget, 'queue')
        verify(args.budget)

if __name__ == '__main__':
    main()
