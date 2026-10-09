"""Regression guards for RSP-only rebuilds and existing SP-shadow composition."""
from pathlib import Path
import importlib.util
import tempfile
from prepare import generate

ROOT=Path(__file__).resolve().parents[2]
REF=ROOT/'.refs/ares'


def main():
    spec=importlib.util.spec_from_file_location('prior_sp_shadow',ROOT/'spikes/039-ares-cpu-sp-fetch/prepare.py')
    prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
    with tempfile.TemporaryDirectory(prefix='rsp-shadow-test-',dir=ROOT/'target') as temporary:
        out=Path(temporary)
        def reset(composed):
            (out/'n64.cpp').write_text('#include <n64/rsp/rsp.cpp>\n',encoding='utf-8',newline='\n')
            if composed:prior.generate(REF,out)
            else:(out/'include/n64/rsp/rsp.hpp').unlink(missing_ok=True)
            # Keep stale rsp.cpp intentionally: a failed earlier build leaves it.
            generate(REF,out,sp_backing=composed)
            header=(out/'include/n64/rsp/rsp.hpp').read_text(encoding='utf-8')
            cpp=(out/'rsp.cpp').read_text(encoding='utf-8')
            assert header.count('inline PlaidRspInstructionObserver')==1
            assert header.count('plaidRspDmemObserver(plaidOffset,Size,plaidValue);')==1
            assert cpp.count('plaidRspInstructionObserver(true,')==1
            assert cpp.count('plaidRspInstructionObserver(false,')==1
            assert ('rsp_io.cpp' in cpp)==composed and ('rsp_dma.cpp' in cpp)==composed
            assert ('plaidSpWordObserver' in header)==composed
            return header,cpp,(out/'n64.cpp').read_bytes()
        for composed in (False,True,False,True):
            first=reset(composed);assert reset(composed)==first
    print('PASS repeated RSP-only/SP-composed shadows and stale failed-output guards; no reference execution claim')


if __name__=='__main__':main()
