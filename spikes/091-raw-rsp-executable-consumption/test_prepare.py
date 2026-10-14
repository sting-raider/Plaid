"""Default shadows stay exact; fetch receipts touch only existing interpreter reads."""
from pathlib import Path
import importlib.util
import os
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


def main():
    if os.name=='nt':
        script=subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',str(Path(__file__).resolve())],text=True).strip()
        subprocess.run(['wsl','-d','Ubuntu','--exec','python3',script],check=True);return
    ref=ROOT/'.refs/ares'
    assert subprocess.check_output(['git','-C',str(ref),'rev-parse','HEAD'],text=True).strip()=='9408cb43d4948fc3ea6e152a307a34348df3fe04'
    sp=load('sp_shadow',ROOT/'spikes/039-ares-cpu-sp-fetch/prepare.py')
    rsp=load('rsp_shadow',ROOT/'spikes/042-ares-rsp-dmem-history/prepare.py')
    retained=ROOT/'target/dmem-storage-cuts-primary/sensor'
    with tempfile.TemporaryDirectory(dir=ROOT/'target',prefix='rsp-fetch-recipe-') as temporary:
        base=Path(temporary)
        for enabled in (False,True):
            output=base/str(enabled);output.mkdir()
            (output/'n64.cpp').write_text('#include <n64/rsp/rsp.cpp>\n')
            sp.generate(ref,output);rsp.generate(ref,output,sp_backing=True,instruction_fetches=enabled)
            header=(output/'include/n64/rsp/rsp.hpp').read_text()
            source=(output/'rsp.cpp').read_text()
            if not enabled:
                assert 'PlaidRspImemReadObserver' not in header and 'plaidInstructionRead' not in source
                for path in ('include/n64/rsp/rsp.hpp','rsp.cpp'):
                    actual=(output/path).read_text().replace(str(output),'<OUT>')
                    expected=(retained/path).read_text().replace(str(retained),'<OUT>')
                    assert actual==expected,path
            else:
                assert source.count('imem.read<Word>(')==2
                assert source.count('plaidRspImemReadObserver(')==2
                assert source.count('plaidRspInstructionFetchObserver(true,')==2
                assert source.count('plaidRspInstructionFetchObserver(false,')==2
                assert 'plaidInstructionRead = plaidNextRead' in source
                assert 'plaidNextReadAddress & imem.maskWord' in source
                assert 'plaidInstructionPc & imem.maskWord' in source
                assert 'PlaidRspImemReadObserver' in header
    print('PASS exact retained default shadows and two original read points with performed-only receipt binding')


if __name__=='__main__':main()
