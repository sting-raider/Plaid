"""Source-bound finite SP producer-site inventory, not dataflow provenance."""
from pathlib import Path
from collections import Counter
import hashlib
import json

ROOT=Path(__file__).resolve().parents[2]
DIRECTORY=ROOT/'target/ares-boot-sp-history-spike/610000'


def main():
    report=json.loads((DIRECTORY/'rust-sp-history-report.json').read_text(encoding='utf-8'))
    assert report['scope']=='finite_actual_cpu_sp_reads_and_observed_stores'
    assert not any(report[k] for k in ('native_complete','mutation_coverage_certified','executable_lifetime_certified'))
    counts=Counter();sites=Counter();last=None;records=0;sha=hashlib.sha256();ended=False
    with (DIRECTORY/'traced.ndjson.history.ndjson').open('rb') as file:
        for line in file:
            assert not ended and line.endswith(b'\n')
            sha.update(line);e=json.loads(line)
            if e['record']=='header':assert e['format']=='plaid-ares-access-history-v3'
            elif e['record']=='end':
                assert records==e['record_count']==report['records'];ended=True
            else:
                records+=1;assert e['ordinal']==records
                if e['record']=='fetch':last=e
                if e['record']=='sp_word' and e['write']:
                    counts[f"{'cpu' if e['cpu'] else 'other'}_bank_{e['bank']}"]+=1
                    if e['cpu']:
                        word=last['word'] if last and last['pc']==e['pc'] else None
                        sites[(e['pc'],word,e['bank'])]+=1
                elif e['record']=='sp_dma_store':counts[f"dma_bank_{e['bank']}"]+=1
    assert ended and sha.hexdigest()==report['history_sha256']
    result=dict(scope='finite_observed_sp_producer_sites_no_dataflow_claim',history_sha256=sha.hexdigest(),
        counts=dict(sorted(counts.items())),sites=[dict(pc=p,word=w,bank=b,observations=n) for (p,w,b),n in sorted(sites.items(),key=lambda item:(item[0][0],-1 if item[0][1] is None else item[0][1],item[0][2]))],
        mutation_coverage_certified=False,executable_lifetime_certified=False,native_complete=False)
    path=DIRECTORY/'sp-producer-sites.json';path.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result,sort_keys=True),flush=True)
    print('RESULT_SHA256='+hashlib.sha256(path.read_bytes()).hexdigest(),flush=True)


if __name__=='__main__':main()
