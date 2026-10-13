"""Verify storage effects against the exact independent reference baseline."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expected_effects():
    rows = [(0,0x10,4,0xf1234567)]*2 + [(0,0x14,4,0x10203040),
        (0,0x18,4,0x11223344),(0,0x1c,4,0x55667788),
        (0,0x20,4,0x01234567),(0,0x24,4,0x89abcdef)]
    rows += [(0,0x30+4*n,4,0x01020304+0x04040404*n) for n in range(4)]
    rows += [(0,0x41+n,1,v) for n,v in enumerate(bytes.fromhex('a1b2c3d4'))]
    # Values verified against the exact pinned RBusDevice declaration.
    rows += [(0,0x50+n,1,n) for n in (5,6,4,10)]
    rows += [(0,0x70,2,0x2345),(3,0,256,0),(1,0,256,0),
        (2,0,256,0),(4,0,256,0),(1,0,64,0)]
    return [dict(ordinal=i+1,kind=k,address=a,bytes=b,value=v) for i,(k,a,b,v) in enumerate(rows)]


def main():
    if os.name == 'nt':
        path = subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',str(HERE/'run.py')],text=True).strip()
        subprocess.run(['wsl','-d','Ubuntu','--exec','python3',path,*sys.argv[1:]],check=True)
        return
    output = ROOT/'target/storage-mutation-primary'
    output.mkdir(parents=True,exist_ok=True)
    builder = load('storage_builder',ROOT/'spikes/003-ares-oracle/run.py')
    results = {}
    if '--verify-existing' not in sys.argv:
        for name, driver, sensor in [('baseline','baseline.cpp',False),('sensor','driver.cpp',True)]:
            print('Building',name,flush=True)
            executable = builder.build(HERE/driver,output/name,extra_sources=[HERE/'driver.cpp'],memory_mutation_access=sensor)
            for mode in ('plain','traced','repeat'):
                result = subprocess.check_output([str(executable),'plain' if mode=='plain' else 'traced'],timeout=30)
                (output/f'{name}-{mode}.json').write_bytes(result)
    for name in ('baseline','sensor'):
        results[name] = {mode:json.loads((output/f'{name}-{mode}.json').read_bytes()) for mode in ('plain','traced','repeat')}
    states = results['baseline']['plain']['states']
    for modes in results.values():
        for result in modes.values(): assert result['states'] == states
    for result in results['baseline'].values(): assert result['effects'] == []
    assert results['sensor']['plain']['effects'] == []
    assert results['sensor']['traced'] == results['sensor']['repeat']
    assert results['sensor']['traced']['effects'] == expected_effects(), results['sensor']['traced']['effects']
    assert len(states) == 20
    by_name = {state['name']:state for state in states}
    assert by_name['saved']['ram'] == by_name['restored']['ram']
    assert by_name['outside']['ram'] == by_name['translated']['ram']
    assert by_name['loaded']['ram'][:8] == list(bytes.fromhex('76543210fedcba98'))
    assert by_name['foreign']['ram'] == by_name['reallocated']['ram'] == [0]*64
    hashes = {str(path.relative_to(output)):hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(output.glob('*-*.json'))}
    for name in ('baseline','sensor'):
        for filename in ('oracle','build.json'):
            path=output/name/filename
            hashes[str(path.relative_to(output))]=hashlib.sha256(path.read_bytes()).hexdigest()
    receipt = dict(format='plaid-storage-mutation-sensing-receipt-v0',revision=builder.REV,
        states=len(states),effects=len(expected_effects()),controls_equal=True,repeat_equal=True,
        artifacts=hashes,
        source_sha256=hashlib.sha256((output/'sensor-traced.json').read_bytes()).hexdigest(),
        complete_mutation_census_certified=False,executable_lifetime_certified=False,native_complete=False)
    (output/'receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    print(json.dumps(receipt,sort_keys=True),flush=True)


if __name__ == '__main__': main()
