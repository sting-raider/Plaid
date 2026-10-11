"""Execute combined actual RSP/CPU sensor with independent unchanged reference."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
from verify import verify,reject_forgeries

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUTPUT=ROOT/'target/ares-rsp-cpu-refetch-spike'


def main():
    if os.name=='nt':
        path=subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(['wsl','-d','Ubuntu','--exec','python3',path],check=True);return
    spec=importlib.util.spec_from_file_location('rsp_cpu_builder',ROOT/'spikes/003-ares-oracle/run.py')
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    OUTPUT.mkdir(parents=True,exist_ok=True)
    driver=HERE/'driver.cpp';extras=(driver,ROOT/'spikes/042-ares-rsp-dmem-history/observer.hpp')
    text=driver.read_text(encoding='utf-8')
    for filename in ('../003-ares-oracle/driver.cpp','../042-ares-rsp-dmem-history/observer.hpp'):
        text=text.replace(f'"{filename}"',f'"{(HERE/filename).resolve()}"')
    binaries=[]
    for enabled in (0,1):
        path=OUTPUT/('sensor.cpp' if enabled else 'baseline.cpp')
        path.write_text(f'#define PLAID_COMPOSED_SENSOR {enabled}\n'+text,encoding='utf-8',newline='\n')
        options=dict(raw_fetch_access=True,physical_fetch_access=True,fetch_boundary_access=True,
            sp_backing_access=True,rsp_dmem_access=True) if enabled else {}
        binaries.append(builder.build(path,OUTPUT/('sensor' if enabled else 'baseline'),extra_sources=extras,**options))
    results={}
    for key,exe,arg in (('baseline',binaries[0],'plain'),('disabled',binaries[1],'plain'),
            ('instrumented',binaries[1],'traced'),('repeat',binaries[1],'traced')):
        raw=subprocess.check_output([str(exe),arg],text=True,timeout=30)
        results[key]=json.loads(raw)
    assert all(r['checkpoints']==results['baseline']['checkpoints'] for r in results.values())
    assert results['baseline']['events']==results['disabled']['events']==[]
    assert results['instrumented']==results['repeat']
    summary=verify(results['instrumented']['events'])
    summary['forgeries_rejected']=reject_forgeries(results['instrumented']['events'])
    path=OUTPUT/'results.json';path.write_text(json.dumps(dict(summary=summary,runs=results),indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(summary,sort_keys=True),flush=True)
    print('RESULT_SHA256='+hashlib.sha256(path.read_bytes()).hexdigest(),flush=True)
    print('PASS actual RSP/CPU refetch composition, same-value writers, overwrite and independent checkpoints',flush=True)


if __name__=='__main__':main()
