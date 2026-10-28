"""SDK whole-cache writeback invalidates; partial hit writeback keeps clean lines."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import ares_oracle
import json
import os
import shutil
import subprocess

def run(exe, cc, T):
    A, out = T.A,T.OUT
    program=[*T.li(A.sp,0x80007f00),*T.li(A.gp,0x80001000)]
    cases=[('osWritebackDCache',16),('osWritebackDCache',8192),('osWritebackDCache',8208),('osWritebackDCacheAll',0)]
    for n,(name,size) in enumerate(cases):
        cached=0x80001080+n*0x20; uncached=cached|0x20000000
        program += [*T.poke(cached,0x11223344+n),*T.call(name,cached,size),
                    *T.poke(uncached,0xaabbccdd+n),*T.li(A.t0,cached),A.lw(A.t1,0,A.t0),A.sw(A.t1,4*n,A.gp)]
    program += [*A.DONE,
        'osWritebackDCache', A.sltiu(A.t0,A.a1,8192),A.beq(A.t0,A.zero,'all'),A.nop,
        47<<26|A.a0<<21|25<<16,A.jr(A.ra),A.nop,
        'osWritebackDCacheAll','all',*T.li(A.t0,0x80000000),A.addiu(A.t1,A.zero,512),
        'loop',47<<26|A.t0<<21|1<<16,A.addiu(A.t0,A.t0,16),A.addiu(A.t1,A.t1,-1),
        A.bgtz(A.t1,'loop'),A.nop,A.jr(A.ra),A.nop]
    binary=T.build(exe,cc,'cache-writeback',program,['osWritebackDCache','osWritebackDCacheAll'])
    native=subprocess.run([str(binary),'--dump','0x80001000','64'],capture_output=True,text=True,timeout=30)
    rows=[json.loads(line) for line in native.stdout.splitlines() if line.startswith('{')]
    stop=next(row for row in rows if 'stop' in row)
    assert native.returncode==0 and stop['fault']==0 and stop['stop']=='exit',(native.stdout,native.stderr)
    actual=next(row['words'] for row in rows if 'dump' in row)
    oracle=ares_oracle.default()
    args=[str(oracle),str(out/'cache-writeback.bin'),hex(A.EXIT)]
    reference=subprocess.run(args,capture_output=True,text=True,timeout=120)
    assert reference.returncode==0,(reference.stdout,reference.stderr)
    expected=json.loads(reference.stdout)
    assert expected['pc']==A.EXIT and expected['ram']==actual,(expected['ram'][:4],actual[:4])
    assert actual[:4]==[0x11223344,0xaabbccde,0xaabbccdf,0xaabbcce0],actual[:4]
    print('cache writeback: hit writeback retains; 8 KiB/larger and All index writeback invalidate; RAM/PC/fault match pinned ares')

if __name__=='__main__':
    import test_runtime as T
    run(T.ROOT/'target/debug'/('plaid.exe' if os.name=='nt' else 'plaid'),
        os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang'),T)
