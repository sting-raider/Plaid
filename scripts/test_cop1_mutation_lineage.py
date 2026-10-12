"""COP1 source/context composition contracts; optional retained reference matrix."""
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
FORMAT = 'plaid-cop1-fpr-lineage-v0'


def initial():
    result = [0x7000000000000000+i for i in range(32)]
    result[0], result[1] = 0x1021324355667788, 0x99aabbcc10213243
    return result


def selection(operation, fr, ft):
    width = 4 if operation in ('LWC1', 'SWC1', 'MTC1') else 8
    physical = ft if fr else ft & ~1
    slots = list(range(8)) if width == 8 else list(range(0, 4) if not fr and ft & 1 else range(4, 8))
    return physical, slots


def normalize(case):
    load, load_fr, load_ft, store, store_fr, store_ft, action = case['args']
    actual = case['traced']
    assert case['plain']['events'] == []
    assert {k:v for k,v in case['plain'].items() if k not in ('mode','events')} == {
        k:v for k,v in actual.items() if k not in ('mode','events')}
    raw = initial()
    assert (raw[0], raw[1]) == (actual['before_f0'], actual['before_f1'])
    events, contexts = [], []

    def append(kind, **fields):
        events.append(dict(kind=kind, event=dict(ordinal=len(events)+1, **fields)))
        return len(events)

    if action not in ('success', 'overwrite_equal'):
        assert not actual['events']
        assert (actual['final_f0'], actual['final_f1']) == (raw[0], raw[1])
        reason = {'cu1off':'cu1_disabled','misalign':'misaligned','tlbmiss':'tlb_miss'}[action]
        append('failed_load', context=1, phase=1, operation=load.lower(), architectural_fpr=load_ft,
               fr=bool(load_fr), reason=reason)
    else:
        read, write = actual['events']
        assert read['ordinal'] == 1 and not read['write'] and read['phase'] == 1
        assert write['ordinal'] == 2 and write['write'] and write['phase'] == 3
        physical, slots = selection(load, load_fr, load_ft)
        append('completed_read', context=1, phase=1, address=read['address'], bytes=read['bytes'],
               uncached_cpu=read['uncached_cpu'], value=read['value'])
        append('fpr_write', context=1, phase=1, operation=load.lower(), architectural_fpr=load_ft,
               fr=bool(load_fr), physical_fpr=physical, slots=slots, value=read['value'], source_read_ordinal=1)
        storage = list(raw[physical].to_bytes(8, 'big'))
        for slot, value in zip(slots, read['value'].to_bytes(read['bytes'], 'big')):
            storage[slot] = value
        raw[physical] = int.from_bytes(bytes(storage), 'big')
        assert (raw[0], raw[1]) == (actual['after_load_f0'], actual['after_load_f1'])
        if action == 'overwrite_equal':
            append('fpr_write', context=2, phase=2, operation='mtc1' if load == 'LWC1' else 'dmtc1',
                   architectural_fpr=load_ft, fr=bool(load_fr), physical_fpr=physical, slots=slots,
                   value=read['value'], source_read_ordinal=None)
        assert (raw[0], raw[1]) == (actual['after_overwrite_f0'], actual['after_overwrite_f1'])
        physical, slots = selection(store, store_fr, store_ft)
        ordinal = append('store', context=3, phase=3, operation=store.lower(), architectural_fpr=store_ft,
                         fr=bool(store_fr), physical_fpr=physical, slots=slots, destination=write['address'],
                         bytes=write['bytes'], uncached_cpu=write['uncached_cpu'], value=write['value'])
        # Declared fixture inputs from its authenticated instruction constructor;
        # FPR0/1 snapshots and the backing payload are independently observed.
        # Other FPRs are initialized constants never addressed by this matrix.
        gpr = [0]*32
        gpr[16], gpr[17], gpr[8] = 0xffffffffa0004000, 0xffffffffa0005000, read['value']
        contexts.append(dict(instruction_word=((0x39 if store == 'SWC1' else 0x3d)<<26)|(17<<21)|(store_ft<<16),
                             gpr=gpr, raw_fprs=raw, fr=bool(store_fr), cu1=True,
                             effect=dict(effect_ordinal=ordinal, virtual_destination=gpr[17],
                                         physical_destination=write['address'], domain='backing',
                                         payload=list(write['value'].to_bytes(write['bytes'], 'big')))))
        assert (raw[0], raw[1]) == (actual['final_f0'], actual['final_f1'])
    return dict(format=FORMAT, initial_fprs=initial(), events=events), contexts


