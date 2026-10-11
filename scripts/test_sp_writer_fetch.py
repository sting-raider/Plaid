"""Compose complete SP sources, captured writers and actual executable reads."""
from pathlib import Path
import copy
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from test_sp_history import ROOT, fixture


def main():
    cargo = shutil.which('cargo') or str(Path.home()/'.cargo/bin/cargo.exe')
    subprocess.run([cargo,'build','--locked','-p','plaid'],cwd=ROOT,check=True)
    exe=ROOT/('target/debug/plaid.exe' if os.name=='nt' else 'target/debug/plaid')
    source,firmware_bytes,original_rows,original_fetches=fixture()
    with tempfile.TemporaryDirectory(prefix='sp-writer-fetch-',dir=ROOT/'target') as temporary:
        directory=Path(temporary)
        rom=directory/'synthetic.z64';rom.write_bytes(source)
        firmware=directory/'synthetic-firmware.bin';firmware.write_bytes(firmware_bytes)
        history=directory/'history.ndjson';fetched=directory/'fetch.ndjson'
        legacy=directory/'legacy.json';output=directory/'writers.json'
        def run(command,*args,ok=True):
            result=subprocess.run([str(exe),command,*map(str,args)],capture_output=True,text=True)
            assert (result.returncode==0)==ok,(command,result.stdout,result.stderr)
            return result
        def save(rows,fetches):
            active=pending=0;seq=0
            for ordinal,row in enumerate(rows[1:-1],1):
                row['ordinal']=ordinal
                if row['record']=='fetch_begin':active=ordinal
                row['context']=active
                if row['record']=='fetch_end':pending,active=active,0
                if row['record']=='fetch':
                    row['fetch_context']=pending;pending=0
                    row['fetch_seq']=seq;seq+=1
            rows[-1].update(record_count=len(rows)-2,fetch_count=seq)
            rows[0]['budget']=max(rows[0]['budget'],seq)
            fetches[0]['budget']=max(fetches[0]['budget'],seq)
            for i,row in enumerate(fetches[1:-1]):row['seq']=i
            fetches[-1]['fetch_count']=len(fetches)-2
            for path,records in ((history,rows),(fetched,fetches)):
                path.write_text(''.join(json.dumps(row)+'\n' for row in records),encoding='utf-8')
            return hashlib.sha256(history.read_bytes()).hexdigest(),hashlib.sha256(fetched.read_bytes()).hexdigest()
        def inspect(rows,fetches):
            expected_h,expected_f=save(rows,fetches)
            inputs=(rom,firmware,fetched,history)
            run('inspect-sp-boot-history',*inputs,legacy)
            run('inspect-sp-writer-fetch',*inputs,expected_h,expected_f,output)
            run('verify-sp-writer-fetch',*inputs,expected_h,expected_f,output)
            report=json.loads(output.read_bytes())
            assert report['projection']==json.loads(legacy.read_bytes())
            assert not any(report[field] for field in ('ultimate_ancestry_certified','mutation_coverage_certified','executable_lifetime_certified','native_complete'))
            return report,(*inputs,expected_h,expected_f)
        report,inputs=inspect(copy.deepcopy(original_rows),copy.deepcopy(original_fetches))
        assert (report['captured_writes'],report['fully_compatible_fetches'])==(2,1)
        writers=report['samples'][0]['writers']
        assert all(w['kind']=={'kind':'word_sink','cpu':True} for w in writers)
        assert len({w['write_ordinal'] for w in writers})==1
        preserved=output.read_bytes()
        for index in range(4):
            before=inputs[index].read_bytes()
            run('inspect-sp-writer-fetch',*inputs,inputs[index],ok=False)
            assert inputs[index].read_bytes()==before
        run('inspect-sp-writer-fetch',*inputs[:4],'0'*64,inputs[5],output,ok=False)
        run('inspect-sp-writer-fetch',*inputs[:5],'0'*64,output,ok=False)
        assert output.read_bytes()==preserved
        altered=json.loads(preserved);altered['samples'][0]['writers'][0]['write_ordinal']+=1
        output.write_text(json.dumps(altered),encoding='utf-8')
        run('verify-sp-writer-fetch',*inputs,output,ok=False)
        rows=copy.deepcopy(original_rows)
        rows[:]=[row for row in rows if not (row['record']=='sp_word' and row['write'])]
        report,_=inspect(rows,copy.deepcopy(original_fetches))
        assert all(w['kind']['kind']=='dma_sink' and w['kind']['read_ordinal'] is not None for w in report['samples'][0]['writers'])
        rows=copy.deepcopy(original_rows)
        # Reuse the existing explicit actual-read/fetch shape for two further
        # discrete observations, with a contradictory byte followed by equal bits.
        start=max(i for i,row in enumerate(rows) if row['record']=='fetch_begin')
        template=copy.deepcopy(rows[start:-1]);fetches=copy.deepcopy(original_fetches)
        word=fetches[-2]['word']
        for value in (word^0x01000000,word):
            span=copy.deepcopy(template)
            for row in span:
                if row['record']=='sp_word':row['value']=value
                elif row['record']=='fetch_end':row['value']=value
                elif row['record']=='fetch':row['word']=value
            rows[-1:-1]=span
            event=copy.deepcopy(fetches[-2]);event['word']=value;fetches[-1:-1]=[event]
        report,_=inspect(rows,fetches)
        assert (report['fully_compatible_fetches'],report['partially_compatible_fetches'],report['unknown_sp_fetches'])==(1,2,0)
        assert report['contradicted_byte_candidates']==1
        assert any(sample['backing']['last_fetch']==3 and sample['writers'][0] is None for sample in report['samples'])
        rows=copy.deepcopy(original_rows)
        rows[:]=[row for row in rows if row['record']!='sp_dma_store' and not (row['record']=='sp_word' and row['write'])]
        report,_=inspect(rows,copy.deepcopy(original_fetches))
        assert report['unknown_sp_fetches']==1 and report['fully_compatible_fetches']==0
    print('SP writer/fetch composition: same-value replacement, DMA source receipts, permanent byte cuts, missing writers, complete source/report/input gates and legacy projection passed')


if __name__=='__main__':main()
