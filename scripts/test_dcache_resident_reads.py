"""Shared resident-read/writeback CLI contract; optional authenticated actual capture."""
from pathlib import Path
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FORMAT = 'plaid-dcache-resident-read-history-v1'


def main():
    cargo = shutil.which('cargo') or str(Path.home()/'.cargo/bin/cargo.exe')
    subprocess.run([cargo, 'build', '--locked', '-p', 'plaid'], cwd=ROOT, check=True)
    exe = ROOT/('target/debug/plaid.exe' if os.name == 'nt' else 'target/debug/plaid')
    with tempfile.TemporaryDirectory(prefix='dcache-read-', dir=ROOT/'target') as temporary:
        directory = Path(temporary)
        source, output = directory/'source.json', directory/'report.json'

        def save(events):
            source.write_text(json.dumps(dict(format=FORMAT, events=events)), encoding='utf-8')
            return hashlib.sha256(source.read_bytes()).hexdigest()

        def run(command, digest, ok=True, target=output):
            result = subprocess.run([str(exe), command, str(source), digest, str(target)], capture_output=True, text=True)
            assert (result.returncode == 0) == ok, (command, result.stdout, result.stderr)

        events = [
            dict(record='backing_read', ordinal=1, physical_line=0x2000, payload=[17]*16),
            dict(record='fill', ordinal=2, physical_line=0x2000, slot=0, payload=[17]*16),
            dict(record='backing_word_mutation', ordinal=3, physical=0x2000, payload=[34]*4),
            dict(record='cached_word_read', ordinal=4, pc=0x80006008, effective_virtual=0xffffffff80002000,
                 physical=0x2000, slot=0, payload=[17]*4),
        ]
        digest = save(events)
        run('inspect-dcache-resident-reads', digest)
        run('verify-dcache-resident-reads', digest)
        report = json.loads(output.read_bytes())
        assert report['reads'][0]['resident_generation'] == 2
        assert report['reads'][0]['current_captured_backing']['payload'] == [34]*4
        before = source.read_bytes()
        run('inspect-dcache-resident-reads', digest, ok=False, target=source)
        assert source.read_bytes() == before
        run('inspect-dcache-resident-reads', '0'*64, ok=False)
        forged = copy.deepcopy(report)
        forged['reads'][0]['resident_generation'] = 3
        output.write_text(json.dumps(forged), encoding='utf-8')
        run('verify-dcache-resident-reads', digest, ok=False)
        forged_events = copy.deepcopy(events)
        forged_events[3]['effective_virtual'] = 0x1234567880002000
        run('inspect-dcache-resident-reads', save(forged_events), ok=False)

        if len(sys.argv) == 2:
            raw = Path(sys.argv[1]).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == '6a1bdf2b2f59916ba32f9951db6bae2378eec4fa21854ceae0660970c222f0e9'
            capture = json.loads(raw)
            canonical = json.dumps(capture, sort_keys=True, separators=(',', ':')).encode()
            assert hashlib.sha256(canonical).hexdigest() == 'feab0c6e4d651116f1267c4f5a36e047c6be81634a062d35c2067a5765e21d28'
            reports = {}
            for name, case in capture['cases'].items():
                rows = sorted((e['ordinal'], kind, e) for kind, group in case['events'].items() for e in group)
                normalized, ordinals, fill_for_burst, dispatch = [], {}, {}, None

                def append(record, **fields):
                    normalized.append(dict(record=record, ordinal=len(normalized)+1, **fields))
                    return len(normalized)

                for original, kind, e in rows:
                    if kind == 'bursts':
                        if not e['dcache']:
                            continue
                        assert not e['write'] and e['bytes'] == 16
                        payload = list(b''.join(w.to_bytes(4, 'big') for w in e['words'][:4]))
                        ordinals[original] = append('backing_read', physical_line=e['address'], payload=payload)
                        # Completed miss access below authenticates this successful fill.
                        fill_for_burst[original] = append('fill', physical_line=e['address'], slot=(e['address'] >> 4)&511, payload=payload)
                    elif kind == 'scalars':
                        assert e['write'] and e['uncached_cpu'] and e['bytes'] == 4
                        ordinals[original] = append('backing_word_mutation', physical=e['address'], payload=list(e['value'].to_bytes(4, 'big')))
                    elif kind in ('dreads', 'dwrites'):
                        assert e['bytes'] == 4 and e['tag']&1 and (e['tag']&~1) == (e['paddr']&~4095)
                        assert e['index'] == (e['paddr'] >> 4)&511
                        if not e['hit_before']:
                            assert normalized[-1]['record'] == 'fill'
                            assert normalized[-1]['physical_line'] == e['paddr']&~15
                        fields = dict(physical=e['paddr'], slot=e['index'], payload=list(e['value'].to_bytes(4, 'big')))
                        if kind == 'dreads':
                            fields.update(pc=e['pc'], effective_virtual=e['vaddr'])
                            ordinals[original] = append('cached_word_read', **fields)
                            if e['pc']&0xffffffff == case['facts']['dispatch_pc']:
                                assert dispatch is None
                                dispatch = ordinals[original]
                        else:
                            ordinals[original] = append('resident_word_mutation', **fields)
                    else:
                        raise AssertionError(kind)
                digest = save(normalized)
                run('inspect-dcache-resident-reads', digest)
                run('verify-dcache-resident-reads', digest)
                actual = json.loads(output.read_bytes())
                assert len(actual['reads']) == len(case['events']['dreads'])
                receipt = next(r for r in actual['reads'] if r['read_ordinal'] == dispatch)
                assert int.from_bytes(bytes(receipt['payload']), 'big') == case['facts']['expected_pointer']
                if name == 'resident':
                    mutation = ordinals[case['events']['dwrites'][0]['ordinal']]
                    assert all(o['kind'] == 'resident_word_mutation' and o['mutation_ordinal'] == mutation for o in receipt['origins'])
                    assert receipt['current_captured_backing'] is None  # no invented initial writer
                else:
                    scalar = ordinals[case['events']['scalars'][0]['ordinal']]
                    assert receipt['current_captured_backing']['write_ordinal'] == scalar
                    bursts = [e for e in case['events']['bursts'] if e['dcache'] and e['address'] == 0x2000]
                    expected = bursts[-1]['ordinal']
                    assert receipt['resident_generation'] == fill_for_burst[expected]
                    assert all(o['backing_read_ordinal'] == ordinals[expected] for o in receipt['origins'])
                assert not actual['pointer_table_immutability_certified']
                assert not actual['executable_target_identity_certified']
                assert not actual['writeback']['native_complete']
                reports[name] = actual
                forged = copy.deepcopy(actual)
                forged['reads'][-1]['resident_generation'] = receipt['current_captured_backing']['write_ordinal'] if name != 'resident' else 1
                output.write_text(json.dumps(forged), encoding='utf-8')
                run('verify-dcache-resident-reads', digest, ok=False)
                # Even a freshly authenticated source cannot substitute equal-slot decoy residency.
                forged = copy.deepcopy(normalized)
                next(e for e in forged if e['ordinal'] == dispatch)['physical'] = 0x4000
                run('inspect-dcache-resident-reads', save(forged), ok=False)
            combined = json.dumps(reports, sort_keys=True, separators=(',', ':')).encode()
            print('ACTUAL_REPORT_SET_SHA256=' + hashlib.sha256(combined).hexdigest())
            print('PASS five authenticated actual cases, all captured cached reads and ten fresh forgeries')
    print('PASS resident-read CLI source/report/input contracts')


if __name__ == '__main__':
    main()
