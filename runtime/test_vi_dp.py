"""VI registers, COP0 Compare and the DP interrupt as guest code observes them (ADR-0198, ADR-0199)."""
import json
import os
import shutil
import subprocess

VI = 0xa4400000

def run(exe, cc, T):
    A = T.A
    log = 0x80003000
    dpq, dpbuf, viq, vibuf, slot, task, dl = 0x80002000, 0x80002020, 0x80002040, 0x80002060, 0x80002080, 0x80004100, 0x80006000
    names = ['osCreateThread','osStartThread','osCreateMesgQueue','osSetEventMesg','osSpTaskStartGo','osRecvMesg',
             'osGetCount','__osSetCompare']
    cq, cqbuf = 0x800020a0, 0x800020c0
    def read(address, offset):
        return [*T.li(A.t0,address),A.lw(A.t1,0,A.t0),A.sw(A.t1,offset,A.gp)]
    program = [*T.li(A.sp,0x80007f00),
               *T.call('osCreateThread',0x80002100,1,'t',0,0x8000ff00,10),
               *T.call('osStartThread',0x80002100),
               *A.DONE,  # the boot context never resumes
               't',  # a thread, so it may block
               *T.li(A.gp,log),
               # registers keep the bits ares vi/io.cpp keeps, mirrored every 0x40 bytes
               *T.poke(VI+0x04,0xffffffff),*T.poke(VI+0x1c,0xffffffff),*T.poke(VI+0x18,0x20d),*T.poke(VI+0x0c,2),
               *read(VI+0x04,0),*read(VI+0x1c,4),*read(VI+0x44,8),
               # the retrace is OS_EVENT_VI; just after it the line is near VI_V_INTR, field 0
               *T.call('osCreateMesgQueue',viq,vibuf,4),*T.call('osSetEventMesg',7,viq,0x77),
               *T.call('osRecvMesg',viq,slot,1),*read(VI+0x10,12),*read(slot,16),
               # a frozen RDP holds the graphics task's DP interrupt until the thaw
               *T.call('osCreateMesgQueue',dpq,dpbuf,4),*T.call('osSetEventMesg',9,dpq,0x66),
               *T.poke(task,1),*T.poke(task+0x30,dl),*T.poke(dl,0xb8000000),
               *T.poke(0xa410000c,8),  # DPC_STATUS: set freeze
               *T.call('osSpTaskStartGo',task),
               *T.call('osRecvMesg',viq,slot,1),  # after a retrace any posted event is delivered
               *T.call('osRecvMesg',dpq,slot,0),A.sw(A.v0,20,A.gp),
               *T.poke(0xa410000c,4),  # clear freeze
               *T.call('osRecvMesg',dpq,slot,1),A.sw(A.v0,24,A.gp),*read(slot,28),
               # Count reaching Compare is OS_EVENT_COUNTER
               *T.call('osCreateMesgQueue',cq,cqbuf,4),*T.call('osSetEventMesg',3,cq,0x55),
               *T.call('osGetCount'),*T.li(A.t0,0x20000),A.addu(A.a0,A.v0,A.t0),A.jal('__osSetCompare'),A.nop,
               *T.call('osRecvMesg',cq,slot,1),*read(slot,32),
               *A.DONE]
    for name in names: program += [name,A.jr(A.ra),A.nop]
    binary=T.build(exe,cc,'vi-dp',program,names)
    result=subprocess.run([str(binary),'--stop-at','none','--seconds','5','--dump',hex(log),'9'],capture_output=True,text=True,timeout=30)
    rows=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    stop=next(row for row in rows if 'stop' in row)
    assert result.returncode==0 and stop['stop']=='exit',(result.stdout,result.stderr)
    words=next(row['words'] for row in rows if 'dump' in row)
    assert words[:3]==[0xffffff,0x1f0fff,0xffffff],[hex(w) for w in words]
    assert words[3] & 1 == 0 and 2 <= words[3] < 0x40 and words[4]==0x77,[hex(w) for w in words]
    assert words[5:]==[0xffffffff,0,0x66,0x55],[hex(w) for w in words]
    assert stop['framebuffer']=='00ffffff',stop
    print('VI and DP: registers keep ares bits and mirror, the retrace is OS_EVENT_VI near VI_V_INTR, '
          'a frozen RDP holds the DP event until the thaw, Count reaching Compare is OS_EVENT_COUNTER')

if __name__=='__main__':
    import test_runtime as T
    run(T.ROOT/'target/debug'/('plaid.exe' if os.name=='nt' else 'plaid'),
        os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang'),T)
