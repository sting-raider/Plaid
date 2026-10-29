"""Guest current-thread cells follow actual host scheduler handoffs."""
import json
import subprocess


def run(exe, cc, T):
    A=T.A
    cell,one,two,queue,buffer,slot,log=0x80004000,0x80002000,0x80002200,0x80005000,0x80005020,0x80005040,0x80003000
    def observe(offset):
        return [*T.li(A.t0,cell),A.lw(A.t1,0,A.t0),*T.li(A.t0,log),A.sw(A.t1,offset,A.t0)]
    names=['osGetThreadPri','osCreateThread','osStartThread','osCreateMesgQueue','osRecvMesg','osSendMesg','osStopThread']
    program=[*T.li(A.sp,0x80007f00),*T.call('osGetThreadPri',0),*observe(0),
        *T.call('osCreateMesgQueue',queue,buffer,1),
        *T.call('osCreateThread',one,1,'one',0,0x8000ff00,10),*T.call('osStartThread',one),*A.DONE,
        'one',*observe(4),*T.call('osCreateThread',two,2,'two',0,0x80017f00,20),*T.call('osStartThread',two),
        *observe(12),*T.call('osSendMesg',queue,7,1),*observe(20),*A.DONE,
        'two',*observe(8),*T.call('osRecvMesg',queue,slot,1),*observe(16),*T.call('osStopThread',0),*A.DONE]
    for name in names:program += [name,A.jr(A.ra),A.nop]
    bindings={name:{'__osRunningThread':cell} for name in ['osGetThreadPri','osStartThread']}
    binary=T.build(exe,cc,'running-thread',program,names,data_bindings=bindings,
        source_sizes={name:8 for name in bindings})
    def check(binary):
        p=subprocess.run([str(binary),'--dump',hex(log),'6'],capture_output=True,text=True,timeout=30)
        rows=[json.loads(line) for line in p.stdout.splitlines() if line.startswith('{')]
        assert not p.returncode and next(row for row in rows if 'stop' in row)['fault']==0,(p.stdout,p.stderr)
        assert next(row for row in rows if 'dump' in row)['words']==[0,one,two,one,two,one],rows
    check(binary)
    out=T.OUT
    raw=(out/'running-thread.bin').read_bytes()
    rom=bytearray(0x1000);rom[:4]=bytes.fromhex('80371240');rom[8:12]=A.BASE.to_bytes(4,'big')
    path,mapped,source=(out/name for name in ['running-thread.z64','running-thread.map.json','running-thread.parts.c'])
    path.write_bytes(rom+raw)
    subprocess.run([str(exe),'discover',str(path),'0x1000',hex(A.BASE),hex(len(raw)),hex(A.BASE),str(mapped),str(out/'running-thread.runtime.json')],check=True,capture_output=True)
    subprocess.run([str(exe),'lower-map',str(path),str(mapped),hex(A.BASE),hex(A.EXIT),str(source),'--parts','3'],check=True,capture_output=True)
    objects=[]
    for part in sorted(out.glob('running-thread.parts.part*.c')):
        obj=part.with_suffix('.o');subprocess.run([cc,'-O1','-std=gnu11','-Werror','-DPLAID_SAFEPOINTS','-c',str(part),'-o',str(obj)],check=True);objects.append(obj)
    split=out/'running-thread.parts.exe'
    def compile(runtime,target,lowered,objects=()):
        subprocess.run([cc,'-O1','-std=gnu11','-DPLAID_SAFEPOINTS',f'-DPLAID_LOWERED="{lowered}"','-I',str(out),'-I',str(T.ROOT/'runtime'),str(runtime),*map(str,objects),'-pthread','-o',str(target)],check=True)
    compile(T.ROOT/'runtime/plaid_rt.c',split,source.name,objects);check(split)
    runtime=(T.ROOT/'runtime/plaid_rt.c').read_text()
    needle='  if (running_thread_global) wr32(running_thread_global, next && next != &boot ? next->guest : 0);'
    assert needle in runtime
    mutated=out/'running-thread.runtime-mutant.c';mutated.write_text(runtime.replace(needle,''))
    mutant=out/'running-thread.mutant.exe';compile(mutated,mutant,'running-thread.c')
    try:check(mutant)
    except AssertionError:pass
    else:raise AssertionError('missing scheduler publication mutation survived')
    pc=A.label_pcs(program)['osGetThreadPri']
    # Damage source after loading, before the first call; registration must
    # refuse before its guest cell or host scheduler binding can change.
    needle='  plaid_load_images(S);';assert needle in runtime
    damaged=runtime.replace(needle,needle+f' S->ram[{pc&0x1fffffff}] ^= 1;')
    mutated.write_text(damaged);compile(mutated,mutant,'running-thread.c')
    p=subprocess.run([str(mutant),'--dump',hex(cell),'1'],capture_output=True,text=True,timeout=30)
    rows=[json.loads(line) for line in p.stdout.splitlines() if line.startswith('{')]
    assert p.returncode and next(row for row in rows if 'stop' in row)['fault']==8,rows
    assert next(row for row in rows if 'dump' in row)['words']==[0],rows
    print('PASS SDK current-thread binding: boot, preemption, blocking, wakeup and stop handoffs visible to guest code')


if __name__=='__main__':
    import os,shutil,sys
    from pathlib import Path
    import test_runtime as T
    T.OUT.mkdir(parents=True,exist_ok=True)
    run(Path(os.environ['PLAID_TEST_EXE']).resolve(),shutil.which('gcc'),T)
