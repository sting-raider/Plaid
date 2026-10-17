"""Native SDK contracts for one gamepad with no attached Controller/Rumble Pak."""
import json
import os
import shutil
import subprocess

def run(exe, cc, T):
    A = T.A
    status, bits, log = 0x80005000, 0x80005020, 0x80003000
    names = ['osContInit','osContGetQuery','__osPfsGetStatus','osMotorInit','osMotorStart','osMotorStop','__osEepStatus','osEepromProbe']
    program = [*T.li(A.sp,0x80007f00),*T.li(A.gp,log),
               *T.poke(status-4,0x11223344),*T.poke(status+16,0x55667788),
               *T.call('osContInit',0,bits,status),A.sw(A.v0,0,A.gp)]
    for n in range(4):
        program += [*T.call('__osPfsGetStatus',0,n),A.sw(A.v0,4+n*4,A.gp)]
    for n,name in enumerate(['osMotorInit','osMotorStart','osMotorStop']):
        program += [*T.call(name,0,0,0),A.sw(A.v0,20+n*4,A.gp)]
    program += [*T.call('osContGetQuery',status)]
    for n,address in enumerate([status-4,status,status+4,status+8,status+12,status+16,bits]):
        program += [*T.li(A.t0,address),A.lw(A.t1,0,A.t0),A.sw(A.t1,32+n*4,A.gp)]
    program += [*T.call('__osEepStatus',0,status),A.sw(A.v0,60,A.gp),
                *T.li(A.t0,status),A.lw(A.t1,0,A.t0),A.sw(A.t1,64,A.gp),
                *T.call('osEepromProbe',0),A.sw(A.v0,68,A.gp)]
    program += A.DONE
    for name in names:program += [name,A.jr(A.ra),A.nop]
    binary=T.build(exe,cc,'controller-policy',program,names)
    result=subprocess.run([str(binary),'--dump',hex(log),'18'],capture_output=True,text=True,timeout=30)
    rows=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    stop=next(row for row in rows if 'stop' in row)
    assert result.returncode==0 and stop['fault']==0 and stop['stop']=='exit',(result.stdout,result.stderr)
    expected=[0,1,1,1,1,1,1,1,0x11223344,0x00050200,8,8,8,0x55667788,0x01000000,0,0x80000000,1]
    assert next(row['words'] for row in rows if 'dump' in row)==expected,rows
    print('controller policy: one gamepad, absent-Pak status, disconnected ports, PFS/motor errors and bounded status writes')

if __name__=='__main__':
    import test_runtime as T
    run(T.ROOT/'target/debug'/('plaid.exe' if os.name=='nt' else 'plaid'),
        os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang'),T)
