"""Reconstruct the original C++ v3 bytes without reparsing unchanged payloads."""
from pathlib import Path
import argparse
import hashlib
import json


def inspect(path):
    digest=hashlib.sha256()
    raw_count=old_count=removed=raw_begin=old_begin=0
    with path.open('rb') as stream:
        header=stream.readline()
        assert header.count(b'plaid-ares-access-history-v5')==1
        assert header.count(b'observed_ordinary_storage_mutations_and_pi_queue_sp_backing')==1
        digest.update(header.replace(b'plaid-ares-access-history-v5',b'plaid-ares-access-history-v3')
            .replace(b'observed_ordinary_storage_mutations_and_pi_queue_sp_backing',b'identity_ram_pi_queue_and_observed_sp_backing'))
        for raw in stream:
            assert raw.endswith(b'\n')
            if raw.startswith(b'{"record":"end"'):
                footer=json.loads(raw)
                assert footer['record_count']==raw_count and not stream.read(1)
                marker=b'"record_count":'+str(raw_count).encode()
                assert raw.count(marker)==1
                digest.update(raw.replace(marker,b'"record_count":'+str(old_count).encode()))
                break
            raw_count+=1
            first=raw.index(b',"ordinal":')
            second=raw.index(b',"context":',first)
            third=raw.index(b',"pc":',second)
            assert int(raw[first+11:second])==raw_count
            if raw.startswith(b'{"record":"storage_effect"'):
                removed+=1
                continue
            old_count+=1
            if raw.startswith(b'{"record":"fetch_begin"'):
                raw_begin,old_begin=raw_count,old_count
            context=int(raw[second+11:third])
            assert context==0 or context==raw_begin
            tail=raw[third:]
            if raw.startswith(b'{"record":"fetch"'):
                start=tail.index(b'"fetch_context":')+16
                end=tail.index(b',',start)
                assert int(tail[start:end])==raw_begin
                tail=tail[:start]+str(old_begin).encode()+tail[end:]
            digest.update(raw[:first]+b',"ordinal":'+str(old_count).encode()+
                b',"context":'+str(old_begin if context else 0).encode()+tail)
        else:
            raise AssertionError('incomplete source footer')
    return dict(raw_records=raw_count,legacy_records=old_count,storage_effects=removed,
        legacy_sha256=digest.hexdigest())


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('history',type=Path)
    parser.add_argument('expected_sha256')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=inspect(args.history)
    assert result['legacy_sha256']==args.expected_sha256,result
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print('PASS complete original legacy history bytes:',json.dumps(result,sort_keys=True))


if __name__=='__main__': main()
