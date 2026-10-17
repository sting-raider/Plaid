"""Raw ROM DMA boundary versus pinned ares PI transfers and acknowledgments."""
import json
import hashlib
import os
import subprocess

def run(exe, cc, T):
    A, out = T.A, T.OUT
    rom = out/'raw-rom.z64'
    rom.write_bytes(bytes.fromhex('80371240') + bytes(0x2000 - 4))
    destination = 0xa0001040
    program = [*T.li(A.sp,0x80007f00), *T.li(A.gp,0x80001000),
               *T.poke(destination-4,0x12345678), *T.poke(destination+16,0x87654321),
               *T.call('osPiRawStartDma',0,0x100,destination,16), A.sw(A.v0,0,A.gp),
               'wait', *T.li(A.t0,0xa4600010), A.lw(A.t1,0,A.t0), A.andi(A.t1,A.t1,3),
               A.bne(A.t1,A.zero,'wait'), A.nop,
               *T.call('osPiGetStatus'), A.sw(A.v0,4,A.gp), *T.poke(0xa4600010,2),
               *T.call('osPiGetStatus'), A.sw(A.v0,8,A.gp)]
    canaries = [*range(A.s0,A.s7+1),A.gp,A.sp,A.fp]
    initial = [word for register in range(A.s0,A.s7+1) for word in T.li(register,0x81234000+register)]
    initial += [*T.li(A.fp,0x89abcdef),*T.li(A.t2,0x13579bdf),A.mthi(A.t2),*T.li(A.t2,0x2468ace0),A.mtlo(A.t2)]
    program = initial + program
    program += [A.sd(register,0x80+8*n,A.gp) for n,register in enumerate(canaries)]
    program += [A.mfhi(A.t2),A.sd(A.t2,0xe0,A.gp),A.mflo(A.t2),A.sd(A.t2,0xe8,A.gp),*A.DONE,
               'osPiRawStartDma', *T.li(A.t0,0xa4600000),
               *T.li(A.t1,0x1fffffff), A.and_(A.t1,A.a2,A.t1), A.sw(A.t1,0,A.t0),
               *T.li(A.t1,0x10000000), A.or_(A.t1,A.t1,A.a1), A.sw(A.t1,4,A.t0),
               A.addiu(A.t1,A.a3,-1), A.sw(A.t1,12,A.t0), A.jr(A.ra), A.addiu(A.v0,A.zero,0),
               'osPiGetStatus', *T.li(A.t0,0xa4600010), A.jr(A.ra), A.lw(A.v0,0,A.t0)]
    native = T.build(exe,cc,'raw-rom',program,['osPiRawStartDma','osPiGetStatus'])
    actual = subprocess.run([str(native),'--rom',str(rom),'--dump','0x80001000','64'],capture_output=True,text=True,timeout=30)
    rows = [json.loads(line) for line in actual.stdout.splitlines() if line.startswith('{')]
    stop = next(row for row in rows if 'stop' in row)
    assert actual.returncode==0 and stop['fault']==0 and stop['pi_dma']==1, (actual.stdout,actual.stderr)
    memory = next(row['words'] for row in rows if 'dump' in row)
    oracle=T.ROOT/'target/native-slice/oracle/oracle'
    metadata=json.loads((oracle.parent/'build.json').read_text())
    assert metadata['revision']==A.builder().REV
    for key,source in [('driver','096-native-slice'),('fixture_driver','003-ares-oracle')]:
        assert metadata[key]==hashlib.sha256((T.ROOT/f'spikes/{source}/driver.cpp').read_bytes()).hexdigest()
    args=[str(oracle),str(out/'raw-rom.bin'),hex(A.EXIT)]
    if os.name=='nt':
        def linux(p): return subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',str(p)],text=True).strip()
        args=['wsl','-d','Ubuntu','--exec',linux(oracle),linux(out/'raw-rom.bin'),hex(A.EXIT)]
    reference=subprocess.run(args,capture_output=True,text=True,timeout=120)
    assert reference.returncode==0,(reference.stdout,reference.stderr)
    expected=json.loads(reference.stdout)
    assert expected['pc']==A.EXIT and expected['ram']==memory,(expected['ram'],memory)
    assert memory[:3]==[0,8,0] and memory[15]==0x12345678 and memory[20]==0x87654321
    # The boundary refuses unsupported direction, bounds and alignment rather
    # than silently applying an aligned-ROM copy to other PI operations.
    for name,arguments,reason in [
        ('write',(1,0x100,destination,16),'PI write to cartridge'),
        ('bounds',(0,0x2000,destination,16),'PI DMA outside the ROM'),
        ('executable',(0,0x100,A.BASE,16),'runtime write refused'),
        ('alignment',(0,0x101,destination,16),'unaligned raw PI DMA is not modeled')]:
        bad=[*T.li(A.sp,0x80007f00),*T.call('osPiRawStartDma',*arguments),*A.DONE,
             'osPiRawStartDma',A.jr(A.ra),A.nop]
        binary=T.build(exe,cc,'raw-rom-'+name,bad,['osPiRawStartDma'])
        failed=subprocess.run([str(binary),'--rom',str(rom)],capture_output=True,text=True,timeout=30)
        assert failed.returncode==1 and reason in failed.stdout and '"pi_dma":0' in failed.stdout,(failed.stdout,failed.stderr)
    print('raw ROM PI DMA: RAM/guards/return and interrupt status/ack match pinned ares; writes, bounds and unsupported alignment refused')

if __name__=='__main__':
    import shutil
    import test_runtime as T
    run(T.ROOT/'target/debug'/('plaid.exe' if os.name=='nt' else 'plaid'),
        os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang'),T)
