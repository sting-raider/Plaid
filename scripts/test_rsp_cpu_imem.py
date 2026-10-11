"""Generic composed Rust consumer against the independent controlled fixture."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
FORMAT='plaid-rsp-cpu-imem-history-v0'
PROFILE='ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-rsp-cpu-imem-scalar-sbv2e0-v0'


def main():
    cargo=shutil.which('cargo') or str(Path.home()/'.cargo/bin/cargo.exe')
    subprocess.run([cargo,'build','--locked','-p','plaid'],cwd=ROOT,check=True)
    exe=ROOT/('target/debug/plaid.exe' if os.name=='nt' else 'target/debug/plaid')
    spec=importlib.util.spec_from_file_location('independent_fixture',ROOT/'spikes/047-ares-rsp-cpu-imem-compose/verify.py')
    fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
    original=dict(format=FORMAT,profile=PROFILE,initial_dmem=list(bytes.fromhex('340800aaaaee7722')),
        initial_imem=list(bytes.fromhex('deadbeef')*5),final_dmem=list(bytes.fromhex('aaee7722aaee7722')),
        final_imem=list(bytes.fromhex('1122334411223344aaee7722aaee7722aaee7722')),events=fixture.fixture_events())
    starts=[e for e in original['events'] if e['kind']=='cpu_begin']
    ends=[e for e in original['events'] if e['kind']=='cpu_end']
    original['steps']=[dict(phase=a['phase'],index=i,word=a['word'],pc=a['pc'],before=a['gpr'],after=b['gpr'])
        for i,(a,b) in enumerate(zip(starts,ends))]
    with tempfile.TemporaryDirectory(prefix='rsp-cpu-imem-',dir=ROOT/'target') as temporary:
        directory=Path(temporary);source=directory/'source.json';output=directory/'report.json'
        def run(command,expected,ok=True,target=output):
            result=subprocess.run([str(exe),command,str(source),expected,str(target)],capture_output=True,text=True)
            assert (result.returncode==0)==ok,(command,result.stdout,result.stderr)
        def save(data):
            source.write_text(json.dumps(data),encoding='utf-8')
            return hashlib.sha256(source.read_bytes()).hexdigest()
        digest=save(original);run('inspect-rsp-cpu-imem',digest);run('verify-rsp-cpu-imem',digest)
        report=json.loads(output.read_bytes());copies=report['copies']
        assert len(copies)==3 and [c['phase'] for c in copies]==[3,6,13]
        assert copies[0]['word']==copies[1]['word'] and copies[0]['source_bytes']!=copies[1]['source_bytes']
        assert [b['kind'] for b in copies[2]['source_bytes']]==['cpu','unknown','rsp','rsp']
        assert copies[2]['read_ordinal']==45 and copies[2]['source_register']==8
        assert all(b['kind']=='unknown' for b in report['final_imem_writers'][16:20])
        assert report['final_dmem_sha256']==hashlib.sha256(bytes.fromhex('aaee7722aaee7722')).hexdigest()
        assert report['final_imem_sha256']==hashlib.sha256(bytes.fromhex('1122334411223344aaee7722aaee7722aaee7722')).hexdigest()
        assert not any(report[k] for k in ('source_ancestry_certified','mutation_coverage_certified','imem_execution_certified','executable_lifetime_certified','native_complete'))
        before=source.read_bytes();run('inspect-rsp-cpu-imem',digest,ok=False,target=source);assert source.read_bytes()==before
        run('inspect-rsp-cpu-imem','0'*64,ok=False)
        saved=output.read_bytes();forged=json.loads(saved);forged['copies'][2]['read_ordinal']=48
        output.write_text(json.dumps(forged),encoding='utf-8');run('verify-rsp-cpu-imem',digest,ok=False)
        output.write_bytes(saved)
        # Reject internally consistent fake identities and impossible producers,
        # beyond a mere digest or fixed fixture-event equality check.
        for phase,kind,field,value in [(3,'sp_write','address',0x04001080),(3,'sp_write','bank',0),
            (3,'sp_write','bytes',1),(3,'sp_write','cpu',False),(4,'rsp_begin','word',13),
            (4,'rsp_sink','context',1),(9,'rsp_begin','vector_byte',0),(8,'foreign_sink','offset',4),
            (14,'cpu_begin','word',0),(16,'sp_write','context',50),(3,'sp_write','ordinal',True)]:
            forged=copy.deepcopy(original);next(e for e in forged['events'] if e['phase']==phase and e['kind']==kind)[field]=value
            run('inspect-rsp-cpu-imem',save(forged),ok=False)
        forged=copy.deepcopy(original)
        next(e for e in forged['events'] if e['kind']=='cpu_begin' and e['phase']==3)['gpr'][8]|=1<<40
        run('inspect-rsp-cpu-imem',save(forged),ok=False)
        forged=copy.deepcopy(original);forged['events'].pop(15)
        run('inspect-rsp-cpu-imem',save(forged),ok=False)
        forged=copy.deepcopy(original);forged['final_imem'][8]^=1
        run('inspect-rsp-cpu-imem',save(forged),ok=False)
        forged=copy.deepcopy(original);forged['steps'][0]['word']=0
        run('inspect-rsp-cpu-imem',save(forged),ok=False)
        # Production accepts renamed phases and shifted code PCs: this is a
        # decoder/effect protocol, not hardcoded equality to the test fixture.
        generalized=copy.deepcopy(original)
        for event in generalized['events']:
            event['phase']+=100
            if event['pc']>0xffffffff00000000:event['pc']+=0x100
        for step in generalized['steps']:step['phase']+=100;step['pc']+=0x100
        digest=save(generalized);run('inspect-rsp-cpu-imem',digest)
        assert [c['phase'] for c in json.loads(output.read_bytes())['copies']]==[103,106,113]
    print('RSP/CPU IMEM: decoded producers, register-specific copies, mixed/unknown origins, same-value cuts, generic identities and full source/report/input gates passed')


if __name__=='__main__':main()
