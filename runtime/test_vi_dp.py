"""libultra VI and DP side effects that guest code observes (ADR-0198)."""
import json
import os
import shutil
import subprocess

def run(exe, cc, T):
    A = T.A
    log, nextp, context, fb = 0x80003000, 0x80005000, 0x80005100, 0x80100000
    dpq, dpbuf, viq, vibuf, slot, task, dl = 0x80002000, 0x80002020, 0x80002040, 0x80002060, 0x80002080, 0x80004100, 0x80006000
    names = ['osCreateThread','osStartThread','osCreateMesgQueue','osSetEventMesg','osViSetEvent','osViSwapBuffer',
             'osSpTaskStartGo','osRecvMesg']
    program = [*T.li(A.sp,0x80007f00),
               *T.call('osCreateThread',0x80002100,1,'t',0,0x8000ff00,10),
               *T.call('osStartThread',0x80002100),
               *A.DONE,  # the boot context never resumes
               't',  # a thread, so it may block
               *T.li(A.gp,log),
               # osViSwapBuffer stores the framebuffer in __osViNext->framep
               *T.poke(nextp,context),*T.poke(context+4,0x80000000),
               *T.call('osViSwapBuffer',fb),
               *T.li(A.t0,context+4),A.lw(A.t1,0,A.t0),A.sw(A.t1,0,A.gp),
               # a frozen RDP holds the graphics task's DP interrupt until the thaw
               *T.call('osCreateMesgQueue',dpq,dpbuf,4),*T.call('osSetEventMesg',9,dpq,0x66),
               *T.call('osCreateMesgQueue',viq,vibuf,4),*T.call('osViSetEvent',viq,0x77,1),
               *T.poke(task,1),*T.poke(task+0x30,dl),*T.poke(dl,0xb8000000),
               *T.poke(0xa410000c,8),  # DPC_STATUS: set freeze
               *T.call('osSpTaskStartGo',task),
               *T.call('osRecvMesg',viq,slot,1),  # after a retrace any posted event is delivered
               *T.call('osRecvMesg',dpq,slot,0),A.sw(A.v0,4,A.gp),
               *T.poke(0xa410000c,4),  # clear freeze
               *T.call('osRecvMesg',dpq,slot,1),A.sw(A.v0,8,A.gp),
               *T.li(A.t0,slot),A.lw(A.t1,0,A.t0),A.sw(A.t1,12,A.gp),
               *A.DONE]
    for name in names: program += [name,A.jr(A.ra),A.nop]
    binary=T.build(exe,cc,'vi-dp',program,names,data_bindings={'osViSwapBuffer':{'__osViNext':nextp}})
    result=subprocess.run([str(binary),'--stop-at','none','--seconds','5','--dump',hex(log),'4'],capture_output=True,text=True,timeout=30)
    rows=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    assert result.returncode==0 and next(row for row in rows if 'stop' in row)['stop']=='exit',(result.stdout,result.stderr)
    assert next(row['words'] for row in rows if 'dump' in row)==[fb,0xffffffff,0,0x66],rows
    print('VI and DP side effects: osViSwapBuffer stores __osViNext->framep; a frozen RDP holds the DP event until the thaw')

if __name__=='__main__':
    import test_runtime as T
    run(T.ROOT/'target/debug'/('plaid.exe' if os.name=='nt' else 'plaid'),
        os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang'),T)
