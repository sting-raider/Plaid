from pathlib import Path
import re


def generate(ref, out):
    ref, out = Path(ref), Path(out)
    header = (ref/'ares/n64/cpu/cpu.hpp').read_text(encoding='utf-8')
    decl = '''// Project-owned observational callback; no reference object fields.\nusing PlaidCpuInstructionObserver = void (*)(bool,u64,u32);\ninline PlaidCpuInstructionObserver plaidCpuInstructionObserver = nullptr;\n'''
    hp = out/'include/n64/cpu/cpu.hpp'; hp.parent.mkdir(parents=True, exist_ok=True)
    hp.write_text(decl + header, encoding='utf-8', newline='\n')

    source = ref/'ares/n64/cpu/cpu.cpp'
    cpu = source.read_text(encoding='utf-8')
    cpu = re.sub(r'#include "([^"]+)"', lambda m: f'#include "{ref/"ares/n64/cpu"/m[1]}"', cpu)
    marker = '  instructionPrologue(ipu.pc, *data);\n  decoderEXECUTE(*data);'
    assert cpu.count(marker) == 1
    cpu = cpu.replace(marker, '  instructionPrologue(ipu.pc, *data);\n  if(plaidCpuInstructionObserver) plaidCpuInstructionObserver(true, ipu.pc, *data);\n  decoderEXECUTE(*data);')
    marker = '  instructionEpilogue<0>();\n  pipeline.end();'
    assert cpu.count(marker) == 1
    cpu = cpu.replace(marker, '  instructionEpilogue<0>();\n  if(plaidCpuInstructionObserver) plaidCpuInstructionObserver(false, 0, *data);\n  pipeline.end();')
    cp = out/'cpu.cpp'; cp.write_text(cpu, encoding='utf-8', newline='\n')
    unity = (out/'n64.cpp').read_text(encoding='utf-8')
    marker = '#include <n64/cpu/cpu.cpp>'
    assert unity.count(marker) == 1
    (out/'n64.cpp').write_text(unity.replace(marker, f'#include "{cp}"'), encoding='utf-8', newline='\n')
