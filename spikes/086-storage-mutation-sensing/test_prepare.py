"""Guard source drift and opt-in shadow reuse without a reference execution claim."""
from pathlib import Path
import shutil
import subprocess
import tempfile
from unittest.mock import patch
from run import ROOT, HERE, load


def main():
    recipe = load('storage_recipe',HERE/'prepare.py')
    builder = load('storage_recipe_builder',ROOT/'spikes/003-ares-oracle/run.py')
    def command_output(command,**kwargs):
        return builder.REV+'\n' if command[0]=='git' else 'recipe compiler stub\n'
    def command_run(command,**kwargs):
        if '-o' in command: Path(command[command.index('-o')+1]).touch()
        return subprocess.CompletedProcess(command,0)
    with tempfile.TemporaryDirectory(prefix='storage-recipe-',dir=ROOT/'target') as temporary:
        output = Path(temporary)
        with patch.object(builder.subprocess,'check_output',command_output), patch.object(builder.subprocess,'run',command_run):
            for enabled,access in ((True,False),(False,False),(True,True),(False,True)):
                builder.build(HERE/'baseline.cpp',output,raw_fetch_access=access,physical_fetch_access=access,
                    rdram_scalar_access=access,memory_mutation_access=enabled)
                header = output/'include/n64/memory/lsb/writable.hpp'
                assert header.exists() == enabled
                assert (output/'include/n64/memory/memory.hpp').exists() == enabled
                if enabled:
                    source=header.read_text()
                    assert 'if constexpr(Size == Byte || Size == Half || Size == Word)' in source
                    assert source.count('plaidMemoryMutationObserver(this,') == 5
                    assert 'if(s.reading() && plaidMemoryMutationObserver)' in source
                    assert f'#include "{header}"' in (output/'include/n64/memory/memory.hpp').read_text()
        # Every audited input independently rejects mutation before shadow output.
        reference = output/'reference'
        for name in recipe.AUDITS:
            destination=reference/name
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/'.refs/ares'/name,destination)
        recipe.generate(reference,output/'portable')
        writable=output/'portable/include/n64/memory/lsb/writable.hpp'
        before=writable.read_bytes()
        for name in recipe.AUDITS:
            path=reference/name
            path.write_text(path.read_text(encoding='utf-8'),encoding='utf-8',newline='\n')
        recipe.generate(reference,output/'portable')
        assert writable.read_bytes()==before
        for name in recipe.AUDITS:
            path=reference/name
            old=path.read_bytes();path.write_bytes(old+b'\n')
            try:
                recipe.generate(reference,output/'rejected')
            except AssertionError:
                pass
            else:
                raise AssertionError('edited reference accepted: '+name)
            path.write_bytes(old)
    print('PASS four opt-in/reuse combinations, portable line-ending equivalence and three independent reference drift rejections; no execution claim')


if __name__ == '__main__': main()
