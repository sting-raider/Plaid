"""Check only the new PI-storage rule on a previously authenticated full source.

This is a delta check, not a replacement for the canonical source validator.
The CLI requires an independently retained canonical report and its digest.
"""
from pathlib import Path
import argparse
import hashlib
import json


def inspect(path,expected):
    digest=hashlib.sha256();attempt=effect=wrapper=None
    attempts=identity=failed=unscoped=0
    with path.open('rb') as stream:
        for raw in stream:
            digest.update(raw)
            if raw.startswith(b'{"record":"storage_effect",'):
                e=json.loads(raw)
                if attempt is None:
                    unscoped+=1
                    continue
                assert effect is None and wrapper is None
                assert (e['kind'],e['bytes'],e['context'],e['pc'],e['value'],e['ordinal']) == \
                    (0,1,0,attempt['pc'],attempt['value'],attempt['ordinal']+1)
                effect=e
            elif raw.startswith(b'{"record":"scalar",') and b'"pi":{' in raw:
                e=json.loads(raw)
                assert attempt is not None and wrapper is None
                wrapper=e
            elif raw.startswith(b'{"record":"pi_dma",'):
                e=json.loads(raw)
                if e['event']==4:
                    assert attempt is None
                    attempt=e;effect=wrapper=None;attempts+=1
                elif e['event']==5:
                    assert attempt is not None
                    if effect is None:
                        assert wrapper is None
                        failed+=1
                    else:
                        # The new physical-parent branch must be unselected on
                        # this retained source to reuse its earlier report.
                        assert wrapper is not None
                        assert (effect['address'],wrapper['address'],effect['ordinal']+2) == \
                            (e['dram'],e['dram'],e['ordinal'])
                        assert wrapper['ordinal']==effect['ordinal']+1
                        identity+=1
                    attempt=effect=wrapper=None
    assert attempt is None
    assert digest.hexdigest()==expected
    return dict(source_sha256=expected,attempts=attempts,unchanged_wrapper_writers=identity,
        missing_primitives=failed,unscoped_storage_effects=unscoped,
        new_physical_parent_branch_selected=False)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('history',type=Path)
    parser.add_argument('source_sha256')
    parser.add_argument('report',type=Path)
    parser.add_argument('report_sha256')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    raw=args.report.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==args.report_sha256
    report=json.loads(raw)
    assert report['projection']['history_sha256']==args.source_sha256
    assert report['projection']['format']=='plaid-observed-sp-backing-report-v1'
    result=inspect(args.history,args.source_sha256)
    assert result['unchanged_wrapper_writers']==report['projection']['projection']['projection']['successful_pi_writes']
    result['retained_report_sha256']=args.report_sha256
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print('PASS complete authenticated source delta; retained report is semantically unchanged:',json.dumps(result,sort_keys=True))


if __name__=='__main__': main()
