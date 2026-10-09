from pathlib import Path


def generate(ref, out):
    ref, out = Path(ref), Path(out)
    hp = out/'include/n64/cpu/cpu.hpp'
    assert hp.exists()
    header = hp.read_text(encoding='utf-8')
    decl = '''// Project-owned observational callback; no reference object fields.\nusing PlaidCpuInstructionObserver = void (*)(bool,u64,u32);\ninline PlaidCpuInstructionObserver plaidCpuInstructionObserver = nullptr;\n'''
    assert 'plaidCpuInstructionObserver' not in header
    hp.write_text(decl + header, encoding='utf-8', newline='\n')

    cp = out/'cpu.cpp'
    assert cp.exists()
    cpu = cp.read_text(encoding='utf-8')
    marker = '  instructionPrologue(ipu.pc, *data);\n  decoderEXECUTE(*data);'
    assert cpu.count(marker) == 1
    cpu = cpu.replace(marker, '  instructionPrologue(ipu.pc, *data);\n  if(plaidCpuInstructionObserver) plaidCpuInstructionObserver(true, ipu.pc, *data);\n  decoderEXECUTE(*data);')
    marker = '  instructionEpilogue<0>();\n  pipeline.end();'
    assert cpu.count(marker) == 1
    cpu = cpu.replace(marker, '  instructionEpilogue<0>();\n  if(plaidCpuInstructionObserver) plaidCpuInstructionObserver(false, 0, *data);\n  pipeline.end();')
    cp.write_text(cpu, encoding='utf-8', newline='\n')

    unity = (out/'n64.cpp').read_text(encoding='utf-8')
    assert unity.count(f'#include "{cp}"') == 1