def main():
    cargo = shutil.which('cargo') or str(Path.home()/'.cargo/bin/cargo.exe')
    subprocess.run([cargo, 'build', '--locked', '-p', 'plaid'], cwd=ROOT, check=True)
    exe = ROOT/('target/debug/plaid.exe' if os.name == 'nt' else 'target/debug/plaid')
    with tempfile.TemporaryDirectory(prefix='cop1-compose-', dir=ROOT/'target') as temporary:
        directory = Path(temporary)
        source, context, output = directory/'source.json', directory/'contexts.json', directory/'report.json'

        def save(history, inputs):
            source.write_text(json.dumps(history), encoding='utf-8')
            context.write_text(json.dumps(inputs), encoding='utf-8')
            return hashlib.sha256(source.read_bytes()).hexdigest(), hashlib.sha256(context.read_bytes()).hexdigest()

        def run(command, digests, ok=True, target=output):
            result = subprocess.run([str(exe), command, str(source), digests[0], str(context), digests[1], str(target)],
                                    capture_output=True, text=True)
            assert (result.returncode == 0) == ok, (result.stdout, result.stderr)

        payload = list(bytes.fromhex('10213243'))
        events = [dict(kind='completed_read', event=dict(ordinal=1, context=1, phase=1, address=0x4000,
                                                        bytes=4, uncached_cpu=True, value=0x10213243)),
                  dict(kind='fpr_write', event=dict(ordinal=2, context=1, phase=1, operation='lwc1',
                                                  architectural_fpr=1, fr=False, physical_fpr=0, slots=[0,1,2,3],
                                                  value=0x10213243, source_read_ordinal=1)),
                  dict(kind='store', event=dict(ordinal=3, context=3, phase=3, operation='swc1',
                                               architectural_fpr=1, fr=False, physical_fpr=0, slots=[0,1,2,3],
                                               destination=0x5000, bytes=4, uncached_cpu=True, value=0x10213243))]
        history = dict(format=FORMAT, initial_fprs=initial(), events=events)
        gpr=[0]*32;gpr[17]=0xffffffffa0005000
        inputs=[dict(instruction_word=(0x39<<26)|(17<<21)|(1<<16),gpr=gpr,raw_fprs=initial(),fr=False,cu1=True,
                     effect=dict(effect_ordinal=3,virtual_destination=gpr[17],physical_destination=0x5000,
                                 domain='backing',payload=payload))]
        digests=save(history,inputs);run('compose-cop1-mutations',digests);run('verify-cop1-mutations',digests)
        for path in (source,context):
            before=path.read_bytes();run('compose-cop1-mutations',digests,ok=False,target=path);assert path.read_bytes()==before
        run('compose-cop1-mutations',('0'*64,digests[1]),ok=False)
        run('compose-cop1-mutations',(digests[0],'0'*64),ok=False)
        forged=copy.deepcopy(inputs);forged[0]['cu1']=False
        run('compose-cop1-mutations',save(history,forged),ok=False)
        run('compose-cop1-mutations',save(history,[]),ok=False)
        digests=save(history,inputs);run('compose-cop1-mutations',digests)
        report=json.loads(output.read_bytes());report['lineage']['stores'][0]['byte_origins'][0]['read_ordinal']=2
        output.write_text(json.dumps(report),encoding='utf-8');run('verify-cop1-mutations',digests,ok=False)

        if len(sys.argv)==2:
            raw=Path(sys.argv[1]).read_bytes()
            assert hashlib.sha256(raw).hexdigest()=='773673751c6735cb4c4f7b66c736eb18f2d59ddcac7c8ad817caf2d81a41291a'
            matrix=json.loads(raw);assert len(matrix)==96
            reports=[];normalized=[];stores=0;mixed=0;false_matches=0
            for case in matrix:
                history,inputs=normalize(case);digests=save(history,inputs)
                run('compose-cop1-mutations',digests);run('verify-cop1-mutations',digests)
                report=json.loads(output.read_bytes());reports.append(report);normalized.append(dict(history=history,inputs=inputs))
                assert len(report['mutations'])==len(inputs)
                for store in report['lineage']['stores']:
                    stores+=1
                    parents=[o['kind']=='rdram_read' for o in store['byte_origins']]
                    mixed+=any(parents) and not all(parents)
                    actual=case['traced']['events'];false_matches+=case['args'][-1]=='success' and actual[0]['value']==actual[1]['value'] and not any(parents)
                    forged=copy.deepcopy(inputs);forged[0]['cu1']=False
                    run('compose-cop1-mutations',save(history,forged),ok=False)
                assert not report['decoded_context_ancestry_certified'] and not report['mutation_census_certified'] and not report['native_complete']
            assert (stores,mixed,false_matches)==(72,10,6),(stores,mixed,false_matches)
            for label,data in [('NORMALIZED_MATRIX',normalized),('REPORT_SET',reports)]:
                print(label+'_SHA256='+hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest())
            print('PASS all 96 actual cases, 72 canonical store joins, 10 mixed origins, 6 equal-value counterexamples and 72 CU1 forgeries')
    print('PASS COP1 two-source CLI composition/rechecking/input contracts')


if __name__=='__main__':
    main()
