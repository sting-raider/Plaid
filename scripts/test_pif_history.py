"""Strict finite PIF boot CLI with full nested sources and protected inputs."""
from pathlib import Path
import argparse
import copy
import json
import os
import shutil
import subprocess
import tempfile
from test_sp_history import ROOT,fixture as prior_fixture


def fixture():
    source,firmware,rows,fetches=prior_fixture()
    rows[0].update(format='plaid-ares-access-history-v4',policy='identity_ram_pi_queue_sp_and_observed_pif_backing')
    pc=fetches[1]['pc']
    rows.insert(1,dict(record='pif_rom_write_attempt',pc=pc,write=True,offset=0,bytes=4,value=7))
    i=next(n for n,e in enumerate(rows) if e['record']=='fetch_begin')
    rows.insert(i+1,dict(record='pif_rom_word',pc=pc,write=False,offset=0,bytes=4,value=0))
    active=pending=0
    for n,e in enumerate(rows[1:-1],1):
        e['ordinal']=n
        if e['record']=='fetch_begin':active=n
        e['context']=active
        if e['record']=='fetch_end':pending,active=active,0
        if e['record']=='fetch':e['fetch_context'],pending=pending,0
    rows[-1]['record_count']=len(rows)-2
    return source,firmware,rows,fetches


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--no-build',action='store_true');args=parser.parse_args()
    if not args.no_build:
        cargo=shutil.which('cargo') or str(Path.home()/'.cargo/bin/cargo.exe')
        subprocess.run([cargo,'build','-p','plaid','--locked'],cwd=ROOT,check=True)
    exe=ROOT/('target/debug/plaid.exe' if os.name=='nt' else 'target/debug/plaid')
    source,fw,rows,fetches=fixture()
    with tempfile.TemporaryDirectory(prefix='pif-history-cli-',dir=ROOT/'target') as temporary:
        directory=Path(temporary);firmware=directory/'firmware.bin';firmware.write_bytes(fw)
        trace=directory/'fetch.ndjson';history=directory/'history.ndjson'
        def write(path,rows):path.write_text(''.join(json.dumps(e)+'\n' for e in rows),encoding='utf-8')
        write(history,rows);write(trace,fetches)
        def command(name,*args):return subprocess.run([str(exe),name,*map(str,args)],capture_output=True,text=True)
        reports=[]
        for order in ('z64','v64','n64'):
            width=2 if order=='v64' else 4
            encoded=source if order=='z64' else b''.join(source[n:n+width][::-1] for n in range(0,len(source),width))
            rom=directory/f'toy.{order}';rom.write_bytes(encoded)
            output=directory/f'{order}.json';inputs=(rom,firmware,trace,history)
            result=command('inspect-pif-boot-history',*inputs,output);assert result.returncode==0,result.stderr
            assert command('verify-pif-boot-history',*inputs,output).returncode==0
            report=json.loads(output.read_text(encoding='utf-8'))
            assert (report['fetches'],report['pif_backed_fetches'],report['other_or_unwitnessed_fetches'])==(2,1,1)
            assert len(report['samples'])==1 and report['samples'][0]['offset']==0
            assert report['write_attempts'][0]['value']==7
            assert report['supplied_firmware_matching_fetches']==1
            assert report['projection']['dma_store_receipts'][0]['read_ordinal'] is not None
            assert report['projection']['projection']['accepted_requests']==3
            assert not any(report[k] for k in ('mutation_coverage_certified','executable_lifetime_certified','native_complete'))
            reports.append(output.read_bytes())
            for source_path in inputs:
                before=source_path.read_bytes();assert command('inspect-pif-boot-history',*inputs,source_path).returncode!=0
                assert source_path.read_bytes()==before
        assert reports[0]==reports[1]==reports[2]
        original=output.read_bytes()
        for field in ('mutation_coverage_certified','executable_lifetime_certified','native_complete'):
            output.write_text(json.dumps(dict(report,**{field:True})),encoding='utf-8')
            assert command('verify-pif-boot-history',*inputs,output).returncode!=0
        changed=copy.deepcopy(report);changed['samples'][0]['first_read_ordinal']+=1
        output.write_text(json.dumps(changed),encoding='utf-8');assert command('verify-pif-boot-history',*inputs,output).returncode!=0
        output.write_bytes(original)
        changed=copy.deepcopy(rows)
        next(e for e in changed if e['record']=='pif_rom_write_attempt')['value']^=1
        write(history,changed);assert command('verify-pif-boot-history',*inputs,output).returncode!=0
        rejected=directory/'rejected.json'
        for values in (rows[:-1],[dict(rows[0],format='plaid-ares-access-history-v3'),*rows[1:]]):
            write(history,values)
            assert command('inspect-pif-boot-history',*inputs,rejected).returncode!=0 and not rejected.exists()
        write(history,rows)
        for old in ('inspect-sp-boot-history','inspect-pi-queue-boot-history','inspect-pi-boot-history','inspect-boot-history','inspect-pi-fetch-lineage'):
            assert command(old,*inputs,rejected).returncode!=0 and not rejected.exists()
        changed=copy.deepcopy(rows);next(e for e in changed if e['record']=='pif_rom_word')['bytes']=1
        write(history,changed);assert command('inspect-pif-boot-history',*inputs,rejected).returncode!=0 and not rejected.exists()
        write(history,rows);firmware.write_bytes(bytes([1])+fw[1:])
        assert command('inspect-pif-boot-history',*inputs,rejected).returncode!=0 and not rejected.exists()
    print('PIF CLI: canonical orders, exact backing/sink witnesses, full source/report binding, version/input protection and uncertified flags passed')


if __name__=='__main__':main()
