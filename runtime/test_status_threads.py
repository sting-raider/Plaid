"""Native SDK boundaries retain Status across actual host thread handoffs."""
import json
import subprocess

def run(exe, cc, T):
    A = T.A
    global_mask, one, two = 0x80004000, 0x80002000, 0x80002200
    queue, buffer, slot, log = 0x80005000, 0x80005020, 0x80005040, 0x80003000
    def observe(offset):
        return [*T.call('__osGetSR'), *T.li(A.t0, log), A.sw(A.v0, offset, A.t0)]
    names = ['osCreateThread', 'osSetIntMask', '__osGetSR', 'osStartThread',
             'osCreateMesgQueue', '__osDisableInt', '__osRestoreInt',
             'osRecvMesg', 'osSendMesg', '__osSetFpcCsr', 'osPiGetStatus', 'osMotorStart', 'osMotorStop']
    program = [*T.li(A.sp, 0x80007f00), *T.poke(global_mask, 0x003fff01),
               *T.call('osPiGetStatus'), *T.li(A.t0, log), A.sw(A.v0, 32, A.t0),
               *T.call('osMotorStart'), *T.li(A.t0, log), A.sw(A.v0, 36, A.t0),
               *T.call('osMotorStop'), *T.li(A.t0, log), A.sw(A.v0, 40, A.t0),
               *T.call('osCreateMesgQueue', queue, buffer, 4),
               *T.call('osCreateThread', one, 1, 'one', 0, 0x80010000, 10),
               *T.call('osStartThread', one), *A.DONE,
               'one', *observe(0), *T.call('__osDisableInt'),
               *T.call('osCreateThread', two, 2, 'two', 0, 0x80018000, 20),
               *T.call('osStartThread', two), *observe(8),
               *T.li(A.t0, two + 0x118), A.lw(A.t1, 0, A.t0),
               *T.li(A.t0, log), A.sw(A.t1, 24, A.t0),
               *T.li(A.t0, two + 0x128), A.lw(A.t1, 0, A.t0),
               *T.li(A.t0, log), A.sw(A.t1, 28, A.t0),
               *T.call('__osRestoreInt', 1), *observe(12),
               *T.call('osSendMesg', queue, 0x1234, 1), *A.DONE,
               'two', *observe(4), *T.call('osSetIntMask', 0x0015ab01),
               *T.call('osRecvMesg', queue, slot, 1), *observe(16),
               0x44800000,  # MTC1 zero,f0: exercise acquisition inside a split guest unit
               *T.call('__osSetFpcCsr', 0x01000800), *observe(20), *A.DONE]
    for name in names: program += [name, A.jr(A.ra), A.nop]
    native = T.build(exe, cc, 'status-threads', program, names,
                     status_globals={'osCreateThread':global_mask,'osSetIntMask':global_mask}, fr0=True)
    expected = [0xff01,0xff01,0xff00,0xff01,0xab01,0x2000ab01,0xab02,0x15,0,1,1]
    def check(binary):
        result = subprocess.run([str(binary), '--dump', hex(log), str(len(expected))], capture_output=True, text=True, timeout=30)
        rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
        stop = next(row for row in rows if 'stop' in row)
        assert result.returncode == 0 and stop['fault'] == 0 and stop['stop'] == 'exit', (result.stdout,result.stderr)
        assert next(row['words'] for row in rows if 'dump' in row) == expected, rows
    check(native)
    # Exercise the production multipart linker seam as well as lower-c.
    out = T.OUT
    raw = (out / 'status-threads.bin').read_bytes()
    rom = bytearray(0x1000); rom[:4] = bytes.fromhex('80371240'); rom[8:12] = A.BASE.to_bytes(4,'big')
    path, mapped, source = (out / n for n in ('status-threads.z64','status-threads.map.json','status-threads.parts.c'))
    path.write_bytes(rom + raw)
    subprocess.run([str(exe),'discover',str(path),'0x1000',hex(A.BASE),hex(len(raw)),hex(A.BASE),str(mapped),
                    str(out/'status-threads.runtime.json'),'--fr0'],check=True,capture_output=True)
    subprocess.run([str(exe),'lower-map',str(path),str(mapped),hex(A.BASE),hex(A.EXIT),str(source),'--parts','3'],check=True,capture_output=True)
    invalid = json.loads(mapped.read_bytes())
    next(f for _,f in invalid['runtime_functions'] if f['name']=='osCreateThread').pop('status_global')
    bad_map = out/'status-threads.unbound.map.json'
    bad_map.write_text(json.dumps(invalid))
    report = subprocess.run([str(exe),'solve',str(path),str(bad_map),'--guarded-ram'],check=True,capture_output=True,text=True)
    verdict = json.loads(report.stdout)
    assert verdict['status']=='open' and any(b['kind']=='runtime_status_abi' for b in verdict['blockers']),verdict
    objects = []
    for part in sorted(out.glob('status-threads.parts.part*.c')):
        obj = part.with_suffix('.o')
        subprocess.run([cc,'-O2','-std=gnu11','-Werror','-DPLAID_SAFEPOINTS','-c',str(part),'-o',str(obj)],check=True)
        objects.append(obj)
    assert objects, 'multipart fixture emitted no separate function unit'
    split_native = out/'status-threads-parts.exe'
    subprocess.run([cc,'-O2','-std=gnu11','-DPLAID_SAFEPOINTS','-DPLAID_LOWERED="status-threads.parts.c"','-I',str(out),
                    str(T.ROOT/'runtime/plaid_rt.c'),*map(str,objects),'-pthread','-o',str(split_native)],check=True)
    check(split_native)
    print('Status threads: single/multipart native handoffs, disabled creator, saved IE, resume/restore, lazy COP1 and PI/motor exports')

if __name__ == '__main__':
    import os, shutil
    import test_runtime as T
    run(T.ROOT/'target/debug'/('plaid.exe' if os.name == 'nt' else 'plaid'),
        os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang'), T)
