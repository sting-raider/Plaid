"""Source-bound observed byte-chain CLI; no native or lifetime certification."""
from pathlib import Path
import argparse
import copy
import json
import os
import shutil
import subprocess
import tempfile
from test_pi_queue_history import ROOT, fixture


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-build',action='store_true')
    args = parser.parse_args()
    if not args.no_build:
        cargo = shutil.which('cargo') or str(Path.home()/'.cargo/bin/cargo.exe')
        subprocess.run([cargo,'build','-p','plaid','--locked'],cwd=ROOT,check=True)
    exe = ROOT/('target/debug/plaid.exe' if os.name == 'nt' else 'target/debug/plaid')
    source,fw,rows,fetches = fixture()
    with tempfile.TemporaryDirectory(prefix='pi-lineage-cli-',dir=ROOT/'target') as temporary:
        directory=Path(temporary)
        firmware=directory/'firmware.bin';firmware.write_bytes(fw)
        history=directory/'history.ndjson';trace=directory/'fetch.ndjson'
        def write(path,rows):
            path.write_text(''.join(json.dumps(e)+'\n' for e in rows),encoding='utf-8')
        write(history,rows);write(trace,fetches)
        def command(name,*args):
            return subprocess.run([str(exe),name,*map(str,args)],capture_output=True,text=True)
        reports=[]
        for order in ('z64','v64','n64'):
            width=2 if order=='v64' else 4
            encoded=source if order=='z64' else b''.join(source[n:n+width][::-1] for n in range(0,len(source),width))
            rom=directory/f'toy.{order}';rom.write_bytes(encoded)
            output=directory/f'{order}.json';inputs=(rom,firmware,trace,history)
            result=command('inspect-pi-fetch-lineage',*inputs,output)
            assert result.returncode==0,result.stderr
            assert command('verify-pi-fetch-lineage',*inputs,output).returncode==0
            report=json.loads(output.read_text(encoding='utf-8'))
            assert (report['fetches'],report['fully_attributed_fetches'],report['unattributed_fetches'])==(2,1,1)
            assert report['observed_rom_byte_fetches']==4 and len(report['samples'])==1
            assert report['samples'][0]['bytes'][0]['transfer']==1
            assert not any(report[k] for k in ('mutation_coverage_certified','executable_lifetime_certified','native_complete'))
            reports.append(output.read_bytes())
            for source_path in inputs:
                before=source_path.read_bytes()
                assert command('inspect-pi-fetch-lineage',*inputs,source_path).returncode!=0
                assert source_path.read_bytes()==before
        assert reports[0]==reports[1]==reports[2]
        original=output.read_bytes()
        for field in ('mutation_coverage_certified','executable_lifetime_certified','native_complete'):
            changed=dict(report,**{field:True});output.write_text(json.dumps(changed),encoding='utf-8')
            assert command('verify-pi-fetch-lineage',*inputs,output).returncode!=0
        changed=copy.deepcopy(report);changed['samples'][0]['bytes'][0]['writer_ordinal']+=1
        output.write_text(json.dumps(changed),encoding='utf-8')
        assert command('verify-pi-fetch-lineage',*inputs,output).returncode!=0
        output.write_bytes(original)
        changed=copy.deepcopy(rows)
        next(e for e in changed if e['record']=='pi_dma' and e['event']==6)['dram']+=1
        write(history,changed)
        assert command('verify-pi-fetch-lineage',*inputs,output).returncode!=0
        rejected=directory/'rejected.json'
        for values in (rows[:-1],[dict(rows[0],format='plaid-ares-access-history-v1'),*rows[1:]]):
            write(history,values)
            assert command('inspect-pi-fetch-lineage',*inputs,rejected).returncode!=0 and not rejected.exists()
        write(history,rows)
        firmware.write_bytes(bytes([1])+fw[1:])
        assert command('inspect-pi-fetch-lineage',*inputs,rejected).returncode!=0 and not rejected.exists()
    print('PI fetch lineage CLI: canonical orders, raw byte writers, complete-source/report binding, uncertified flags and input protection passed')


if __name__=='__main__':main()
