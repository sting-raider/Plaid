"""Exact actual-method scopes; opt-out/read-only shadows remain unchanged."""
from pathlib import Path
import importlib.util,os,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[2]
def main():
    if os.name=='nt':
        p=subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',str(Path(__file__).resolve())],text=True).strip()
        subprocess.run(['wsl','-d','Ubuntu','--exec','python3',p],check=True);return
    path=ROOT/'spikes/042-ares-rsp-dmem-history/prepare.py';spec=importlib.util.spec_from_file_location('prepare',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    ref=ROOT/'.refs/ares';assert subprocess.check_output(['git','-C',str(ref),'rev-parse','HEAD'],text=True).strip()=='9408cb43d4948fc3ea6e152a307a34348df3fe04'
    with tempfile.TemporaryDirectory(dir=ROOT/'target',prefix='rsp-actor-recipe-') as temp:
        for reads in (False,True):
            out=Path(temp)/str(reads);out.mkdir();(out/'n64.cpp').write_text('#include <n64/rsp/rsp.cpp>\n');m.generate(ref,out,word_reads=reads,instruction_fetches=True,scalar_stores=True)
            header=(out/'include/n64/rsp/rsp.hpp').read_text();ipu=(out/'rsp-interpreter-ipu.cpp').read_text()
            assert 'PlaidRspScalarStoreObserver' in header
            assert ipu.count('PlaidRspScalarStoreScope plaidStoreScope(')==3
            for kind,name in enumerate(('SB','SH','SW')):
                assert f'auto RSP::{name}(cr32& rt, cr32& rs, s16 imm) -> void {{\n  PlaidRspScalarStoreScope plaidStoreScope({kind});' in ipu
            assert ipu.count('plaidRspWordReadObserver(')==int(reads)
            assert 'dmem.writeUnaligned<Word>(rs.u32 + imm, rt.u32);' in ipu
    print('PASS anchored SB/SH/SW actor scopes, no extra guest access, optional existing Word reads')
if __name__=='__main__':main()
