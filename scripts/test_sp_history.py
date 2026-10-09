"""Strict finite SP boot CLI with full nested sources and protected inputs."""
from pathlib import Path
import argparse
import copy
import json
import os
import shutil
import subprocess
import tempfile
from test_pi_queue_history import ROOT,fixture as prior_fixture


def fixture():
    source,firmware,rows,fetches=prior_fixture()
    rows[0].update(format='plaid-ares-access-history-v3',policy='identity_ram_pi_queue_and_observed_sp_backing')
    i=max(n for n,e in enumerate(rows) if e['record']=='fetch_begin')
    pc=rows[i]['pc'];word=fetches[2]['word']
    rows[i:i]=[
        dict(record='scalar',pc=pc,write=False,address=4096,aligned_address=4096,bytes=8,device=4,value=word<<32),
        dict(record='sp_dma_store',pc=pc,dram=4096,bank=1,offset=0,bytes=8,value=word<<32),
        dict(record='sp_word',pc=pc,write=True,address=0x04001003,bank=1,offset=0,bytes=4,value=word,cpu=True)]
    pc=0xffffffffa4001000
    for e in rows[i+3:-1]:
        e['pc']=pc
        if e['record']=='scalar':
            e.clear();e.update(record='sp_word',pc=pc,write=False,address=0x04001000,bank=1,offset=0,bytes=4,value=word,cpu=True)
        elif e['record']=='fetch':e['physical']=0x04001000
        else:e.update(vaddr=pc,translated=0x04001000,bus=0x04001000)
    fetches[2].update(pc=pc,physical=0x04001000)
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
    with tempfile.TemporaryDirectory(prefix='sp-history-cli-',dir=ROOT/'target') as temporary:
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
            result=command('inspect-sp-boot-history',*inputs,output);assert result.returncode==0,result.stderr
            assert command('verify-sp-boot-history',*inputs,output).returncode==0
            report=json.loads(output.read_text(encoding='utf-8'))
            assert (report['fetches'],report['sp_backed_fetches'],report['other_or_unwitnessed_fetches'])==(2,1,1)
            assert len(report['samples'])==1 and report['samples'][0]['bank']==1
            assert report['dma_store_receipts'][0]['read_ordinal'] is not None
            assert report['projection']['accepted_requests']==3
            assert not any(report[k] for k in ('mutation_coverage_certified','executable_lifetime_certified','native_complete'))
            reports.append(output.read_bytes())
            for source_path in inputs:
                before=source_path.read_bytes();assert command('inspect-sp-boot-history',*inputs,source_path).returncode!=0
                assert source_path.read_bytes()==before
        assert reports[0]==reports[1]==reports[2]
        original=output.read_bytes()
        for field in ('mutation_coverage_certified','executable_lifetime_certified','native_complete'):
            output.write_text(json.dumps(dict(report,**{field:True})),encoding='utf-8')
            assert command('verify-sp-boot-history',*inputs,output).returncode!=0
        changed=copy.deepcopy(report);changed['samples'][0]['first_read_ordinal']+=1
        output.write_text(json.dumps(changed),encoding='utf-8');assert command('verify-sp-boot-history',*inputs,output).returncode!=0
        output.write_bytes(original)
        changed=copy.deepcopy(rows)
        next(e for e in changed if e['record']=='sp_word' and e['write'])['value']^=1
        write(history,changed);assert command('verify-sp-boot-history',*inputs,output).returncode!=0
        rejected=directory/'rejected.json'
        for values in (rows[:-1],[dict(rows[0],format='plaid-ares-access-history-v2'),*rows[1:]]):
            write(history,values)
            assert command('inspect-sp-boot-history',*inputs,rejected).returncode!=0 and not rejected.exists()
        write(history,rows)
        for old in ('inspect-pi-queue-boot-history','inspect-pi-boot-history','inspect-boot-history','inspect-pi-fetch-lineage'):
            assert command(old,*inputs,rejected).returncode!=0 and not rejected.exists()
        changed=copy.deepcopy(rows);next(e for e in changed if e['record']=='sp_word' and not e['write'])['bank']=0
        write(history,changed);assert command('inspect-sp-boot-history',*inputs,rejected).returncode!=0 and not rejected.exists()
        write(history,rows);firmware.write_bytes(bytes([1])+fw[1:])
        assert command('inspect-sp-boot-history',*inputs,rejected).returncode!=0 and not rejected.exists()
    print('SP CLI: canonical orders, exact backing/sink witnesses, full source/report binding, version/input protection and uncertified flags passed')


if __name__=='__main__':main()
